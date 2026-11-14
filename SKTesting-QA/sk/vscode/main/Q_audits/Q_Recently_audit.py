"""
Q_Recently_audit wrapper — delegates directly to the formula & business rule
validation engine in audit/A_Recently_audit.py.
"""
import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from audit.A_Recently_audit import (
    A_Recently_Audit,
    validate_recently_audited_by_rules,
    load_stock_sheet_data,
    calc_expected_stock,
    REQUIRED_COLUMNS,
    FORM_RULES,
    PAGE_RULES,
    ROW_FORMULA_RULES,
)

def Q_Recently_Audit(page, Config):
    """
    Main entry point for Q Audit Recently Audited formula & rule validation.
    """
    # Ensure backwards compatibility for audit name attribute
    if not hasattr(Config, "ap_audit_name") and hasattr(Config, "audit_name"):
        Config.ap_audit_name = Config.audit_name

    return A_Recently_Audit(page, Config)

__all__ = [
    "Q_Recently_Audit",
    "A_Recently_Audit",
    "validate_recently_audited_by_rules",
    "load_stock_sheet_data",
    "calc_expected_stock",
    "REQUIRED_COLUMNS",
    "FORM_RULES",
    "PAGE_RULES",
    "ROW_FORMULA_RULES",
]
