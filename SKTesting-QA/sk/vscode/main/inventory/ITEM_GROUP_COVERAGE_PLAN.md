# Stockount Item Groups — Coverage Plan

**Automation module:** `inventory/create_group.py`  
**Source:** User-provided Angular/PrimeNG DOM and existing `Inventory.py` workflow.  
**Scope:** General, Accounting, Advanced, Label Configuration, UOM Conversions, cross-tab persistence, save/navigation, failure handling and responsive/permission scenarios.

## Current implementation

The `inventory/create_group.py` module contains reusable Playwright helpers for tab navigation, field selection, accounting mode, Advanced checkboxes, UOM enablement, adding UOM rows, preview state, disabled controls, cross-tab value persistence, barcode configuration, and save submission.

The original entry point remains:

```python
from inventory.create_group import create_group

create_group(page, Config)
```

Useful optional `Config` attributes:
- `accounting_mode = "Basic Accounting Mode"` or `"Inventory Accounting Mode"`
- `costing_method = "Weighted Average"` (FIFO/LIFO are disabled in the supplied DOM)
- `accounting_accounts = {"SaleAccountId": "Sales Revenue", "PurchaseAccountId": "Purchase Expenses"}`; provide only fields applicable to the chosen mode and existing account labels
- `advanced_toggles = {"AllowDiscount": True, "EditSalePrice": False}`; keys must match the actual formcontrolname values in the supplied DOM
- `label_fields = {"<confirmed-formcontrolname>": "<value>"}`; use only after inspecting Label Configuration with `inspect_label_configuration_controls(page)`
- `enable_uom_conversions = True`
- `primary_uom = "Bale"` (must exist in the active company)
- `uom_value_type = "Integer only"` (must match an available option)
- `fields = ["Item Code", "Item Name"]` for barcode configuration
- `ids = ["Serial Number", "IMEI", "Barcode"]` when inventory type is Serialized

Don't hardcode tenant-dependent account or UOM IDs. Select visible option labels and verify what the UI displays. The app's success toast/notification should be asserted according to the actual behavior returned by `detect_feedback`; a click alone is not proof of save success.

## Test matrix — 28 planned test cases

| TC ID | Tab / Scope | Scenario | Priority | Implementation / verification |
|---|---|---|---|---|
| IG_TC_001 | General | Verify the five tab labels render and tab navigation works | High | `assert_item_group_tabs(page)`; `open_item_group_tab(page, tab_name)` |
| IG_TC_002 | General | Required field validation prevents incomplete creation | Critical | Leave required fields blank; assert field-level validation and disabled/blocked Save according to observed UX |
| IG_TC_003 | General | Create valid Unit, Batch and Serialized groups | Critical | `open_add_item_group`, `fill_group_name`, `select_inventory_type`, barcode helper, save and verify persisted row |
| IG_TC_004 | General | Duplicate Item Group name is handled clearly | High | Create once, submit same name again; assert duplicate validation and no duplicate record |
| IG_TC_005 | General | Maximum length, whitespace-only name, invalid characters and trimming | Medium | Boundary data-driven test; limits/allowed characters must come from product requirements, not inferred from DOM |
| IG_TC_006 | Accounting | Verify Accounting fields and costing method cards | High | Open Accounting; assert Costing Method and mode-specific dropdowns are visible |
| IG_TC_007 | Accounting | Verify dropdown option selection | High | `select_prime_dropdown(page, form_control_name, option_name)`; test SaleAccountId, PurchaseAccountId, StockAdjId, StockTransferId when enabled |
| IG_TC_008 | Accounting | Verify required account fields, if required by product rules | High | Test empty and selected values; exact requiredness must be confirmed from form validation/business rules |
| IG_TC_009 | Accounting | Saved accounting configuration persists after reopening | High | Select supported values, save, reopen the same group and compare visible selections |
| IG_TC_010 | Advanced | Verify fields and default values | High | Assert AllowDiscount, EditSalePrice, ChangeInvoiceDate, AllowNonTaxable, DNBeforeInvoice, GRNBeforeInvoice, DNWithInvoice, GRNWithInvoice states against approved defaults |
| IG_TC_011 | Advanced | Verify available configuration toggles can be changed ON/OFF | High | `set_checkbox(page, form_control_name, enabled)`; assert each value before/after save |
| IG_TC_012 | Advanced | Verify dependent fields and disabled features | High | Verify dependencies for transaction toggles; `assert_disabled_advanced_options(page)` checks the two disabled feature controls in supplied DOM |
| IG_TC_013 | Label Configuration | Verify tab renders the expected label configuration UI | High | Open tab and capture current controls; exact assertions pending Label Configuration DOM |
| IG_TC_014 | Label Configuration | Verify label fields, configuration validation and add/remove behavior | High | Implement after obtaining the rendered tab DOM and expected business rules; do not reuse barcode selectors unless markup confirms they are shared |
| IG_TC_015 | Label Configuration | Verify saved label settings persist after reopening | High | Configure, save, reopen group and compare labels after DOM/requirements are available |
| IG_TC_016 | UOM Conversions | Verify Enable UOM Conversions switch ON/OFF | High | `set_uom_conversions_enabled(page, True/False)`; assert switch state and disabled banner |
| IG_TC_017 | UOM Conversions | Verify Primary UOM and Value Type dropdown selection | High | `select_prime_dropdown(page, "uomStructureId", "...", component="app-uom-conversions")`; repeat for `valueType` |
| IG_TC_018 | UOM Conversions | Add Secondary and Tertiary UOM rows | High | `add_secondary_uom(page)`, `add_tertiary_uom(page)`; assert new rows/fields render before configuring them |
| IG_TC_019 | UOM Conversions | Verify default UOM choice and conversion validation | High | Assert one default radio is selected; verify invalid/missing/non-positive conversion values once row DOM and business rules are known |
| IG_TC_020 | UOM Conversions | Verify preview reflects configured conversion rows | Medium | `assert_uom_preview_empty(page)` for initial state; after configuration assert preview text and ratio using actual rendered output |
| IG_TC_021 | All tabs | Switching tabs must retain entered unsaved data | Critical | `assert_tab_switch_preserves_value(page, source_tab, target_tab, selector, value)`; extend to form controls on each tab |
| IG_TC_022 | All tabs | Save valid configuration across tabs | Critical | Configure valid values in all tabs, assert Save enabled, submit and assert app success signal plus created record |
| IG_TC_023 | All tabs | Saved configuration persists after reopening | Critical | Reopen newly created group and compare all configured General, Accounting, Advanced, Label and UOM settings |
| IG_TC_024 | All tabs | Invalid configuration blocks submission | Critical | Create one invalid condition per relevant control; assert validation and absence of a successful create response/record |
| IG_TC_025 | All tabs | Back navigation and unsaved-change handling | Medium | Change a field, click Back; verify confirmation/discard/preserve behavior against approved UX |
| IG_TC_026 | All tabs | Save API/server failure is surfaced and data is handled safely | High | Simulate a failed save response via Playwright route/API mocking; assert error UI, no false-success toast and recoverable inputs |
| IG_TC_027 | All tabs | Responsive/mobile layout | High | Use mobile viewport; verify tabs remain usable, no clipped controls, dropdown overlays, Save/Back accessibility and page scrolling |
| IG_TC_028 | All tabs | Create/edit permissions | High | Test permitted and restricted roles; assert controls/route behavior and server-side denial, not only hidden buttons |

## DOM-grounded selectors

These selectors come directly from the supplied markup and should be preferred over Angular-generated IDs such as `pn_id_104` or `_ngcontent-...`.

| Element | Locator |
|---|---|
| Item Group tab | `button.item-group-tab` + exact visible tab name |
| Group name | `input[formcontrolname='groupName']` |
| Advanced native toggles | `input[type='checkbox'][formcontrolname='AllowDiscount']` (substitute actual form control name) |
| Costing method card | `button.costing-method-card` + visible method name |
| Accounting dropdown | `p-dropdown[formcontrolname='SaleAccountId']` (substitute actual form control name) |
| UOM enable switch | `app-uom-conversions p-inputswitch[formcontrolname='enabled']` |
| Primary UOM dropdown | `app-uom-conversions p-dropdown[formcontrolname='uomStructureId']` |
| UOM Value Type dropdown | `app-uom-conversions p-dropdown[formcontrolname='valueType']` |
| Add Secondary UOM | Button with accessible name containing `Add Secondary UOM` |
| Add Tertiary UOM | Button with accessible name containing `Add Tertiary UOM` |
| UOM preview empty state | `.uom-preview-empty` |
| Save | `app-add-edit-item-group button[type='submit']` |
| Disabled negative-stock / low-stock controls | `.advanced-item` row located via corresponding image `alt`, then checkbox |

Avoid selectors tied to generated PrimeNG IDs, `_ngcontent` IDs, DOM order, or broad `nth()` unless the option list has been scoped to its intended dropdown panel.

## Important observations and gaps

1. The supplied DOM confirms FIFO and LIFO are disabled. The supplied Advanced DOM also shows Allow Negative Stock and Enable Low Stock Alert disabled. Tests should assert disabled state and must not force-click these controls.
2. UOM's native checkbox is visually hidden inside PrimeNG. Interact through the visible `.p-inputswitch-slider`, then assert the underlying checkbox state.
3. The current form DOM shows a disabled Save button while the overall form is invalid. Tests should assert the expected state after setting required General fields; never click Save with force to bypass validation.
4. Label Configuration's actual panel DOM is not included in the supplied snippet. Exact field selectors and validation expectations for IG_TC_013–015 remain open until that DOM and the requirements are supplied.
5. Accounting requirements are not fully specified by the DOM alone. Do not assume account fields are mandatory in both modes or that switching modes should persist all values without validating the business rule.
6. Cross-tab UI values, save success and persisted state require observable assertions. A button click is not a test pass.
7. The current helper module is committed, but it has not been executed against a live Stockount browser session from this conversation. Run it in your configured QA environment and refine any UI behavior that differs from the captured DOM.

## Suggested execution order

1. General happy path and mandatory validation.
2. Accounting fields and mode switching.
3. Advanced toggles and default states.
4. UOM disabled/enabled behavior, row creation and preview.
5. Cross-tab state retention, save/reopen persistence.
6. Duplicate/error handling, role permissions and mobile layout.
7. Label Configuration tests after DOM inspection.

Run the scenarios against a dedicated QA tenant with a unique group name per run. Clean up test records only through a supported UI/API flow and avoid running creation tests against production data.

## Reusable code-generation prompt

> You are extending the Stockount Playwright QA automation in Q-A Runner.
>
> Target file: `SKTesting-QA/sk/vscode/main/inventory/create_group.py`. Related entry point: `inventory/Inventory.py`. Use Python and Playwright sync API.
>
> Use the supplied DOM and the Item Groups coverage matrix in this document as the source of truth. Generate stable, reusable, DOM-grounded helpers and test functions for IG_TC_001–IG_TC_028. Keep the existing `create_group(page, Config)` entry point compatible with the current workflow.
>
> Requirements:
> - Use role-based locators, visible labels and Angular `formcontrolname` values where available. Do not depend on Angular-generated `_ngcontent` selectors or dynamic PrimeNG IDs.
> - Scope each PrimeNG option list to its matching dropdown panel. Wait for a real visible/hidden/state change instead of fixed sleeps.
> - Assert UI outcomes: current tab, field values, checked/unchecked state, disabled state, validation errors, success/error feedback and saved values after reopening.
> - Cover General, Accounting, Advanced, Label Configuration and UOM Conversions, plus tab switching, create/save, duplicate name, back navigation, server errors, roles and responsive layout.
> - Respect observed disabled controls: FIFO, LIFO, Allow Negative Stock and Enable Low Stock Alert must not be force-clicked. Test their disabled state.
> - For UOM conversions, use the visible PrimeNG switch slider to change state and assert the hidden native checkbox. Verify the disabled banner when UOM conversions are off.
> - Keep tenant-dependent account/UOM options configurable. Do not invent values, mandatory rules, ratio formulas, length limits or selectors absent from the supplied DOM.
> - Mark requirements that are unclear or whose DOM is missing as TODO/open questions instead of claiming coverage. Specifically, request the Label Configuration DOM before writing exact selectors for that tab.
> - Use descriptive test IDs matching the coverage matrix, isolated test data and cleanup. Preserve any existing login and feedback-handler conventions; do not hardcode credentials.
> - Return the complete changed file(s), the TC-to-function mapping, assumptions/open questions and exact command to run the tests. Do not report tests as passed unless they were actually executed.
