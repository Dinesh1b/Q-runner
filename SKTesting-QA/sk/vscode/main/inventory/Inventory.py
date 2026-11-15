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
from excel_logger import write_log, set_excel_path
from inventory.create_group import create_group, update_group
from inventory.Item_import_add import import_app
from inventory.location import settings


# ======================================================
# CONFIG
# ======================================================

class Config:

    # ── Login & Environment ───────────────────────────────
    USE_CUSTOM_LOGIN = True
    company_name = "Test_TuddeCompany_16/10"
    if USE_CUSTOM_LOGIN:
        email = "tuddefonugu-3882@yopmail.com"
        password = "12345678"
    else:
        email = None
        password = None

    browsername  = "chrome"
    environments = "production"   # production, staging, development
    Branch       = "DE"

    # ── Item Group Setup ──────────────────────────────────
    group_name     = "QA_GRP_1112_2214"
    inventory_type = "Unit"                     # Unit | Batch | Serialized
    fields         = ["Item Code", "Item Name"]
    ids            = []                          # Serialized IDs (only when Serialized)

    # Accounting tab
    accounting_mode     = "Basic Accounting Mode"
    costing_method      = "Weighted Average"
    accounting_accounts = {
        "SaleAccountId":     "Sales Revenue",
        "PurchaseAccountId": "Purchase Expenses",
    }

    # Advanced tab (formcontrolname -> on/off)
    advanced_toggles = {
        "AllowDiscount": True,
        "EditSalePrice": True,
    }

    # UOM Conversions tab
    enable_uom_conversions = False   # Unit group: items keep their own UOM
    primary_uom    = "Bale"
    uom_value_type = "Integer only"
    secondary_uoms = [{"uom": "Box",    "quantity": 10}]               # 1 Box = 10 Bale
    tertiary_uoms  = [{"uom": "Pallet", "quantity": 5, "base": "Box"}] # 1 Pallet = 5 Box
    default_uom    = None            # UOM name to mark as Default; None keeps Primary

    run_create_group = True    # create a new item group
    run_update_group = False   # update the saved group to match config above

    # ── Location Setup ────────────────────────────────────
    zones  = ["SA"]
    aisles = ["A1", "A2", "A3"]
    bays   = ["B1", "B2", "B3", "B4", "B5"]
    levels = ["L1", "L2", "L3", "L4", "L5"]

    run_location_setup = False   # add zones / aisles / bays / levels

    # ── Item Import ───────────────────────────────────────
    EXCEL_FILE: str = os.environ.get(
        "IMPORT_EXCEL_FILE",
        r"C:\Users\dines\3D Objects\main_qexcel.xlsx",
    )
    sheet_name = "Data"

    # Single item (not from Excel)
    Item_Name         = "Item 039"
    Item_Code         = "ITM0039"
    Item_UOM          = "kg"
    Item_Category     = "GMA"
    Item_Tag          = "test tag1"
    Item_CP           = 100
    Item_SP           = 150
    Item_Barcode      = "890000000039"
    Item_Description  = ""
    Item_TaxHsn       = ""
    Item_Tax          = ""
    Item_ReorderLimit = ""

    run_import_app   = True    # import items from Excel
    run_add_item     = True    # add single item (ITM0039)
    run_import_items = True    # import sheet Data (ITM0001–ITM0010)


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

        # ── Item Group ────────────────────────────────────
        if Config.run_create_group:
            create_group(page, Config)
        else:
            print("x create_group")

        if Config.run_update_group:
            update_group(page, Config)
        else:
            print("x update_group")

        # ── Location Setup ────────────────────────────────
        if Config.run_location_setup:
            settings(page, Config)
        else:
            print("x location_setup")

        # ── Import Items ──────────────────────────────────
        if Config.run_import_app:
            import_app(page, Config)
        else:
            print("x import_app")

        browser.close()
