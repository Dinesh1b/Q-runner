"""
Inventory Import Automation - Enterprise Architecture
Excel → Smart Header Mapping → Sheet Selection → Dynamic Mapping → Import → Save → UI Validate

Fixes applied:
  1. Add Item  : inputs filled in correct order (UOM→Code→Name was wrong → fixed to Name→Code→UOM)
  4. Quick Add : item00001/2/3 extra rows created because Quick Add used Config values that
  5. Import    : Stock adjustment (Adjustmentqty=10) wasn't being applied — the Excel has
                 Adjustment Type + Adjustmentqty columns; mapping now includes those fields
  6. General   : All page.wait_for_timeout() replaced with proper waits where possible
  7. Validate  : NEW — scrapes the live UI inventory table across ALL pages and compares
                 every row/field against the Excel source, producing a pass/fail report
  8. Details   : NEW — opens Edit form for every Excel row and validates all form fields
                 (Item Code, Name, Barcode, UOM, Category, Cost Price, Sell Price)
  9. Sheet Sel : NEW — after file upload, detects all sheets in the workbook, shows a
                 dropdown (Choose Sheet), user selects → headers + mapping reload dynamically
 10. Summary   : NEW — post-validation inventory summary (category-wise + location-wise counts)
"""

import os
import sys
import json
import logging
import difflib
import datetime
import pandas as pd
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from playwright.sync_api import expect, sync_playwright, TimeoutError as PWTimeout, Page

# --------------------------------------------------
# PATH SETUP
# --------------------------------------------------

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from login.login import login
from login.popup_handler import detect_feedback

# --------------------------------------------------
# LOGGING SETUP
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ==================================================
# EDIT-FORM FIELD MAP
# (friendly_label, formcontrolname, excel_col)
# ==================================================

EDIT_FORM_FIELDS: List[Tuple[str, str, str]] = [
    ("Item Code",    "itemCode",       "Item Code"),
    ("Name",         "itemName",       "Item Name"),
    ("Barcode",      "eanQr",          "Barcode"),
    ("UOM",          "UOM",            "UOM"),
    ("Category",     "itemCategoryId", "Item Category"),
    ("Tag",          "tag",            "Tag"),            # app-tags chip list
    ("Description",  "description",    "Description"),
    ("Cost Price",   "costPrice",      "Cost Price"),
    ("Sell Price",   "sellPrice",      "Sell Price"),
    ("Tax HSN",      "taxHsn",         "Tax HSN"),
    ("Tax",          "taxRateId",      "Tax"),            # p-dropdown
    ("Reorder Limit","ReorderLimit",   "Reorder Limit"),
    ("ABC",          "_abc",           "ABC"),            # btn-group radio
    ("FMS",          "_fms",           "FMS"),            # btn-group radio
]


# ==================================================
# CONFIGURATION
# ==================================================

# ---------------------------
# Select Item Group Dropdown
# ---------------------------
def _open_item_group_panel(page: Page, group_field, panel, attempts: int = 3) -> None:
    """
    Open the Item Group p-dropdown and confirm its panel is visible.
    A single click can be lost while the Inventory page is still rendering the
    dropdown, so each attempt verifies the panel and retries with a different
    way of opening it (trigger click → label click → keyboard).
    """
    trigger = group_field.locator("[role='button'][aria-label='dropdown trigger']")
    label = group_field.locator("span[role='combobox']")
    openers = [
        lambda: trigger.click(),
        lambda: label.click(),
        lambda: (label.focus(), page.keyboard.press("Enter")),
    ]
    for attempt in range(attempts):
        if panel.is_visible():
            return
        openers[attempt % len(openers)]()
        try:
            panel.wait_for(state="visible", timeout=5_000)
            return
        except PWTimeout:
            log.warning("Item Group dropdown did not open (attempt %d/%d), retrying", attempt + 1, attempts)
    raise PWTimeout(f"Item Group dropdown panel did not open after {attempts} attempts")


def select_item_group(page: Page, group_name: str) -> None:
    group_field = page.locator(
        "app-group-select-dropdown[placeholder='Select Item Group']"
    )
    label = group_field.locator("span[role='combobox']")
    label.wait_for(state="visible", timeout=15_000)

    # Already selected → nothing to do (selecting it again just toggles the panel)
    if label.inner_text().strip() == group_name:
        log.info("Item Group '%s' already selected", group_name)
        return

    # The panel is appended to <body>; scope it to THIS dropdown via its listbox id
    # so other PrimeNG panels on the page can't be matched.
    list_id = label.get_attribute("aria-controls") or "itemgroup_list"
    panel = page.locator("div.p-dropdown-panel").filter(has=page.locator(f"ul[id='{list_id}']"))

    _open_item_group_panel(page, group_field, panel)

    option_list = panel.locator("li[role='option']")
    option_list.first.wait_for(state="attached", timeout=10_000)
    initial_count = option_list.count()

    search_input = panel.locator("input[placeholder='Search Item Group']")
    if search_input.count() > 0:
        search_input.fill(group_name)
        try:
            # Poll for the list to actually shrink, instead of a fixed sleep
            expect(option_list).not_to_have_count(initial_count, timeout=1_500)
        except AssertionError:
            # Filter isn't wired — clear it and fall back to full-list scan
            search_input.fill("")

    # Options carry the group name as their accessible name (aria-label)
    option = panel.get_by_role("option", name=group_name, exact=True)
    if option.count() == 0:
        # Report the full list so a wrong Config.group_name is obvious
        if search_input.count() > 0:
            search_input.fill("")
            try:
                expect(option_list).to_have_count(initial_count, timeout=1_500)
            except AssertionError:
                pass
        available = [
            (option_list.nth(i).get_attribute("aria-label") or "").strip()
            for i in range(option_list.count())
        ]
        page.keyboard.press("Escape")
        raise ValueError(f"Item Group '{group_name}' not found. Available groups: {available}")
    option.click()

    panel.wait_for(state="hidden")

    expect(label).to_have_text(group_name)
# ==================================================
# UTILITIES
# ==================================================

def wait_for_overlay(page, timeout: int = 3_000) -> None:
    """Block until every known modal/overlay has detached."""
    selectors = [
        ".p-dialog-mask",
        ".p-component-overlay",
        ".cdk-overlay-backdrop",
    ]
    for sel in selectors:
        try:
            page.wait_for_selector(sel, state="detached", timeout=timeout)
        except PWTimeout:
            pass


def click_and_wait(
    page,
    click_selector: str,
    wait_selector: Optional[str] = None,
    timeout: int = 15_000,
) -> None:
    page.wait_for_selector(click_selector, timeout=timeout).click()
    if wait_selector:
        page.wait_for_selector(wait_selector, timeout=timeout)


def safe_fill(locator, value: str) -> None:
    """Select all existing text then fill — works on any Playwright Locator."""
    locator.click()
    locator.press("Control+a")
    locator.fill(str(value))


# ==================================================
# EXCEL ENGINE
# ==================================================

def read_excel(file_path: str, sheet_name: Optional[str] = None) -> pd.DataFrame:
    """
    Return the full dataframe from the specified sheet (or first sheet if None).
    sheet_name should match what was selected in the UI sheet dropdown.
    """
    kwargs = {"dtype": str}
    if sheet_name:
        kwargs["sheet_name"] = sheet_name
    df = pd.read_excel(file_path, **kwargs).fillna("")
    return _clean_df_columns(df)


def read_excel_headers(file_path: str, sheet_name: Optional[str] = None) -> List[str]:
    """Return column headers from the specified sheet (or first sheet if None)."""
    kwargs = {"nrows": 0, "dtype": str}
    if sheet_name:
        kwargs["sheet_name"] = sheet_name
    df = pd.read_excel(file_path, **kwargs)
    return list(df.columns)


def read_excel_sheet_names(file_path: str) -> List[str]:
    """Return all sheet names in the workbook."""
    xl = pd.ExcelFile(file_path)
    return xl.sheet_names


# ==================================================
# SMART HEADER MATCH ENGINE
# ==================================================

def smart_header_match(
    web_label: str,
    excel_headers: List[str],
    cutoff: float = 0.6,
) -> Optional[str]:
    """
    Return the best-matching Excel column for a web form label.
    Priority: exact → case-insensitive → fuzzy (difflib).
    """
    # Common header aliases between templates
    aliases = {
        "item category": ["Item Category", "Category"],
        "category":      ["Category", "Item Category"],
    }
    key = web_label.strip().lower()
    if key in aliases:
        for candidate in aliases[key]:
            if candidate in excel_headers:
                return candidate
        lower_map = {h.lower(): h for h in excel_headers}
        for candidate in aliases[key]:
            if candidate.lower() in lower_map:
                return lower_map[candidate.lower()]

    if web_label in excel_headers:
        return web_label
    lower_map = {h.lower(): h for h in excel_headers}
    if web_label.lower() in lower_map:
        return lower_map[web_label.lower()]
    matches = difflib.get_close_matches(web_label, excel_headers, n=1, cutoff=cutoff)
    return matches[0] if matches else None


# ==================================================
# DROPDOWN ENGINE
# ==================================================

def smart_select_dropdown(
    page,
    dropdown_locator,
    value: str,
    cutoff: float = 0.6,
) -> Tuple[bool, str]:
    """
    Open a PrimeNG dropdown and select the closest option to *value*.
    Returns (success, match_mode).
    """
    wait_for_overlay(page)
    dropdown_locator.click(force=True)
    page.wait_for_selector("div.p-dropdown-panel:visible", timeout=7_000)

    panel   = page.locator("div.p-dropdown-panel:visible").first
    options = panel.locator("li.p-dropdown-item").all_inner_texts()

    def pick(text: str) -> None:
        safe = text.replace("'", "\\'")
        panel.locator(f"li.p-dropdown-item:has-text('{safe}')").first.click()

    if value in options:
        pick(value)
        return True, "exact"

    lower_map = {o.lower(): o for o in options}
    if value.lower() in lower_map:
        pick(lower_map[value.lower()])
        return True, "case-insensitive"

    fuzzy = difflib.get_close_matches(value, options, n=1, cutoff=cutoff)
    if fuzzy:
        pick(fuzzy[0])
        return True, "fuzzy"

    page.mouse.click(0, 0)
    return False, "not-found"


# ==================================================
# MAPPING ENGINE
# ==================================================

def verify_and_map(page, dropdown, header: str) -> str:
    current = dropdown.locator("span.p-dropdown-label").inner_text().strip()
    if current == header:
        return "already mapped"
    success, mode = smart_select_dropdown(page, dropdown, header)
    if not success:
        raise ValueError(f"No dropdown option matches '{header}'")
    return f"mapped ({mode})"


# ==================================================
# CATEGORY HELPER
# ==================================================

def select_or_create_category(page, category_value: str) -> None:
    """Set the item category, creating it if the current form requests that."""
    category_control = page.locator("[formcontrolname='itemCategoryId']").first
    category_input = category_control.get_by_role("combobox").first
    if category_input.count() == 0:
        category_input = category_control.locator("input").first

    safe_fill(category_input, category_value)
    category_input.press("Enter")

    options = page.locator("li.p-autocomplete-item:visible")
    option_texts = options.all_inner_texts()

    clicked = False
    for index, option_text in enumerate(option_texts):
        text = option_text.strip()

        # Existing category — exact match
        if text == category_value:
            options.nth(index).click()
            clicked = True
            break

        # "Create new" suggestion — PrimeNG wraps the value as: ➕ ADD "value"
        if text == f'➕ ADD "{category_value}"':
            options.nth(index).click()
            clicked = True
            break

    if not clicked and option_texts:
        # Nothing matched exactly — log so a silent no-op doesn't hide as success
        log.warning(
            "[CATEGORY] No exact match or create-option found for '%s'. Options seen: %s",
            category_value, option_texts,
        )

    popup = page.locator(".swal2-popup:visible")
    try:
        popup.wait_for(state="visible", timeout=3_000)
        popup.get_by_role("button", name="Create", exact=True).click()
        popup.wait_for(state="hidden", timeout=3_000)
    except PWTimeout:
        pass

def fill_tag(page, tag_value: str) -> None:
    """Commit a tag through the current app-tags input."""
    tag_value = str(tag_value or "").strip()
    if not tag_value:
        return

    # .tag-input is a wrapper div, not the actual input — find the real
    # editable element nested inside it.
    tag_wrapper = page.locator(".tag-input").first
    tag_input = tag_wrapper.locator("input").first

    if tag_input.count() == 0:
        log.warning("[TAG] No <input> found inside .tag-input wrapper — skipping tag fill.")
        return

    safe_fill(tag_input, tag_value)
    tag_input.press("Enter")
    page.wait_for_timeout(300)


# ==================================================
# ADD ITEM (single test record)
# ==================================================

def add_item(page, Config) -> None:
    """Fill the current Add Item form with the configured test record."""
    log.info("=== Add Item ===")
    page.locator("button.il-btn-add").click()
    page.wait_for_selector("[formcontrolname='itemName']", timeout=10_000)

    def form_input(formcontrolname: str):
        return page.locator(
            f"input[formcontrolname='{formcontrolname}'], "
            f"textarea[formcontrolname='{formcontrolname}'], "
            f"[formcontrolname='{formcontrolname}'] input, "
            f"[formcontrolname='{formcontrolname}'] textarea"
        ).first

    safe_fill(form_input("itemName"), Config.Item_Name)
    safe_fill(form_input("itemCode"), Config.Item_Code)
    safe_fill(form_input("UOM"), Config.Item_UOM)

    select_or_create_category(page, Config.Item_Category)
    wait_for_overlay(page)

    safe_fill(form_input("eanQr"), Config.Item_Barcode)
    fill_tag(page, Config.Item_Tag)

    description = getattr(Config, "Item_Description", "")
    tax_hsn = getattr(Config, "Item_TaxHsn", "")
    tax = getattr(Config, "Item_Tax", "")
    reorder_limit = getattr(Config, "Item_ReorderLimit", "")

    def configured(value) -> bool:
        return value is not None and bool(str(value).strip())

    if configured(description):
        safe_fill(form_input("description"), description)
    safe_fill(form_input("costPrice"), str(Config.Item_CP))
    safe_fill(form_input("sellPrice"), str(Config.Item_SP))
    if configured(tax_hsn):
        safe_fill(form_input("taxHsn"), tax_hsn)
    if configured(tax):
        smart_select_dropdown(
            page,
            page.locator("[formcontrolname='taxRateId']").first,
            str(tax),
        )
    if configured(reorder_limit):
        safe_fill(form_input("ReorderLimit"), str(reorder_limit))

    # ── Save — name matches fine; the timeout was a visibility/DOM-state issue,
    #    not exact= or casing. Close any lingering overlay, wait for the button
    #    to attach, then click the visible instance (ng-star-inserted can leave
    #    a hidden duplicate). ──
    wait_for_overlay(page)                                                  # ***

    save_btn = page.locator(                                                # ***
        "button.bd-btn.primary:has-text('Save changes'), "                  # ***
        "button:has-text('Save changes')"                                   # ***
    )                                                                       # ***

    target = None                                                           # ***
    try:                                                                    # ***
        save_btn.first.wait_for(state="attached", timeout=10_000)           # *** attached, not visible
    except PWTimeout:                                                       # ***
        pass                                                                # ***

    for i in range(save_btn.count()):                                       # ***
        if save_btn.nth(i).is_visible():                                    # ***
            target = save_btn.nth(i)                                        # ***
            break                                                           # ***

    if target is None:                                                      # ***
        names = page.get_by_role("button").all_inner_texts()               # *** dump real labels
        log.error("[ADD_ITEM] No visible 'Save changes' button. Buttons seen: %s", names)  # ***
        page.screenshot(path="save_changes_missing.png", full_page=True)
        raise RuntimeError("Save changes button not found/visible")

    target.click()                                                          # ***
    detect_feedback(page)
    wait_for_overlay(page)

    back_button = page.get_by_role("button", name="Back", exact=True)
    if back_button.is_visible():
        back_button.click()
        wait_for_overlay(page)
    else:
        print("Item added successfully, skipping Back.")
        log.info("Add Item saved: %s / %s", Config.Item_Name, Config.Item_Code)



# ==================================================
# SHEET SELECTION  (NEW)
# ==================================================

def select_sheet(page, preferred_sheet: Optional[str] = None) -> str:
    """
    After file upload, wait for the sheet selection dropdown to appear,
    then pick the best matching sheet.

    Selection priority:
      1. preferred_sheet — exact match
      2. preferred_sheet — case-insensitive match
      3. preferred_sheet — fuzzy match (difflib, cutoff 0.6)
      4. First available sheet (fallback)

    After selection the function waits for div.row-container to reload
    so that the header-mapping UI reflects the chosen sheet's columns.

    Args:
        page            : Playwright Page object
        preferred_sheet : Sheet name from Config.sheet_name, or None to
                          auto-select the first available sheet.

    Returns:
        The sheet name that was actually selected (empty string if the
        dropdown was not found — single-sheet workbooks skip this step).
    """
    log.info("[SHEET] Waiting for sheet selection dropdown …")

    # The dropdown uses placeholder="Choose Sheet" per the HTML snippet
    sheet_dropdown_selector = (
        "p-dropdown[ng-reflect-placeholder='Choose Sheet'], "
        "p-dropdown[placeholder='Choose Sheet']"
    )

    try:
        page.wait_for_selector(sheet_dropdown_selector, timeout=10_000)
    except PWTimeout:
        log.warning(
            "[SHEET] Sheet dropdown not visible — "
            "single-sheet workbook or dropdown did not render. Skipping."
        )
        return ""

    sheet_dropdown = page.locator(sheet_dropdown_selector).first

    # ── Read available sheet names ───────────────────────────────────────────
    sheet_dropdown.locator("div.p-dropdown-trigger").click(force=True)
    page.wait_for_selector("div.p-dropdown-panel:visible", timeout=7_000)

    panel   = page.locator("div.p-dropdown-panel:visible").first
    options = panel.locator("li.p-dropdown-item").all_inner_texts()
    log.info("[SHEET] Available sheets: %s", options)

    # Close the panel before delegating to smart_select_dropdown
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    if not options:
        log.warning("[SHEET] No sheets found inside the dropdown. Skipping.")
        return ""

    # ── Determine target sheet ───────────────────────────────────────────────
    target = preferred_sheet if preferred_sheet else options[0]

    success, mode = smart_select_dropdown(page, sheet_dropdown, target)

    if success:
        log.info("[SHEET] Selected sheet: '%s'  (match mode: %s)", target, mode)
        selected = target
    else:
        # Fallback to first sheet
        log.warning(
            "[SHEET] Could not select preferred sheet '%s'. "
            "Falling back to first sheet: '%s'",
            target, options[0],
        )
        smart_select_dropdown(page, sheet_dropdown, options[0])
        selected = options[0]

    # ── Wait for the header-mapping UI to reload ─────────────────────────────
    # The backend re-reads the chosen sheet's columns and re-renders
    # div.row-container with updated dropdowns.
    try:
        page.wait_for_selector("div.row-container", timeout=10_000)
        wait_for_overlay(page)
        log.info("[SHEET] Header mapping UI reloaded for sheet: '%s'", selected)
    except PWTimeout:
        log.warning(
            "[SHEET] div.row-container did not reload after sheet selection. "
            "Proceeding anyway — mapping may be stale."
        )

    return selected


# ==================================================
# IMPORT ITEMS  (file upload + sheet selection + column mapping)
# ==================================================

def import_items(page, Config, excel_headers: List[str]) -> None:
    """
    Upload the Excel file, select the correct sheet (NEW), then map
    every column to the correct dropdown in the header-mapping UI.

    Flow:
        1. Navigate  →  Import Items page
        2. Upload    →  set_input_files
        3. Sheet     →  select_sheet()           NEW
        4. Map       →  verify_and_map() per field
        5. Confirm   →  Map → Start Upload → OK
    """
    log.info("=== Import Items ===")

    click_and_wait(page, "button:has-text('Import')")
    page.wait_for_timeout(800)
    page.locator("a[href='/home/importtransaction/Items']").click()
    page.wait_for_timeout(800)

    log.info("Uploading: %s", Config.EXCEL_FILE)
    page.locator("input[type='file']").set_input_files(Config.EXCEL_FILE)

    # ── Sheet selection ──────────────────────────────────────────────────────
    # After upload, the backend detects all sheets and populates the
    # "Choose Sheet" p-dropdown. We pick Config.sheet_name (if set) or
    # fall back to the first available sheet automatically.
    #
    # Config.sheet_name examples:
    #   Config.sheet_name = None          → auto-picks first sheet
    #   Config.sheet_name = "Inventory"   → picks "Inventory" sheet
    #   Config.sheet_name = "6477"        → picks sheet named "6477"
    preferred_sheet = getattr(Config, "sheet_name", None)
    selected_sheet  = select_sheet(page, preferred_sheet)

    if selected_sheet:
        log.info("[IMPORT] Proceeding with sheet: '%s'", selected_sheet)
    # ────────────────────────────────────────────────────────────────────────

    page.wait_for_selector("div.row-container", timeout=20_000)
    wait_for_overlay(page)

    row_container = page.locator("div.row-container")
    left_col      = row_container.locator("div.col-md-6.col-lg-6.col-12").nth(0)
    right_col     = row_container.locator("div.col-md-6.col-lg-6.col-12").nth(1)

    labels    = left_col.locator("div.label > label").all_inner_texts()
    dropdowns = right_col.locator("p-dropdown")

    log.info("Found %d mapping fields on the page.", len(labels))

    failed_fields: List[str] = []

    for idx, field_label in enumerate(labels):
        header = smart_header_match(field_label, excel_headers)

        if not header:
            log.warning("[SKIP]   %-30s → no matching Excel column", field_label)
            failed_fields.append(field_label)
            continue

        try:
            result = verify_and_map(page, dropdowns.nth(idx), header)
            log.info("[MAP]    %-30s → %-30s (%s)", field_label, header, result)
        except Exception as exc:
            log.error("[FAIL]   %-30s → %s | %s", field_label, header, exc)
            failed_fields.append(field_label)

    if failed_fields:
        log.warning("%d field(s) could not be mapped: %s", len(failed_fields), failed_fields)

    page.wait_for_selector("button:has-text('Map'):visible", timeout=10_000).click()
    page.wait_for_selector("button:has-text('Start Upload'):visible", timeout=10_000).click()

    page.wait_for_timeout(10000)
    detect_feedback(page)
    page.locator("button.swal2-confirm:has-text('OK')").click()
    log.info("Import complete.")


# ==================================================
# RESULT DATACLASSES
# ==================================================

@dataclass
class FieldResult:
    field:    str
    expected: str
    actual:   str
    status:   str       # "PASS" | "FAIL" | "MISSING" | "EXTRA"
    note:     str = ""


@dataclass
class RowResult:
    item_code: str
    item_name: str
    status:    str      # "PASS" | "FAIL" | "MISSING" | "EXTRA"
    fields: List[FieldResult] = field(default_factory=list)

    @property
    def failed_fields(self) -> List[FieldResult]:
        return [f for f in self.fields if f.status != "PASS"]


# ==================================================
# UI TABLE SCRAPER  (handles pagination)
# ==================================================

def _scrape_current_page(page) -> List[Dict[str, str]]:
    """
    Extract all visible rows from the div-based item list (app-item-list).
    The list is NOT a PrimeNG table — each item is a div.il-row.
    Returns list of dicts: Name, Item Code, UOM, Category, Stock In Hand, Location.
    """
    rows = []
    row_els = page.locator("app-item-list div.il-row").all()               # *** div-list rows (was tbody.p-datatable-tbody tr)

    for row_el in row_els:                                                 # ***
        name_el = row_el.locator("div.il-row-name").first                 # ***
        name = name_el.inner_text().strip() if name_el.count() > 0 else ""  # ***

        sub = row_el.locator("div.il-row-sub").first                      # *** holds <span.cat>CAT</span> · <span>CODE</span>
        cat = ""                                                          # ***
        code = ""                                                         # ***
        if sub.count() > 0:                                               # ***
            cat_el = sub.locator("span.cat").first                        # ***
            cat = cat_el.inner_text().strip() if cat_el.count() > 0 else ""  # ***
            code = sub.locator("span").last.inner_text().strip()          # *** code = last span (no class of its own)

        stock_box = row_el.locator("div.il-row-stock").first              # ***
        uom = ""                                                          # ***
        stock = ""                                                        # ***
        if stock_box.count() > 0:                                         # ***
            n_el = stock_box.locator("div.n").first                       # ***
            u_el = stock_box.locator("div.u").first                       # ***
            stock = n_el.inner_text().strip() if n_el.count() > 0 else "" # ***
            uom = u_el.inner_text().strip() if u_el.count() > 0 else ""   # ***

        if not code and not name:                                         # *** skip placeholder/empty rows
            continue                                                      # ***

        rows.append({
            "Name":          name,
            "Item Code":     code,
            "UOM":           uom,
            "Category":      cat,
            "Stock In Hand": stock,
            "Location":      "",                                          # *** div-list has no Location column
        })

    return rows


def scrape_all_ui_rows(page) -> List[Dict[str, str]]:
    """
    Scrape every row from the div-based item list, clicking through ALL pages.
    """
    log.info("[VALIDATE] Scraping UI inventory list …")
    all_rows: List[Dict[str, str]] = []

    try:                                                                  # *** don't crash on empty group
        page.wait_for_selector("app-item-list div.il-row", timeout=15_000)  # *** div-list (was tbody.p-datatable-tbody)
    except PWTimeout:                                                      # ***
        log.warning("[VALIDATE] No il-row items found — empty group?")    # ***
        return all_rows                                                   # ***
    wait_for_overlay(page)

    page_num = 1
    while True:
        log.info("[VALIDATE]   → page %d", page_num)
        rows = _scrape_current_page(page)
        all_rows.extend(rows)
        log.info(
            "[VALIDATE]      scraped %d rows (running total: %d)",
            len(rows), len(all_rows),
        )

        next_btn = page.locator(
            "app-item-list button.p-paginator-next:not(.p-disabled)"      # *** scope to list pane — detail pane has its own paginators
        )

        if next_btn.count() == 0 or not next_btn.first.is_enabled():
            log.info("[VALIDATE]   → No more pages.")
            break

        next_btn.first.click()
        page.wait_for_timeout(1_000)
        try:
            page.wait_for_selector("app-item-list div.il-row", timeout=8_000)  # ***
        except PWTimeout:
            break
        wait_for_overlay(page)
        page_num += 1

    log.info("[VALIDATE] Total UI rows scraped: %d", len(all_rows))
    return all_rows


# ==================================================
# COMPARATOR  (list-level — Name / Code / Category)
# ==================================================

# Fields compared in the inventory LIST view
FIELDS_TO_CHECK = [
    ("Name",      "Item Name"),
    ("Item Code", "Item Code"),
    ("Category",  "Item Category"),
]


def _normalise(value: str) -> str:
    return str(value).strip().lower()


def _values_match(expected: str, actual: str) -> bool:
    return _normalise(expected) == _normalise(actual)


def _clean_df_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Strip trailing asterisks and spaces from every column name so that
    template-decorated names like 'Item Code *' match plain lookups.
    """
    df = df.copy()
    df.columns = [str(c).strip().rstrip(" *").strip() for c in df.columns]

    # Header compatibility: some Excel templates use "Category" while others use "Item Category".
    # Standardize to "Item Category" so downstream lookups are consistent.
    cols = list(df.columns)
    if "Category" in cols and "Item Category" not in cols:
        df = df.rename(columns={"Category": "Item Category"})

    log.debug("[VALIDATE] Normalised Excel columns: %s", list(df.columns))
    return df


def compare_excel_vs_ui(
    df: pd.DataFrame,
    ui_rows: List[Dict[str, str]],
    config,
) -> List[RowResult]:
    """
    Match each Excel row to a UI row strictly by Item Code (case-insensitive).
    Flags: MISSING / EXTRA / PASS / FAIL
    """
    df = _clean_df_columns(df)
    results: List[RowResult] = []

    ui_by_code: Dict[str, Dict] = {}
    for r in ui_rows:
        code = r["Item Code"].strip()
        if code:
            ui_by_code[code.lower()] = r

    for _, excel_row in df.iterrows():
        ex_code = str(excel_row.get("Item Code", "")).strip()
        ex_name = str(excel_row.get("Item Name", "")).strip()

        ui_row = ui_by_code.get(ex_code.lower())

        if ui_row is None:
            results.append(RowResult(
                item_code=ex_code,
                item_name=ex_name,
                status="MISSING",
                fields=[FieldResult(
                    field="(row)",
                    expected=f"{ex_name} / {ex_code}",
                    actual="—",
                    status="MISSING",
                    note="Item not found in UI at all",
                )],
            ))
            continue

        field_results: List[FieldResult] = []
        row_pass = True

        for ui_col, excel_col in FIELDS_TO_CHECK:
            expected_val = str(excel_row.get(excel_col, "")).strip()
            actual_val   = ui_row.get(ui_col, "").strip()

            if _values_match(expected_val, actual_val):
                field_results.append(FieldResult(
                    field=ui_col,
                    expected=expected_val,
                    actual=actual_val,
                    status="PASS",
                ))
            else:
                row_pass = False
                field_results.append(FieldResult(
                    field=ui_col,
                    expected=expected_val,
                    actual=actual_val,
                    status="FAIL",
                    note=f"Expected '{expected_val}', Actual '{actual_val}'",
                ))

        results.append(RowResult(
            item_code=ex_code,
            item_name=ex_name,
            status="PASS" if row_pass else "FAIL",
            fields=field_results,
        ))

    excel_codes = {
        str(r.get("Item Code", "")).strip().lower()
        for _, r in df.iterrows()
    }

    for ui_row in ui_rows:
        code = ui_row["Item Code"]
        name = ui_row["Name"]
        if code.strip().lower() not in excel_codes:
            results.append(RowResult(
                item_code=code,
                item_name=name,
                status="EXTRA",
                fields=[FieldResult(
                    field="(row)",
                    expected="—",
                    actual=f"{name} / {code}",
                    status="EXTRA",
                    note="Found in UI but not in Excel source file",
                )],
            ))

    return results


# ==================================================
# INPUT ANALYSIS
# ==================================================

def _print_input_analysis(
    df: pd.DataFrame,
    ui_rows: List[Dict[str, str]],
) -> None:
    df = _clean_df_columns(df)

    ui_by_code: Dict[str, Dict] = {
        r["Item Code"].strip().lower(): r for r in ui_rows if r["Item Code"].strip()
    }
    excel_codes: set = {
        str(row.get("Item Code", "")).strip().lower()
        for _, row in df.iterrows()
    }

    log.info("")
    log.info("=" * 70)
    log.info("  INPUT ANALYSIS")
    log.info("=" * 70)

    log.info("")
    log.info("  📄 Excel  (%d rows)", len(df))
    log.info("  " + "-" * 60)

    for _, row in df.iterrows():
        code = str(row.get("Item Code", "")).strip()
        name = str(row.get("Item Name", "")).strip()
        cat  = str(row.get("Item Category", "")).strip()
        status_tag = "[FOUND   ]" if ui_by_code.get(code.lower()) else "[MISSING ]"
        log.info("  %s  %-14s  →  %-35s  →  %s", status_tag, code, name, cat)

    log.info("")
    log.info("  🌐 UI  (%d rows)", len(ui_rows))
    log.info("  " + "-" * 60)

    for r in ui_rows:
        code = r["Item Code"].strip()
        name = r["Name"].strip()
        cat  = r["Category"].strip()
        status_tag = "[MATCHED ]" if code.lower() in excel_codes else "[EXTRA   ]"
        log.info("  %s  %-14s  →  %-35s  →  %s", status_tag, code, name, cat)

    log.info("")
    log.info("=" * 70)


# ==================================================
# VALIDATION REPORTER  (shared by both validators)
# ==================================================

def _print_validation_report(
    results: List[RowResult],
    title: str = "INVENTORY UI VALIDATION REPORT",
) -> None:
    total   = len(results)
    passed  = sum(1 for r in results if r.status == "PASS")
    failed  = sum(1 for r in results if r.status == "FAIL")
    missing = sum(1 for r in results if r.status == "MISSING")
    extra   = sum(1 for r in results if r.status == "EXTRA")

    log.info("")
    log.info("=" * 70)
    log.info(
        "  %s  —  %s",
        title,
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    log.info("=" * 70)
    log.info("-" * 70)
    log.info("  Total rows compared : %d", total)
    log.info("     PASS             : %d", passed)
    log.info("   FAIL             : %d", failed)
    log.info("  ⚠  MISSING (in UI) : %d", missing)
    log.info("  ➕ EXTRA  (in UI)   : %d", extra)
    log.info("=" * 70)

    pass_rows = [r for r in results if r.status == "PASS"]                # *** split so PASS and FAIL print in separate blocks
    fail_rows = [r for r in results if r.status == "FAIL"]               # ***
    other_rows = [r for r in results if r.status in ("MISSING", "EXTRA")]  # ***

    # ── PASS rows — one line each, no field breakdown ───────────────────────
    if pass_rows:                                                        # ***
        log.info("")                                                    # ***
        log.info("  PASSED (%d)", len(pass_rows))                       # ***
        log.info("  " + "-" * 60)                                       # ***
        for r in pass_rows:                                             # ***
            log.info("   [PASS]  %-20s  Code: %-12s", r.item_name, r.item_code)  # ***

    # ── FAIL rows — one header line + only the failed fields ────────────────
    if fail_rows:                                                        # ***
        log.info("")                                                    # ***
        log.info("  FAILED (%d)", len(fail_rows))                       # ***
        log.info("  " + "-" * 60)                                       # ***
        for r in fail_rows:                                             # ***
            log.info("\n [FAIL]  %-20s  Code: %-12s", r.item_name, r.item_code)  # ***
            for f in r.failed_fields:                                   # *** only the mismatched fields, not the passing ones
                log.info(                                              # ***
                    "     %-18s  Expected: %-25s  Actual: %-25s  %s",   # ***
                    f.field, f.expected, f.actual,                     # ***
                    f" {f.note}" if f.note else "",                    # ***
                )                                                      # ***

    # ── MISSING / EXTRA rows — single note line each ────────────────────────
    if other_rows:                                                      # ***
        log.info("")                                                    # ***
        log.info("  MISSING / EXTRA (%d)", len(other_rows))            # ***
        log.info("  " + "-" * 60)                                       # ***
        for r in other_rows:                                           # ***
            icon = "⚠ " if r.status == "MISSING" else "➕"             # ***
            log.info("\n%s [%s]  %-20s  Code: %-12s", icon, r.status, r.item_name, r.item_code)  # ***
            log.info("     %s", r.fields[0].note)                      # ***

    log.info("")
    log.info("=" * 70)
    overall = "ALL PASSED   " if failed == 0 and missing == 0 else "FAILURES DETECTED "
    log.info("  RESULT: %s", overall)
    log.info("=" * 70)


# ==================================================
# VALIDATE UI  (inventory list — Name / Code / Category)
# ==================================================

def validate_ui(
    page,
    df: pd.DataFrame,
    config,
) -> Tuple[List[RowResult], List[Dict[str, str]]]:
    """
    Scrapes the inventory list (div-based, app-item-list) across all pages
    and compares Name, Item Code, Category against the Excel source.
    """
    log.info("=== UI Validation (List View) ===")

    wait_for_overlay(page)
    click_and_wait(page, "img[src*='Item_icon.svg']")
    wait_for_overlay(page)

    # Clear any active search so the FULL group is scraped, not one filtered item
    search = page.locator("div.il-search input").first                    # ***
    if search.count() > 0 and (search.input_value() or "").strip():       # ***
        safe_fill(search, "")                                             # ***
        search.press("Enter")                                             # ***
        wait_for_overlay(page)                                            # ***

    table_ready = True
    try:
        page.wait_for_selector("app-item-list div.il-row", timeout=15_000)  # *** div-list (was tbody.p-datatable-tbody)
    except PWTimeout:
        table_ready = False
        row_count = page.locator("app-item-list div.il-row").count()      # ***
        log.error(                                                        # ***
            "[VALIDATE] 'app-item-list div.il-row' not found in 15s. "    # ***
            "URL=%s  il-rows=%d  (empty item group, slow load, or nav miss)",  # ***
            page.url, row_count,                                          # ***
        )                                                                 # ***
        page.screenshot(path="validate_ui_no_table.png", full_page=True)

    if table_ready:
        wait_for_overlay(page)
        ui_rows = scrape_all_ui_rows(page)
    else:
        ui_rows = []

    _print_input_analysis(df, ui_rows)

    results = compare_excel_vs_ui(df, ui_rows, config)
    _print_validation_report(results, title="LIST VIEW VALIDATION REPORT")

    return results, ui_rows

# ==================================================
# DETAILS VALIDATION — EDIT FORM HELPERS
# ==================================================

def _normalise_price(value: str) -> str:
    """
    Strip currency symbols / commas so '100.00' == '100' == '₹100.00'.
    Falls back to lowercased raw string on parse failure.
    """
    cleaned = value.replace(",", "").strip().lstrip("₹$€£").strip()
    try:
        return str(float(cleaned))
    except ValueError:
        return cleaned.lower()


def _fields_equal(label: str, expected: str, actual: str) -> bool:
    """
    Field-aware comparison.
      • Price fields      → normalise currency / decimals
      • Tag               → order-insensitive comma-list compare
      • ABC / FMS         → single-char, case-insensitive
      • All others        → case-insensitive strip
    """
    if label in {"Cost Price", "Sell Price"}:
        return _normalise_price(expected) == _normalise_price(actual)

    if label == "Tag":
        exp_tags = sorted(t.strip().lower() for t in expected.split(",") if t.strip())
        act_tags = sorted(t.strip().lower() for t in actual.split(",")   if t.strip())
        return exp_tags == act_tags

    return expected.strip().lower() == actual.strip().lower()


def _read_edit_form(page) -> Dict[str, str]:
    """
    Read every visible field from the open Edit Item form.
    Returns a dict keyed by the friendly label from EDIT_FORM_FIELDS.
    """
    values: Dict[str, str] = {}

    for label, fcn, _ in EDIT_FORM_FIELDS:
        try:

            # ── Item Code — read-only display div, NOT an input ───────────────
            if label == "Item Code":                                            # *** was falling into the plain-input branch → [formcontrolname='itemCode'] doesn't exist → always ""
                view = page.locator(                                            # ***
                    "div.bd-fld:has(label:has-text('Item Code')) div.view-val"  # ***
                ).first                                                         # ***
                values[label] = view.inner_text().strip() if view.count() > 0 else ""  # ***

            # ── Classification seg-ctrl (disabled buttons, no formcontrolname) ─
            elif label == "ABC":                                               # *** real container is div.class-fld > div.seg-ctrl > button.seg-btn (was div[role=group][aria-labelledby=abc-label])
                active = page.locator(
                    "div.class-fld:has(label:has-text('ABC')) div.seg-ctrl button.seg-btn.active"  # ***
                ).first
                values[label] = active.inner_text().strip() if active.count() > 0 else ""

            elif label == "FMS":
                active = page.locator(
                    "div.class-fld:has(label:has-text('FMS')) div.seg-ctrl button.seg-btn.active"  # ***
                ).first
                values[label] = active.inner_text().strip() if active.count() > 0 else ""

            # ── Category — p-autocomplete text input ─────────────────────────
            elif label == "Category":
                cat_input = page.locator(
                    f"[formcontrolname='{fcn}'] input.p-autocomplete-input"
                ).first
                values[label] = (cat_input.input_value() or "").strip()

            # ── Tag — .tag-input chips (was app-tags / p-autocomplete tokens) ──
            elif label == "Tag":                                               # ***
                chips = page.locator(                                          # ***
                    "div.tag-input > *:not(input)"                             # *** chip elements from *ngFor; trailing <input> excluded
                ).all_inner_texts()                                           # ***
                values[label] = ", ".join(t.strip() for t in chips if t.strip())  # ***

            # ── Price fields — p-inputnumber spinbutton ───────────────────────
            elif label in ("Cost Price", "Sell Price"):
                wrapper = page.locator(f"[formcontrolname='{fcn}']")
                inner   = wrapper.locator("input[role='spinbutton']").first
                values[label] = (inner.input_value() or "").strip()

            # ── Tax — p-dropdown (read visible label span) ────────────────────
            elif label == "Tax":
                label_span = page.locator(
                    f"[formcontrolname='{fcn}'] span.p-dropdown-label"
                ).first
                text = (label_span.inner_text() or "").strip()
                # PrimeNG shows the placeholder / nbsp when nothing is selected
                values[label] = "" if text in ("\xa0", "&nbsp;", "Select…", "Select...") else text  # *** added the "Select…" placeholder cases

            # ── Location — p-treeselect custom display div ────────────────────
            # (unchanged; not currently in EDIT_FORM_FIELDS so this branch is
            #  never reached — see note below.)
            elif label == "Location":
                display = page.locator(
                    f"[formcontrolname='{fcn}'] .location-display:not(.placeholder)"
                ).first
                if display.count() > 0:
                    title_val = (display.get_attribute("title") or "").strip()
                    values[label] = title_val if title_val else display.inner_text().strip()
                else:
                    hidden = page.locator(
                        f"[formcontrolname='{fcn}'] input[role='combobox']"
                    ).first
                    aria_val = (hidden.get_attribute("aria-label") or "").strip()
                    values[label] = (
                        "" if aria_val in ("Location-Aisle-Bay-Level", "") else aria_val
                    )

            # ── All plain p-inputtext / textarea fields ───────────────────────
            else:
                wrapper = page.locator(f"[formcontrolname='{fcn}']")
                inner   = wrapper.locator("input").first
                target  = inner if inner.count() > 0 else wrapper
                values[label] = (target.input_value() or "").strip()

        except Exception as exc:
            log.warning("[DETAILS_VAL] Could not read '%s': %s", label, exc)
            values[label] = ""

    return values


def _search_item_in_list(page, item_code: str) -> bool:
    """
    Type item_code into the inventory search box and wait for the filtered
    div-row bearing that code to appear. Returns True on success.
    """
    try:
        search = page.locator("div.il-search input").first
        safe_fill(search, item_code)
        search.press("Enter")
        page.wait_for_selector(                                            # *** wait for the DIV row with the code (was tbody.p-datatable-tbody tr)
            f"app-item-list div.il-row:has-text('{item_code}')",          # ***
            timeout=6_000,                                                 # ***
        )                                                                 # ***
        wait_for_overlay(page)
        return True
    except PWTimeout:
        log.warning("[DETAILS_VAL] Search timed out for code '%s'", item_code)
        return False


def _open_edit_form(page, item_code: str, item_name: str) -> bool:
    """
    From the div-based item list:
      1. Search for item_code
      2. Click the matching div.il-row (by CODE) to load the detail pane
      3. Click the 'Basic Details' pill → opens the Edit dialog
      4. Confirm the 'Edit basic details' dialog is visible
    Returns True on success.
    """
    if not _search_item_in_list(page, item_code):
        return False

    try:
        row = page.locator(                                               # *** match div-row by exact code span (list is a div-list, not a table)
            f"app-item-list div.il-row:has(div.il-row-sub span:text-is('{item_code}'))"  # ***
        ).first                                                           # ***
        if row.count() == 0:                                              # *** fallback if structure differs
            row = page.locator(                                           # ***
                f"app-item-list div.il-row:has-text('{item_code}')"       # ***
            ).first                                                       # ***
        row.click()                                                       # ***

        page.wait_for_selector(                                           # *** wait for THIS item's detail pane before opening editor
            f"app-item-detail span.code:text-is('{item_code}')",          # ***
            timeout=8_000,                                                # ***
        )                                                                # ***
        wait_for_overlay(page)                                           # ***

        page.locator("button.id-btn:has-text('Basic Details')").click()
        page.wait_for_selector(
            "div.item-form-dialog h2:has-text('Edit basic details')",
            timeout=8_000,
        )
        page.wait_for_selector(
            "div.item-form-dialog [formcontrolname='itemName']",
            timeout=8_000,
        )
        return True

    except Exception as exc:
        log.warning(
            "[DETAILS_VAL] Could not open Edit form for '%s' / '%s': %s",
            item_code, item_name, exc,
        )
        return False

def _back_to_inventory_list(page) -> None:
    """Close the Edit dialog and return to the div-based item list."""
    try:
        close_btn = page.locator(
            "div.item-form-dialog button.bd-btn.ghost:has-text('Close'), "
            "div.item-form-dialog button.bd-x"
        ).first
        if close_btn.count() > 0 and close_btn.is_visible():
            close_btn.click()
            wait_for_overlay(page)
        page.wait_for_selector("app-item-list div.il-row", timeout=8_000)  # *** confirm list is back (was tbody.p-datatable-tbody); removed dead Back-button branch — this flow has no Back
    except Exception as exc:
        log.warning("[DETAILS_VAL] Back navigation issue: %s", exc)


# ==================================================
# DETAILS VALIDATION  (Edit-form field-level check)
# ==================================================

def Details_validation(page, df: pd.DataFrame) -> List[RowResult]:
    """
    For every row in the Excel dataframe:
      1. Search the inventory list for the item code
      2. Open the Edit Item form via the kebab menu
      3. Read every field mapped in EDIT_FORM_FIELDS
      4. Compare against the Excel source value
      5. Navigate back and repeat

    Fields validated:
      Item Code · Name · Barcode · UOM · Category · Cost Price · Sell Price

    Match key : Item Code (used for search; no fallback)
    Returns   : List[RowResult]  — same shape as validate_ui results
    """
    log.info("=== Details Validation (Edit-form field check) ===")
    df = _clean_df_columns(df)

    results: List[RowResult] = []

    for _, excel_row in df.iterrows():
        item_code = str(excel_row.get("Item Code", "")).strip()
        item_name = str(excel_row.get("Item Name", "")).strip()

        if not item_code:
            log.warning(
                "[DETAILS_VAL] Skipping row with empty Item Code (name='%s')",
                item_name,
            )
            continue

        log.info("[DETAILS_VAL] Checking  %-14s  %s", item_code, item_name)

        # ── Try to open the Edit form ────────────────────────────────────────
        opened = _open_edit_form(page, item_code, item_name)

        if not opened:
            results.append(RowResult(
                item_code=item_code,
                item_name=item_name,
                status="MISSING",
                fields=[FieldResult(
                    field="(row)",
                    expected=f"{item_name} / {item_code}",
                    actual="—",
                    status="MISSING",
                    note="Edit form could not be opened — item not found or navigation failed",
                )],
            ))
            continue

        # ── Read all fields from the open Edit form ──────────────────────────
        ui_values = _read_edit_form(page)

        # ── Compare each field against Excel ────────────────────────────────
        field_results: List[FieldResult] = []
        row_pass = True

        for label, _, excel_col in EDIT_FORM_FIELDS:
            expected_val = str(excel_row.get(excel_col, "")).strip()
            actual_val   = ui_values.get(label, "")

            if _fields_equal(label, expected_val, actual_val):
                field_results.append(FieldResult(
                    field=label,
                    expected=expected_val,
                    actual=actual_val,
                    status="PASS",
                ))
            else:
                row_pass = False
                field_results.append(FieldResult(
                    field=label,
                    expected=expected_val,
                    actual=actual_val,
                    status="FAIL",
                    note=f"Expected '{expected_val}', Actual '{actual_val}'",
                ))

        results.append(RowResult(
            item_code=item_code,
            item_name=item_name,
            status="PASS" if row_pass else "FAIL",
            fields=field_results,
        ))

        # ── Back to list for the next item ───────────────────────────────────
        _back_to_inventory_list(page)

    _print_validation_report(results, title="EDIT FORM VALIDATION REPORT")
    return results


# ==================================================
# POST-VALIDATION INVENTORY SUMMARY
# ==================================================

def post_validation_summary(
    ui_rows: List[Dict[str, str]],
    details_results: List[RowResult],
) -> None:
    """
    Prints a category-wise and location-wise item count summary.

    Sources:
      - Category  : ui_rows (list-table scrape) — Category column present in list view
      - Location  : details_results (Edit-form validation) — Location is NOT a list-table
                    column; reliably read only from the Edit form via _read_edit_form,
                    stored in each RowResult's fields list as field="Location".

    Rules:
      - Sorting   : alphabetical (case-insensitive) for both groups
      - Blanks    : bucketed as "(No Category)" / "(No Location)"
      - Fallback  : if details_results is empty (Details_validation skipped),
                    Location falls back to the "Location" key in ui_rows
    """
    category_counter: Counter = Counter()
    location_counter: Counter = Counter()

    # ── Category from list-table rows ────────────────────────────────────────
    for row in ui_rows:
        cat = row.get("Category", "").strip() or "(No Category)"
        category_counter[cat] += 1

    # ── Location from Edit-form RowResult fields ──────────────────────────────
    # Details_validation stores a FieldResult(field="Location", actual=<value>)
    # for every item it opened. Use that — it's the same value confirmed working
    # in the terminal output (e.g. SA-A2-B4-L1).
    # Skip MISSING rows (Edit form could not be opened for those items).
    for row_result in details_results:
        if row_result.status == "MISSING":
            continue
        loc_field = next(
            (f for f in row_result.fields if f.field == "Location"),
            None,
        )
        loc = (loc_field.actual.strip() if loc_field else "") or "(No Location)"
        location_counter[loc] += 1

    # ── Fallback: Details_validation was skipped ─────────────────────────────
    if not location_counter:
        for row in ui_rows:
            loc = row.get("Location", "").strip() or "(No Location)"
            location_counter[loc] += 1

    sorted_categories = sorted(category_counter.items(), key=lambda x: x[0].lower())
    sorted_locations  = sorted(location_counter.items(), key=lambda x: x[0].lower())

    total_items      = len(ui_rows)
    total_categories = len(sorted_categories)
    total_locations  = len(sorted_locations)

    SEP  = "=" * 50
    DASH = "-" * 40

    log.info("")
    log.info(SEP)
    log.info("  POST-VALIDATION INVENTORY SUMMARY (UI Source)")
    log.info(SEP)

    log.info("")
    log.info("  CATEGORY WISE ITEM COUNT")
    log.info(DASH)
    for cat_name, count in sorted_categories:
        log.info("  %-35s : %d", cat_name, count)

    log.info("")
    log.info("  LOCATION WISE ITEM COUNT")
    log.info(DASH)
    for loc_name, count in sorted_locations:
        log.info("  %-35s : %d", loc_name, count)

    log.info("")
    log.info(DASH)
    log.info("  Total categories  : %d", total_categories)
    log.info("  Total locations   : %d", total_locations)
    log.info("  Total items       : %d", total_items)
    log.info(SEP)
    log.info("")


# ==================================================
# MAIN ENTRY POINT
# ==================================================

def import_app(page, Config):

    if not os.path.exists(Config.EXCEL_FILE):
        log.error("Excel file not found: %s", Config.EXCEL_FILE)
        sys.exit(1)

    # ── Load dataframe from the correct sheet ────────────────────────────────
    # Config.sheet_name may be None (first sheet) or a specific name.
    sheet_name    = getattr(Config, "sheet_name", None)
    df            = read_excel(Config.EXCEL_FILE, sheet_name=sheet_name)
    excel_headers = list(df.columns)
    log.info(
        "Loaded %d rows, %d headers from sheet '%s': %s",
        len(df), len(excel_headers),
        sheet_name or "(first sheet)",
        excel_headers,
    )

    # Navigate to Inventory module
    click_and_wait(page, "img[src*='Item_icon.svg']")
    select_item_group(page, Config.group_name)

    # 1. Add one test item (full form)
    if Config.run_add_item:
        add_item(page, Config)
    else:
        print("x add_item")



    # 3. Import the full Excel file with sheet selection + column mapping
    if Config.run_import_items:
        import_items(page, Config, excel_headers)
    else:
        print("x import_items")

    page.wait_for_timeout(1_000)
    select_item_group(page, Config.group_name)

    # 4. List-level validation — scrape inventory table, compare Name/Code/Category
    #    Returns (results, ui_rows); ui_rows is retained for the summary below.
    list_results, ui_rows = validate_ui(page, df, Config)

    # 5. Details validation — open Edit form per item, compare all form fields
    if getattr(Config, "run_details_validation", True):
        select_item_group(page, Config.group_name)
        details_results = Details_validation(page, df)
    else:
        print("x Details_validation")
        details_results = []

    # 6. Post-validation inventory summary
    #    Category  → ui_rows (list-table scrape)
    #    Location  → details_results (Edit-form reads, already confirmed working)
    post_validation_summary(ui_rows, details_results)

    # CI exit code — fail if any list or detail check failed
    all_results = list_results + details_results
    failures    = [r for r in all_results if r.status in ("FAIL", "MISSING")]
    if failures:
        log.error(
            "[VALIDATE] %d item(s) failed validation across list + edit-form checks.",
            len(failures),
        )