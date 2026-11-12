"""
Step 4 — Recount sub-audit (static page) > Recount review (approve).
"""
import re

from audit.finish_common import (
    STATIC_AUDIT, _audit_list, _confirm_swal, _entry, _list_row, _row,
)
from audit.complete_audit_popup import _enter_resolution
from audit.stock_audit_checks import _clean, _num, _table


# --------------------------------------------------------------
# RECOUNT SUB-AUDIT (static counting page)
# --------------------------------------------------------------
def step_recount(page, Config, res, plan, st):
    area = "Recount sub-audit"
    todo = {c: _entry(plan, c)["recount"] for c, a in st.get("actions", {}).items() if a == "Recount"}
    _audit_list(page, Config)
    row = _list_row(page, Config.ap_audit_name, "Recount Audit")
    res.check(area, "Recount Audit row created", row.count() == 1, _clean(row.inner_text())[:60] if row.count() else "")
    row.locator("button.audit-name-link").click()
    page.locator(STATIC_AUDIT).wait_for(state="visible", timeout=20000)
    page.wait_for_timeout(2500)
    static = page.locator(STATIC_AUDIT)
    for code, qty in todo.items():
        if qty is None:
            res.check(area, f"{code} recount qty in sheet", False, "recount_qty empty")
            continue
        item = static.locator(f"tr#item-{code}").first     # first row = item's stock location
        item.click()
        page.wait_for_timeout(800)
        static.locator("input.sa-step-input").first.fill(f"{qty:g}")
        static.locator("button.sa-btn-save").click()
        page.wait_for_timeout(2500)
        cells = [_clean(t) for t in item.locator("td").all_inner_texts()]
        res.check(area, f"{code} recounted {qty:g}", f"{qty:g}" in cells, str(cells))
    static.locator("button.sa-btn-finish:visible").first.click()
    _confirm_swal(page, "finish the audit")
    page.wait_for_url(re.compile(r"/home/audit$"), timeout=20000)
    page.wait_for_selector("button.audit-name-link", timeout=45000)
    page.wait_for_timeout(1500)
    status = _clean(_list_row(page, Config.ap_audit_name, "Recount Audit").locator("td").last.inner_text())
    res.check(area, "Recount Audit completed", status == "Completed", status)


# --------------------------------------------------------------
# RECOUNT REVIEW
# --------------------------------------------------------------
def step_recount_review(page, Config, res, plan, st):
    area = "Recount review"
    url = _enter_resolution(page, Config, res, st)
    res.check(area, "Opens recount review", "auditresolutionrecount" in url, url.split("/")[-1])
    page.wait_for_selector("app-layout table tbody tr", timeout=20000)
    page.wait_for_timeout(2000)
    idx, rows = _table(page, "app-layout")
    for r in rows:
        code = r[idx["ITEM CODE"]]
        qty = _entry(plan, code)["recount"]
        exp = _num(r[idx["EXPECTED"]])
        res.check(area, f"{code} recount = sheet", _num(r[idx["RECOUNT"]]) == qty, f"page={r[idx['RECOUNT']]} sheet={qty}")
        res.check(area, f"{code} recount variance", _num(r[idx["RECOUNT VARIANCE"]]) == (qty or 0) - exp,
                  f"{r[idx['RECOUNT VARIANCE']]} vs {(qty or 0) - exp:g}")
        _row(page, "app-layout", code).locator("input[type=checkbox]").check(force=True)
    page.locator("app-layout button.action-approve").click()
    _confirm_swal(page, "Saved Successfully")
    res.check(area, "Recounts approved", True)
    page.locator("app-layout button:visible", has_text="Next").first.click()
    page.wait_for_timeout(4000)
