"""
Audit Plan UI Validation Module
Compares Config expected values against live UI state (Playwright).
Covers all 3 wizard steps + mapping step (Step 3).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

log = logging.getLogger(__name__)

# ======================================================
# CONFIG
# ======================================================
DRY_RUN = False
SEED = None
FAST_MODE = False
ENABLE_REPORTING = True

SLEEP_TIME = 0.10 if FAST_MODE else 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    field: str
    expected: Any
    actual: Any
    passed: bool
    note: str = ""

    @property
    def missing(self) -> Set[str]:
        if isinstance(self.expected, (set, list)) and isinstance(self.actual, (set, list)):
            return set(self.expected) - set(self.actual)
        return set()

    @property
    def extra(self) -> Set[str]:
        if isinstance(self.expected, (set, list)) and isinstance(self.actual, (set, list)):
            return set(self.actual) - set(self.expected)
        return set()


@dataclass
class ValidationReport:
    results: List[ValidationResult] = field(default_factory=list)

    def add(self, r: ValidationResult) -> None:
        self.results.append(r)

    @property
    def passed(self) -> List[ValidationResult]:
        return [r for r in self.results if r.passed]

    @property
    def failed(self) -> List[ValidationResult]:
        return [r for r in self.results if not r.passed]

    @property
    def overall_pass(self) -> bool:
        return all(r.passed for r in self.results)

    def print_summary(self) -> str:
        lines: List[str] = []
        lines.append("=" * 60)
        lines.append("UI VALIDATION SUMMARY")
        lines.append("=" * 60)
        lines.append(f"Total Fields Validated : {len(self.results)}")
        lines.append(f"Passed                : {len(self.passed)}")
        lines.append(f"Failed                : {len(self.failed)}")

        if self.failed:
            lines.append("")
            lines.append("FAILED VALIDATIONS:")
            lines.append("-" * 60)
            lines.append(f"{'Field Name':<35} {'Expected':<25} {'Actual'}")
            lines.append("-" * 60)
            for r in self.failed:
                exp = _fmt(r.expected)
                act = _fmt(r.actual)
                lines.append(f"{r.field:<35} {exp:<25} {act}")
                if r.missing:
                    lines.append(f"  ↳ Missing  : {sorted(r.missing)}")
                if r.extra:
                    lines.append(f"  ↳ Extra    : {sorted(r.extra)}")
                if r.note:
                    lines.append(f"  ↳ Note     : {r.note}")

        lines.append("")
        lines.append("PASSED VALIDATIONS:")
        lines.append("-" * 60)
        lines.append(f"{'Field Name':<35} {'Value'}")
        lines.append("-" * 60)
        for r in self.passed:
            lines.append(f"{r.field:<35} {_fmt(r.expected)}")

        lines.append("")
        overall = "PASS" if self.overall_pass else "FAIL"
        lines.append(f"Overall Result: {overall}")
        lines.append("=" * 60)

        summary = "\n".join(lines)
        log.info("\n" + summary)
        return summary


@dataclass
class MappingReport:
    mapping_type_result: Optional[ValidationResult] = None
    user_results: List[ValidationResult] = field(default_factory=list)

    @property
    def overall_pass(self) -> bool:
        all_results = self.user_results[:]
        if self.mapping_type_result:
            all_results.append(self.mapping_type_result)
        return all(r.passed for r in all_results)

    def print_summary(self) -> str:
        lines: List[str] = []
        lines.append("=" * 60)
        lines.append("MAPPING VALIDATION SUMMARY")
        lines.append("=" * 60)

        # ── Mapping Type block ───────────────────────────────────────────────
        if self.mapping_type_result:
            r = self.mapping_type_result
            lines.append("Mapping Type")
            lines.append(f"  Expected : {r.expected}")
            lines.append(f"  Actual   : {r.actual}")
            lines.append(f"  Result   : {'PASS' if r.passed else 'FAIL'}")
            lines.append("")

        # ── Per-user assignment blocks ───────────────────────────────────────
        for r in self.user_results:
            # Determine label: Categories vs Locations
            label = (
                "Categories"
                if "category" in r.field.lower() or "categor" in r.field.lower()
                else "Locations"
            )
            # Extract user name from field like "Dinesh B | By Category"
            user_part = r.field.split("|")[0].strip() if "|" in r.field else r.field

            exp_set = set(r.expected) if isinstance(r.expected, (list, set)) else {r.expected}
            act_set = set(r.actual)   if isinstance(r.actual,   (list, set)) else {r.actual}

            missing = sorted(exp_set - act_set)
            extra   = sorted(act_set - exp_set)

            lines.append("-" * 60)
            lines.append(f"User : {user_part}")

            lines.append(f"Expected {label}:")
            for v in sorted(exp_set):
                lines.append(f"  {v}")

            lines.append(f"Actual {label}:")
            for v in sorted(act_set):
                lines.append(f"  {v}")

            lines.append(f"Expected Count : {len(exp_set)}")
            lines.append(f"Actual Count   : {len(act_set)}")
            lines.append(f"Result : {'PASS' if r.passed else 'FAIL'}")

            if missing:
                lines.append(f"  Missing Values : {missing}")
            if extra:
                lines.append(f"  Extra Values   : {extra}")

        lines.append("")
        overall = "PASS" if self.overall_pass else "FAIL"
        lines.append(f"OVERALL RESULT : {overall}")
        lines.append("=" * 60)

        summary = "\n".join(lines)
        log.info("\n" + summary)
        return summary


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fmt(v: Any) -> str:
    if isinstance(v, (list, set)):
        return ", ".join(str(x) for x in sorted(v))
    return str(v) if v is not None else "(none)"


def _norm(s: str) -> str:
    """Lowercase + strip for set comparisons."""
    return (s or "").strip().lower()


def _safe_text(locator, timeout: int = 4000) -> str:
    try:
        locator.wait_for(state="visible", timeout=timeout)
        return locator.inner_text().strip()
    except Exception:
        return ""





def _val(result: ValidationResult, report: ValidationReport) -> None:
    status = "PASS" if result.passed else "FAIL"
    log.info(
        f"[{status}] {result.field} | "
        f"Expected: {_fmt(result.expected)} | Actual: {_fmt(result.actual)}"
    )
    report.add(result)


def _check(
    field: str,
    expected: Any,
    actual: Any,
    report: ValidationReport,
    set_compare: bool = False,
    note: str = "",
) -> None:
    if set_compare:
        exp_set = {_norm(str(x)) for x in (expected or [])}
        act_set = {_norm(str(x)) for x in (actual   or [])}
        passed  = exp_set == act_set
    else:
        passed = _norm(str(expected)) == _norm(str(actual))

    _val(
        ValidationResult(field=field, expected=expected, actual=actual,
                         passed=passed, note=note),
        report,
    )


# ─────────────────────────────────────────────────────────────────────────────
# UI readers
# ─────────────────────────────────────────────────────────────────────────────

class UIReader:
    """Thin wrapper around page to read field values from the audit wizard."""

    def __init__(self, page: Page):
        self.page = page

    # ── Step 1 ──────────────────────────────────────────────────────────────

    def audit_owner(self) -> str:
        loc = self.page.locator(
            "p-dropdown[formcontrolname='auditOwner'] span.p-dropdown-label"
        )
        return _safe_text(loc)
    def group_name(self) -> str:
        loc = self.page.locator("form:visible #role span.p-dropdown-label").first
        return _safe_text(loc)
    def audit_name(self) -> str:
        loc = self.page.locator("input[formcontrolname='name']")
        try:
            loc.wait_for(state="attached", timeout=4000)
            return (loc.input_value() or "").strip()
        except Exception:
            return ""

    def audit_type(self) -> str:
        for value in ("Complete Count", "Cycle Count"):
            radio = self.page.locator(
                f"p-radiobutton[value='{value}'] .p-radiobutton-box"
            )
            try:
                cls = radio.get_attribute("class") or ""
                if "p-highlight" in cls:
                    return value
            except Exception:
                pass
        return ""

    def frequency(self) -> str:
        loc = self.page.locator(
            "p-dropdown[formcontrolname='frequencyId'] span.p-dropdown-label"
        )
        return _safe_text(loc)

    def start_date(self) -> str:
        loc = self.page.locator("p-calendar[formcontrolname='startDateTime'] input")
        try:
            loc.wait_for(state="attached", timeout=3000)
            return (loc.input_value() or "").strip()
        except Exception:
            return ""

    def end_date(self) -> str:
        loc = self.page.locator("p-calendar[formcontrolname='endDateTime'] input")
        try:
            loc.wait_for(state="attached", timeout=3000)
            return (loc.input_value() or "").strip()
        except Exception:
            return ""

    # ── Step 2 ──────────────────────────────────────────────────────────────

    def auditors(self) -> List[str]:
        loc = self.page.locator(
            "p-multiselect[formcontrolname='auditor'] .p-multiselect-label"
        )
        text = _safe_text(loc)
        if "Selected" in text or "selected" in text:
            return self._read_multiselect_selected(
                "p-multiselect[formcontrolname='auditor']"
            )
        if text and text != "Choose Auditor(s)":
            return [t.strip() for t in text.split(",") if t.strip()]
        return []

    def _read_multiselect_selected(self, ms_selector: str) -> List[str]:
        selected: List[str] = []
        try:
            trigger = self.page.locator(f"{ms_selector} .p-multiselect-trigger")
            trigger.click()
            panel = self.page.locator("div.p-multiselect-panel")
            panel.wait_for(state="visible", timeout=5000)
            items = panel.locator("li.p-multiselect-item")
            for i in range(items.count()):
                item = items.nth(i)
                cls  = item.get_attribute("class") or ""
                if "p-highlight" in cls:
                    text = item.inner_text().strip()
                    if text:
                        selected.append(text)
            self.page.keyboard.press("Escape")
        except Exception as e:
            log.debug(f"_read_multiselect_selected error: {e}")
        return selected

    def is_damaged_checked(self) -> bool:
        return self._checkbox_state("isDamageQty")

    def is_stock_checked(self) -> bool:
        return self._checkbox_state("isStockItems")

    def is_geo_checked(self) -> bool:
        return self._checkbox_state("isGeoTagging")

    def _checkbox_state(self, controlname: str) -> bool:
        loc = self.page.locator(f"input[formcontrolname='{controlname}']")
        try:
            loc.wait_for(state="attached", timeout=3000)
            return loc.is_checked()
        except Exception:
            return False

    def photo_validation_type(self) -> str:
        for value in ("", "Random", "Damaged"):
            try:
                if value == "":
                    box = self.page.locator(
                        "p-radiobutton[name='photoValidationType'] input[value='']"
                    ).locator("xpath=ancestor::p-radiobutton").locator(".p-radiobutton-box")
                else:
                    box = self.page.locator(
                        f"p-radiobutton[name='photoValidationType'][value='{value}'] .p-radiobutton-box"
                    )
                cls = box.get_attribute("class") or ""
                if "p-highlight" in cls:
                    return "None" if value == "" else value
            except Exception:
                pass
        return ""

    def photo_sample_size(self) -> str:
        loc = self.page.locator("input[formcontrolname='photoValidationSize']")
        try:
            loc.wait_for(state="visible", timeout=3000)
            return loc.input_value()
        except Exception:
            return ""

    def cross_audit_type(self) -> str:
        reverse_map = {
            "": "None",
            "Random": "Random Recheck",
            "Discrepancy": "Discrepancy Recheck",
        }
        for value in ("", "Random", "Discrepancy"):
            try:
                if value == "":
                    box = self.page.locator(
                        "p-radiobutton[name='crossCheckType'] input[value='']"
                    ).locator("xpath=ancestor::p-radiobutton").locator(".p-radiobutton-box")
                else:
                    box = self.page.locator(
                        f"p-radiobutton[name='crossCheckType'][value='{value}'] .p-radiobutton-box"
                    )
                cls = box.get_attribute("class") or ""
                if "p-highlight" in cls:
                    return reverse_map[value]
            except Exception:
                pass
        return ""

    def cross_auditor(self) -> str:
        loc = self.page.locator(
            "p-dropdown[formcontrolname='crossCheckAuditor'] span.p-dropdown-label"
        )
        return _safe_text(loc)

    def cross_check_size(self) -> str:
        loc = self.page.locator("input[formcontrolname='crossCheckSize']")
        try:
            loc.wait_for(state="attached", timeout=2000)
            return (loc.input_value() or "").strip()
        except Exception:
            return ""

    # ── Step 3 ──────────────────────────────────────────────────────────────

    def mapping_type(self) -> str:
        loc = self.page.locator(
            "p-dropdown[formcontrolname='periodicalType'] span.p-dropdown-label"
        )
        return _safe_text(loc)

    def auditor_rows(self) -> List[str]:
        """Return list of auditor names from the mapping table."""
        rows  = self.page.locator("table tr")
        names: List[str] = []
        cnt   = rows.count()
        for i in range(1, cnt):                    # skip header row
            tds = rows.nth(i).locator("td")
            if tds.count() >= 2:
                names.append(tds.nth(1).inner_text().strip())
        return names

    # ── PRIMARY: read inline label text displayed in the multiselect ────────
    def selected_items_for_row_inline(self, row_index: int = 0) -> List[str]:
        """
        Read the INLINE label text that PrimeNG renders inside the multiselect
        when items are already selected.  The label looks like:
            "Parts, Vehicle"
            "SA-A1-B1-L1, SA-A1-B1-L2, SA-A1-B1-L3"
            "3 items selected"    falls back to panel read

        Returns a normalised, deduplicated list of value strings.
        """
        try:
            rows = self.page.locator("table tr")
            row  = rows.nth(row_index + 1)          # +1 skips header

            # PrimeNG renders selected items in this span when ≤ threshold count
            label_loc = row.locator(
                "div.p-multiselect span.p-multiselect-label"
            )
            label_loc.wait_for(state="attached", timeout=4000)
            label_text = label_loc.inner_text().strip()

            # If PrimeNG shows "N items selected" the text isn't useful —
            # fall back to opening the panel to read highlighted items.
            if not label_text or "selected" in label_text.lower() or "choose" in label_text.lower():
                log.debug(
                    f"Row {row_index}: inline label '{label_text}' "
                    "not usable — falling back to panel read."
                )
                return self.selected_items_for_row_panel(row_index)

            # Split on comma, strip each token, drop blanks, deduplicate
            items = list(dict.fromkeys(
                t.strip() for t in label_text.split(",") if t.strip()
            ))
            log.debug(f"Row {row_index} inline items: {items}")
            return items

        except Exception as e:
            log.debug(f"selected_items_for_row_inline({row_index}): {e}")
            return self.selected_items_for_row_panel(row_index)

    # ── FALLBACK: open the panel and read p-highlight items ─────────────────
    def selected_items_for_row_panel(self, row_index: int = 0) -> List[str]:
        """
        Open the multiselect panel for the given table row, collect every
        item whose li has the 'p-highlight' class, then close the panel.
        """
        selected: List[str] = []
        try:
            rows = self.page.locator("table tr")
            row  = rows.nth(row_index + 1)
            ms   = row.locator("div.p-multiselect")
            ms.click()

            panel = self.page.locator("div.p-multiselect-panel")
            panel.wait_for(state="visible", timeout=5000)

            items = panel.locator("li.p-multiselect-item")
            for i in range(items.count()):
                item = items.nth(i)
                cls  = item.get_attribute("class") or ""
                if "p-highlight" in cls:
                    # PrimeNG sometimes appends "  N Items" on a second line
                    raw   = item.inner_text().strip()
                    label = raw.split("\n")[0].strip()
                    if label:
                        selected.append(label)

            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(300)

        except Exception as e:
            log.debug(f"selected_items_for_row_panel({row_index}): {e}")

        return selected

    # ── Public API: try inline first, then panel ─────────────────────────────
    def selected_items_for_row(self, row_index: int = 0) -> List[str]:
        """
        Unified entry point.  Tries the fast inline-label read first;
        falls back to panel if the label text is unusable.
        """
        return self.selected_items_for_row_inline(row_index)


# ─────────────────────────────────────────────────────────────────────────────
# Navigation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _navigate_to_step(page: Page, step: int) -> None:
    try:
        steps = page.locator("ul.progressbar li")
        if steps.count() >= step:
            steps.nth(step - 1).click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1000)
    except Exception as e:
        log.debug(f"_navigate_to_step({step}) error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Main UI validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_audit_plan_ui(page: Page, Config) -> ValidationReport:
    report = ValidationReport()
    reader = UIReader(page)

    log.info("=" * 60)
    log.info("STARTING AUDIT PLAN UI VALIDATION")
    log.info("=" * 60)

    # ── Step 1 ──────────────────────────────────────────────────────────────
    log.info("\n--- Step 1: Basic Settings ---")
    _navigate_to_step(page, 1)

    if _has(Config, "Audit_Owner"):
        _check("Audit Owner", Config.Audit_Owner, reader.audit_owner(), report)

    if _has(Config, "Group_Name"):
        _check("Item Group (Role)", Config.Group_Name, reader.group_name(), report)

    if _has(Config, "ap_audit_name"):
        _check("Audit Plan Name", Config.ap_audit_name, reader.audit_name(), report)

    if _has(Config, "Audit_Type"):
        _check("Audit Type", Config.Audit_Type, reader.audit_type(), report)

    if _has(Config, "frequency"):
        _check("Frequency", Config.frequency, reader.frequency(), report)

    if _has(Config, "frequency") and _norm(str(Config.frequency)) not in ("manual",):
        from datetime import datetime, timedelta

        expected_start = datetime.today()
        expected_end   = expected_start + timedelta(days=getattr(Config, "Day_s", 0))

        # Matches the format used when typing dates in select_start_end_date()
        expected_start_str = expected_start.strftime("%m/%d/%Y")
        expected_end_str   = expected_end.strftime("%m/%d/%Y")

        actual_start = reader.start_date()
        actual_end   = reader.end_date()

        _check(
            "Start Date",
            expected_start_str,
            actual_start,
            report,
            note="Compared as MM/DD/YYYY",
        )
        _check(
            "End Date",
            expected_end_str,
            actual_end,
            report,
            note=f"Expected = today + {getattr(Config, 'Day_s', 0)} days (MM/DD/YYYY)",
        )
    
    safe_click(page.get_by_role("button", name="Next"))
    # ── Step 2 ──────────────────────────────────────────────────────────────
    log.info("\n--- Step 2: Auditor Settings ---")
    _navigate_to_step(page, 2)
    page.wait_for_timeout(800)

    if _has(Config, "Auditor1") or _has(Config, "Auditor2"):
        expected_auditors = _collect_auditors(Config)
        actual_auditors   = reader.auditors()
        _check(
            "Auditors",
            set(expected_auditors),
            set(actual_auditors),
            report,
            set_compare=True,
        )

    if _has(Config, "A_Checkboxes_Audit_Damaged"):
        _check(
            "Audit Damaged Inventory",
            _to_bool(Config.A_Checkboxes_Audit_Damaged),
            reader.is_damaged_checked(),
            report,
        )

    if _has(Config, "A_Checkboxes_BlindCount"):
        _check(
            "Show Stock Count to Auditor",
            _to_bool(Config.A_Checkboxes_BlindCount),
            reader.is_stock_checked(),
            report,
        )

    if _has(Config, "A_Checkboxes_geo"):
        _check(
            "Geo Tagging",
            _to_bool(Config.A_Checkboxes_geo),
            reader.is_geo_checked(),
            report,
        )

    if _has(Config, "photo_type"):
        _check(
            "Photo Validation Type",
            Config.photo_type,
            reader.photo_validation_type(),
            report,
        )
        if Config.photo_type == "Random" and _has(Config, "sample_size"):
            _check(
                "Photo Validation Sample Size (%)",
                str(Config.sample_size),
                reader.photo_sample_size(),
                report,
            )

    if _has(Config, "CROSS_AUDIT_TYPE"):
        _check(
            "Cross Audit Type",
            Config.CROSS_AUDIT_TYPE,
            reader.cross_audit_type(),
            report,
        )

    if (
        _has(Config, "CROSS_Auditor_name")
        and _has(Config, "CROSS_AUDIT_TYPE")
        and Config.CROSS_AUDIT_TYPE != "None"
    ):
        _check(
            "Cross Auditor",
            Config.CROSS_Auditor_name,
            reader.cross_auditor(),
            report,
        )
    safe_click(page.get_by_role("button", name="Next"))
    # ── Step 3 (Mapping Type only — full mapping handled separately) ─────────
    log.info("\n--- Step 3: Mapping ---")
    _navigate_to_step(page, 3)
    page.wait_for_timeout(800)

    if _has(Config, "AUDIT_MAPPING_TYPE"):
        _check(
            "Mapping Type",
            Config.AUDIT_MAPPING_TYPE,
            reader.mapping_type(),
            report,
        )

    report.print_summary()
    return report


# ─────────────────────────────────────────────────────────────────────────────
# Mapping validation  (FIXED)
# ─────────────────────────────────────────────────────────────────────────────

def validate_mapping_config(page: Page, Config) -> MappingReport:
    """
    Validates Step 3 mapping assignments (By Category or By Location) by:
      1. Reading expected values from the Excel mapping sheet.
      2. Reading actual selected values from the inline multiselect label
         (e.g. "Parts, Vehicle" or "SA-A1-B1-L1, SA-A1-B1-L2") and falling
         back to the panel p-highlight approach if the label is unusable.
      3. Comparing as normalised sets and reporting Missing / Extra / Counts.
    """
    mreport = MappingReport()
    reader  = UIReader(page)

    log.info("=" * 60)
    log.info("STARTING MAPPING VALIDATION")
    log.info("=" * 60)

    _navigate_to_step(page, 3)
    page.wait_for_timeout(800)

    # ── 1. Validate Mapping Type ─────────────────────────────────────────────
    expected_mt = getattr(Config, "AUDIT_MAPPING_TYPE", None)
    actual_mt   = reader.mapping_type()
    mt_passed   = _norm(str(expected_mt)) == _norm(actual_mt)

    mt_result = ValidationResult(
        field="Mapping Type",
        expected=expected_mt,
        actual=actual_mt,
        passed=mt_passed,
    )
    mreport.mapping_type_result = mt_result
    log.info(
        f"[{'PASS' if mt_passed else 'FAIL'}] Mapping Type | "
        f"Expected: {expected_mt} | Actual: {actual_mt}"
    )

    # If Mapping Type itself is wrong or Random, no assignment rows to check
    if not mt_passed:
        log.warning("⚠ Mapping Type mismatch — skipping assignment validation.")
        mreport.print_summary()
        return mreport

    if _norm(str(expected_mt)) == "random":
        log.info("ℹ Mapping type is Random — no assignment rows to validate.")
        mreport.print_summary()
        return mreport

    # ── 2. Load expected assignments from Excel ──────────────────────────────
    auditor_map = _load_auditor_mapping_safe(Config)
    if not auditor_map:
        log.warning("⚠ Auditor mapping could not be loaded from Excel — aborting mapping validation.")
        mreport.print_summary()
        return mreport

    # ── 3. Read auditor rows from the UI table ───────────────────────────────
    auditor_names = reader.auditor_rows()
    log.info(f"Auditor rows found in UI: {auditor_names}")

    for row_idx, auditor_ui_raw in enumerate(auditor_names):
        # Strip item-count suffix like "Dinesh B  (6 Items)"
        auditor_ui = auditor_ui_raw.split("(")[0].strip()

        # ── Match auditor to Excel map (exact → normalised fallback) ─────────
        auditor_key = auditor_ui
        if auditor_key not in auditor_map:
            auditor_key = next(
                (k for k in auditor_map if _norm(k) == _norm(auditor_ui)),
                None,
            )

        # ── Build expected set ───────────────────────────────────────────────
        expected_set: Set[str] = set()
        if auditor_key and auditor_key in auditor_map:
            if _norm(str(expected_mt)) == "by category":
                expected_set = {
                    _norm(c) for c in auditor_map[auditor_key]["categories"]
                }
            elif _norm(str(expected_mt)) == "by location":
                expected_set = {
                    _norm(s) for s in auditor_map[auditor_key]["storages"]
                }
        else:
            log.warning(
                f"⚠ Auditor '{auditor_ui}' not found in Excel mapping — "
                "expected set will be empty."
            )

        # ── Read actual set from UI (inline label → panel fallback) ──────────
        actual_raw  = reader.selected_items_for_row(row_idx)
        actual_set  = {_norm(a) for a in actual_raw if a.strip()}

        # ── Compare ──────────────────────────────────────────────────────────
        passed      = expected_set == actual_set
        label_type  = "By Category" if _norm(str(expected_mt)) == "by category" else "By Location"
        field_label = f"{auditor_ui} | {label_type}"

        result = ValidationResult(
            field=field_label,
            expected=expected_set,
            actual=actual_set,
            passed=passed,
        )
        mreport.user_results.append(result)

        status = "PASS" if passed else "FAIL"
        log.info(f"[{status}] {field_label}")
        log.info(f"  Expected Count : {len(expected_set)} | Actual Count : {len(actual_set)}")
        if not passed:
            if result.missing:
                log.info(f"  Missing Values : {sorted(result.missing)}")
            if result.extra:
                log.info(f"  Extra Values   : {sorted(result.extra)}")

    mreport.print_summary()
    return mreport


# ─────────────────────────────────────────────────────────────────────────────
# Combined runner
# ─────────────────────────────────────────────────────────────────────────────

def run_full_validation(page: Page, Config) -> Tuple[ValidationReport, MappingReport]:
    ui_report      = validate_audit_plan_ui(page, Config)
    mapping_report = validate_mapping_config(page, Config)
    return ui_report, mapping_report


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

def _has(Config, attr: str) -> bool:
    return hasattr(Config, attr) and getattr(Config, attr) is not None


def _to_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("true", "yes", "1")


def _collect_auditors(Config) -> List[str]:
    auditors = []
    for attr in ("Auditor1", "Auditor2", "Auditor3", "Auditor4"):
        v = getattr(Config, attr, None)
        if v:
            auditors.append(str(v).strip())
    return auditors


def _load_auditor_mapping_safe(Config) -> Dict[str, Dict[str, List[str]]]:
    """
    Load auditor → categories/storages from the Excel mapping sheet.
    Returns an empty dict on any failure rather than raising.

    Sheet columns:
        Config.EXCEL_auditor_col   e.g. "Auditor"
        Config.EXCEL_category_col  e.g. "Category"
        Config.EXCEL_storage_col   e.g. "Storage"
    Each row can have comma-separated values in category / storage columns.
    """
    try:
        sheet_name = getattr(Config, "EXCEL_SHEET_AUDITOR_MAPPING", None)
        if isinstance(sheet_name, str):
            sheet_name = sheet_name.strip()

        if sheet_name in (None, "", "None"):
            workbook = pd.ExcelFile(Config.EXCEL_PATH)
            if "AUDITOR_MAPPING" in workbook.sheet_names:
                sheet_name = "AUDITOR_MAPPING"
            elif len(workbook.sheet_names) == 1:
                sheet_name = workbook.sheet_names[0]
            else:
                raise ValueError(
                    "EXCEL_SHEET_AUDITOR_MAPPING is required for audit mapping validation. "
                    f"Available sheets: {', '.join(workbook.sheet_names)}"
                )

        df = pd.read_excel(
            Config.EXCEL_PATH,
            sheet_name=sheet_name,
        )

        if isinstance(df, dict):
            if sheet_name in df:
                df = df[sheet_name]
            elif len(df) == 1:
                df = next(iter(df.values()))
            else:
                raise ValueError(
                    "Unable to resolve a single auditor-mapping sheet from the workbook."
                )

        result: Dict[str, Dict[str, List[str]]] = {}
        seen:   Dict[str, Dict[str, Set[str]]]  = {}

        for _, row in df.iterrows():
            auditor = str(row[Config.EXCEL_auditor_col]).strip()
            if not auditor or auditor.lower() == "nan":
                continue

            if auditor not in result:
                result[auditor] = {"categories": [], "storages": []}
                seen[auditor]   = {"categories": set(), "storages": set()}

            # ── Categories ──────────────────────────────────────────────────
            cat_val = str(row.get(Config.EXCEL_category_col, "")).strip()
            if cat_val and cat_val.lower() != "nan":
                for cat in cat_val.split(","):
                    cat = cat.strip()
                    if cat and _norm(cat) not in seen[auditor]["categories"]:
                        result[auditor]["categories"].append(cat)
                        seen[auditor]["categories"].add(_norm(cat))

            # ── Storages / Locations ─────────────────────────────────────────
            stor_val = str(row.get(Config.EXCEL_storage_col, "")).strip()
            if stor_val and stor_val.lower() != "nan":
                for stor in stor_val.split(","):
                    stor = stor.strip()
                    if stor and _norm(stor) not in seen[auditor]["storages"]:
                        result[auditor]["storages"].append(stor)
                        seen[auditor]["storages"].add(_norm(stor))

        return result

    except Exception as e:
        log.error(f" Could not load auditor mapping from Excel: {e}", exc_info=True)
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Navigation / click helpers (kept from original)
# ─────────────────────────────────────────────────────────────────────────────

def safe_click(locator) -> None:
    locator.wait_for(state="attached", timeout=15000)
    locator.wait_for(state="visible",  timeout=15000)
    locator.scroll_into_view_if_needed()
    locator.page.wait_for_load_state("networkidle")
    try:
        locator.click(timeout=10000)
    except Exception:
        locator.click(force=True)


def click_audit(page: Page, ap_audit_name: str, Config) -> None:
    page.wait_for_load_state("networkidle")
    row = page.locator(
        f"table tbody tr:has(button.audit-name-link:has-text('{Config.ap_audit_name}'))"
    ).first
    row.locator("button.audit-name-link").first.click()
    print(f"   Opened audit: {Config.ap_audit_name}")


def _navigate_to_audit_list(page, Config):
    page.wait_for_selector("a[href='/home/audit']", state="visible")
    page.click("a[href='/home/audit']")
    time.sleep(SLEEP_TIME)
    safe_click(page.locator("button:has-text('Audit Plan')"))
    time.sleep(SLEEP_TIME)
    click_audit(page, Config.ap_audit_name, Config)
    page.wait_for_load_state("networkidle")
    time.sleep(SLEEP_TIME)
    _run_validation(page, Config)
    safe_click(page.locator("button.primary-button:has-text('Update')"))
    validate_audit_list_row(page, Config)

# ─────────────────────────────────────────────────────────────────────────────
# Validation runner
# ─────────────────────────────────────────────────────────────────────────────

def _run_validation(page: Page, Config) -> None:


    log.info("")
    log.info("=" * 60)
    log.info("POST-SAVE UI VALIDATION")
    log.info("=" * 60)

    try:
        ui_report, mapping_report = run_full_validation(page, Config)

        overall = (
            "PASS"
            if (ui_report.overall_pass and mapping_report.overall_pass)
            else "FAIL"
        )
        log.info(f"\n🏁 COMBINED VALIDATION RESULT: {overall}")

        if not ui_report.overall_pass:
            log.warning(f"  ⚠  UI field failures: {len(ui_report.failed)}")
            for r in ui_report.failed:
                log.warning(
                    f"     ✗ {r.field} | Expected: {r.expected} | Actual: {r.actual}"
                )

        if not mapping_report.overall_pass:
            failed_mapping = [r for r in mapping_report.user_results if not r.passed]
            log.warning(f"  ⚠  Mapping failures: {len(failed_mapping)}")
            for r in failed_mapping:
                log.warning(f"     ✗ {r.field}")
                if r.missing:
                    log.warning(f"       Missing : {sorted(r.missing)}")
                if r.extra:
                    log.warning(f"       Extra   : {sorted(r.extra)}")

    except:
        log.error(f" UI Validation error: ", exc_info=True)
def validate_audit_list_row(page: Page, Config) -> ValidationResult:
    log.info(f"VALIDATING AUDIT LIST ROW: '{Config.ap_audit_name}'")

    search_box = page.locator("input[placeholder='Search by Name or Audit Type or Frequency']")
    if search_box.count() > 0:
        search_box.fill(Config.ap_audit_name)
        page.wait_for_timeout(600)  # debounce delay for filtered results

    row = page.locator(
        f"table tbody tr:has(td[data-label='Name'] span[title='{Config.ap_audit_name}'])"
    ).first
    row.wait_for(state="visible", timeout=8000)

    def _cell(label: str) -> str:
        try:
            cell = row.locator(f"td[data-label='{label}']")
            cell.wait_for(state="visible", timeout=3000)
            return cell.inner_text().strip()
        except Exception:
            return ""

    actual_audit_type = _cell("Audit Type")
    actual_start       = _cell("Start Date")
    actual_end         = _cell("End Date")
    actual_frequency   = _cell("Frequency")

    from datetime import datetime, timedelta
    expected_start = datetime.today()
    expected_end   = expected_start + timedelta(days=getattr(Config, "Day_s", 0))
    expected_start_str = expected_start.strftime("%Y-%m-%d")
    expected_end_str   = expected_end.strftime("%Y-%m-%d")

    checks = [
        ("Audit Type", Config.Audit_Type, actual_audit_type),
        ("Frequency",  Config.frequency,  actual_frequency),
    ]
    if _norm(str(Config.frequency)) != "manual":
        checks.append(("Start Date", expected_start_str, actual_start))
        checks.append(("End Date",   expected_end_str,   actual_end))

    all_passed = True
    for field_name, expected, actual in checks:
        passed = _norm(str(expected)) == _norm(str(actual))
        log.info(f"[{'PASS' if passed else 'FAIL'}] {field_name} | Expected: {expected} | Actual: {actual}")
        if not passed:
            all_passed = False

    # clear search box so it doesn't affect subsequent navigation
    if search_box.count() > 0:
        search_box.fill("")
        page.wait_for_timeout(400)

    return ValidationResult(
        field="Audit List Row",
        expected=Config.ap_audit_name,
        actual=Config.ap_audit_name if all_passed else "(mismatch — see log)",
        passed=all_passed,
    )


    
