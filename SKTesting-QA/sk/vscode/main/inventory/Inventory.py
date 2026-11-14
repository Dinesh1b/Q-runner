import sys
import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from login.login import login
from login.popup_handler import detect_feedback
from excel_logger import write_log, set_excel_path
from inventory.create_group import create_group, update_group
from inventory.Item_import_add import import_app
from inventory.location import settings
# Item Group values (name, type, barcode fields, IDs, Accounting, Advanced, UOM) live in backend/Config.py → Inventory Setup
from backend.Config import Config as GroupConfig
class Config:

        # ── Conditional Login Control ─────────────────────────────
    USE_CUSTOM_LOGIN = True
    company_name = "Test_TuddeCompany_16/10"
    if USE_CUSTOM_LOGIN:
        email = "tuddefonugu-3882@yopmail.com"
        password = "12345678"
    else:
        email = None
        password = None

    browsername = "chrome"
    environments = "production" # production, staging, development

    Branch = "DE"
    Group_Name = "QA_GRP_1112_2214"
    run_create_group = True    # QA_GRP_1112_2214 (Unit) was created on staging on 11-12 22:15
    run_update_group = False    # update the saved group named group_name so it matches backend/Config.py
    run_location_setup = False
    zones  = ["SA"]
    aisles = ["A1", "A2", "A3"]
    bays   = ["B1","B2","B3","B4","B5"]
    levels = ["L1", "L2", "L3", "L4", "L5"]


    

    sheet_name = "Data"

#itme itme imports
    run_import_app = True

    EXCEL_FILE: str = os.environ.get(
        "IMPORT_EXCEL_FILE",
        r"C:\Users\dines\3D Objects\main_qexcel.xlsx"
    )
    run_add_item = True          # ITM0039: in the group, not on sheet Data -> the audit's excess item

    run_import_items = True      # sheet Data: ITM0001-ITM0010

    # --- Add Item test record (single item, not from Excel) ---
    Item_Name     = "Item 039"   # Item Name   (was wrongly used as UOM before)
    Item_Code     = "ITM0039"    # Item Code
    Item_UOM      = "kg"         # UOM         (was wrongly used as Item Name before)
    Item_Category = "GMA"        # Category
    Item_Tag      = "test tag1"   # Tag
    Item_CP       = 100          # Cost Price  (was hardcoded "100" in script, ignored Config)
    Item_SP       = 150          # Sell Price  (was hardcoded "150" in script, ignored Config)
    Item_Barcode  = "890000000039"  # EAN/QR
    Item_Description  = ""        # Optional
    Item_TaxHsn       = ""        # Optional
    Item_Tax          = ""        # Optional
    Item_ReorderLimit = ""        # Optional


# ======================================================
# MAIN EXECUTION
# ======================================================

if __name__ == "__main__":

    if hasattr(Config, "Group_Name") and Config.Group_Name:
        GroupConfig.group_name = Config.Group_Name

    with sync_playwright() as p:

        browser, page = login(
            p,
            browser_name=Config.browsername,
            environment=Config.environments,
            email=Config.email,
            password=Config.password,
            company_name=Config.company_name
        )
        if Config.run_location_setup:
             settings(page, Config)
        else:
            print("x location_setup")
        if Config.run_create_group:
             create_group(page,  GroupConfig)
        else:
            print("x create_group")
        if Config.run_update_group:
             update_group(page, GroupConfig)
        else:
            print("x update_group")
        if Config.run_import_app:
             # Import into the same item group (backend/Config.py group_name)
             import_app(page, type("ImportConfig", (Config,), {"group_name": GroupConfig.group_name}))
        else:
            print("x Itme_imports")
        browser.close()