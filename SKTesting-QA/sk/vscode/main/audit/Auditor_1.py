from asyncio import timeout
import time
import os
import sys
from datetime import datetime
from typing import List, Optional, Tuple
import pandas as pd
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

from login.popup_handler import detect_feedback
from login.logger_setup import mirrored_print


# ======================================================
# UTILITY FUNCTIONS
# ======================================================
def normalize(text: str) -> str:
    """Remove commas and extra spaces"""
    return text.replace(",", "").strip()


# --------------------------------------------------------------
# DYNAMIC STOCK AUDIT PAGE (v2) SELECTORS — used by A_SA
# --------------------------------------------------------------
ASV2_ITEM_SEARCH    = "app-audit-stock-v2 p-autocomplete#autoComplete input.p-autocomplete-input"
ASV2_SUGGESTION     = "li.p-autocomplete-item"
ASV2_ITEM_LOADED    = "app-audit-stock-v2 section.asv2-item:not(.is-empty)"
ASV2_AUDIT_LOCATION = "app-audit-stock-v2 div.asv2-location app-location-tree-select p-treeselect"
ASV2_AUDITED_QTY    = "app-audit-stock-v2 input[formcontrolname='auditedQty']"
ASV2_DAMAGED_QTY    = "app-audit-stock-v2 input[formcontrolname='damagedQty']"
ASV2_ADD_COUNT_BTN  = "app-audit-stock-v2 button.asv2-submit"
ASV2_ADD_ITEM_BTN   = "app-audit-stock-v2 button.asv2-add-item"
ASV2_CONTINUOUS     = "app-audit-stock-v2 .asv2-switch p-inputswitch"
ASV2_LIST_REFRESH   = "app-audit-stock-list-v2 button[aria-label='Refresh']"
ASV2_LIST_COUNT     = "app-audit-stock-list-v2 span.aslv2-count-pill"


# --------------------------------------------------------------
# ENABLE CONTINUOUS COUNT
# --------------------------------------------------------------
def enable_continuous_count(page) -> None:
    toggle = page.locator(ASV2_CONTINUOUS)
    if toggle.locator("input[role='switch']").get_attribute("aria-checked") != "true":
        toggle.click()
        page.wait_for_timeout(300)
        print("   Continuous Count ENABLED")


# --------------------------------------------------------------
# STATIC STOCK AUDIT PAGE SELECTORS — used by S_SA
# (the desktop and mobile layouts both render some buttons, hence :visible)
# --------------------------------------------------------------
STATIC_LOCATION      = "app-static-audit div.sa-location-select app-location-tree-select p-treeselect"
STATIC_ITEM_SEARCH   = "app-static-audit input.p-autocomplete-input[placeholder*='Item Code']"
STATIC_QTY_INPUTS    = "app-static-audit input.sa-step-input"
STATIC_ADD_COUNT_BTN = "app-static-audit button.sa-btn-save:visible"
STATIC_PANEL_CLOSE   = "app-static-audit button.sa-panel-close:visible"
STATIC_ADD_ITEM_BTN  = "app-static-audit button.sa-btn-add:visible"


# ======================================================
# SHARED BY A_SA AND S_SA
# ======================================================

# --------------------------------------------------------------
# SELECT LOCATION — PrimeNG TreeSelect (app-location-tree-select)
# Typing the full path (e.g. "w1-4252") in the search box auto-selects the
# matching node; Escape closes the panel and keeps it. Clicking an already
# selected node would deselect it, so only click when it isn't selected.
# --------------------------------------------------------------
def select_tree_location(page, treeselect_selector: str, value: str, timeout: int = 7000) -> bool:
    try:
        treeselect = page.locator(treeselect_selector).first
        treeselect.wait_for(state="visible", timeout=timeout)
        treeselect.locator(".p-treeselect-trigger").click()

        panel = page.locator("div.p-treeselect-panel").last
        panel.wait_for(state="visible", timeout=timeout)
        page.wait_for_timeout(300)

        panel.locator("input.location-search-input").fill(value)
        page.wait_for_timeout(800)

        last_part = value.split("-")[-1]
        node = panel.locator(f"li[role='treeitem'][aria-label='{last_part}']").first
        if panel.locator(".p-tree-empty-message").is_visible() or node.count() == 0:
            print(f"   ⚠️ Location not found in audit location tree: {value}")
            page.keyboard.press("Escape")
            return False

        if node.get_attribute("aria-selected") != "true":
            node.locator(":scope > .p-treenode-content").click()
            page.wait_for_timeout(300)

        if panel.is_visible():
            page.keyboard.press("Escape")
        panel.wait_for(state="hidden", timeout=timeout)

        print(f"   Location selected: {treeselect.locator('.location-display').inner_text().strip()}")
        return True

    except PlaywrightTimeoutError:
        print(f"   ⚠️ Timeout while selecting audit location: {value}")
        page.keyboard.press("Escape")
        return False


# --------------------------------------------------------------
# LOCATION MISMATCH PROMPT (audited location != item's stock location)
# The Excel row says where the item was counted, so proceed.
# --------------------------------------------------------------
def confirm_location_mismatch(page, timeout: int = 1500) -> None:
    popup = page.locator(".swal2-popup:visible", has_text="Location Mismatch")
    try:
        popup.wait_for(state="visible", timeout=timeout)
    except PlaywrightTimeoutError:
        return
    popup.locator("button.swal2-confirm").click()
    popup.wait_for(state="hidden", timeout=5000)
    print("   ⚠️ Location mismatch confirmed (audited location differs from stock location)")


# --------------------------------------------------------------
# FILL ITEM DETAILS — BOUND (Add item dialog form fields)
# The Add item dialog has no location field; location is set on the
# count screen when the count is added.
# --------------------------------------------------------------
def fill_item_details_bound(
    page,
    ITEM_CODE1: str,
    ITEM_NAME1: str = "",
    CATEGORY1: str = "",
    COST_PRICE1: str = "",
    SELL_PRICE1: str = "",
    BARCODE1: str = "",
    UOM1: str = "",
):
    page.wait_for_selector("div.p-dialog-mask", timeout=9000)
    page.wait_for_selector("div.p-dialog", timeout=9000)
    page.wait_for_selector("div.p-dialog-content div.dialog-content", timeout=9000)

    dialog = page.locator("div.p-dialog-content div.dialog-content")

    if CATEGORY1:
        dialog.locator("p-dropdown[formcontrolname='itemCategoryId']").click()
        page.wait_for_selector("div.p-dropdown-panel li.p-dropdown-item")
        page.locator(f"div.p-dropdown-panel li:has-text('{CATEGORY1}')").click()

    dialog.locator("input[formcontrolname='itemCode']").fill(ITEM_CODE1)
    page.wait_for_timeout(500)

    if ITEM_NAME1:
        dialog.locator("input[formcontrolname='itemName']").fill(ITEM_NAME1)
        page.wait_for_timeout(500)

    if COST_PRICE1:
        dialog.locator("input[formcontrolname='costPrice']").fill(COST_PRICE1)
        page.wait_for_timeout(500)

    if SELL_PRICE1:
        dialog.locator("input[formcontrolname='sellPrice']").fill(SELL_PRICE1)
        page.wait_for_timeout(500)

    if BARCODE1:
        dialog.locator("input[formcontrolname='eanQr']").fill(BARCODE1)
        page.wait_for_timeout(500)

    if UOM1:
        dialog.locator("input[formcontrolname='uom']").fill(UOM1)
        page.wait_for_timeout(500)

    dialog.locator("button[type='submit']").click()
    page.wait_for_timeout(500)


# --------------------------------------------------------------
# EXCEL LOADER
# Config keys used:
#   EXCEL_PATH             — workbook
#   EXCEL_SHEET_auditor_1  — sheet name
#   EXCEL_LOCATION_COL1    — location column (empty location is allowed)
#   EXCEL_CODE_COL1        — item code column
#   EXCEL_AUDITED_COL1     — audited qty column
#   EXCEL_DAMAGED_COL1     — damaged qty column (empty = not recorded)
# --------------------------------------------------------------
def load_count_rows(Config) -> List[Tuple[str, str, float, Optional[float]]]:
    path         = Config.EXCEL_PATH
    sheet_name   = Config.EXCEL_SHEET_auditor_1
    location_col = Config.EXCEL_LOCATION_COL1
    code_col     = Config.EXCEL_CODE_COL1
    audited_col  = Config.EXCEL_AUDITED_COL1
    damaged_col  = Config.EXCEL_DAMAGED_COL1

    if not os.path.exists(path):
        print(f" Excel file not found: {path}")
        sys.exit(1)

    df = pd.read_excel(path, sheet_name=sheet_name)

    for col in (location_col, code_col):
        if col not in df.columns:
            print(f" Missing column in Excel: '{col}'  (found: {list(df.columns)})")
            sys.exit(1)

    items: List[Tuple[str, str, float, Optional[float]]] = []

    for row_no, (_, row) in enumerate(df.iterrows(), start=2):
        location_raw = row.get(location_col)
        code_raw = row.get(code_col)

        # Empty Location is allowed
        location = "" if pd.isna(location_raw) else str(location_raw).strip()

        # Empty Item Code should still be skipped
        if pd.isna(code_raw) or str(code_raw).strip() == "":
            print(f"⚠️ Row {row_no}: Empty Item Code — skipping row...")
            continue
        code = str(code_raw).strip()

        audited_val = pd.to_numeric(row.get(audited_col), errors="coerce")
        audited     = float(audited_val) if not pd.isna(audited_val) else 0

        damaged_raw = row.get(damaged_col)
        if pd.isna(damaged_raw) or str(damaged_raw).strip() == "":
            damaged = None
        else:
            damaged_val = pd.to_numeric(damaged_raw, errors="coerce")
            damaged = float(damaged_val) if not pd.isna(damaged_val) else None

        items.append((location, code, audited, damaged))

    if not items:
        print("⚠ No valid rows found in Excel — check column names and data.")

    return items


# --------------------------------------------------------------
# SELECT BRANCH
# --------------------------------------------------------------
def select_branch(page, branch_text: str):
    dropdown = page.locator(
        'xpath=/html/body/app-root/app-layout/div/app-header/div[1]/div[2]/div[2]//p-dropdown'
    )
    dropdown.wait_for(state="visible", timeout=30000)
    dropdown.locator(".p-dropdown-label").click()

    panel = page.locator(".p-dropdown-panel").last
    panel.wait_for(state="visible", timeout=30000)

    search = panel.locator("input.p-dropdown-filter")
    if search.count() > 0:
        search.fill("")
        search.fill(branch_text)
        page.wait_for_timeout(300)

    option = panel.locator("li.p-dropdown-item", has_text=branch_text)
    if option.count() == 0:
        raise Exception(f" Branch not found: {branch_text}")

    option.first.click()
    panel.wait_for(state="hidden", timeout=30000)

    dropdown.locator(
        ".p-dropdown-label", has_text=branch_text
    ).wait_for(state="visible", timeout=30000)


# --------------------------------------------------------------
# CLICK AUDIT ROW
# --------------------------------------------------------------
def click_audit_row(page, ap_audit_name):
    try:
        page.wait_for_load_state("networkidle", timeout=10000)   # the list keeps polling at times
    except Exception:
        pass

    # Long names are shown truncated ("QA_FC_explore_1..."); the full name is the cell's title
    page.wait_for_selector("button.audit-name-link", timeout=30000)
    link = page.locator(f"table tbody td[title='{ap_audit_name}'] button.audit-name-link")
    if link.count() == 0:
        link = page.locator(
            f"table tbody tr:has(button.audit-name-link:has-text('{ap_audit_name}')) button.audit-name-link"
        )
    link.first.click()
    print(f"   Opened audit: {ap_audit_name}")


def select_navigation_option(page, option_name: str):
    """
    option_name: one of 'Stock Audit', 'Audit Summary', 'Settings'
    """
    page.wait_for_selector("div[role='dialog'][aria-labelledby='auditNavTitle']")

    card = page.locator(
        f"button.create-type-card:has(h6.create-type-card__title:text-is('{option_name}'))"
    )
    card.click()


def A_SA(page, Config):

    # ----------------------
    # Helpers for binding inputs
    # ----------------------
    def human_type_input(page, selector: str, text: str, delay_seconds: float = 0.03) -> None:
        el = page.locator(selector).first
        el.wait_for(state="visible", timeout=7000)
        el.focus()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.type(str(text), delay=int(delay_seconds * 1000))
        el.evaluate("el => el.blur()")
        page.wait_for_timeout(0.08)

    def js_set_number_with_events(page, selector: str, value: str) -> None:
        locator = page.locator(selector).first
        locator.wait_for(state="attached", timeout=7000)
        locator.evaluate(
            """(el, val) => {
                try {
                    if (el.type === 'number') {
                        const n = Number(val);
                        el.valueAsNumber = isNaN(n) ? 0 : n;
                    } else {
                        el.value = val;
                    }
                } catch (e) {
                    el.value = val;
                }
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                if (typeof el.blur === 'function') el.blur();
            }""",
            value,
        )
        page.wait_for_timeout(0.06)

    # Audit location currently chosen in the header tree (skip re-selecting it)
    current_location = {"value": None}

    # --------------------------------------------------------------
    # SELECT AUDIT LOCATION — header "Select audit location" tree
    # --------------------------------------------------------------
    def select_location_inline(page, value: str, timeout: int = 7000) -> bool:
        if not value:
            return False
        if current_location["value"] == value:
            return True
        ok = select_tree_location(page, ASV2_AUDIT_LOCATION, value, timeout)
        current_location["value"] = value if ok else None
        return ok

    # --------------------------------------------------------------
    # CLICK ADD ITEM BUTTON
    # --------------------------------------------------------------
    def click_add_item_button(page, timeout: int = 7000) -> None:
        page.click(ASV2_ADD_ITEM_BTN, timeout=timeout)

        page.wait_for_selector("div.p-dialog-mask", timeout=8000)
        page.wait_for_selector("div.p-dialog", timeout=8000)
        page.wait_for_selector("div.p-dialog-content div.dialog-content", timeout=8000)
        page.wait_for_timeout(200)

    # --------------------------------------------------------------
    # FILL ITEM DETAILS — UNBOUND (count the new item after dialog closes)
    # --------------------------------------------------------------
    def fill_item_details_unbound(
        page,
        LOCATION1: str,
        ITEM_CODE1: str,
        audited_qty1: float,
        damaged_qty1: float
    ):
        save_btn = page.locator(
            "div.p-dialog-content div.dialog-content button.primary-button:has-text('Save')"
        )
        if save_btn.count() > 0 and save_btn.first.is_visible():
            save_btn.first.click()

        page.wait_for_selector("div.p-dialog-mask", state="detached", timeout=8000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(200)

        add_item_count(page, ITEM_CODE1, audited_qty1, damaged_qty1, LOCATION1)

    # --------------------------------------------------------------
    # ADD ITEM COUNT (audit pane form)
    # --------------------------------------------------------------
    def add_item_count(
        page,
        item_query: str,
        audited_qty: int,
        damaged_qty: Optional[float],
        location: str,
    ) -> bool:
        if location:
            if not select_location_inline(page, location):
                return False
        else:
            print("   ⚠️ Empty Location — skipping location selection")

        ac = page.locator(ASV2_ITEM_SEARCH).first
        ac.scroll_into_view_if_needed()
        ac.click()
        ac.fill("")
        ac.type(item_query, delay=50)

        try:
            page.wait_for_selector(f"{ASV2_SUGGESTION}:visible", timeout=5000)
            exact = page.locator(f"{ASV2_SUGGESTION}[aria-label^='{item_query} - ']")
            (exact if exact.count() > 0 else page.locator(ASV2_SUGGESTION)).first.click()
            page.wait_for_selector(ASV2_ITEM_LOADED, timeout=5000)
        except PlaywrightTimeoutError:
            print(f"⚠️ No autocomplete suggestion found for item: {item_query}")
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
            return False

        page.wait_for_timeout(100)

        page.fill(ASV2_AUDITED_QTY, str(audited_qty))

        if damaged_qty is not None:
            page.fill(ASV2_DAMAGED_QTY, str(damaged_qty))
        else:
            print("   ⚠️ Empty Damaged Qty — skipping damaged quantity fill")

        page.click(ASV2_ADD_COUNT_BTN)
        confirm_location_mismatch(page)
        detect_feedback(page)
        page.wait_for_timeout(200)

        return True

    # --------------------------------------------------------------
    # NEW ADD ITEM (optional pre-audit item creation)
    # --------------------------------------------------------------
    def new_add_item(page):
        click_add_item_button(page)

        fill_item_details_bound(
            page,
            Config.ITEM_CODE1,
            Config.ITEM_NAME1,
            Config.CATEGORY1,
            Config.COST_PRICE1,
            Config.SELL_PRICE1,
            Config.BARCODE1,
            Config.UOM1,
        )

        fill_item_details_unbound(
            page,
            Config.LOCATION1,
            Config.ITEM_CODE1,
            Config.audited_qty1,
            Config.damaged_qty1,
        )

    # --------------------------------------------------------------
    # NAVIGATE TO ONGOING AUDITS
    # Uses Config.asa_email / asa_password for auditor login,
    # and Config.ap_audit_name to find the correct audit row.
    # --------------------------------------------------------------
    def navigate_to_ongoing_audits(page, Config):
        print("📂 Navigating to Ongoing Audits...")
        print(f"👤 Auditor: {Config.email}")

        page.wait_for_timeout(500)
        page.wait_for_selector("a[href='/home/audit']", state="visible")
        page.click("a[href='/home/audit']")
        print("   Clicked on 'Audits' in sidebar")
        try:
            page.wait_for_load_state("networkidle", timeout=10000)   # the list keeps polling at times
        except Exception:
            pass

        select_branch(page, Config.Branch)
        print(f"   Branch selected: {Config.Branch}")

        click_audit_row(page, Config.ap_audit_name)

        select_navigation_option(page, "Stock Audit")

        # Optional: add new item before bulk Excel import
        if Config.run_new_add_item:
            new_add_item(page)
        else:
            print(" New add item skipped")

        print(f"Processed {Config.ITEM_CODE1} ({Config.audited_qty1}/{Config.damaged_qty1}/{Config.LOCATION1})")
        detect_feedback(page)
        page.wait_for_timeout(500)

        # ============================================
        # Load items from Excel (asa_* config)
        # ============================================
        print("\n" + "-" * 70)
        print("🔷 ADDING ITEMS FROM EXCEL (Inline Form)")
        print(f"   Sheet   : {Config.EXCEL_SHEET_auditor_1}")
        print(f"   Loc col : {Config.EXCEL_LOCATION_COL1}")
        print(f"   Code col: {Config.EXCEL_CODE_COL1}")
        print(f"   Aud col : {Config.EXCEL_AUDITED_COL1}")
        print(f"   Dam col : {Config.EXCEL_DAMAGED_COL1}")
        print("-" * 70)

        items_to_add = load_count_rows(Config)

        # Baseline for the post-run checks
        list_count_before = read_list_count(page)
        run_started       = datetime.now()
        entered           = []   # (code, audited, damaged, audit location in effect)

        # ── Bulk loop ──────────────────────────────────────────────
        success_count = 0
        fail_count    = 0

        for idx, (location, code, audited, damaged) in enumerate(items_to_add, start=1):
            print(f"\n[{idx}/{len(items_to_add)}] ➡️  {code} | A:{audited}  D:{damaged} | {location}")
            success = add_item_count(page, code, audited, damaged, location)

            if success:
                print(f"   [{idx}/{len(items_to_add)}] {code} "
                      f"(Audited: {audited}, Damaged: {damaged})")
                detect_feedback(page)
                success_count += 1
                entered.append((code, audited, damaged, current_location["value"]))
            else:
                print(f" [{idx}/{len(items_to_add)}] Failed: {code}")
                fail_count += 1

            page.wait_for_timeout(Config.WAIT_AFTER_ACTION)

        print(f"\n📊 Summary: {success_count} succeeded, {fail_count} failed")

        # Feature checks + cross-check: list, Count summary, Finish (declaration), Audit Summary
        if getattr(Config, "run_asv2_checks", False):
            return run_stock_audit_checks(page, Config, entered, list_count_before, run_started)

    # --------------------------------------------------------------
    # ENTRY POINT
    # --------------------------------------------------------------
    # Imported here: stock_audit_checks imports this module's selectors
    from audit.stock_audit_checks import read_list_count, run_stock_audit_checks

    return navigate_to_ongoing_audits(page, Config)
def S_SA(page, Config):
    """
    Static stock audit (app-static-audit): every item is listed, grouped by its
    stock location; the auditor's own location is set in "MY LOCATION".
    """

    # Location currently chosen in "MY LOCATION" (skip re-selecting it)
    current_location = {"value": None}

    # --------------------------------------------------------------
    # SELECT LOCATION — "MY LOCATION" tree
    # --------------------------------------------------------------
    def select_location_inline(page, value: str, timeout: int = 7000) -> bool:
        if not value:
            return False
        if current_location["value"] == value:
            return True
        ok = select_tree_location(page, STATIC_LOCATION, value, timeout)
        current_location["value"] = value if ok else None
        return ok

    # --------------------------------------------------------------
    # CLICK ADD ITEM BUTTON
    # --------------------------------------------------------------
    def click_add_item_button(page, timeout: int = 7000) -> None:
        page.click(STATIC_ADD_ITEM_BTN, timeout=timeout)

        page.wait_for_selector("div.p-dialog-mask", timeout=8000)
        page.wait_for_selector("div.p-dialog", timeout=8000)
        page.wait_for_selector("div.p-dialog-content div.dialog-content", timeout=8000)
        page.wait_for_timeout(200)

    # --------------------------------------------------------------
    # FILL ITEM DETAILS — UNBOUND (count the new item after dialog closes)
    # --------------------------------------------------------------
    def fill_item_details_unbound(
        page,
        LOCATION1: str,
        ITEM_CODE1: str,
        audited_qty1: float,
        damaged_qty1: float
    ):
        save_btn = page.locator(
            "div.p-dialog-content div.dialog-content button.primary-button:has-text('Save')"
        )
        if save_btn.count() > 0 and save_btn.first.is_visible():
            save_btn.first.click()

        page.wait_for_selector("div.p-dialog-mask", state="detached", timeout=8000)
        page.wait_for_timeout(200)

        add_item_count(page, ITEM_CODE1, audited_qty1, damaged_qty1, LOCATION1)

    # --------------------------------------------------------------
    # ADD ITEM COUNT (count panel of the static list)
    # --------------------------------------------------------------
    def add_item_count(
        page,
        item_query: str,
        audited_qty: int,
        damaged_qty: Optional[float],
        location: str,
    ) -> bool:
        if location:
            if not select_location_inline(page, location):
                return False
        else:
            print("   ⚠️ Empty Location — skipping location selection")

        ac = page.locator(STATIC_ITEM_SEARCH).first
        ac.scroll_into_view_if_needed()
        ac.click()
        ac.fill("")
        ac.type(item_query, delay=50)

        try:
            page.wait_for_selector("li.p-autocomplete-item:visible", timeout=5000)
            exact = page.locator(f"li.p-autocomplete-item[aria-label^='{item_query} - ']")
            (exact if exact.count() > 0 else page.locator("li.p-autocomplete-item")).first.click()
        except PlaywrightTimeoutError:
            print(f"⚠️ No autocomplete suggestion found for item: {item_query}")
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
            return False

        # The search filters the list to the item's rows (one per stock location group);
        # open the first one unless the count panel is already open
        save_btn = page.locator(STATIC_ADD_COUNT_BTN).first
        page.wait_for_timeout(500)
        if not save_btn.is_visible():
            row = page.locator(f"app-static-audit tr[id='item-{item_query}']").first
            try:
                row.wait_for(state="visible", timeout=5000)
            except PlaywrightTimeoutError:
                print(f"⚠️ Item row not found in the list: {item_query}")
                return False
            row.click()
        save_btn.wait_for(state="visible", timeout=5000)

        qty_inputs = page.locator(STATIC_QTY_INPUTS)
        qty_inputs.nth(0).fill(str(audited_qty))

        if damaged_qty is None:
            print("   ⚠️ Empty Damaged Qty — skipping damaged quantity fill")
        elif qty_inputs.count() > 1:
            qty_inputs.nth(1).fill(str(damaged_qty))
        else:
            print("   ⚠️ No damaged qty field on this audit — damaged qty not recorded")

        page.click(STATIC_ADD_COUNT_BTN)
        confirm_location_mismatch(page)
        detect_feedback(page)

        close = page.locator(STATIC_PANEL_CLOSE)
        if close.count() > 0:
            close.first.click()
        page.wait_for_timeout(300)

        return True

    # --------------------------------------------------------------
    # NEW ADD ITEM (optional pre-audit item creation)
    # --------------------------------------------------------------
    def new_add_item(page):
        click_add_item_button(page)

        fill_item_details_bound(
            page,
            Config.ITEM_CODE1,
            Config.ITEM_NAME1,
            Config.CATEGORY1,
            Config.COST_PRICE1,
            Config.SELL_PRICE1,
            Config.BARCODE1,
            Config.UOM1,
        )

        fill_item_details_unbound(
            page,
            Config.LOCATION1,
            Config.ITEM_CODE1,
            Config.audited_qty1,
            Config.damaged_qty1,
        )

    # --------------------------------------------------------------
    # NAVIGATE TO ONGOING AUDITS
    # --------------------------------------------------------------
    def navigate_to_ongoing_audits(page, Config):
        print("📂 Navigating to Ongoing Audits...")
        print(f"👤 Auditor: {Config.email}")

        page.wait_for_timeout(500)
        page.wait_for_selector("a[href='/home/audit']", state="visible")
        page.click("a[href='/home/audit']")
        print("   Clicked on 'Audits' in sidebar")
        try:
            page.wait_for_load_state("networkidle", timeout=10000)   # the list keeps polling at times
        except Exception:
            pass

        select_branch(page, Config.Branch)
        print(f"   Branch selected: {Config.Branch}")

        click_audit_row(page, Config.ap_audit_name)

        select_navigation_option(page, "Stock Audit")
        page.wait_for_selector("app-static-audit", timeout=30000)

        # Optional: add new item before bulk Excel import
        if Config.run_new_add_item:
            new_add_item(page)
        else:
            print(" New add item skipped")

        print(f"Processed {Config.ITEM_CODE1} ({Config.audited_qty1}/{Config.damaged_qty1}/{Config.LOCATION1})")
        detect_feedback(page)
        page.wait_for_timeout(500)

        # ============================================
        # Load items from Excel
        # ============================================
        print("\n" + "-" * 70)
        print("🔷 ADDING ITEMS FROM EXCEL (Static list)")
        print(f"   Sheet   : {Config.EXCEL_SHEET_auditor_1}")
        print(f"   Loc col : {Config.EXCEL_LOCATION_COL1}")
        print(f"   Code col: {Config.EXCEL_CODE_COL1}")
        print(f"   Aud col : {Config.EXCEL_AUDITED_COL1}")
        print(f"   Dam col : {Config.EXCEL_DAMAGED_COL1}")
        print("-" * 70)

        items_to_add = load_count_rows(Config)

        # ── Bulk loop ──────────────────────────────────────────────
        success_count = 0
        fail_count    = 0

        for idx, (location, code, audited, damaged) in enumerate(items_to_add, start=1):
            print(f"\n[{idx}/{len(items_to_add)}] ➡️  {code} | A:{audited}  D:{damaged} | {location}")
            success = add_item_count(page, code, audited, damaged, location)

            if success:
                print(f"   [{idx}/{len(items_to_add)}] {code} "
                      f"(Audited: {audited}, Damaged: {damaged})")
                success_count += 1
            else:
                print(f" [{idx}/{len(items_to_add)}] Failed: {code}")
                fail_count += 1

            page.wait_for_timeout(Config.WAIT_AFTER_ACTION)

        print(f"\n📊 Summary: {success_count} succeeded, {fail_count} failed")

    # --------------------------------------------------------------
    # ENTRY POINT
    # --------------------------------------------------------------
    return navigate_to_ongoing_audits(page, Config)


# ======================================================
# MAIN EXECUTION ROUTER
# ======================================================
def stock_audit(page, Config):
    """
    Route execution based on audit type.
    """
    SD_audit_type = str(
        getattr(Config, "SD_audit_type", getattr(Config, "audit_type", "Dynamic"))
    ).strip().lower()

    if SD_audit_type == "static":
        result = S_SA(page, Config)
        print("\n   Static Stock Audit completed.")
    else:
        result = A_SA(page, Config)
        print("\n   Dynamic Stock Audit completed.")
    return result
