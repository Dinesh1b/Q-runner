import sys
import os
import time
from datetime import datetime
import logging
from playwright.sync_api import sync_playwright, expect, TimeoutError as PWTimeout, Page
from login.popup_handler import detect_feedback

log = logging.getLogger(__name__)

# ---------------------------
# Select Inventory Type
# ---------------------------
def select_inventory_type(page, Config, inventory_type):
    card = page.locator("button.inventory-type-card", has_text=inventory_type)
    card.wait_for(state="visible")
    card.click()


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


# ---------------------------
# Add Field
# ---------------------------
def add_field(page, field_index, field_type):

    print(f" Adding Field {field_index}: {field_type}")

    combos = page.locator("span[role='combobox'][aria-label='Select']")
    count_before = combos.count()

    page.get_by_role("button", name="Add Field").click()

    page.wait_for_function(
        f"document.querySelectorAll(\"span[role='combobox'][aria-label='Select']\").length > {count_before}"
    )

    dropdown = page.locator("span[role='combobox'][aria-label='Select']").last
    dropdown.scroll_into_view_if_needed()
    dropdown.click()

    panel = page.locator("div.p-dropdown-panel").last
    panel.wait_for(state="visible")

    panel.locator("li[role='option']", has_text=field_type).click()

    print(f" Field {field_index} set")


# ---------------------------
# Add Serialized IDs
# ---------------------------
def add_ids(page, Config):

    for index, id_name in enumerate(Config.ids, start=1):

        field = page.locator(f"input[formcontrolname='id{index}Name']")
        field.wait_for(state="visible")
        field.fill(id_name)

        print(f" ID {index} added → {id_name}")

        if index < len(Config.ids):

            add_btn = page.locator("button", has_text="Add ID")
            add_btn.click()

            page.wait_for_selector(
                f"input[formcontrolname='id{index+1}Name']"
            )

def add_field_types(page,field_types):

    for index, field_type in enumerate(field_types, start=2):
        add_field(page, index, field_type)

# ---------------------------
# Automation Logic
# ---------------------------
def create_group(page, Config):
    page.click("img[src*='Item_icon.svg']")
    page.wait_for_timeout(500)

    page.get_by_role("button", name="Item Groups").click()
    page.wait_for_timeout(500)

    page.click("button:has-text('Add Item Group')")
    page.wait_for_timeout(500)
    print("Add Item Group")

    page.fill("input[formcontrolname='groupName']", Config.group_name)

    #    Fixed: pass both Config and inventory_type
    select_inventory_type(page, Config, Config.inventory_type)

    #    Fixed: pass Config
    if Config.inventory_type == "Serialized":
        add_ids(page, Config)

    page.locator("input[placeholder='Barcode']").click()
    print("Click Barcode Config")

    #    Fixed: pass field_types
    add_field_types(page, Config.fields)

    barcode_dialog = page.locator("div.p-dialog").filter(has_text="Barcode Configuration")      # ***
    ok_btn = barcode_dialog.locator(".dialog-footer").get_by_role("button", name="Ok", exact=True)  # ***

    ok_btn.wait_for(state="visible")  # ***
    ok_btn.click()
    print("click OK")
    page.wait_for_timeout(500)
    detect_feedback(page)
    page.click("button:has-text('Save')")
    detect_feedback(page)
    page.locator("a.cad-crumb-link").get_by_text("Inventory", exact=True).click()

    #select_item_group(page, Config.group_name)

