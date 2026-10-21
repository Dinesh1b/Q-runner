"""
Item Group creation and five-tab coverage helpers for Stockount.

Selectors are based on the DOM supplied for the Item Group page.
This module deliberately does not assume the missing Label Configuration DOM.
"""

from __future__ import annotations

import logging
import re
from typing import Iterable, Optional

from playwright.sync_api import Page, Locator, expect, TimeoutError as PWTimeout

log = logging.getLogger(__name__)

TAB_NAMES = (
    "General",
    "Accounting",
    "Advanced",
    "Label Configuration",
    "UOM Conversions",
)


def _tab(page: Page, name: str) -> Locator:
    """Resolve one Item Group tab by its visible title."""
    tab = page.locator("button.item-group-tab").filter(
        has=page.locator(".tab-title", has_text=re.compile(rf"^{re.escape(name)}$"))
    )
    expect(tab).to_have_count(1)
    return tab


def open_item_group_tab(page: Page, name: str) -> None:
    """Open a tab and assert that its button became active."""
    if name not in TAB_NAMES:
        raise ValueError(f"Unknown Item Group tab: {name!r}")
    target = _tab(page, name)
    target.scroll_into_view_if_needed()
    target.click()
    expect(target).to_have_class(re.compile(r"\bactive\b"))
    log.info("Opened Item Group tab: %s", name)


def assert_item_group_tabs(page: Page) -> None:
    """Validate the five visible tabs without relying on Angular-generated IDs."""
    tabs = page.locator("button.item-group-tab")
    expect(tabs).to_have_count(5)
    for name in TAB_NAMES:
        expect(_tab(page, name)).to_be_visible()


def _visible_tab_panel(page: Page) -> Locator:
    """Return the visible form tab panel (hidden panels are excluded)."""
    panels = page.locator("app-add-edit-item-group form > .tab-panel:visible")
    expect(panels).to_have_count(1)
    return panels


def select_inventory_type(page: Page, inventory_type: str) -> None:
    """Select Unit, Batch, or Serialized on the General tab."""
    allowed = {"Unit", "Batch", "Serialized"}
    if inventory_type not in allowed:
        raise ValueError(f"inventory_type must be one of {sorted(allowed)}")
    card = page.locator("button.inventory-type-card").filter(has_text=inventory_type)
    expect(card).to_be_visible()
    card.click()
    expect(card).to_have_class(re.compile(r"\bactive\b"))


def fill_group_name(page: Page, group_name: str) -> None:
    """Fill and verify the Item Group name field from the supplied DOM."""
    field = page.locator("input[formcontrolname='groupName']")
    expect(field).to_be_visible()
    field.fill(group_name)
    expect(field).to_have_value(group_name)


def set_checkbox(page: Page, form_control_name: str, enabled: bool) -> None:
    """Set a native checkbox by Angular formcontrolname and verify its state."""
    checkbox = page.locator(
        f"app-add-edit-item-group input[type='checkbox'][formcontrolname='{form_control_name}']"
    )
    expect(checkbox).to_have_count(1)
    expect(checkbox).to_be_enabled()
    if checkbox.is_checked() != enabled:
        checkbox.check() if enabled else checkbox.uncheck()
    expect(checkbox).to_be_checked() if enabled else expect(checkbox).not_to_be_checked()


def assert_advanced_toggle_state(
    page: Page, form_control_name: str, expected_enabled: bool
) -> None:
    """Assert the state of an Advanced native checkbox without changing it."""
    checkbox = page.locator(
        f"app-add-edit-item-group input[type='checkbox'][formcontrolname='{form_control_name}']"
    )
    expect(checkbox).to_have_count(1)
    if expected_enabled:
        expect(checkbox).to_be_enabled()
    else:
        expect(checkbox).to_be_disabled()


def select_prime_dropdown(
    page: Page,
    form_control_name: str,
    option_name: str,
    *,
    component: str = "app-add-edit-item-group",
) -> None:
    """
    Select a PrimeNG dropdown option scoped by its Angular form control.
    Works for the supplied UOM and accounting dropdown patterns.
    """
    dropdown = page.locator(
        f"{component} p-dropdown[formcontrolname='{form_control_name}']"
    )
    expect(dropdown).to_have_count(1)
    expect(dropdown).to_be_visible()
    expect(dropdown).to_have_class(re.compile(r"p-inputwrapper"))

    # This assertion intentionally fails if the feature is disabled in the UI.
    root = dropdown.locator(".p-dropdown")
    expect(root).not_to_have_class(re.compile(r"p-disabled"))

    label = dropdown.locator("span[role='combobox']")
    label.click()

    list_id = label.get_attribute("aria-controls")
    if list_id:
        panel = page.locator("div.p-dropdown-panel").filter(
            has=page.locator(f"#{list_id}")
        )
    else:
        panel = page.locator("div.p-dropdown-panel:visible").last

    panel.wait_for(state="visible", timeout=10_000)
    option = panel.get_by_role("option", name=option_name, exact=True)
    expect(option).to_be_visible()
    option.click()
    panel.wait_for(state="hidden")
    expect(label).to_contain_text(option_name)


def select_costing_method(page: Page, method: str) -> None:
    """Select an enabled costing method; disabled methods are not force-clicked."""
    if method not in {"Weighted Average", "FIFO", "LIFO"}:
        raise ValueError("method must be Weighted Average, FIFO, or LIFO")
    open_item_group_tab(page, "Accounting")
    card = page.locator("button.costing-method-card").filter(
        has_text=re.compile(rf"^{re.escape(method)}(?:\s|$)")
    )
    expect(card).to_have_count(1)
    if method in {"FIFO", "LIFO"}:
        expect(card).to_be_disabled()
        raise ValueError(f"{method} is disabled in the supplied DOM; cannot select it.")
    expect(card).to_be_enabled()
    card.click()
    expect(card).to_have_class(re.compile(r"\bactive\b"))


def set_accounting_mode(page: Page, mode_name: str) -> None:
    """Toggle between accounting mode buttons using visible text."""
    if mode_name not in {"Basic Accounting Mode", "Inventory Accounting Mode"}:
        raise ValueError(f"Unsupported accounting mode: {mode_name!r}")
    open_item_group_tab(page, "Accounting")
    button = page.get_by_role("button", name=mode_name, exact=True)
    expect(button).to_be_visible()
    button.click()
    expect(button).to_have_class(re.compile(r"\bactive\b"))


def set_uom_conversions_enabled(page: Page, enabled: bool) -> None:
    """Set the PrimeNG Enable UOM Conversions switch."""
    open_item_group_tab(page, "UOM Conversions")
    switch = page.locator(
        "app-uom-conversions p-inputswitch[formcontrolname='enabled'] "
        "input[type='checkbox'][role='switch']"
    )
    expect(switch).to_be_visible()
    if switch.is_checked() != enabled:
        switch.click()
    expect(switch).to_be_checked() if enabled else expect(switch).not_to_be_checked()

    if enabled:
        expect(page.get_by_text("UOM conversions are disabled. Only the Primary UOM will be used.", exact=True)).to_have_count(0)
    else:
        expect(page.get_by_text(
            "UOM conversions are disabled. Only the Primary UOM will be used.",
            exact=True
        )).to_be_visible()


def add_secondary_uom(page: Page) -> None:
    open_item_group_tab(page, "UOM Conversions")
    button = page.get_by_role("button", name=re.compile(r"Add Secondary UOM", re.I))
    expect(button).to_be_visible()
    expect(button).to_be_enabled()
    button.click()


def add_tertiary_uom(page: Page) -> None:
    open_item_group_tab(page, "UOM Conversions")
    button = page.get_by_role("button", name=re.compile(r"Add Tertiary UOM", re.I))
    expect(button).to_be_visible()
    expect(button).to_be_enabled()
    button.click()


def assert_uom_preview_empty(page: Page) -> None:
    """Check the known initial preview state shown in the supplied DOM."""
    open_item_group_tab(page, "UOM Conversions")
    expect(page.locator(".uom-preview-empty")).to_have_text(
        "No Secondary or Tertiary UOMs configured yet."
    )


def assert_form_save_state(page: Page, should_be_enabled: bool) -> None:
    """Check Save state; the overall form may remain invalid until required fields are filled."""
    save = page.locator("app-add-edit-item-group button[type='submit']")
    expect(save).to_have_count(1)
    if should_be_enabled:
        expect(save).to_be_enabled()
    else:
        expect(save).to_be_disabled()


def save_item_group(page: Page) -> None:
    """Submit only when Save is enabled; then wait for user-visible feedback."""
    save = page.locator("app-add-edit-item-group button[type='submit']")
    expect(save).to_be_visible()
    expect(save).to_be_enabled()
    save.click()
    # Do not infer success from clicking. The caller should assert the actual toast,
    # navigation, or saved row according to the app's observed success behavior.
    log.info("Submitted Item Group form; verify the application's success signal.")


def assert_disabled_advanced_options(page: Page) -> None:
    """Verify feature flags visibly disabled in the supplied Advanced DOM."""
    open_item_group_tab(page, "Advanced")
    for image_alt in ("allowNegativeStock", "lowStockAlert"):
        row = page.locator(".advanced-item").filter(
            has=page.locator(f"img[alt='{image_alt}']")
        )
        expect(row).to_have_count(1)
        expect(row.locator("input[type='checkbox']")).to_be_disabled()


def assert_tab_switch_preserves_value(
    page: Page, source_tab: str, target_tab: str, selector: str, value: str
) -> None:
    """A focused cross-tab persistence check for any stable field selector."""
    open_item_group_tab(page, source_tab)
    field = page.locator(selector)
    expect(field).to_be_visible()
    field.fill(value)
    open_item_group_tab(page, target_tab)
    open_item_group_tab(page, source_tab)
    expect(field).to_have_value(value)


def open_add_item_group(page: Page) -> None:
    """Navigate to Add Item Group using semantic UI locators."""
    inventory_icon = page.locator("img[src*='Item_icon.svg']")
    expect(inventory_icon).to_be_visible()
    inventory_icon.click()
    page.get_by_role("button", name="Item Groups", exact=True).click()
    page.get_by_role("button", name=re.compile(r"Add Item Group", re.I)).click()
    expect(page.locator("input[formcontrolname='groupName']")).to_be_visible()
    assert_item_group_tabs(page)


def configure_barcode(page: Page, field_types: Iterable[str]) -> None:
    """Configure barcode fields using the supplied Barcode Configuration dialog."""
    page.locator("input[placeholder='Barcode']").click()
    for field_type in field_types:
        combos = page.locator("span[role='combobox'][aria-label='Select']")
        before = combos.count()
        page.get_by_role("button", name="Add Field", exact=True).click()
        expect(combos).to_have_count(before + 1)
        dropdown = combos.last
        dropdown.click()
        panel = page.locator("div.p-dropdown-panel:visible").last
        panel.wait_for(state="visible")
        panel.get_by_role("option", name=re.compile(re.escape(field_type), re.I)).click()

    dialog = page.locator("div.p-dialog").filter(has_text="Barcode Configuration")
    expect(dialog).to_be_visible()
    dialog.get_by_role("button", name="Ok", exact=True).click()
    expect(dialog).to_be_hidden()


def create_group(page: Page, Config) -> None:
    """
    Backwards-compatible create_group entry point.

    This preserves the current workflow's core behavior. The extra tab coverage
    helpers above can be called from targeted test functions using test data.
    Do not silently invent accounting, labels, or UOM settings that are absent
    from Config or from the supplied test specification.
    """
    open_add_item_group(page)
    fill_group_name(page, Config.group_name)
    select_inventory_type(page, Config.inventory_type)

    if Config.inventory_type == "Serialized":
        ids = getattr(Config, "ids", [])
        for index, id_name in enumerate(ids, start=1):
            field = page.locator(f"input[formcontrolname='id{index}Name']")
            expect(field).to_be_visible()
            field.fill(id_name)
            if index < len(ids):
                page.get_by_role("button", name=re.compile(r"Add ID", re.I)).click()
                expect(page.locator(f"input[formcontrolname='id{index + 1}Name']")).to_be_visible()

    configure_barcode(page, getattr(Config, "fields", []))

    # Optional test configuration can provide these explicitly. Avoid guessing
    # account IDs or UOM labels because options depend on the current company.
    if getattr(Config, "enable_uom_conversions", False):
        set_uom_conversions_enabled(page, True)
        uom_name = getattr(Config, "primary_uom", None)
        if uom_name:
            select_prime_dropdown(page, "uomStructureId", uom_name, component="app-uom-conversions")
        value_type = getattr(Config, "uom_value_type", None)
        if value_type:
            select_prime_dropdown(page, "valueType", value_type, component="app-uom-conversions")

    save_item_group(page)
