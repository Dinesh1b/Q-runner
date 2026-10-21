import re

from playwright.sync_api import expect, Error as PWError, TimeoutError as PWTimeout

from login.popup_handler import detect_feedback

# ---------------------------
# Optional Config keys (skipped unless set)
# ---------------------------
#   accounting_mode        = "Basic Accounting Mode"     # or "Inventory Accounting Mode"
#   costing_method         = "Weighted Average"
#   accounting_accounts    = {"SaleAccountId": "Sales Revenue"}   # Accounting tab: formcontrolname -> account
#   advanced_toggles       = {"AllowNonTaxable": True}   # Advanced tab: formcontrolname -> on/off
#   enable_uom_conversions = True                         # UOM Conversions tab switch
#   primary_uom            = "Bale"                       # required when UOM conversions are on
#   uom_value_type         = "Integer only"


# ---------------------------
# Select Inventory Type
# ---------------------------
def select_inventory_type(page, Config, inventory_type):
    title = page.locator(
        ".inventory-title",
        has_text=re.compile(rf"^\s*{re.escape(inventory_type)}\s*$", re.I),
    )
    card = page.locator("button.inventory-type-card").filter(has=title)
    card.click()
    expect(card).to_have_class(re.compile(r"\bactive\b"))


# ---------------------------
# Select Item Group Dropdown
# ---------------------------
def select_item_group(page, group_name):
    dropdown = page.locator("p-dropdown[placeholder='Select Item Group']")
    dropdown.locator("div.p-dropdown-trigger").click()

    panel = page.locator("div.p-dropdown-panel")
    panel.locator("input.p-dropdown-filter").fill(group_name)

    panel.locator("li.p-dropdown-item", has_text=group_name).first.click()


# ---------------------------
# Select PrimeNG Dropdown Option
# ---------------------------
def select_dropdown(page, dropdown, option_text):
    combo = dropdown.locator("span[role='combobox']")
    combo.click()

    # The options panel is appended to <body>; find it through the combobox's listbox id
    list_id = combo.get_attribute("aria-controls")
    if list_id:
        panel = page.locator(f"div.p-dropdown-panel:has([id='{list_id}'])")
    else:
        panel = page.locator("div.p-dropdown-panel:visible").last
    panel.wait_for(state="visible")

    panel.get_by_role("option", name=option_text, exact=True).click()
    expect(combo).to_have_text(option_text)


# ---------------------------
# Barcode Configuration Dialog
# ---------------------------
def barcode_dialog(page):
    return page.locator("div.p-dialog").filter(
        has=page.locator(".p-dialog-title", has_text="Barcode Configuration")
    )


def open_barcode_dialog(page):
    page.locator("input[placeholder='Barcode']").click()
    dialog = barcode_dialog(page)
    dialog.wait_for(state="visible")
    # Field 1 must be rendered before add_field counts the rows
    dialog.locator("p-dropdown[formcontrolname='key']").first.wait_for()
    print("Click Barcode Config")


def close_barcode_dialog(page):
    dialog = barcode_dialog(page)
    dialog.locator(
        ".dialog-footer button.primary-button", has_text=re.compile(r"^\s*Ok\s*$")
    ).click()
    dialog.wait_for(state="hidden")
    print("click OK")


# ---------------------------
# Add Field
# ---------------------------
def add_field(page, field_index, field_type):

    print(f" Adding Field {field_index}: {field_type}")

    dialog = barcode_dialog(page)
    dropdowns = dialog.locator("p-dropdown[formcontrolname='key']")
    count_before = dropdowns.count()

    # Match the icon button by text: its accessible name includes the icon glyph
    dialog.locator(".dialog-footer button", has_text="Add Field").click()
    expect(dropdowns).to_have_count(count_before + 1)

    dropdown = dropdowns.last
    dropdown.scroll_into_view_if_needed()
    select_dropdown(page, dropdown, field_type)

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

            # Each ID column can show its own "+Add ID" link; use the newest one
            add_btn = page.locator(
                "app-add-edit-item-group button.link-name", has_text="Add ID"
            ).last
            add_btn.click()

            page.wait_for_selector(
                f"input[formcontrolname='id{index+1}Name']"
            )

def add_field_types(page,field_types):

    for index, field_type in enumerate(field_types, start=2):
        add_field(page, index, field_type)


# ---------------------------
# Open Add Item Group
# ---------------------------
def open_add_item_group(page):
    page.locator("a.sidenav-nav-link[href='/home/inventory']").click()

    pill = page.locator("button.id-pill", has_text="Item Groups")
    add_btn = page.locator("button", has_text="Add Item Group")

    # Inventory re-routes itself to the last viewed item right after it opens,
    # which can swallow a click on "Item Groups"; wait for that, then retry until the list shows.
    try:
        page.wait_for_url(re.compile(r"/home/inventory\?.*item="), timeout=10000)
    except PWTimeout:
        pass
    pill.wait_for(state="visible")

    for attempt in range(1, 4):
        try:
            if pill.is_visible():
                pill.click(timeout=5000)
            add_btn.wait_for(state="visible", timeout=10000)
            break
        except PWTimeout:
            print(f" Item Groups did not open (attempt {attempt}), retrying")
    else:
        raise AssertionError("Item Groups page did not open after 3 attempts")

    add_btn.click()
    page.locator("input[formcontrolname='groupName']").wait_for(state="visible")
    print("Add Item Group")


# ---------------------------
# Open Item Group Tab
# ---------------------------
def open_tab(page, name):
    tab = page.locator("button.item-group-tab").filter(
        has=page.locator(".tab-title", has_text=re.compile(rf"^\s*{re.escape(name)}\s*$"))
    )
    tab.click()
    expect(tab).to_have_class(re.compile(r"\bactive\b"))


# ---------------------------
# Accounting (optional)
# ---------------------------
def configure_accounting(page, Config):
    open_tab(page, "Accounting")

    method = getattr(Config, "costing_method", None)
    if method:
        card = page.locator("button.costing-method-card").filter(
            has=page.locator(".costing-method-title", has_text=re.compile(rf"^\s*{re.escape(method)}\b", re.I))
        )
        expect(card, f"Unknown costing method: {method}").to_have_count(1)
        expect(card, f"Costing method is disabled: {method}").to_be_enabled()
        if not re.search(r"\bactive\b", card.get_attribute("class") or ""):
            card.click()
        expect(card).to_have_class(re.compile(r"\bactive\b"))
        print(f" Costing method → {method}")

    mode = getattr(Config, "accounting_mode", None) or "Basic Accounting Mode"
    toggle = page.locator("button.accounting-mode-toggle", has_text=mode)
    expect(toggle, f"Unknown accounting mode: {mode}").to_have_count(1)
    if not re.search(r"\bactive\b", toggle.get_attribute("class") or ""):
        toggle.click()
    expect(toggle).to_have_class(re.compile(r"\bactive\b"))
    print(f" Accounting mode → {mode}")

    # Both modes render the same account fields; use the block of the chosen mode
    block = page.locator("div.accounting-mode-block").filter(has=toggle)
    for control, account in (getattr(Config, "accounting_accounts", None) or {}).items():
        dropdown = block.locator(f"p-dropdown[formcontrolname='{control}']")
        expect(dropdown, f"{control} is not an account field in {mode}").to_have_count(1)
        select_dropdown(page, dropdown, account)
        print(f" {control} → {account}")


# ---------------------------
# Advanced Toggles (optional)
# ---------------------------
def set_advanced_toggles(page, toggles):
    open_tab(page, "Advanced")

    # Turn options off before turning others on, in case some are mutually exclusive
    for name, enabled in sorted(toggles.items(), key=lambda item: item[1]):
        toggle = page.locator("app-add-edit-item-group label.advanced-toggle").filter(
            has=page.locator(f"input[formcontrolname='{name}']")
        )
        checkbox = toggle.locator("input[type='checkbox']")
        expect(checkbox, f"Unknown Advanced toggle: {name}").to_have_count(1)
        expect(checkbox, f"Advanced toggle is disabled: {name}").to_be_enabled()

        # The real checkbox is invisible (opacity 0, 0x0); click the visible pill instead
        if checkbox.is_checked() != enabled:
            toggle.locator("span.toggle-pill").click()
        expect(checkbox).to_be_checked(checked=enabled)
        print(f" Advanced: {name} → {'on' if enabled else 'off'}")

    # Some toggles may switch others off, so check them all again
    for name, enabled in toggles.items():
        checkbox = page.locator(
            f"app-add-edit-item-group label.advanced-toggle input[formcontrolname='{name}']"
        )
        expect(checkbox, f"Advanced toggle {name} changed after setting the others").to_be_checked(
            checked=enabled
        )


# ---------------------------
# UOM Conversions (optional)
# ---------------------------
def configure_uom(page, Config):
    open_tab(page, "UOM Conversions")

    uom = page.locator("app-add-edit-item-group .tab-panel:visible app-uom-conversions")
    switch = uom.locator("p-inputswitch[formcontrolname='enabled']")
    switch_input = switch.locator("input[role='switch']")
    if not switch_input.is_checked():
        switch.locator(".p-inputswitch-slider").click()
    expect(switch_input).to_be_checked()
    print(" UOM conversions → on")

    primary = uom.locator("p-dropdown[formcontrolname='uomStructureId']").first
    primary_uom = getattr(Config, "primary_uom", None)
    if primary_uom:
        select_dropdown(page, primary, primary_uom)
        print(f" Primary UOM → {primary_uom}")
    elif "Select UOM" in primary.inner_text():
        raise ValueError("Config.primary_uom is required when enable_uom_conversions is True")

    value_type = getattr(Config, "uom_value_type", None)
    if value_type:
        select_dropdown(page, uom.locator("p-dropdown[formcontrolname='valueType']").first, value_type)
        print(f" UOM value type → {value_type}")


# ---------------------------
# Save & Verify
# ---------------------------
def invalid_fields(page):
    # Inactive tabs are not rendered, so visit each one to collect its invalid controls
    names = set()
    tabs = page.locator("button.item-group-tab")
    for i in range(tabs.count()):
        tabs.nth(i).click()
        expect(tabs.nth(i)).to_have_class(re.compile(r"\bactive\b"))
        names.update(page.locator("app-add-edit-item-group [formcontrolname].ng-invalid").evaluate_all(
            "els => els.map(e => e.getAttribute('formcontrolname'))"
        ))
    return sorted(names)


def save_group(page, group_name):
    form = page.locator("app-add-edit-item-group")
    save = form.locator("div.form-footer button[type='submit']")
    try:
        expect(save).to_be_enabled(timeout=10000)
    except AssertionError:
        raise AssertionError(f"Save is still disabled; invalid fields: {invalid_fields(page)}") from None

    save.click()
    print("click Save")

    try:
        messages = detect_feedback(page)
    except PWError as e:
        # detect_feedback can raise if a toast vanishes while it is read; the list check below decides
        print(f" Feedback check failed: {e}")
        messages = []
    errors = [m for m in messages if re.search(r"error|fail|exist|invalid", m, re.I)]
    if errors:
        raise AssertionError(f"Item Group '{group_name}' was not saved: {errors}")

    # Back is only needed if Save keeps the form open
    back = form.locator("div.form-footer button", has_text="Back")
    if back.is_visible():
        back.click()

    search = page.locator("#groupSearchInput")
    search.fill(group_name)
    search.press("Enter")
    expect(page.get_by_text(group_name, exact=True).first).to_be_visible(timeout=15000)
    print(f"Item Group '{group_name}' listed")


# ---------------------------
# Automation Logic
# ---------------------------
def create_group(page, Config):
    open_add_item_group(page)
    page.wait_for_timeout(1000)

    page.fill("input[formcontrolname='groupName']", Config.group_name)
    page.wait_for_timeout(1000)

    #    Fixed: pass both Config and inventory_type
    select_inventory_type(page, Config, Config.inventory_type)
    page.wait_for_timeout(1000)

    #    Fixed: pass Config
    if Config.inventory_type == "Serialized":
        add_ids(page, Config)

    open_barcode_dialog(page)
    page.wait_for_timeout(1000)

    #    Fixed: pass field_types
    add_field_types(page, Config.fields)

    close_barcode_dialog(page)

    if any(getattr(Config, key, None) for key in ("accounting_mode", "costing_method", "accounting_accounts")):
        configure_accounting(page, Config)
        page.wait_for_timeout(1000)

    advanced_toggles = getattr(Config, "advanced_toggles", None)
    if advanced_toggles:
        set_advanced_toggles(page, advanced_toggles)
        page.wait_for_timeout(1000)

    if getattr(Config, "enable_uom_conversions", False):
        configure_uom(page, Config)
        page.wait_for_timeout(1000)

    save_group(page, Config.group_name)

    # Verify Dropdown
    #select_item_group(page, Config.group_name)
