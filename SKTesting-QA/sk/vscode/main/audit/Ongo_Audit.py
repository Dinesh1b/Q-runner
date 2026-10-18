import sys
import time
import os
import pandas as pd
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright
from login.popup_handler import detect_feedback
from login.logger_setup import mirrored_print
import pyautogui
# --------------------------------------------------------------
# GLOBAL SPEED CONTROL
# --------------------------------------------------------------
SLEEP_TIME = 1

def Ongo_Audit(page, Config):
    # --------------------------------------------------------------
    # UTILITIES
    # --------------------------------------------------------------
    def wait_for_overlay_to_disappear(page):
        for selector in [
            ".p-dialog-mask",
            ".p-component-overlay",
            ".cdk-overlay-backdrop"
        ]:
            try:
                page.wait_for_selector(selector, state="detached", timeout=2000)
            except PlaywrightTimeoutError:
                pass

    def is_already_mapped(dropdown_locator) -> bool:
        try:
            label = dropdown_locator.locator(
                "span.p-dropdown-label:not(.p-placeholder)"
            )
            return label.count() > 0 and label.first.inner_text().strip() != ""
        except:
            return False

    # --------------------------------------------------------------
    # DROPDOWN OPTION SELECTOR
    # --------------------------------------------------------------
    def select_option_for_dropdown_locator(page, dropdown_locator, option_text):
        dropdown_locator.click()
        time.sleep(SLEEP_TIME)

        option_text_norm = option_text.strip().lower()
        items = page.locator("li.p-dropdown-item")

        for i in range(items.count()):
            item = items.nth(i)
            if not item.is_visible():
                continue

            text = item.inner_text().strip().lower()
            if text == option_text_norm:
                item.scroll_into_view_if_needed()
                item.click(force=True)
                time.sleep(SLEEP_TIME)
                return True

        return False
    def select_navigation_option(page, option_name: str):
        """
        option_name: one of 'Stock Audit', 'Audit Summary', 'Settings'
        """
        page.wait_for_selector("div[role='dialog'][aria-labelledby='auditNavTitle']")

        card = page.locator(
            f"button.create-type-card:has(h6.create-type-card__title:text-is('{option_name}'))"
        )
        card.click()

        page.locator("button.create-type-btn--primary:has-text('Continue')").click()
    # --------------------------------------------------------------
    # WAIT FOR MAPPING ROWS
    # --------------------------------------------------------------
    def wait_for_mapping_rows(page, required_labels, timeout_ms=45000):
        deadline = time.time() + (timeout_ms / 1000)
        last_seen_labels = []

        row_container = page.locator("div.row-container").first
        left_col = row_container.locator("div.col-md-6").nth(0)
        labels = left_col.locator("div.label > label")

        while time.time() < deadline:
            wait_for_overlay_to_disappear(page)

            if row_container.count() > 0 and row_container.first.is_visible():
                current_labels = [
                    labels.nth(i).inner_text().strip()
                    for i in range(labels.count())
                    if labels.nth(i).inner_text().strip()
                ]

                if current_labels:
                    last_seen_labels = current_labels

                if all(label in current_labels for label in required_labels):
                    return current_labels

            page.wait_for_timeout(500)

        raise Exception(
            f"Header mapping rows did not load in time. "
            f"Required={required_labels}, seen={last_seen_labels}"
        )

    # --------------------------------------------------------------
    # SELECT SHEET (NEW)
    # --------------------------------------------------------------
    def select_sheet(page, preferred_sheet):
        selector = "p-dropdown[placeholder='Choose Sheet'], p-dropdown[ng-reflect-placeholder='Choose Sheet']"
        mirrored_print(f"[SHEET] Waiting for selection dropdown (preferred: {preferred_sheet})")
        
        try:
            # Wait a short time to see if the dropdown appears
            page.wait_for_selector(selector, timeout=8000)
            dropdown = page.locator(selector).first
            
            # Use existing helper to select the option
            ok = select_option_for_dropdown_locator(page, dropdown, preferred_sheet)
            if ok:
                mirrored_print(f"   Selected target sheet: {preferred_sheet}")
                time.sleep(SLEEP_TIME)
                return preferred_sheet
            else:
                mirrored_print(f"⚠ Preferred sheet '{preferred_sheet}' not found. Picking first available.")
                dropdown.click()
                time.sleep(SLEEP_TIME)
                first_opt = page.locator("li.p-dropdown-item").first
                if first_opt.count() > 0:
                    txt = first_opt.inner_text().strip()
                    first_opt.click()
                    mirrored_print(f"   Selected fallback sheet: {txt}")
                    time.sleep(SLEEP_TIME)
                    return txt
        except PlaywrightTimeoutError:
            mirrored_print("ℹ No sheet selection dropdown appeared (skipping step)")
            return None
        except Exception as e:
            mirrored_print(f"⚠ Sheet selection error: {str(e)}")
            return None
        return None

    # --------------------------------------------------------------
    # HEADER MAPPING + VERIFICATION
    # --------------------------------------------------------------
    def map_headers(page, mapping):
        row_container = page.locator("div.row-container").first
        left_col = row_container.locator("div.col-md-6").nth(0)
        right_col = row_container.locator("div.col-md-6").nth(1)

        labels = left_col.locator("div.label > label")
        dropdowns = right_col.locator("p-dropdown")

        label_texts = [
            labels.nth(i).inner_text().strip()
            for i in range(labels.count())
        ]

        mirrored_print(f"Found headers in UI: {label_texts}")

        all_ok = True

        for required_label, excel_header in mapping.items():
            wait_for_overlay_to_disappear(page)

            if required_label not in label_texts:
                mirrored_print(f" UI missing label: {required_label}")
                all_ok = False
                continue

            idx = label_texts.index(required_label)
            dropdown = dropdowns.nth(idx)

            if is_already_mapped(dropdown):
                mapped_value = dropdown.locator(
                    "span.p-dropdown-label"
                ).inner_text().strip()

                if mapped_value.lower() == excel_header.lower():
                    mirrored_print(f"✔ Verified: {required_label} → {mapped_value}")
                    continue
                else:
                    mirrored_print(
                        f"⚠ Mismatch: {required_label} → {mapped_value} "
                        f"(expected {excel_header})"
                    )

            ok = select_option_for_dropdown_locator(page, dropdown, excel_header)

            if not ok:
                mirrored_print(f" Failed to map {required_label}")
                all_ok = False
            else:
                mirrored_print(f"✔ Mapped {required_label} → {excel_header}")

        if not all_ok:
            raise Exception(" Header mapping verification FAILED")

        mirrored_print("   Header mapping & verification completed successfully")

    # --------------------------------------------------------------
    # SET CHECKBOX
    # --------------------------------------------------------------
    def set_checkbox(page, selector, should_be_checked):
        checkbox = page.wait_for_selector(selector)
        if should_be_checked and not checkbox.is_checked():
            checkbox.check(force=True)
        elif not should_be_checked and checkbox.is_checked():
            checkbox.uncheck(force=True)

    # --------------------------------------------------------------
    # SELECT BRANCH (PrimeNG p-dropdown via XPath)
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
        panel.locator("li.p-dropdown-item").get_by_text(branch_text, exact=True)
        option = panel.locator("li.p-dropdown-item", has_text=branch_text)
        if option.count() == 0:
            raise Exception(f" Branch not found: {branch_text}")

        option.first.click()
        panel.wait_for(state="hidden", timeout=30000)

        dropdown.locator(
            ".p-dropdown-label", has_text=branch_text
        ).wait_for(state="visible", timeout=30000)

    # --------------------------------------------------------------
    # SELECT AUDITORS
    # --------------------------------------------------------------
    def select_auditors(page, auditor_list):
        auditors = [a for a in auditor_list if a]
        if not auditors:
            return

        dropdown = page.locator("p-multiselect[formcontrolname='auditor']")
        dropdown.wait_for(state="visible")
        dropdown.locator(".p-multiselect-label").click()

        panel = page.locator("div.p-multiselect-panel").last
        panel.wait_for(state="visible")
        
        for auditor in auditors:
            search = panel.locator("input.p-multiselect-filter")
            if search.count() > 0:
                search.fill("")
                search.fill(auditor)
                page.wait_for_timeout(300)

            option = panel.locator("li.p-multiselect-item", has_text=auditor)
            if option.count() == 0:
                print(f"⚠️ Auditor not found, skipping: {auditor}")
                continue

            if "p-highlight" not in (option.first.get_attribute("class") or ""):
                option.first.click()
                page.wait_for_timeout(300)

        page.keyboard.press("Escape")
        panel.wait_for(state="hidden")

    # --------------------------------------------------------------
    # LOAD AUDITOR MAPPING FROM EXCEL SHEET
    # --------------------------------------------------------------
    def _read_auditor_mapping_df(Config):
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
                        "EXCEL_SHEET_AUDITOR_MAPPING is required for Audit Plan mapping. "
                        f"Available sheets: {', '.join(workbook.sheet_names)}"
                    )

            df = pd.read_excel(
                Config.EXCEL_PATH,
                sheet_name=sheet_name
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

            return df

    def load_auditor_mapping(Config):
            df = _read_auditor_mapping_df(Config)

            result = {}   # { auditor: { "categories": [], "storages": [] } }
            seen   = {}   # { auditor: { "categories": set, "storages": set } }

            for _, row in df.iterrows():
                auditor = str(row[Config.EXCEL_auditor_col]).strip()
                if not auditor or auditor.lower() == "nan":
                    continue

                if auditor not in result:
                    result[auditor] = {"categories": [], "storages": []}
                    seen[auditor]   = {"categories": set(), "storages": set()}

                # --- Category column ---
                cat_val = str(row.get(Config.EXCEL_category_col, "")).strip()
                if cat_val and cat_val.lower() != "nan":
                    for cat in cat_val.split(","):
                        cat = cat.strip()
                        if cat and cat.lower() not in seen[auditor]["categories"]:
                            result[auditor]["categories"].append(cat)
                            seen[auditor]["categories"].add(cat.lower())

                # --- Storage column ---
                stor_val = str(row.get(Config.EXCEL_storage_col, "")).strip()
                if stor_val and stor_val.lower() != "nan":
                    for stor in stor_val.split(","):
                        stor = stor.strip()
                        if stor and stor.lower() not in seen[auditor]["storages"]:
                            result[auditor]["storages"].append(stor)
                            seen[auditor]["storages"].add(stor.lower())

            return result

        # --------------------------------------------------------------
        # FIND EXACT AUDITOR ROW  (exact <td> match, not substring)
        # --------------------------------------------------------------
    def find_auditor_row(page, auditor_name):
                rows = page.locator("tr")
                for i in range(rows.count()):
                    row = rows.nth(i)
                    tds = row.locator("td")
                    for j in range(tds.count()):
                        if tds.nth(j).inner_text().strip() == auditor_name:
                            return row
                return None

    # --------------------------------------------------------------
    # OPEN MULTISELECT PANEL FOR A ROW
        # --------------------------------------------------------------
    def open_multiselect_panel(page, row):
            row.locator("div.p-multiselect").click()
            panel = page.locator("div.p-multiselect-panel").filter(
                has=page.locator(":visible")
            )
            panel.wait_for(state="visible")
            return panel

    # --------------------------------------------------------------
    # SELECT ITEMS IN AN OPEN MULTISELECT PANEL (idempotent)
    # --------------------------------------------------------------
    def select_items_in_panel(page, panel, items, auditor_name, item_type):
            for item_text in items:
                option = panel.locator("li.p-multiselect-item", has_text=item_text)

                if option.count() == 0:
                    print(
                        f"âš  {item_type} '{item_text}' not found for '{auditor_name}'"
                    )
                    continue

                cls = option.first.get_attribute("class") or ""
                if "p-highlight" not in cls:
                    option.first.click()
                    page.wait_for_timeout(300)
                else:
                    print(
                        f"âœ” Already selected: '{item_text}' for '{auditor_name}'"
                    )

            page.keyboard.press("Escape")
            page.wait_for_timeout(300)


    # --------------------------------------------------------------
    # APPLY AUDITOR ASSIGNMENTS
    # --------------------------------------------------------------
    def apply_auditor_assignments(page, mapping_type, Config):
        """Fixed: accepts Config; mapping key 'By Storage' → 'By Location' per UI."""
        if mapping_type == "Random":
            print("ℹ Mapping type is Random — no assignments needed")
            return

        auditor_map = load_auditor_mapping(Config)
        print(f"📋 Loaded auditor mapping: {auditor_map}")

        for auditor, data in auditor_map.items():

            if mapping_type == "By Category":
                items = data["categories"]
                item_type = "Category"
            elif mapping_type == "By Location":
                # UI label is "By Location"; excel col mapped via Config.EXCEL_storage_col
                items = data["storages"]
                item_type = "Location"
            else:
                raise ValueError(
                    f"Unknown AUDIT_MAPPING_TYPE: '{mapping_type}'. "
                    "Must be 'Random', 'By Category', or 'By Location'."
                )

            if not items:
                print(f"⚠ No {item_type} found for '{auditor}' in sheet")
                continue

            print(f"→ Assigning {item_type} {items} to '{auditor}'")
            row = find_auditor_row(page, auditor)
            if row is None:
                print(f" Row not found for auditor: '{auditor}'")
                continue

            panel = open_multiselect_panel(page, row)
            select_items_in_panel(page, panel, items, auditor, item_type)
    # --------------------------------------------------------------
    # TEST MAPPING AND SAVING
    # --------------------------------------------------------------
    def test_mapping_and_saving(page):

        mirrored_print("📥 Uploading primary file")
        time.sleep(SLEEP_TIME)
        page.set_input_files("input#formFileSm", Config.EXCEL_PATH)
        time.sleep(SLEEP_TIME)
        # ── NEW: Sheet selection ──────────────────────────────────────────
        # Mandatory if the workbook has multiple sheets or the app requires it
        pref_sheet = getattr(Config, 'oa_sheet', 'Data')
        time.sleep(SLEEP_TIME)
        select_sheet(page, pref_sheet)
        # ──────────────────────────────────────────────────────────────────

        page.wait_for_selector("div.row-container")
    # -----------------------------
    # First mapping attempt
    # -----------------------------
        wait_for_mapping_rows(page, list(Config.oa_mapping.keys()))

        map_headers(page, Config.oa_mapping)

        page.click("button:has-text('Map')")
        time.sleep(SLEEP_TIME)

        detect_feedback(page)
    
        #page.locator("button.swal2-confirm:has-text('OK')").click(timeout=3000)

        page.click("button:has-text('Save')")
        detect_feedback(page)
        page.mouse.click(200, 300)


    def click_photo_validation_type(page, photo_type: str, sample_size=None):
        """
        photo_type: "None", "Random", "Damaged"
        sample_size: required only when photo_type == "Random" (fills 'Enter Sample Size')
        """
        print(f"➡️ Select Photo Validation Type: {photo_type}")

        valid_types = ["None", "Random", "Damaged"]
        if photo_type not in valid_types:
            raise Exception(f"Invalid Photo Validation Type: {photo_type}. Valid: {valid_types}")

        # Open the dropdown
        dropdown = page.locator("p-dropdown[formcontrolname='selectedValidationType']")
        dropdown.locator(".p-dropdown-label").click()

        # Select the matching option — role-based locator is robust against the
        # dynamic pn_id_288 ids PrimeNG generates for the overlay/listbox
        page.get_by_role("option", name=photo_type, exact=True).click()

        # ── Sample Size only applies when "Random" is chosen ──
        if photo_type == "Random":
            if sample_size in (None, ""):
                raise Exception("❌ Photo Validation Type 'Random' requires a Sample Size value")

            size_input = page.locator("input[formcontrolname='validationSize']")
            size_input.wait_for(state="visible", timeout=8000)
            size_input.fill("")
            size_input.fill(str(sample_size))
            print(f"✔ Sample Size set to {sample_size}")
        else:
            print(f"ℹ️ No Sample Size needed for '{photo_type}'")


    # --------------------------------------------------------------
    # CLICK AUDIT ROW
    # --------------------------------------------------------------
    def click_audit(page, ap_audit_name):
        page.wait_for_load_state("networkidle")

        # Find and click the specific audit using ap_audit_name
        row = page.locator(
            f"table tbody tr:has(button.audit-name-link:has-text('{Config.ap_audit_name}'))"
        ).first
        row.locator("button.audit-name-link").first.click()
        print(f"   Opened audit: {Config.ap_audit_name}")

    # --------------------------------------------------------------
    # MAIN FLOW
    # Ongoing Audit only uses: oa_group_name, ap_audit_name, oa_excel_path
    # Credentials (oa_email / oa_password) and Excel column config
    # have moved to Auditor 1 SA (A_SA.py) — see asa_* fields.
    # --------------------------------------------------------------
    def setup_Audit(page):
        page.wait_for_selector("a[href='/home/audit']", state="visible")
        page.click("a[href='/home/audit']")
        time.sleep(SLEEP_TIME)

        select_branch(page, Config.Branch)
        print(f"   Branch selected: {Config.Branch}")
        time.sleep(SLEEP_TIME)

        click_audit(page, Config.ap_audit_name)
        
        detect_feedback(page)

        select_navigation_option(page, "Settings")
        time.sleep(SLEEP_TIME)

        print("   Opened audit settings")
        oa_aud1 = getattr(Config, "oa_Auditor1", None) or Config.Auditor1
        oa_aud2 = getattr(Config, "oa_Auditor2", None) or Config.Auditor2
        print(f"   select_auditors= {Config.oa_Auditor1}, {Config.oa_Auditor2}")

        select_auditors(page, [Config.oa_Auditor1, Config.oa_Auditor2])

        set_checkbox(page, "input[formcontrolname='IsDamageQty']",       Config.A_Checkboxes_Audit_Damaged)
        print(f"   Set IsDamageQty = {Config.A_Checkboxes_Audit_Damaged}")
        set_checkbox(
    page,
    "xpath=//label[normalize-space(text())='Enable Blind Count']/ancestor::div[contains(@class,'row')][1]//input[@type='checkbox']",
    Config.A_Checkboxes_BlindCount
)
        print(f"   Set BlindCount = {Config.A_Checkboxes_BlindCount}")
        set_checkbox(page, "input[formcontrolname='isGeoLocation']",     Config.A_Checkboxes_geo)
        print(f"   Set isGeoLocation = {Config.A_Checkboxes_geo}")
        click_photo_validation_type(page, Config.oa_photo_type, Config.oa_sample_size)
        time.sleep(SLEEP_TIME)

        page.click("button:has-text('Update')")
        detect_feedback(page)
        time.sleep(SLEEP_TIME)

        page.click("button:has-text('Import Stock Sheet')")
        test_mapping_and_saving(page)
        time.sleep(SLEEP_TIME)
                # "Random" â†’ nothing extra; "By Category"/"By Storage" ’ assign from sheet
        
        mapping_type = Config.AUDIT_MAPPING_TYPE
        page.locator("p-dropdown[formcontrolname='auditMappingType']").click()
        page.locator("li.p-dropdown-item", has_text=mapping_type).click()
        time.sleep(SLEEP_TIME)
        apply_auditor_assignments(page, mapping_type, Config) 
        
        time.sleep(SLEEP_TIME)

        page.click("button:has-text('Update')")
        detect_feedback(page)
        time.sleep(SLEEP_TIME)

    # --------------------------------------------------------------
    # ENTRY POINT
    # --------------------------------------------------------------
    setup_Audit(page)
