"""
RECENTLY AUDITED TABLE — FORMULA & BUSINESS RULE VALIDATION
=============================================================
Validates the 'Recently audited' list (app-audit-stock-list-v2) on the
Stock Audit page directly against business formulas and rules, without
relying on a rigid, hardcoded expected-rows Excel sheet.

Rules: Stock Audit, Add count (stock qty by location)
=====================================================
A. Location rules
   R1: Audit location is optional. If none is selected, Audited Location = Unassigned.
   R2: Unassigned is a normal location value. Unassigned = Unassigned counts as a match.
   R3: A match means the audit location is in the item’s stock-by-location list (row exists, even qty 0).
   R4: A mismatch means no stock row exists at the audit location.

B. Stock Location and Stock Qty rules (saved row)
   R5: Match            → Stock Location = Audit location, Stock Qty = Qty at that location
   R6: Mismatch         → Stock Location = Unassigned,    Stock Qty = Total stock qty (all locations)
   R7: Match with qty 0 → Stock Location = Audit location, Stock Qty = 0 (not a fallback to total)

C. Form rules
   R8:  Audited qty is required (ng-invalid when blank). Add count is blocked.
   R9:  Damaged qty is optional. Min 0, stepper minus is disabled at 0.
   R10: The Stock Location dropdown on the form is read-only (disabled).
   R11: Total stock on the form = the sum of all stock-by-location qty.
   R12: Audit UOM is read-only and comes from the item.
   R13: Clear resets the item, the quantities and the audit location selection.

D. Result rules (Recently audited)
   R14: A successful Add count increases the entries pill by 1 and adds a row.
   R15: The row shows: S.No, Item Code, Item Name, Audited UOM, Auditor Name,
        Stock Qty, Audited Qty, Damaged Qty, Stock Location, Audited Location.
   R16: The info tooltip = Stock qty: <Stock Qty column> · Audited qty: <Audited Qty column>.
   R17: Auditor Name = the logged-in user. The "All auditors" toggle shows other auditors' rows.
   R18: Page size is 5 by default (5, 10, 25, 50, 100). The pager text is "Showing x–y of N entries".
   R19: Print and Delete actions apply per row. Print labels applies to selected rows only.
"""

import os
import re
import sys
from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import openpyxl
from playwright.sync_api import Page

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


# ======================================================================
# DATA BLOCK: RULES & FORMULAS (Fixable configuration)
# ======================================================================

REQUIRED_COLUMNS = [
    "S.No",
    "Item Code",
    "Item Name",
    "Audited UOM",
    "Auditor Name",
    "Stock Qty",
    "Audited Qty",
    "Damaged Qty",
    "Stock Location",
    "Audited Location",
]

# Form rules (checked on the page form elements)
FORM_RULES = OrderedDict([
    ("Audited Qty Required (R8)",     ("is_aud_required", "Audited qty input is required (ng-invalid when blank)")),
    ("Damaged Stepper Minus (R9)",    ("is_dam_disabled", "Damaged qty minus stepper is disabled at 0")),
    ("Stock Location Disabled (R10)", ("is_loc_disabled", "Stock Location dropdown is read-only / disabled")),
    ("Audit UOM Read-Only (R12)",     ("is_uom_readonly", "Audit UOM input is read-only")),
    ("Clear Button Present (R13)",    ("is_clear_visible", "Clear button is visible on form")),
])

# Page-level rules
PAGE_RULES = OrderedDict([
    ("Entries Pill Count (R14)",      ("pill_count == total_rows", "Entries pill equals scraped rows count")),
    ("Required Columns Present (R15)", ("has_required_cols", "Table contains all 10 required columns")),
    ("Pager Text Format (R18)",       ("pager_valid", "Pager matches 'Showing x–y of N entries'")),
    ("Row Actions Present (R19)",     ("has_row_actions", "Print and Delete buttons present on rows")),
])

# Per-row formula rules (evaluated for every scraped row)
ROW_FORMULA_RULES = OrderedDict([
    ("Audited Location (R1)",         ("audited_location != ''", "Must be non-empty (defaults to Unassigned)")),
    ("Stock Location (R5/R6)",        ("stock_location.lower() == exp_stock_location.lower()", "Match -> audit loc; Mismatch -> Unassigned")),
    ("Stock Qty (R5/R6/R7)",          ("stock_qty == exp_stock_qty", "Match -> loc qty; Mismatch -> total stock; Match qty 0 -> 0")),
    ("Audited Qty Valid",             ("audited_qty >= 0", "Audited Qty must be >= 0")),
    ("Damaged Qty Valid (R9)",        ("damaged_qty >= 0", "Damaged Qty must be >= 0")),
    ("Auditor Recorded (R17)",        ("auditor_name != ''", "Auditor name must be present")),
    ("Info Tooltip Format (R16)",     ("tooltip_valid", "Tooltip = 'Stock qty: <Stock Qty> · Audited qty: <Audited Qty>'")),
])


# ======================================================================
# COLUMN INDICES (Actual DOM structure of app-audit-stock-list-v2)
# ======================================================================
# td[0]:  Checkbox (skip)
# td[1]:  S.No
# td[2]:  Item Code (contains .aslv2-info icon with tooltip)
# td[3]:  Item Name
# td[4]:  Audited UOM
# td[5]:  Auditor Name
# td[6]:  Stock Qty
# td[7]:  Audited Qty
# td[8]:  Damaged Qty
# td[9]:  Stock Location
# td[10]: Audited Location
# td[11]: Image
# td[12]: Actions (Print / Delete)

COL_S_NO             = 1
COL_ITEM_CODE        = 2
COL_ITEM_NAME        = 3
COL_UOM              = 4
COL_AUDITOR          = 5
COL_STOCK_QTY        = 6
COL_AUDITED_QTY      = 7
COL_DAMAGE_QTY       = 8
COL_STOCK_LOCATION   = 9
COL_AUDITED_LOCATION = 10
COL_AUDITED_IMAGE    = 11


# ======================================================================
# VALIDATION RESULT DATA STRUCTURES
# ======================================================================
class ValidationStatus(Enum):
    PASSED  = "PASSED"
    FAILED  = "FAILED"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"


@dataclass
class RuleCheckResult:
    rule_id:        str
    description:    str
    expected_value: str
    actual_value:   str
    status:         ValidationStatus
    error_message:  Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.status == ValidationStatus.PASSED


@dataclass
class RowRuleValidation:
    row_number:    int
    item_code:     str
    checks:        List[RuleCheckResult]
    overall_status: ValidationStatus

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)


@dataclass
class FormulaValidationReport:
    total_rows:     int
    entries_pill:   int
    page_checks:    List[RuleCheckResult]
    form_checks:    List[RuleCheckResult]
    row_checks:     List[RowRuleValidation]
    overall_status: ValidationStatus

    def print_report(self):
        print("\n" + "=" * 105)
        print("📋 RECENTLY AUDITED — BUSINESS FORMULA & RULE VALIDATION REPORT")
        print("=" * 105)

        # Executive Summary
        icon = "✅" if self.overall_status == ValidationStatus.PASSED else "❌"
        print(f"\n{icon} OVERALL STATUS : {self.overall_status.value}")
        print(f"   Entries Pill Count : {self.entries_pill}")
        print(f"   Scraped Rows Count : {self.total_rows}")

        # Form Rules
        if self.form_checks:
            print("\n" + "-" * 105)
            print("1. FORM RULES (R8 - R13)")
            print("-" * 105)
            for c in self.form_checks:
                status_icon = "  PASS" if c.passed else "  FAIL"
                print(f" {status_icon} | {c.rule_id:<32} | Exp: {c.expected_value:<15} | Got: {c.actual_value}")

        # Page Rules
        if self.page_checks:
            print("\n" + "-" * 105)
            print("2. PAGE & RESULT RULES (R14 - R19)")
            print("-" * 105)
            for c in self.page_checks:
                status_icon = "  PASS" if c.passed else "  FAIL"
                print(f" {status_icon} | {c.rule_id:<32} | Exp: {c.expected_value:<15} | Got: {c.actual_value}")

        # Per-Row Formula Checks
        print("\n" + "-" * 105)
        print(f"3. PER-ROW LOCATION & STOCK FORMULAS (R1 - R7, R16) — {len(self.row_checks)} row(s)")
        print("-" * 105)

        failed_rows = [r for r in self.row_checks if not r.passed]
        if not failed_rows:
            print("  ✅ All rows passed all formula and business rules.")
        else:
            print(f"  ⚠️ {len(failed_rows)} row(s) had formula/rule discrepancies:\n")
            for r in failed_rows:
                print(f"  Row {r.row_number} [{r.item_code}]:")
                for c in r.checks:
                    if not c.passed:
                        print(f"     ❌ FAIL | {c.rule_id:<28} | Exp: {c.expected_value:<20} | Got: {c.actual_value}")

        # Summary Statistics
        all_checks = self.form_checks + self.page_checks + [c for r in self.row_checks for c in r.checks]
        passed_count = sum(1 for c in all_checks if c.passed)
        failed_count = sum(1 for c in all_checks if not c.passed)
        pct = (passed_count / len(all_checks) * 100) if all_checks else 0.0

        print("\n" + "-" * 105)
        print("STATISTICS")
        print("-" * 105)
        print(f"  Total Checks : {len(all_checks)}")
        print(f"  Passed       : {passed_count}")
        print(f"  Failed       : {failed_count}")
        print(f"  Accuracy     : {pct:.1f}%")
        print("=" * 105 + "\n")


# ======================================================================
# HELPER FUNCTIONS
# ======================================================================
def normalize(text: str) -> str:
    return text.replace(",", "").strip() if text else ""


def _num(text) -> float:
    s = normalize(str(text or ""))
    m = re.match(r"^[-+]?\d+(\.\d+)?", s)
    return float(m.group()) if m else 0.0


def _clean(text) -> str:
    return " ".join(str(text or "").split())


def _calc(formula: str, **kwargs) -> bool:
    """Safe evaluation for formula strings."""
    try:
        scope = {"min": min, "max": max, "round": round, "abs": abs, "sum": sum, "len": len}
        scope.update(kwargs)
        return bool(eval(formula, {"__builtins__": None}, scope))
    except Exception as e:
        return False


def load_stock_sheet_data(excel_path: str, sheet_name: str = "Data") -> Dict[str, Dict[str, float]]:
    """Loads item stock by location: {code: {location: qty}}."""
    stock_by_loc: Dict[str, Dict[str, float]] = {}
    if not excel_path or not os.path.exists(excel_path):
        return stock_by_loc
    try:
        wb = openpyxl.load_workbook(excel_path, data_only=True)
        if sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows_iter = ws.iter_rows(values_only=True)
            first_row = next(rows_iter, None)
            if first_row:
                hdr = [str(c or "").strip() for c in first_row]
                h_map = {h: i for i, h in enumerate(hdr)}
                c_idx = h_map.get("Item Code")
                l_idx = h_map.get("Location")
                q_idx = h_map.get("Adjustmentqty") if "Adjustmentqty" in h_map else h_map.get("Stock Quantity")
                if c_idx is not None and q_idx is not None:
                    for r in rows_iter:
                        code = str(r[c_idx] or "").strip()
                        if not code or code == "None":
                            continue
                        loc = str(r[l_idx] or "Unassigned").strip() if l_idx is not None and r[l_idx] else "Unassigned"
                        qty = float(r[q_idx]) if r[q_idx] is not None else 0.0
                        stock_by_loc.setdefault(code, {})[loc] = qty
    except Exception as e:
        print(f"  ⚠️ Could not load stock data from {excel_path}: {e}")
    return stock_by_loc


def calc_expected_stock(code: str, audit_loc: str, stock_data: Dict[str, Dict[str, float]]) -> Tuple[str, float]:
    """
    Implements Decision Table & Rules R1 - R7:
    R1: Audit location is optional. If none is selected, Audited Location = Unassigned.
    R2: Unassigned is a normal location value. Unassigned = Unassigned counts as a match.
    R3: A match means audit location is in item's stock-by-location list (a row exists, even qty 0).
    R4: A mismatch means no stock row exists at the audit location.
    R5: Match            → Stock Location = Audit location, Stock Qty = Qty at that location
    R6: Mismatch         → Stock Location = Unassigned,    Stock Qty = Total stock qty (all locations)
    R7: Match with qty 0 → Stock Location = Audit location, Stock Qty = 0 (not a fallback to total)
    """
    norm_audit = (audit_loc or "").strip()
    if not norm_audit or norm_audit.lower() in ("none", "0"):
        norm_audit = "Unassigned"

    item_stocks = stock_data.get(code, {})

    # Check match against stock locations (case-insensitive)
    matched_loc = None
    for loc_name in item_stocks:
        if loc_name.strip().lower() == norm_audit.lower():
            matched_loc = loc_name
            break

    if matched_loc is not None:
        # Match (R5, R7)
        return norm_audit, float(item_stocks[matched_loc])
    else:
        # Mismatch (R6)
        total_qty = sum(float(q) for q in item_stocks.values())
        return "Unassigned", total_qty


# ======================================================================
# DOM EXTRACTION & PAGINATION
# ======================================================================
def try_multiple_table_selectors(page: Page) -> Optional[any]:
    selectors = [
        ("app-audit-stock-list-v2 p-table table", "Scoped table in app-audit-stock-list-v2"),
        (".aslv2-ptable table", "CSS - aslv2-ptable class"),
        ("xpath=//*[contains(text(),'Recently audited')]/following::table[1]", "XPath - following Recently audited"),
        ("p-table table", "CSS - p-table element"),
    ]
    for selector, description in selectors:
        try:
            table = page.locator(selector)
            if table.count() > 0 and table.locator("tbody").first.count() > 0:
                return table.first
        except Exception:
            pass
    return None


def wait_for_table_to_load(page: Page) -> bool:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=5000)
        page.wait_for_timeout(2000)
        return try_multiple_table_selectors(page) is not None
    except Exception:
        return False


def get_entries_pill_count(page: Page) -> int:
    """Reads count from pill: '7 entries' -> 7."""
    try:
        pill = page.locator("span.aslv2-count-pill")
        if pill.count() > 0:
            m = re.search(r"\d+", pill.first.inner_text(timeout=3000))
            return int(m.group()) if m else 0
    except Exception:
        pass
    return 0


def extract_row_data(row) -> Dict[str, any]:
    cells = row.locator("td")

    def safe_text(col_idx: int) -> str:
        try:
            text = cells.nth(col_idx).text_content(timeout=3000).strip()
            return " ".join(text.split())
        except Exception:
            return ""

    def has_image(col_idx: int) -> str:
        try:
            img = cells.nth(col_idx).locator("img")
            if img.count() > 0:
                src = img.first.get_attribute("src", timeout=2000) or ""
                if src and "no_image" not in src:
                    return "Yes"
            return "No"
        except Exception:
            return "No"

    def get_tooltip() -> str:
        try:
            tip_el = cells.nth(COL_ITEM_CODE).locator("i.aslv2-info")
            if tip_el.count() > 0:
                return tip_el.first.get_attribute("ng-reflect-content", timeout=2000) or ""
        except Exception:
            pass
        return ""

    return {
        "s_no":             safe_text(COL_S_NO),
        "item_code":        safe_text(COL_ITEM_CODE),
        "item_name":        safe_text(COL_ITEM_NAME),
        "uom":              safe_text(COL_UOM),
        "auditor_name":     safe_text(COL_AUDITOR),
        "stock_qty":        _num(safe_text(COL_STOCK_QTY)),
        "audited_qty":      _num(safe_text(COL_AUDITED_QTY)),
        "damaged_qty":      _num(safe_text(COL_DAMAGE_QTY)),
        "stock_location":   safe_text(COL_STOCK_LOCATION),
        "audited_location": safe_text(COL_AUDITED_LOCATION),
        "audited_image":    has_image(COL_AUDITED_IMAGE),
        "tooltip":          get_tooltip(),
    }


def go_to_next_page(page: Page) -> bool:
    try:
        next_btn = page.locator("app-audit-pager button.apg-btn:has(i.bi-chevron-right)")
        if next_btn.count() == 0 or next_btn.is_disabled():
            return False
        next_btn.click()
        page.wait_for_timeout(1000)
        return True
    except Exception:
        return False


def set_page_size(page: Page, size: str = "100") -> None:
    try:
        dd = page.locator("app-audit-pager .apg-size p-dropdown")
        if dd.count() > 0:
            dd.click()
            opt = page.locator("li.p-dropdown-item", has_text=re.compile(rf"^\s*{size}\s*$"))
            if opt.count() > 0:
                opt.first.click()
                page.wait_for_timeout(1000)
    except Exception:
        pass


# ======================================================================
# FORM & PAGE RULES CHECKERS
# ======================================================================
def check_form_rules(page: Page) -> List[RuleCheckResult]:
    checks = []

    # R8: Audited qty required
    aud_input = page.locator("input[formcontrolname='auditedQty']")
    if aud_input.count():
        cls_val = aud_input.get_attribute("class") or ""
        is_req = "ng-invalid" in cls_val or page.locator(".asv2-field--audited .asv2-required").is_visible()
        checks.append(RuleCheckResult(
            "Audited Qty Required (R8)", "Required input validation",
            "True", str(is_req),
            ValidationStatus.PASSED if is_req else ValidationStatus.FAILED
        ))

    # R9: Damaged stepper minus disabled at 0
    dam_minus = page.locator("button[aria-label='Decrease damaged qty']")
    if dam_minus.count():
        is_dis = dam_minus.is_disabled()
        checks.append(RuleCheckResult(
            "Damaged Stepper Minus (R9)", "Disabled at min value 0",
            "True", str(is_dis),
            ValidationStatus.PASSED if is_dis else ValidationStatus.FAILED
        ))

    # R10: Stock location dropdown is read-only / disabled
    loc_dd = page.locator("p-dropdown[inputid='asv2Location']")
    if loc_dd.count():
        cls_val = loc_dd.get_attribute("class") or ""
        is_dis = "p-disabled" in cls_val
        checks.append(RuleCheckResult(
            "Stock Location Disabled (R10)", "Dropdown is read-only / disabled",
            "True", str(is_dis),
            ValidationStatus.PASSED if is_dis else ValidationStatus.FAILED
        ))

    # R12: Audit UOM input is read-only
    uom_input = page.locator("input#uom")
    if uom_input.count():
        is_ro = uom_input.get_attribute("readonly") is not None
        checks.append(RuleCheckResult(
            "Audit UOM Read-Only (R12)", "Input is read-only",
            "True", str(is_ro),
            ValidationStatus.PASSED if is_ro else ValidationStatus.FAILED
        ))

    # R13: Clear button is visible
    clear_btn = page.locator("button.asv2-btn.warning:has-text('Clear')")
    if clear_btn.count():
        is_vis = clear_btn.is_visible()
        checks.append(RuleCheckResult(
            "Clear Button Present (R13)", "Clear button visible",
            "True", str(is_vis),
            ValidationStatus.PASSED if is_vis else ValidationStatus.FAILED
        ))

    return checks


# ======================================================================
# CORE FORMULA VALIDATOR (No rigid expected Excel sheet required)
# ======================================================================
def validate_recently_audited_by_rules(
    page: Page,
    stock_data: Dict[str, Dict[str, float]],
) -> FormulaValidationReport:
    """
    Main formula and rule validator for the Recently Audited list.
    Evaluates:
      - Form rules R8 - R13
      - Page rules R14, R15, R18, R19
      - Per-row Decision Table rules R1 - R7, R16, R17
    """
    # 1. Check form rules
    form_checks = check_form_rules(page)

    # 2. Check table load
    if not wait_for_table_to_load(page):
        return FormulaValidationReport(
            total_rows=0, entries_pill=0, page_checks=[],
            form_checks=form_checks, row_checks=[],
            overall_status=ValidationStatus.FAILED
        )

    # 3. Entries pill (R14)
    pill_count = get_entries_pill_count(page)

    # 4. Check table header columns (R15)
    headers = [_clean(h) for h in page.locator("app-audit-stock-list-v2 thead th").all_inner_texts()]
    has_required_cols = all(any(req.lower() in h.lower() for h in headers) for req in REQUIRED_COLUMNS)
    page_checks = [
        RuleCheckResult(
            "Required Columns Present (R15)", "Columns match specification",
            "All 10 required columns present",
            f"{len(headers)} columns found",
            ValidationStatus.PASSED if has_required_cols else ValidationStatus.FAILED
        )
    ]

    # 5. Pager text format (R18)
    pager = page.locator("app-audit-pager .apg-info")
    if pager.count():
        pager_text = _clean(pager.inner_text())
        pager_valid = bool(re.search(r"Showing \d+[–-]\d+ of \d+ entries", pager_text, re.I))
        page_checks.append(RuleCheckResult(
            "Pager Text Format (R18)", "Matches 'Showing x–y of N entries'",
            "Showing x–y of N entries", pager_text,
            ValidationStatus.PASSED if pager_valid else ValidationStatus.FAILED
        ))

    # 6. Row actions present (R19)
    print_btn = page.locator("app-audit-stock-list-v2 button.aslv2-row-btn[aria-label='Print']")
    del_btn = page.locator("app-audit-stock-list-v2 button.aslv2-row-btn[aria-label='Delete']")
    has_actions = (print_btn.count() > 0 and print_btn.first.is_visible() and
                   del_btn.count() > 0 and del_btn.first.is_visible())
    page_checks.append(RuleCheckResult(
        "Row Actions Present (R19)", "Print and Delete buttons exist per row",
        "Visible", "Visible" if has_actions else "Missing",
        ValidationStatus.PASSED if has_actions else ValidationStatus.FAILED
    ))

    # 7. Scrape all rows across all pages (set to 100 per page to minimize turns)
    set_page_size(page, "100")
    table = try_multiple_table_selectors(page)
    all_rows = []
    while True:
        rows_loc = table.locator("tbody tr")
        for i in range(rows_loc.count()):
            data = extract_row_data(rows_loc.nth(i))
            if data.get("item_code"):
                all_rows.append(data)
        if not go_to_next_page(page):
            break

    # R14 Check: Entries pill count equals scraped count
    pill_match = (pill_count == len(all_rows))
    page_checks.append(RuleCheckResult(
        "Entries Pill Count (R14)", "Pill count equals total rows",
        str(pill_count), str(len(all_rows)),
        ValidationStatus.PASSED if pill_match else ValidationStatus.FAILED
    ))

    # 8. Per-row rule and formula validation
    row_validations = []
    for idx, row in enumerate(all_rows, start=1):
        code = row["item_code"]
        audit_loc = row["audited_location"]
        stock_loc = row["stock_location"]
        stock_qty = row["stock_qty"]
        aud_qty = row["audited_qty"]
        dam_qty = row["damaged_qty"]
        auditor = row["auditor_name"]
        tooltip = row["tooltip"]

        # Compute formula expectations from R1 - R7
        exp_stock_loc, exp_stock_qty = calc_expected_stock(code, audit_loc, stock_data)

        # Tooltip format (R16): Stock qty: <Stock Qty> · Audited qty: <Audited Qty>
        tooltip_valid = (
            f"Stock qty: {stock_qty:g}" in tooltip and
            f"Audited qty: {aud_qty:g}" in tooltip
        ) if tooltip else True

        row_checks = [
            # R1: Audited Location
            RuleCheckResult(
                "Audited Location (R1)", "Non-empty, defaults to Unassigned",
                "Non-empty", audit_loc,
                ValidationStatus.PASSED if audit_loc else ValidationStatus.FAILED
            ),
            # R5 / R6: Stock Location
            RuleCheckResult(
                "Stock Location (R5/R6)", "Match -> audit loc; Mismatch -> Unassigned",
                exp_stock_loc, stock_loc,
                ValidationStatus.PASSED if stock_loc.lower() == exp_stock_loc.lower() else ValidationStatus.FAILED
            ),
            # R5 / R6 / R7: Stock Qty
            RuleCheckResult(
                "Stock Qty (R5/R6/R7)", "Match -> loc qty; Mismatch -> total; Match 0 -> 0",
                f"{exp_stock_qty:g}", f"{stock_qty:g}",
                ValidationStatus.PASSED if stock_qty == exp_stock_qty else ValidationStatus.FAILED
            ),
            # Audited Qty >= 0
            RuleCheckResult(
                "Audited Qty Valid", "Audited Qty >= 0",
                ">= 0", f"{aud_qty:g}",
                ValidationStatus.PASSED if aud_qty >= 0 else ValidationStatus.FAILED
            ),
            # Damaged Qty >= 0 (R9)
            RuleCheckResult(
                "Damaged Qty Valid (R9)", "Damaged Qty >= 0",
                ">= 0", f"{dam_qty:g}",
                ValidationStatus.PASSED if dam_qty >= 0 else ValidationStatus.FAILED
            ),
            # Auditor recorded (R17)
            RuleCheckResult(
                "Auditor Recorded (R17)", "Auditor Name is not empty",
                "Non-empty", auditor,
                ValidationStatus.PASSED if auditor else ValidationStatus.FAILED
            ),
            # Tooltip format (R16)
            RuleCheckResult(
                "Info Tooltip (R16)", "Stock qty · Audited qty format",
                f"Stock qty: {stock_qty:g} · Audited qty: {aud_qty:g}", tooltip or "(not read)",
                ValidationStatus.PASSED if tooltip_valid else ValidationStatus.FAILED
            ),
        ]

        row_status = ValidationStatus.PASSED if all(c.passed for c in row_checks) else ValidationStatus.FAILED
        row_validations.append(RowRuleValidation(idx, code, row_checks, row_status))

    # Overall Status
    all_passed = (
        all(c.passed for c in form_checks) and
        all(c.passed for c in page_checks) and
        all(r.passed for r in row_validations)
    )

    report = FormulaValidationReport(
        total_rows=len(all_rows),
        entries_pill=pill_count,
        page_checks=page_checks,
        form_checks=form_checks,
        row_checks=row_validations,
        overall_status=ValidationStatus.PASSED if all_passed else ValidationStatus.FAILED
    )
    return report


# ======================================================================
# NAVIGATION HELPERS
# ======================================================================
def select_branch(page: Page, branch_text: str):
    dropdown = page.locator('xpath=/html/body/app-root/app-layout/div/app-header/div[1]/div[2]/div[2]//p-dropdown')
    dropdown.wait_for(state="visible", timeout=30000)
    dropdown.locator(".p-dropdown-label").click()

    panel = page.locator(".p-dropdown-panel").last
    panel.wait_for(state="visible", timeout=30000)

    search = panel.locator("input.p-dropdown-filter")
    if search.count() > 0:
        search.fill(branch_text)
        page.wait_for_timeout(300)

    option = panel.locator("li.p-dropdown-item", has_text=branch_text)
    if option.count() == 0:
        raise Exception(f"Branch not found: {branch_text}")
    option.first.click()
    panel.wait_for(state="hidden", timeout=30000)


def select_navigation_option(page: Page, option_name: str):
    page.wait_for_selector("div[role='dialog'][aria-labelledby='auditNavTitle']")
    card = page.locator(f"button.create-type-card:has(h6.create-type-card__title:text-is('{option_name}'))")
    card.click()
    page.locator("button.create-type-btn--primary:has-text('Continue')").click()


def click_audit(page: Page, ap_audit_name: str):
    page.wait_for_load_state("networkidle")
    row = page.locator(f"table tbody tr:has(button.audit-name-link:has-text('{ap_audit_name}'))").first
    row.locator("button.audit-name-link").first.click()
    page.wait_for_load_state("networkidle")
    print(f"   Opened audit: {ap_audit_name}")


def navigate_to_ongoing_recentlyaudit(page: Page, config):
    print("📂 Navigating to Ongoing Audits...")
    page.wait_for_selector("a[href='/home/audit']", state="visible")
    page.click("a[href='/home/audit']")
    page.wait_for_load_state("networkidle")
    select_branch(page, config.Branch)
    print(f"   Branch selected: {config.Branch}")
    click_audit(page, config.ap_audit_name)
    select_navigation_option(page, "Stock Audit")


# ======================================================================
# ENTRY POINT
# ======================================================================
def A_Recently_Audit(page: Page, Config) -> FormulaValidationReport:
    """
    Main entry point for Recently Audited table formula and rule validation.
    """
    print("\n" + "=" * 80)
    print("🚀 RECENTLY AUDITED — BUSINESS FORMULA & RULE VALIDATION")
    print("=" * 80 + "\n")

    # 1. Load stock sheet data for Rule R1 - R7 resolution
    excel_path = getattr(Config, "EXCEL_PATH", None) or getattr(Config, "oa_excel_path", None)
    stock_data = load_stock_sheet_data(excel_path, sheet_name=getattr(Config, "oa_sheet", "Data"))
    print(f"📦 Loaded stock-by-location data for {len(stock_data)} items from stock sheet")

    # 2. Navigate to the audit
    navigate_to_ongoing_recentlyaudit(page, Config)

    # 3. Wait for page to stabilize
    print("\n⏳ Waiting 5 seconds for Stock Audit page to stabilize...")
    page.wait_for_timeout(5000)

    # 4. Run formula & business rule validation
    report = validate_recently_audited_by_rules(page, stock_data)
    report.print_report()

    return report
