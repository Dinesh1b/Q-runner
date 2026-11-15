import sys
import os
from playwright.sync_api import sync_playwright

# --------------------------------------------------------------
# PATH SETUP
# --------------------------------------------------------------
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from login.login import login
from login.popup_handler import detect_feedback
from excel_logger import write_log
from login.timezone import timezone
from Audit_plan import create_audit
from audit_plan_update_ui import update_audit
from Ad_hoc_Audit import Ad_hoc_Audit
from Ongo_Audit import Ongo_Audit
from Auditor_1 import stock_audit
from Auditor_2 import stock_audit2
from A_audit_Summary import A_audit_Summary
from A_Recently_audit import A_Recently_Audit
from audit.finish_complete_flow import FinishFlow
from audit.settings_tests import run_settings_tests


# ======================================================
# CONFIG
# ======================================================

class Config:

    # ── Login & Environment ───────────────────────────────
    USE_CUSTOM_LOGIN = True
    company_name = "Test_TuddeCompany_16/10"
    if USE_CUSTOM_LOGIN:
        email    = "tuddefonugu-3882@yopmail.com"
        password = "12345678"
    else:
        email    = None
        password = None

    email2    = "vigelluppeutru-1233@yopmail.com"   # Auditor 2 credentials
    password2 = "2ugR20Bc"

    browsername  = "chrome"
    environments = "production"   # production, staging, development
    Branch       = "DE"

    # ── Audit Creation ────────────────────────────────────
    Audit_Owner   = "Test_Tudde"
    Auditor1      = "Test_Tudde"
    Auditor2      = "Vigellup B"          # user of email2
    Group_Name    = "QA_GRP_1112_2214"   # created by inventory/Inventory.py
    Audit_mode    = "Ad_hoc"             # "Ad_hoc" or "Audit_plan"
    Audit_Type    = "Complete Audit"     # Complete Count | Cycle Count | Complete Audit | Partial Audit | Investigation Audit
    SD_audit_type = "Dynamic"           # "Static" or "Dynamic"
    ap_audit_name = "QA_SUM_1113_21"
    frequency     = "daily"             # "daily" | "weekly" | "monthly" | "manual"
    Day_s         = 30
    Target__Day   = "Thursday"
    Target_Date   = "10/09/2026"

    A_Checkboxes_Audit_Damaged = True
    A_Checkboxes_geo           = False
    A_Checkboxes_BlindCount    = False
    photo_type    = "Random"
    sample_size   = 100
    CROSS_AUDIT_TYPE   = "Random Recheck"
    CROSS_Auditor_name = "Dinesh"

    AUDIT_MAPPING_TYPE          = "Random"           # "Random" | "By Category" | "By Storage"
    EXCEL_PATH                  = r"C:\Users\dines\3D Objects\main_qexcel.xlsx"
    EXCEL_SHEET_AUDITOR_MAPPING = "AUDITOR_MAPPING"
    EXCEL_auditor_col           = "Auditor"
    EXCEL_category_col          = "Category"
    EXCEL_storage_col           = "Storage"

    oa_audit_name    = ap_audit_name
    oa_excel_path    = EXCEL_PATH
    oa_Auditor1      = Auditor1
    oa_Auditor2      = Auditor2
    oa_photo_type    = "None"
    oa_sample_size   = 0
    oa_mapping       = {
        "Item Code":      "Item Code",
        "Stock Quantity": "Adjustmentqty",
    }
    WAIT_AFTER_ACTION = 300

    run_timezone            = False
    run_create_audit        = False
    run_update_audit        = False
    run_ui_validation       = False
    run_create_Ad_hoc_Audit = False
    run_setup_Audit         = False

    # ── Auditor 1 Stock Count ─────────────────────────────
    run_new_add_item = False
    ITEM_CODE1    = "ABC1123"
    ITEM_NAME1    = "Test Item"
    CATEGORY1     = "Gear"
    COST_PRICE1   = "100"
    SELL_PRICE1   = "100"
    LOCATION1     = "SA-A1"
    BARCODE1      = "123456789"
    UOM1          = "PCS"
    audited_qty1  = 10
    damaged_qty1  = 0

    EXCEL_SHEET_auditor_1 = "auditor_1"   # ITM0001 10, ITM0002 13 (+1 damaged), ITM0003 6, ITM0039 5
    EXCEL_LOCATION_COL1   = "locations"
    EXCEL_CODE_COL1       = "code"
    EXCEL_AUDITED_COL1    = "audited"
    EXCEL_DAMAGED_COL1    = "damaged"

    run_stock_audit  = False
    run_asv2_checks  = True    # after the counts: test page features + cross-check list / Count summary / Finish / Audit Summary

    # ── Auditor 2 Stock Count ─────────────────────────────
    run_new_add_item2 = False
    ITEM_CODE2    = "ABC1123"
    ITEM_NAME2    = "Test Item"
    CATEGORY2     = "Gear"
    COST_PRICE2   = "100"
    SELL_PRICE2   = "100"
    LOCATION2     = "SA-A1"
    BARCODE2      = "123456789"
    UOM2          = "PCS"
    audited_qty2  = 10
    damaged_qty2  = 0

    EXCEL_SHEET_auditor_2 = "auditor_2"
    EXCEL_LOCATION_COL2   = "locations"
    EXCEL_CODE_COL2       = "code"
    EXCEL_AUDITED_COL2    = "audited"
    EXCEL_DAMAGED_COL2    = "damaged"

    run_stock_audit2 = False

    # ── Finish → Complete (Steps 5–10) ────────────────────
    fc_auditor      = "Dinesh B"                   # recount assignee (Step 8)
    complete_choice = "Move to Not Found"          # Step 7: or "Keep as Unverified"
    fc_closure_note = "QA automated finish/complete run"
    EXCEL_SHEET_finish_flow = "finish_flow"

    run_finish_audit1      = False   # Step 5:  Auditor 1 → Finish audit > Audit Declaration
    run_finish_audit2      = False   # Step 6:  Auditor 2 → Finish audit > Audit Declaration
    run_complete_audit     = False   # Step 7:  Audit Summary > Complete Audit (3-step popup)
    run_resolution_actions = False   # Step 8:  Accept | Recount | Investigate per finish_flow
    run_recount            = False   # Step 9:  Recount sub-audit > review > approve
    run_resolution_summary = False   # Step 10: Resolution summary > Adjustment > Complete > Audit History

    # ── Audit Summary & Reports ───────────────────────────
    EXCEL_SHEET_as_table       = "as_table"
    
    summary_ui_validation      = True    # UI validation: fields, formulas, charts & live Excel export
    e2e_output_dir             = r"C:\Users\dines\3D Objects\QA_E2E"

    run_A_SA_table              = False
    run_A_audit_Summary         = False
    run_A_audit_Summary_history = True   # Post-completion: Audit History validation (UI + Excel + PDF)
    run_A_Recently_Audit        = False

    # ── Audit Settings Tests ──────────────────────────────
    settings_audit_name    = "QA_FC_1102_1907"
    settings_second_auditor = "Dinesh"

    run_settings_tests = False


# ======================================================
# MAIN EXECUTION
# ======================================================

if __name__ == "__main__":
    with sync_playwright() as p:

        browser, page = login(
            p,
            browser_name=Config.browsername,
            environment=Config.environments,
            email=Config.email,
            password=Config.password,
            company_name=Config.company_name,
        )

        # ── Audit Creation ────────────────────────────────
        if Config.Audit_mode == "Ad_hoc":
            if Config.run_create_Ad_hoc_Audit:
                Ad_hoc_Audit(page, Config)
            else:
                print("x create_Ad_hoc_Audit")
        elif Config.Audit_mode == "Audit_plan":
            if Config.run_timezone and Config.frequency.lower() != "manual":
                timezone(page)
            else:
                print("x timezone")
            if Config.run_create_audit:
                create_audit(page, Config)
            else:
                print("x create_audit")
            if Config.run_update_audit:
                update_audit(page, Config)
            else:
                print("x update_audit")
        else:
            print(f"x Invalid Audit_mode: {Config.Audit_mode}")

        if Config.run_setup_Audit:
            Ongo_Audit(page, Config)
        else:
            print("x setup_Audit")

        # ── Auditor 1 Stock Count ─────────────────────────
        if Config.run_stock_audit:
            stock_audit(page, Config)
        else:
            print("x stock_audit")

        # Steps 5–10 share state in one FinishFlow object
        finish_steps = ("run_finish_audit1", "run_finish_audit2", "run_complete_audit",
                        "run_resolution_actions", "run_recount", "run_resolution_summary")
        flow = FinishFlow(Config) if any(getattr(Config, f, False) for f in finish_steps) else None

        # ── Step 5: Auditor 1 → Finish > Audit Declaration ─
        if Config.run_finish_audit1:
            flow.finish_audit(page, Config, "Auditor 1")
        else:
            print("x Step 5 finish_audit (Auditor 1)")

        # ── Auditor 2 Stock Count ─────────────────────────
        switched = False
        if Config.run_stock_audit2:
            same_creds = (
                (Config.email or "") == (Config.email2 or "") and
                (Config.password or "") == (Config.password2 or "")
            )
            if not same_creds:
                browser.close()
                browser, page = login(
                    p,
                    browser_name=Config.browsername,
                    environment=Config.environments,
                    email=Config.email2,
                    password=Config.password2,
                    company_name=Config.company_name,
                )
                page.set_default_timeout(30000)
                switched = True

            stock_audit2(page, Config)

            # ── Step 6: Auditor 2 → Finish > Audit Declaration
            if Config.run_finish_audit2:
                flow.finish_audit(page, Config, "Auditor 2")
            else:
                print("x Step 6 finish_audit (Auditor 2)")
        else:
            print("x stock_audit2")
            if Config.run_finish_audit2:
                print("x Step 6 finish_audit (Auditor 2): run_stock_audit2 is False")

        # ── Back to Auditor 1 login for Steps 7–10 ───────
        if switched:
            browser.close()
            browser, page = login(
                p,
                browser_name=Config.browsername,
                environment=Config.environments,
                email=Config.email,
                password=Config.password,
                company_name=Config.company_name,
            )

        # ── Audit Summary & Reports ───────────────────────

        if Config.run_A_audit_Summary:
            A_audit_Summary(page, Config)
        else:
            print("x A_audit_Summary")

        if Config.run_A_Recently_Audit:
            A_Recently_Audit(page, Config)
        else:
            print("x A_Recently_Audit")

        # ── Step 7: Complete Audit (3-step popup) ─────────
        if Config.run_complete_audit:
            flow.complete_audit(page, Config)
        else:
            print("x Step 7 complete_audit")

        # ── Step 8: Resolution actions ────────────────────
        if Config.run_resolution_actions:
            flow.resolution_actions(page, Config)
        else:
            print("x Step 8 resolution_actions")

        # ── Step 9: Recount sub-audit ─────────────────────
        if Config.run_recount:
            flow.recount(page, Config)
        else:
            print("x Step 9 recount")

        # ── Step 10: Resolution summary → Audit History ───
        if Config.run_resolution_summary:
            flow.resolution_summary(page, Config)
        else:
            print("x Step 10 resolution_summary")

        if flow:
            flow.report(Config)

        # ── Post-Completion: History Validation (UI + Excel + PDF)
        if getattr(Config, "run_A_audit_Summary_history", False):
            print("\n" + "=" * 70)
            print(" AUDIT HISTORY POST-COMPLETION VALIDATION (UI + Excel + PDF)")
            print("=" * 70)
            A_audit_Summary(page, Config, is_history=True)

        # ── Audit Settings Tests ──────────────────────────
        if Config.run_settings_tests:
            run_settings_tests(page, Config)
        else:
            print("x settings_tests")

        browser.close()
