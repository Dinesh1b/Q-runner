"""
Shared pieces of the Finish -> Complete flow: selectors, the `finish_flow` plan sheet,
audit list navigation and small UI helpers used by more than one step.
"""
import re
from typing import Dict

import pandas as pd

from audit.A_audit_Summary import select_branch, select_navigation_option
from audit.stock_audit_checks import _clean

FINISH_BTN   = "button[data-tour-id='finish-audit-btn']"
DECLARATION  = "app-audit-declaration"
SUMMARY      = "app-audit-summary"
FLOW_POPUP   = ".swal2-popup.complete-audit-flow-popup:visible"
SWAL         = ".swal2-popup:visible"
STATIC_AUDIT = "app-static-audit"


# --------------------------------------------------------------
# EXCEL PLAN (`finish_flow` sheet)
# --------------------------------------------------------------
def load_finish_plan(Config) -> Dict[str, dict]:
    """code -> {note, action, recount, remarks}; the '*' row applies to every other item."""
    df = pd.read_excel(Config.EXCEL_PATH, sheet_name=Config.EXCEL_SHEET_finish_flow)
    plan = {}
    for _, r in df.iterrows():
        code = str(r.get("code", "")).strip()
        if not code or code == "nan":
            continue
        plan[code.upper()] = {
            "note":    str(r.get("declaration_note", "")).strip(),
            "action":  str(r.get("resolution", "Accept")).strip().title(),
            "recount": None if pd.isna(r.get("recount_qty")) else float(r.get("recount_qty")),
            "remarks": "" if pd.isna(r.get("remarks")) else str(r.get("remarks")).strip(),
        }
    plan.setdefault("*", {"note": "", "action": "Accept", "recount": None, "remarks": ""})
    return plan


def _entry(plan, code):
    return plan.get(code.upper(), plan["*"])


# --------------------------------------------------------------
# NAVIGATION
# --------------------------------------------------------------
def _audit_list(page, Config):
    page.click("a[href='/home/audit']")
    try:
        page.wait_for_load_state("networkidle", timeout=10000)   # the list keeps polling at times
    except Exception:
        pass
    select_branch(page, Config.Branch)
    page.wait_for_selector("button.audit-name-link", timeout=45000)
    page.wait_for_timeout(1500)


def _list_row(page, name, audit_type):
    # Long names are truncated in the list; the full name is the cell title.
    # A recount creates a second row with the same name and Type "Recount Audit".
    return page.locator("table tbody tr").filter(has=page.locator(f"td[title='{name}']")) \
        .filter(has_text=audit_type).first


def _close_guide(page):
    # "Audit progress" guide panel that slides in on some screens; when closed it
    # stays in the DOM parked outside the viewport
    close = page.locator("app-audit-guide-panel button.agp-close")
    if close.count() and close.evaluate(
            "e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.left < innerWidth && r.right > 0 }"):
        close.click()
        page.wait_for_timeout(500)


def _open_audit(page, Config, option, audit_type="Complete Count"):
    _audit_list(page, Config)
    _list_row(page, Config.ap_audit_name, audit_type).locator("button.audit-name-link").click()
    select_navigation_option(page, option)
    page.wait_for_timeout(1500)
    _close_guide(page)


def _list_status(page, Config, tab, audit_type="Complete Count"):
    page.locator("app-audit button, app-audit a", has_text=tab).first.click()
    page.wait_for_timeout(3000)
    row = _list_row(page, Config.ap_audit_name, audit_type)
    return _clean(row.locator("td").last.inner_text()) if row.count() else None


# --------------------------------------------------------------
# UI HELPERS
# --------------------------------------------------------------
def _pick(page, dropdown, text) -> bool:
    dropdown.click()
    option = page.locator(".p-dropdown-panel:visible li.p-dropdown-item", has_text=text)
    if option.count() == 0:
        page.keyboard.press("Escape")
        return False
    option.first.click()
    page.wait_for_timeout(500)
    return True


def _row(page, scope, code):
    return page.locator(f"{scope} tbody tr").filter(
        has=page.locator("td", has_text=re.compile(rf"^\s*{re.escape(code)}\s*$"))).first


def _confirm_swal(page, text, timeout=8000):
    popup = page.locator(SWAL, has_text=text)
    popup.wait_for(state="visible", timeout=timeout)
    popup.locator("button.swal2-confirm").click()
    page.wait_for_timeout(2500)
