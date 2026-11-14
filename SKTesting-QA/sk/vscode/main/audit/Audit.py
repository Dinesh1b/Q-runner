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
from A_as_table import A_as_table
from A_audit_Summary import A_audit_Summary
from A_Recently_audit import A_Recently_Audit
from audit.finish_complete_flow import FinishFlow
from audit.settings_tests import run_settings_tests




# ======================================================
# CONFIG
# ======================================================

DRY_RUN = False
SEED = None
FAST_MODE = False



class Config:
    USE_CUSTOM_LOGIN = True  # Set to True to use custom login credentials
    company_name = "Test_TuddeCompany_16/10"
    if USE_CUSTOM_LOGIN:
        email = "tuddefonugu-3882@yopmail.com"
        password = "12345678"
    else:
        email = None
        password = None

    email2 = "vigelluppeutru-1233@yopmail.com"  # Auditor 2 credentials
    password2 = "2ugR20Bc"

    browsername = "chrome"
    environments = "production"  # production, staging, development
    Branch = "DE"

    Audit_Owner = "Test_Tudde"   #  user 
    Auditor1 = "Test_Tudde"
    Auditor2 = "Vigellup B"     #  user of email2 
    Group_Name = "QA_GRP_1112_2214"   # created by inventory/Inventory.py (backend/Config.py group_name)
    Audit_mode = "Ad_hoc"  # "Ad_hoc" or "Audit_plan"
    Audit_Type = "Complete Audit"  # Complete Count, Cycle Count, Complete Audit, Partial Audit, Investigation Audit
    SD_audit_type = "Dynamic"  # "Static" or "Dynamic"
    ap_audit_name = "QA_SUM_1113_21"
    frequency = "daily"  # "daily", "weekly", "monthly", "manual"
    Day_s = 30
    Target__Day = "Thursday"
    Target_Date = "10/09/2026"

    A_Checkboxes_Audit_Damaged = True
    A_Checkboxes_geo = False
    A_Checkboxes_BlindCount = False
    photo_type = "Random"
    sample_size = 100
    CROSS_AUDIT_TYPE = "Random Recheck"
    CROSS_Auditor_name = "Dinesh"
    run_timezone = False
    run_create_audit = False
    run_update_audit = False
    run_ui_validation = False  
    run_create_Ad_hoc_Audit = False
     
    
    # -------------------------------------------------------
    # AUDITOR_MAPPING_TYPE # "Random" | "By Category" | "By Storage" 
    # -------------------------------------------------------
    AUDIT_MAPPING_TYPE = "Random"  # "Random", "By Category", "By Storage"
    
    EXCEL_PATH = r"C:\Users\dines\3D Objects\main_qexcel.xlsx"
    EXCEL_SHEET_AUDITOR_MAPPING = "AUDITOR_MAPPING"
    EXCEL_auditor_col = "Auditor"
    EXCEL_category_col = "Category"
    EXCEL_storage_col = "Storage"


    oa_mapping = {
        "Item Code": "Item Code",
        "Stock Quantity": "Adjustmentqty",
    }
    
    
    run_setup_Audit = False
#=============================================================
    run_stock_audit = False
    run_asv2_checks = True   # after the counts: test page features + cross-check list / Count summary / Finish / Audit Summary
    #add item details for auditor 1
    run_new_add_item = False
    ITEM_CODE1 = "ABC1123"
    ITEM_NAME1 = "Test Item"
    CATEGORY1 = "Gear"
    COST_PRICE1 = "100"
    SELL_PRICE1 = "100"
    LOCATION1 = "SA-A1"
    BARCODE1 = "123456789"
    UOM1 = "PCS"    
    audited_qty1 = 10
    damaged_qty1 = 0
    


    #add count for auditor 1
    EXCEL_SHEET_auditor_1 = "auditor_1"   # ITM0001 10, ITM0002 13 (+1 damaged), ITM0003 6, ITM0039 5
    EXCEL_LOCATION_COL1 = "locations"
    EXCEL_CODE_COL1 = "code"
    EXCEL_AUDITED_COL1 = "audited"
    EXCEL_DAMAGED_COL1 = "damaged"
  #  run_A_SA = False

    #add item details for auditor 2
    run_new_add_item2 = False
    ITEM_CODE2 = "ABC1123"
    ITEM_NAME2 = "Test Item"
    CATEGORY2 = "Gear"
    COST_PRICE2 = "100"
    SELL_PRICE2 = "100"
    LOCATION2 = "SA-A1"
    BARCODE2 = "123456789"
    UOM2 = "PCS"    
    audited_qty2 = 10
    damaged_qty2 = 0
    


    #add count for auditor 2
    EXCEL_SHEET_auditor_2 = "auditor_2"
    EXCEL_LOCATION_COL2 = "locations"
    EXCEL_CODE_COL2 = "code"
    EXCEL_AUDITED_COL2 = "audited"
    EXCEL_DAMAGED_COL2 = "damaged"
    run_stock_audit2 = False

    # Shared / Base variables for auditors
    
    oa_audit_name = ap_audit_name
    WAIT_AFTER_ACTION = 300
    oa_excel_path = EXCEL_PATH  
    oa_Auditor2 = Auditor2
    oa_Auditor1 = Auditor1
    oa_photo_type = "None"
    oa_sample_size = 0
    # static auditor 1      run_S_SA = false


    # Report / Summary flags
    run_A_SA_table = False
    EXCEL_SHEET_as_table = "as_table"
    # Audit Summary checks on ap_audit_name (A_audit_Summary.py; flexible formula-based; Ongoing or History)
    run_A_audit_Summary = False
    summary_ui_validation = True             # UI validation: required fields, values, formulas, charts & live Excel export
    run_A_audit_Summary_history = True       # Post-completion: Audit History validation (UI + Excel + PDF)
    run_A_Recently_Audit = False
    EXCEL_SHEET_Recently_Audit = "Recently_Audit"

    # Finish → Complete on ap_audit_name, step by step (finish_complete_flow.py; finish_flow sheet:
    # declaration note + Accept / Recount / Investigate + recount qty + remarks per item). Step 10 closes the audit.
    run_finish_audit1 = False       # Step 5: after Auditor 1's count: Finish audit > Audit Declaration (finish_audit.py)
    run_finish_audit2 = False       # Step 6: after Auditor 2's count: Finish audit > Audit Declaration (finish_audit.py)
    run_complete_audit = False      # Step 7: Audit Summary > Complete Audit, 3-step popup (complete_audit_popup.py)
    run_resolution_actions = False  # Step 8: Accept | Recount | Investigate per finish_flow (resolution_actions.py)
    run_recount = False             # Step 9: Recount sub-audit > review > approve, only if Step 8 chose Recount (recount.py)
    run_resolution_summary = False  # Step 10: Resolution summary > Adjustment report > Complete Audit > Audit History (resolution_summary.py)
    fc_auditor = "Dinesh B"         # recount assignee (Step 8)
    complete_choice = "Move to Not Found"   # Step 7: Complete Audit popup: or "Keep as Unverified"
    fc_closure_note = "QA automated finish/complete run"
    EXCEL_SHEET_finish_flow = "finish_flow"

    # Report folder of the Audit Summary UI validation and the Audit Settings tests
    e2e_output_dir = r"C:\Users\dines\3D Objects\QA_E2E"

    # Audit Settings page test cases (TC-SET-xx); settings + stock sheet are restored afterwards
    run_settings_tests = False
    settings_audit_name = "QA_FC_1102_1907"
    settings_second_auditor = "Dinesh"
#=============================================================
if __name__ == "__main__":
    with sync_playwright() as p:
        browser, page = login(
            p,
            browser_name=Config.browsername,
            environment=Config.environments,
            email=Config.email,
            password=Config.password,
            company_name=Config.company_name
        )
        # Steps 5-10 (Finish → Complete) share their state in one FinishFlow
        finish_steps = ("run_finish_audit1", "run_finish_audit2", "run_complete_audit",
                        "run_resolution_actions", "run_recount", "run_resolution_summary")
        flow = FinishFlow(Config) if any(getattr(Config, f, False) for f in finish_steps) else None
        if Config.Audit_mode == "Ad_hoc":  #    Clean string comparison
            if Config.run_create_Ad_hoc_Audit:
                Ad_hoc_Audit(page, Config)
            else:
                print(" Adhoc audit skipped")
        elif Config.Audit_mode == "Audit_plan":
            if Config.run_timezone and Config.frequency.lower() != "manual":
                timezone(page)
            else:
                print("ℹ️ Skipping timezone")
            if Config.run_create_audit:
                create_audit(page, Config)
            else:
                print(" create audit skipped")
            if Config.run_update_audit:
                update_audit(page, Config)
            else:
                print(" update_audit skipped")
        else:
            print(f" Invalid Audit_mode: {Config.Audit_mode}")  #  Correct attribute name
        if Config.run_setup_Audit:
            Ongo_Audit(page, Config)
        else:
            print(" setup_Audit skipped")
        if Config.run_stock_audit:
            stock_audit(page, Config)
        else:
            print(" stock_audit skipped")
        # ── Step 5: Auditor 1 > Finish audit > Audit Declaration ───────
        if Config.run_finish_audit1:
            flow.finish_audit(page, Config, "Auditor 1")
        else:
            print(" Step 5 finish_audit (Auditor 1) skipped")
        # ── Login as Auditor 2 ─────────────────────────────────────────
        switched = False
        if Config.run_stock_audit2:
            same_creds = (
                (Config.email or "") == (Config.email2 or "") and
                (Config.password or "") == (Config.password2 or "")
            )
            if not same_creds:
                browser.close()  # close Auditor 1 session only when credentials change
                browser, page = login(
                    p,
                    browser_name=Config.browsername,
                    environment=Config.environments,
                    email=Config.email2,
                    password=Config.password2,
                    company_name=Config.company_name
                )
                page.set_default_timeout(30000)
                switched = True

            stock_audit2(page, Config)
            # ── Step 6: Auditor 2 > Finish audit > Audit Declaration ───
            if Config.run_finish_audit2:
                flow.finish_audit(page, Config, "Auditor 2")
            else:
                print(" Step 6 finish_audit (Auditor 2) skipped")
        else:
            print(" stock_audit2 skipped")
            if Config.run_finish_audit2:
                print(" Step 6 finish_audit (Auditor 2) skipped: run_stock_audit2 is False")
        # ── Back to the owner (Auditor 1 login): summary and steps 7-10 ─
        if switched:
            browser.close()
            browser, page = login(
                p,
                browser_name=Config.browsername,
                environment=Config.environments,
                email=Config.email,
                password=Config.password,
                company_name=Config.company_name
            )
        if Config.run_A_SA_table:
            print(" A_audit_Summary running")
            A_as_table(page, Config)
        else:
            print(" A_SA_table skipped")
        if Config.run_A_audit_Summary:
            print(" A_audit_Summary running")
            A_audit_Summary(page, Config)
        else:
            print(" A_audit_Summary skipped")
        if Config.run_A_Recently_Audit:
            print(" A_Recently_Audit running")
            A_Recently_Audit(page, Config)
        else:
            print(" A_Recently_Audit skipped")
        # ── Step 7: Audit Summary > Complete Audit (3-step popup) ──────
        if Config.run_complete_audit:
            flow.complete_audit(page, Config)
        else:
            print(" Step 7 complete_audit skipped")
        # ── Step 8: Resolution actions (Accept | Recount | Investigate) ─
        if Config.run_resolution_actions:
            flow.resolution_actions(page, Config)
        else:
            print(" Step 8 resolution_actions skipped")
        # ── Step 9: Recount sub-audit > review > approve (if Recount) ──
        if Config.run_recount:
            flow.recount(page, Config)
        else:
            print(" Step 9 recount skipped")
        # ── Step 10: Resolution summary > Adjustment > Complete > History
        if Config.run_resolution_summary:
            flow.resolution_summary(page, Config)
        else:
            print(" Step 10 resolution_summary skipped")
        if flow:
            flow.report(Config)
        # ── Post-Complete Validation: Audit History (UI + Excel + PDF) ──
        if getattr(Config, "run_A_audit_Summary_history", False):
            print("\n" + "=" * 70)
            print(" AUDIT HISTORY POST-COMPLETION VALIDATION (UI + Excel + PDF)")
            print("=" * 70)
            A_audit_Summary(page, Config, is_history=True)
        if Config.run_settings_tests:
            run_settings_tests(page, Config)
        else:
            print(" settings_tests skipped")
        browser.close()
