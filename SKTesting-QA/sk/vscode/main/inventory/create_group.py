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
#   enable_uom_conversions = True                         # UOM Conversions switch: True = on, False = off
#   primary_uom            = "Bale"                       # required when UOM conversions are on
#   uom_value_type         = "Integer only"
#   secondary_uoms         = [{"uom": "Box", "quantity": 10}]   # 1 Box = 10 <base>; "base" defaults to Primary
#   tertiary_uoms          = [{"uom": "Pallet", "quantity": 20, "base": "Box"}]
#   default_uom            = "Box"                        # Default UOM radio; Primary when not set
#
# The values live in backend/Config.py → Inventory Setup (with group_name, inventory_type, fields, ids).
# update_group (run_update_group) opens the saved group named group_name,
# makes it match the same keys, clicks Update and verifies every value again.


# ---------------------------
# Select Inventory Type
# ---------------------------
def select_inventory_type(page, Config, inventory_type):
    title = page.locator(
        ".inventory-title",
        has_text=re.compile(rf"^\s*{re.escape(inventory_type)}\s*$", re.I),
    )
    card = page.locator("button.inventory-type-card").filter(has=title)
    # The Edit page opens with the saved type already selected
    if not re.search(r"\bactive\b", card.get_attribute("class") or ""):
        expect(card, f"Inventory type cannot be changed to {inventory_type}").to_be_enabled()
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

    options = panel.locator("li[role='option']")
    options.first.wait_for()
    option = panel.get_by_role("option", name=option_text, exact=True)
    if not option.count():
        # Lists differ per environment (e.g. accounts); say what is available instead of timing out
        available = sorted({name.strip() for name in options.all_inner_texts()})
        page.keyboard.press("Escape")
        raise ValueError(f"'{option_text}' is not an option here. Available: {available}")
    # Some lists repeat a name (e.g. accounts); take the first
    option.first.click()
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

            # Saved IDs (Edit page) are already there; only add the missing ones
            if not page.locator(f"input[formcontrolname='id{index+1}Name']").count():
                # Each ID column can show its own "+Add ID" link; use the newest one
                add_btn = page.locator(
                    "app-add-edit-item-group button.link-name", has_text="Add ID"
                ).last
                add_btn.click()

            page.wait_for_selector(
                f"input[formcontrolname='id{index+1}Name']"
            )

def add_field_types(page,field_types):
    # Field 1 is the default "Bar Code". On the Edit page the saved fields are
    # reused in order, missing ones added and leftovers removed.
    dialog = barcode_dialog(page)
    dropdowns = dialog.locator("p-dropdown[formcontrolname='key']")

    for index, field_type in enumerate(field_types, start=2):
        if index <= dropdowns.count():
            select_dropdown(page, dropdowns.nth(index - 1), field_type)
            print(f" Field {index} set: {field_type}")
        else:
            add_field(page, index, field_type)

    while dropdowns.count() > len(field_types) + 1:
        count = dropdowns.count()
        dialog.locator("[formarrayname='BarcodeConfiguration'] > .card").last.locator("button.text-danger").click()
        try:
            expect(dropdowns).to_have_count(count - 1, timeout=2000)
        except AssertionError:
            # The field may only go after confirming
            page.locator(".p-confirm-dialog .p-confirm-dialog-accept").click()
            expect(dropdowns).to_have_count(count - 1)
        print(f" Field {count} removed")


# ---------------------------
# Open Item Groups / Add Item Group
# ---------------------------
def open_item_groups(page):
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


def open_add_item_group(page):
    open_item_groups(page)
    page.locator("button", has_text="Add Item Group").click()
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
def uom_rows(page, uom, level):
    # level is "Secondary" or "Tertiary"
    return uom.locator("div.uom-section").filter(
        has=page.locator(".uom-section__title", has_text=f"{level} UOMs")
    ).locator("tbody tr")


def fill_uom_row(page, row_locator, row, primary_name):
    # Each row reads: 1 <uom> = <quantity> <base>
    select_dropdown(page, row_locator.locator("p-dropdown[formcontrolname='uomStructureId']"), row["uom"])
    row_locator.locator("input[formcontrolname='quantity']").fill(str(row["quantity"]))
    base = row.get("base") or primary_name
    select_dropdown(page, row_locator.locator("p-dropdown[formcontrolname='baseUomStructureId']"), base)
    return base


def set_uom_rows(page, uom, level, rows, primary_name):
    # Rows already on the page (edit page) are reused in order, missing ones added, leftovers removed
    section_rows = uom_rows(page, uom, level)

    for index, row in enumerate(rows):
        if index >= section_rows.count():
            uom.locator("button.btn-add-row", has_text=f"Add {level} UOM").click()
            expect(section_rows).to_have_count(index + 1)
        base = fill_uom_row(page, section_rows.nth(index), row, primary_name)
        print(f" {level} UOM → 1 {row['uom']} = {row['quantity']} {base}")

    while section_rows.count() > len(rows):
        count = section_rows.count()
        section_rows.last.locator("button.uom-delete-btn").click()
        try:
            expect(section_rows).to_have_count(count - 1, timeout=2000)
        except AssertionError:
            # The row may only go after confirming
            page.locator(".p-confirm-dialog .p-confirm-dialog-accept").click()
            expect(section_rows).to_have_count(count - 1)
        print(f" {level} UOM row {count} removed")


def set_default_uom(page, uom, name):
    label = page.locator(
        "p-dropdown[formcontrolname='uomStructureId'] span[role='combobox']",
        has_text=re.compile(rf"^\s*{re.escape(name)}\s*$"),
    )
    row = uom.locator(".uom-picker-row, tbody tr").filter(has=label)
    expect(row, f"Default UOM is not one of the configured UOMs: {name}").to_have_count(1)
    row.locator("p-radiobutton .p-radiobutton-box").click()
    expect(row.locator("p-radiobutton input[type='radio']")).to_be_checked()
    print(f" Default UOM → {name}")


def configure_uom(page, Config):
    open_tab(page, "UOM Conversions")

    enabled = bool(Config.enable_uom_conversions)
    uom = page.locator("app-add-edit-item-group .tab-panel:visible app-uom-conversions")
    switch = uom.locator("p-inputswitch[formcontrolname='enabled']")
    switch_input = switch.locator("input[role='switch']")
    if switch_input.is_checked() != enabled:
        switch.locator(".p-inputswitch-slider").click()
    expect(switch_input).to_be_checked(checked=enabled)

    if not enabled:
        expect(uom.locator(".uom-disabled-banner")).to_be_visible()
        skipped = [key for key in ("primary_uom", "uom_value_type", "secondary_uoms", "tertiary_uoms", "default_uom")
                   if getattr(Config, key, None)]
        print(" UOM conversions → off" + (f" (skipped {', '.join(skipped)})" if skipped else ""))
        return
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

    primary_name = primary_uom or primary.locator("span[role='combobox']").inner_text().strip()
    set_uom_rows(page, uom, "Secondary", getattr(Config, "secondary_uoms", None) or [], primary_name)
    set_uom_rows(page, uom, "Tertiary", getattr(Config, "tertiary_uoms", None) or [], primary_name)

    default_uom = getattr(Config, "default_uom", None)
    if default_uom:
        set_default_uom(page, uom, default_uom)

    # Save stays enabled when a UOM row is invalid (e.g. quantity 0), so check the rows here
    invalid = uom.locator("[formcontrolname].ng-invalid")
    if invalid.count():
        names = invalid.evaluate_all("els => els.map(e => e.getAttribute('formcontrolname'))")
        raise AssertionError(f"UOM Conversions has invalid fields: {names}")


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


def search_group(page, group_name):
    search = page.locator("#groupSearchInput")
    search.fill(group_name)
    search.press("Enter")
    expect(page.get_by_text(group_name, exact=True).first).to_be_visible(timeout=15000)


def save_group(page, group_name):
    # The submit button reads "Save" on the Add page and "Update" on the Edit page
    form = page.locator("app-add-edit-item-group")
    save = form.locator("div.form-footer button[type='submit']")
    try:
        expect(save).to_be_enabled(timeout=10000)
    except AssertionError:
        raise AssertionError(f"Save is still disabled; invalid fields: {invalid_fields(page)}") from None

    label = save.inner_text().strip()
    save.click()
    print(f"click {label}")

    # Update first asks "Are you sure you want to update this group?" (Cancel / Ok)
    if label == "Update":
        confirm = page.locator(".p-confirm-dialog")
        confirm.wait_for(state="visible", timeout=10000)
        message = confirm.locator(".p-confirm-dialog-message").inner_text().strip()
        if not re.search(r"\bupdate\b", message, re.I):
            raise AssertionError(f"Unexpected confirmation after Update: {message!r}")
        confirm.locator(".p-confirm-dialog-accept").click()
        confirm.wait_for(state="hidden")
        print(f" Confirm: {message} → Ok")

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

    search_group(page, group_name)
    print(f"Item Group '{group_name}' listed")


# ---------------------------
# Verify Saved Values
# ---------------------------
def exact_text(text):
    return re.compile(rf"^\s*{re.escape(str(text))}\s*$")


def number_value(quantity):
    # A saved quantity may come back with decimals, e.g. 10 -> "10.00"
    text = re.escape(str(quantity))
    return re.compile(rf"^\s*{text}{'0*' if '.' in str(quantity) else r'(\.0*)?'}\s*$")


def soft_check(problems, label, expected, assertion):
    # Record a mismatch and keep going, so one run reports every wrong value
    try:
        assertion()
    except AssertionError as e:
        actual = next((line.strip() for line in str(e).splitlines() if line.startswith("Actual value")), "")
        problems.append(f"{label}: expected {expected!r} ({actual})")
        print(f" ✗ {label}: expected {expected!r} ({actual})")
    else:
        print(f" ✓ {label}: {expected}")


def open_saved_group(page, group_name):
    # save_group / search_group leave the Item Groups list filtered to this group
    link = page.locator("button.group-link", has_text=exact_text(group_name))
    link.wait_for(state="visible")
    # The saved UOM rows come in their own request; wait for it so nothing edits or checks them too early
    try:
        with page.expect_response(lambda r: "/uomconversion/group/" in r.url, timeout=15000):
            link.click()
    except PWTimeout:
        pass
    expect(page.locator("app-add-edit-item-group a.cad-crumb-here")).to_have_text(exact_text("Edit Item Group"))
    expect(page.locator("input[formcontrolname='groupName']")).to_have_value(group_name, timeout=15000)
    print(f"Opened '{group_name}'")


def verify_uom(page, Config, problems):
    open_tab(page, "UOM Conversions")
    enabled = bool(Config.enable_uom_conversions)
    uom = page.locator("app-add-edit-item-group .tab-panel:visible app-uom-conversions")
    switch_input = uom.locator("p-inputswitch[formcontrolname='enabled'] input[role='switch']")
    soft_check(problems, "UOM conversions", "on" if enabled else "off",
               lambda: expect(switch_input).to_be_checked(checked=enabled))
    if not enabled:
        return

    combo = "p-dropdown[formcontrolname='{}'] span[role='combobox']"
    primary = uom.locator(".uom-picker-row " + combo.format("uomStructureId"))
    primary_uom = getattr(Config, "primary_uom", None)
    if primary_uom:
        soft_check(problems, "Primary UOM", primary_uom, lambda: expect(primary).to_have_text(primary_uom))
    value_type = getattr(Config, "uom_value_type", None)
    if value_type:
        label = uom.locator(".uom-picker-row " + combo.format("valueType"))
        soft_check(problems, "UOM value type", value_type, lambda: expect(label).to_have_text(value_type))

    primary_name = primary_uom or primary.inner_text().strip()
    for level, key in (("Secondary", "secondary_uoms"), ("Tertiary", "tertiary_uoms")):
        expected_rows = getattr(Config, key, None) or []
        rows = uom_rows(page, uom, level)
        soft_check(problems, f"{level} UOM rows", len(expected_rows),
                   lambda rows=rows, count=len(expected_rows): expect(rows).to_have_count(count))

        for index, row in enumerate(expected_rows[:rows.count()]):
            saved = rows.nth(index)
            base = row.get("base") or primary_name

            def check_row(saved=saved, row=row, base=base):
                expect(saved.locator(combo.format("uomStructureId"))).to_have_text(row["uom"])
                expect(saved.locator("input[formcontrolname='quantity']")).to_have_value(number_value(row["quantity"]))
                expect(saved.locator(combo.format("baseUomStructureId"))).to_have_text(base)

            soft_check(problems, f"{level} UOM {index + 1}", f"1 {row['uom']} = {row['quantity']} {base}", check_row)

    default = getattr(Config, "default_uom", None) or primary_name
    default_row = uom.locator(".uom-picker-row, tbody tr").filter(
        has=page.locator(combo.format("uomStructureId"), has_text=exact_text(default))
    )
    soft_check(problems, "Default UOM", default,
               lambda: expect(default_row.locator("p-radiobutton input[type='radio']")).to_be_checked())


def verify_group(page, Config):
    open_saved_group(page, Config.group_name)
    print(" Verifying saved values")
    problems = []

    # General
    card = page.locator("button.inventory-type-card").filter(
        has=page.locator(".inventory-title", has_text=exact_text(Config.inventory_type))
    )
    soft_check(problems, "Inventory type", Config.inventory_type,
               lambda: expect(card).to_have_class(re.compile(r"\bactive\b")))
    if Config.inventory_type == "Serialized":
        for index, id_name in enumerate(Config.ids, start=1):
            field = page.locator(f"input[formcontrolname='id{index}Name']")
            soft_check(problems, f"ID {index} name", id_name,
                       lambda field=field, id_name=id_name: expect(field).to_have_value(id_name))

    # Barcode fields (Field 1 is the default "Bar Code"); close with X so nothing changes
    page.locator("input[placeholder='Barcode']").click()
    dialog = barcode_dialog(page)
    dialog.wait_for(state="visible")
    expected_fields = ["Bar Code", *Config.fields]
    labels = dialog.locator("p-dropdown[formcontrolname='key'] span[role='combobox']")
    soft_check(problems, "Barcode fields", expected_fields, lambda: expect(labels).to_have_text(expected_fields))
    dialog.locator(".p-dialog-header-close").click()
    dialog.wait_for(state="hidden")

    # Accounting
    if any(getattr(Config, key, None) for key in ("accounting_mode", "costing_method", "accounting_accounts")):
        open_tab(page, "Accounting")
        method = getattr(Config, "costing_method", None)
        if method:
            method_card = page.locator("button.costing-method-card").filter(
                has=page.locator(".costing-method-title", has_text=re.compile(rf"^\s*{re.escape(method)}\b", re.I))
            )
            soft_check(problems, "Costing method", method,
                       lambda: expect(method_card).to_have_class(re.compile(r"\bactive\b")))
        mode = getattr(Config, "accounting_mode", None) or "Basic Accounting Mode"
        toggle = page.locator("button.accounting-mode-toggle", has_text=mode)
        soft_check(problems, "Accounting mode", mode, lambda: expect(toggle).to_have_class(re.compile(r"\bactive\b")))
        block = page.locator("div.accounting-mode-block").filter(has=toggle)
        for control, account in (getattr(Config, "accounting_accounts", None) or {}).items():
            label = block.locator(f"p-dropdown[formcontrolname='{control}'] span[role='combobox']")
            soft_check(problems, control, account,
                       lambda label=label, account=account: expect(label).to_have_text(account))

    # Advanced
    toggles = getattr(Config, "advanced_toggles", None)
    if toggles:
        open_tab(page, "Advanced")
        for name, enabled in toggles.items():
            checkbox = page.locator(f"app-add-edit-item-group label.advanced-toggle input[formcontrolname='{name}']")
            soft_check(problems, name, "on" if enabled else "off",
                       lambda checkbox=checkbox, enabled=enabled: expect(checkbox).to_be_checked(checked=enabled))

    # UOM Conversions
    if getattr(Config, "enable_uom_conversions", None) is not None:
        verify_uom(page, Config, problems)

    # Leave the edit page without saving anything
    page.locator("app-add-edit-item-group div.form-footer button", has_text="Back").click()

    if problems:
        raise AssertionError(f"Item Group '{Config.group_name}' saved with wrong values: " + "; ".join(problems))
    print(f"Item Group '{Config.group_name}' verified")


# ---------------------------
# Automation Logic
# ---------------------------
def apply_group_settings(page, Config):
    # Shared by create_group (Add page) and update_group (Edit page)
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

    if getattr(Config, "enable_uom_conversions", None) is not None:
        configure_uom(page, Config)
        page.wait_for_timeout(1000)


def create_group(page, Config):
    open_add_item_group(page)
    page.wait_for_timeout(1000)

    apply_group_settings(page, Config)

    save_group(page, Config.group_name)

    verify_group(page, Config)

    # Verify Dropdown
    #select_item_group(page, Config.group_name)


def update_group(page, Config):
    # Open the saved group named group_name, make it match Config, Update, then verify
    print(f"Updating '{Config.group_name}' to match Config")
    open_item_groups(page)
    search_group(page, Config.group_name)
    open_saved_group(page, Config.group_name)

    apply_group_settings(page, Config)

    save_group(page, Config.group_name)

    verify_group(page, Config)
