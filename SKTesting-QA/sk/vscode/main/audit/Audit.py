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




# ======================================================
# CONFIG
# ======================================================

DRY_RUN = False
SEED = None
FAST_MODE = False



class Config:
    USE_CUSTOM_LOGIN = True  # Set to True to use custom login credentials
    company_name = ""
    if USE_CUSTOM_LOGIN:
        email = "broiyeibricribrou-1186@yopmail.com"
        password = "pVkW9FYo"
    else:
        email = None
        password = None

    email2 = "haffirauttiyoi-4022@yopmail.com"  # Auditor 2 credentials
    password2 = "BgjONdA2"

    browsername = "chrome"
    environments = "QA"  # production, staging, development
    Branch = "122122"

    Audit_Owner = "dine"
    Auditor1 = "Dinesh"
    Auditor2 = "dine"
    Group_Name = "Item_Unit"
    Audit_mode = "Audit_plan"  # "Ad_hoc" or "Audit_plan"
    Audit_Type = "Complete Count"  # Complete Count, Cycle Count, Complete Audit, Partial Audit, Investigation Audit
    SD_audit_type = "Dynamic"  # "Static" or "Dynamic"
    ap_audit_name = "test1234_1"
    frequency = "daily"  # "daily", "weekly", "monthly", "manual"
    Day_s = 30
    Target__Day = "Thursday"
    Target_Date = "10/09/2026"

    A_Checkboxes_Audit_Damaged = True
    A_Checkboxes_geo = True
    A_Checkboxes_BlindCount = True
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
    
    EXCEL_PATH = r"C:\Users\HP\Videos\main_qexcel.xlsx"
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
    run_stock_audit = True
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
    EXCEL_SHEET_auditor_1 = "auditor_1"
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
    oa_photo_type = "Random"
    oa_sample_size = 100
    # static auditor 1      run_S_SA = false


    # Report / Summary flags
    run_A_SA_table = False
    EXCEL_SHEET_as_table = "as_table"
    run_A_audit_Summary = False
    EXCEL_SHEET_audit_Summary = "auditSummary"
    FILTER_COLUMN = "filter"
    run_A_Recently_Audit = True
    EXCEL_SHEET_Recently_Audit = "Recently_Audit"
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
        # ── Login as Auditor 2 ─────────────────────────────────────────
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

            stock_audit2(page, Config)
        else:
            print(" stock_audit2 skipped")
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
        browser.close()
