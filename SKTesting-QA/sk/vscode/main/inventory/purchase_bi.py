import os
import sys
import json
import logging
import difflib
import datetime
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from playwright.sync_api import sync_playwright, expect, TimeoutError as PWTimeout, Page

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

inventory_type = "Unit"  # Unit, Batch, Serialized

EXCEL_FILES = {
    "Unit":       r"C:\Users\HP\Documents\input\Item_Unit_P.xlsx",
    "Batch":      r"C:\Users\HP\Documents\input\Batch.xlsx",
    "Serialized": r"C:\Users\HP\Documents\input\Serialized.xlsx",
}

if inventory_type not in EXCEL_FILES:
    raise ValueError(f"Invalid inventory_type '{inventory_type}'. Must be one of: {list(EXCEL_FILES)}")


class Config:
    EXCEL_FILE: str    = os.environ.get("IMPORT_EXCEL_FILE", EXCEL_FILES[inventory_type])
    BROWSER_NAME: str = os.environ.get("IMPORT_BROWSER", "chrome")
    ENVIRONMENT: str  = os.environ.get("IMPORT_ENV", "PRODUCTION")
    group_name = "Unit_2.0"
    INVENTORY_TYPE: str = inventory_type # Unit, Batch, Serialized
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
# DROPDOWN ENGINE
# ==================================================

def smart_select_dropdown(
    Page: Page,
    dropdown_locator,
    value: str,
 
 
    cutoff: float = 0.6,
) -> Tuple[bool, str]:
    """
    Open a PrimeNG dropdown and select the closest option to *value*.
    Returns (success, match_mode).
    """
    wait_for_overlay(Page)
    dropdown_locator.click(force=True)
    Page.wait_for_selector("div.p-dropdown-panel:visible", timeout=7_000)

    panel   = Page.locator("div.p-dropdown-panel:visible").first
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

    Page.mouse.click(0, 0)
    return False, "not-found"

# ==================================================
# MAPPING ENGINE
# ==================================================

def verify_and_map(Page: Page, dropdown, header: str) -> str:
    current = dropdown.locator("span.p-dropdown-label").inner_text().strip()
    if current == header:
        return "already mapped"
    success, mode = smart_select_dropdown(Page, dropdown, header)
    if not success:
        raise ValueError(f"No dropdown option matches '{header}'")
    return f"mapped ({mode})"
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
    if web_label in excel_headers:
        return web_label
    lower_map = {h.lower(): h for h in excel_headers}
    if web_label.lower() in lower_map:
        return lower_map[web_label.lower()]
    matches = difflib.get_close_matches(web_label, excel_headers, n=1, cutoff=cutoff)
    return matches[0] if matches else None


# ==================================================
# UTILITIES
# ==================================================    
def wait_for_overlay(Page: Page, timeout: int = 1_000) -> None:
    """Block until every known modal/overlay has detached."""
    selectors = [
        ".p-dialog-mask",
        ".p-component-overlay",
        ".cdk-overlay-backdrop",
    ]
    for sel in selectors:
        try:
            Page.wait_for_selector(sel, state="detached", timeout=timeout)
        except PWTimeout:
            pass
# ==================================================
# EXCEL ENGINE
# ==================================================

def read_excel(file_path: str) -> pd.DataFrame:
    """Return the full dataframe from the first sheet."""
    return pd.read_excel(file_path, dtype=str).fillna("")


def read_excel_headers(file_path: str) -> List[str]:
    df = pd.read_excel(file_path, nrows=0)
    return list(df.columns)


def click_and_wait(
    Page: Page,
    click_selector: str,
    wait_selector: Optional[str] = None,
    timeout: int = 15_000,
) -> None:
    Page.wait_for_selector(click_selector, timeout=timeout).click()
    if wait_selector:
        Page.wait_for_selector(wait_selector, timeout=timeout)

def import_items(Page, Config, excel_headers: List[str]) -> None:
    """Upload the Excel file and map every column to the correct dropdown."""
    log.info("=== Import Items ===")

    Page.locator("xpath=//img[contains(@src,'AppIcon.svg')]").click()
    Page.wait_for_timeout(500)
    Page.locator("li[data-product-name='Inventory']").click()
    Page.wait_for_timeout(500)
    Page.locator("img[ng-reflect-content='Purchases']").first.click()
    Page.wait_for_timeout(500)    
    # Click the chevron/dropdown toggle button
    Page.locator("button.p-splitbutton-menubutton").click()
    Page.wait_for_timeout(500)  
    # Click the Import menu item
    Page.locator("span.p-menuitem-text:has-text('Import')").click()
    Page.wait_for_timeout(500)


    Page.locator("a[href='/home/importtransaction/Purchase']").click()
    Page.wait_for_timeout(800)

    Page.wait_for_timeout(800)
    select_item_group(Page, Config.group_name)
    Page.wait_for_timeout(800)
    log.info("Uploading: %s", Config.EXCEL_FILE)
    Page.locator("input[type='file']").set_input_files(Config.EXCEL_FILE)
    Page.wait_for_timeout(800)
    Page.wait_for_selector("div.row-container", timeout=20_000)
    wait_for_overlay(Page)

    row_container = Page.locator("div.row-container")
    left_col      = row_container.locator("div.col-md-6.col-lg-6.col-12").nth(0)
    right_col     = row_container.locator("div.col-md-6.col-lg-6.col-12").nth(1)

    labels    = left_col.locator("div.label > label").all_inner_texts()
    dropdowns = right_col.locator("p-dropdown")

    log.info("Found %d mapping fields on the Page.", len(labels))

    failed_fields: List[str] = []

    for idx, field in enumerate(labels):
        header = smart_header_match(field, excel_headers)

        if not header:
            log.warning("[SKIP]   %-30s → no matching Excel column", field)
            failed_fields.append(field)
            continue

        try:
            result = verify_and_map(Page, dropdowns.nth(idx), header)
            log.info("[MAP]    %-30s → %-30s (%s)", field, header, result)
        except Exception as exc:
            log.error("[FAIL]   %-30s → %s | %s", field, header, exc)
            failed_fields.append(field)

    if failed_fields:
        log.warning("%d field(s) could not be mapped: %s", len(failed_fields), failed_fields)

    # Confirm mapping and start upload
    Page.wait_for_selector("button:has-text('Map'):visible", timeout=10_000).click()
    Page.wait_for_selector("button:has-text('Start Upload'):visible", timeout=10_000).click()


    Page.wait_for_timeout(10000)
    detect_feedback(Page)
    Page.locator("button.swal2-confirm:has-text('OK')").click()
    log.info("Import complete.")



def main() -> None:
   
    if not os.path.exists(Config.EXCEL_FILE):
        log.error("Excel file not found: %s", Config.EXCEL_FILE)
        sys.exit(1)

    df             = read_excel(Config.EXCEL_FILE)
    excel_headers  = list(df.columns)
    log.info("Loaded %d rows, %d headers: %s", len(df), len(excel_headers), excel_headers)   

    with sync_playwright() as p:
                browser, Page = login(
                    p,
                    browser_name=Config.BROWSER_NAME,
                    environment=Config.ENVIRONMENT,
                )

                # Navigate to Inventory module
                    # Dashboard

                
                
                import_items(Page, Config, excel_headers)
                input("\nPress ENTER to close browser...")      
                browser.close()

    
if __name__ == "__main__":
    main()