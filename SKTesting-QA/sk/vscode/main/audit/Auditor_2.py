"""
Auditor 2 stock audit — the same flows as Auditor 1 (A_SA / S_SA in Auditor_1.py),
run with the auditor-2 settings from Config (ITEM_CODE2, EXCEL_SHEET_auditor_2, ...).
"""
from audit.Auditor_1 import A_SA, S_SA


# ======================================================
# AUDITOR 2 SETTINGS
# ======================================================
# Config names A_SA / S_SA read  ->  the auditor-2 setting served in their place
AUDITOR2_FIELDS = {
    "email":                 "email2",
    "run_new_add_item":      "run_new_add_item2",
    "ITEM_CODE1":            "ITEM_CODE2",
    "ITEM_NAME1":            "ITEM_NAME2",
    "CATEGORY1":             "CATEGORY2",
    "COST_PRICE1":           "COST_PRICE2",
    "SELL_PRICE1":           "SELL_PRICE2",
    "LOCATION1":             "LOCATION2",
    "BARCODE1":              "BARCODE2",
    "UOM1":                  "UOM2",
    "audited_qty1":          "audited_qty2",
    "damaged_qty1":          "damaged_qty2",
    "EXCEL_SHEET_auditor_1": "EXCEL_SHEET_auditor_2",
    "EXCEL_LOCATION_COL1":   "EXCEL_LOCATION_COL2",
    "EXCEL_CODE_COL1":       "EXCEL_CODE_COL2",
    "EXCEL_AUDITED_COL1":    "EXCEL_AUDITED_COL2",
    "EXCEL_DAMAGED_COL1":    "EXCEL_DAMAGED_COL2",
    "run_asv2_checks":       "run_asv2_checks2",    # not set -> checks off for auditor 2
}


class Auditor2Config:
    """Read-only view of Config that serves the auditor-2 settings under the auditor-1 names."""

    def __init__(self, config):
        self._config = config

    def __getattr__(self, name):
        if name == "EXCEL_PATH":
            # Older auditor-2 code read oa_excel_path; keep it as a fallback
            return getattr(self._config, "EXCEL_PATH", "") or getattr(self._config, "oa_excel_path", "")
        return getattr(self._config, AUDITOR2_FIELDS.get(name, name))


def A_SA2(page, Config):
    return A_SA(page, Auditor2Config(Config))


def S_SA2(page, Config):
    return S_SA(page, Auditor2Config(Config))


# ======================================================
# MAIN EXECUTION ROUTER
# ======================================================
def stock_audit2(page, Config):
    """
    Route execution based on audit type.
    """
    SD_audit_type = str(
        getattr(Config, "SD_audit_type", getattr(Config, "audit_type", "Dynamic"))
    ).strip().lower()

    if SD_audit_type == "static":
        result = S_SA2(page, Config)
        print("\n   Static Stock Audit completed.")
    else:
        result = A_SA2(page, Config)
        print("\n   Dynamic Stock Audit completed.")
    return result
