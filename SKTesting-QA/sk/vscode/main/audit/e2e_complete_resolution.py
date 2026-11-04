"""
End-to-end stock audit — stages 7-9: Complete Audit, Resolution, Final verification.

Runs after e2e_stock_audit.py has counted the run's audit (or on its own against an
audit that is already counted). Reuses the finish_complete_flow steps and adds the
cost-price checks (Variance Value = Variance x Cost Price) and the Complete Count report.
"""
import re

from audit.finish_complete_flow import (
    load_finish_plan, step_complete, step_declaration, step_recount, step_recount_review,
    step_resolution_actions, step_resolution_summary, step_start_resolution, watch_adjustment_context,
)
from audit.stock_audit_checks import _clean, _num

REPORT_URL = "/home/auditReport?ReportName=Complete%20Count"


def _sign_ok(variance: float, vtype: str) -> bool:
    vtype = vtype.lower()
    if variance > 0:
        return "positive" in vtype
    if variance < 0:
        return "negative" in vtype
    return vtype in ("-", "", "matched")


# --------------------------------------------------------------
# STAGE 7 — COMPLETE AUDIT (declaration + complete popup)
# --------------------------------------------------------------
def stage_complete_audit(page, Config, run, res, plan, st):
    res.section("Declaration", step_declaration, page, Config, res, plan, st)

    area = "Declaration"
    for item in run["items"]:
        row = st.get("declaration", {}).get(item["code"])
        if row is None:
            continue
        res.check(area, f"{item['code']} stock / audited = run data",
                  row["stock"] == item["stock"] and row["audited"] == (item["counted"] or 0),
                  f"page={row['stock']:g}/{row['audited']:g} run={item['stock']:g}/{item['counted'] or 0:g}")

    res.section("Start resolution", step_start_resolution, page, Config, res, st)


# --------------------------------------------------------------
# STAGE 8 — RESOLUTION
# --------------------------------------------------------------
def stage_resolution(page, Config, run, res, plan, st):
    res.section("Resolution actions", step_resolution_actions, page, Config, res, plan, st)
    if "Recount" in st.get("actions", {}).values():
        res.section("Recount sub-audit", step_recount, page, Config, res, plan, st)
        res.section("Recount review", step_recount_review, page, Config, res, plan, st)
    res.section("Resolution summary", step_resolution_summary, page, Config, res, plan, st)


# --------------------------------------------------------------
# STAGE 9 — FINAL VERIFICATION
# --------------------------------------------------------------
def check_complete_count_report(page, Config, run, res):
    """Reports > Audit > Complete Count, filtered on the run's item group."""
    area = "Final report"
    page.goto(page.url.split("/home/")[0] + REPORT_URL)
    layout = page.locator("app-layout").first
    layout.locator("button", has_text="Search").first.wait_for(state="visible", timeout=30000)
    page.wait_for_timeout(1500)

    group_dd = layout.locator("p-dropdown.new-prime-dropdown").first
    group_dd.click()
    panel = page.locator(".p-dropdown-panel:visible").last
    search = panel.locator("input")
    if search.count():
        search.first.fill(run["group"])
        page.wait_for_timeout(600)
    panel.locator("li.p-dropdown-item").filter(
        has=page.locator("span.gsd-name", has_text=re.compile(rf"^\s*{re.escape(run['group'])}\s*$"))).first.click()
    layout.locator("button", has_text="Search").first.click()
    page.wait_for_timeout(5000)

    headers = [_clean(h) for h in layout.locator("table thead th").all_inner_texts()]
    idx = {h: i for i, h in enumerate(headers)}
    rows = []
    for _ in range(50):
        for r in layout.locator("table tbody tr").all():
            cells = [_clean(t) for t in r.locator("td").all_inner_texts()]
            if len(cells) == len(headers):
                rows.append(cells)
        nxt = layout.locator("button.p-paginator-next")
        if nxt.count() == 0 or nxt.first.is_disabled():
            break
        nxt.first.click()
        page.wait_for_timeout(1500)
    rows = [r for r in rows if r[idx["Audit Name"]] == run["audit"]]
    res.check(area, "Report lists the run's audit", bool(rows), f"{len(rows)} row(s) for {run['audit']}")
    # the recount qty is the expected final count only once the recount was approved in this run
    recount_done = any(a == "Recount review" and c == "Recounts approved" and ok for a, c, ok, _ in res.rows)

    for item in run["items"]:
        lines = [r for r in rows if r[idx["Item Code"]] == item["code"]]
        if not lines:
            res.check(area, f"{item['code']} in report", False, "no row")
            continue
        stock = sum(_num(r[idx["Stock Quantity"]]) for r in lines)
        audited = sum(_num(r[idx["Audited Quantity"]]) for r in lines)
        variance = sum(_num(r[idx["Variance"]]) for r in lines)
        recounted = item["action"] == "Recount" and recount_done
        final = item["recount"] if recounted else (item["counted"] or 0)
        res.check(area, f"{item['code']} stock qty", stock == item["stock"], f"report={stock:g} run={item['stock']:g}")
        res.check(area, f"{item['code']} audited qty" + (" after accepted recount" if recounted else ""),
                  audited == final, f"report={audited:g} expected={final:g}")
        res.check(area, f"{item['code']} variance = audited - stock", variance == audited - stock,
                  f"{variance:g} vs {audited - stock:g}")
        for r in lines:
            v, value, vtype = _num(r[idx["Variance"]]), _num(r[idx["Variance Value"]]), r[idx["Variance Type"]]
            res.check(area, f"{item['code']} variance value = variance x cost price", value == v * item["cost"],
                      f"{r[idx['Location']]}: {value:g} vs {v:g} x {item['cost']:g}")
            res.check(area, f"{item['code']} variance type matches sign", _sign_ok(v, vtype), f"{v:g} -> {vtype!r}")


def check_stock_update(res, st):
    area = "Stock update"
    ctx = st.get("adjustment_context", {})
    if not ctx:
        res.check(area, "Stock adjustment checked", False,
                  "not checked: the resolution summary (adjustment context) was not reached")
    elif ctx.get("sourceMode") == "Excel" and not ctx.get("requiresAdjustment"):
        res.check(area, "Stock adjustment (N/A for Excel source)", True,
                  f"source=Excel status={ctx.get('status')} — nothing is posted to inventory")
    else:
        res.check(area, "Stock adjustment posted", bool(ctx.get("postedAtUtc")),
                  f"source={ctx.get('sourceMode')} status={ctx.get('status')} posted={ctx.get('postedAtUtc')}")


def stage_final_verification(page, Config, run, res, st):
    res.section("Complete audit", step_complete, page, Config, res, st)
    res.section("Final report", check_complete_count_report, page, Config, run, res)
    check_stock_update(res, st)


# --------------------------------------------------------------
# ENTRY POINT
# --------------------------------------------------------------
def run_complete_resolution(page, Config, run, runner):
    """Stages 7-9 on the run's audit; runner is e2e_stock_audit.StageRunner."""
    plan = load_finish_plan(Config)
    st = {"cost": {i["code"].upper(): i["cost"] for i in run["items"]}}
    watch_adjustment_context(page, st)
    runner.run(7, stage_complete_audit, page, Config, run, runner.res, plan, st, needs=(5,))
    runner.run(8, stage_resolution, page, Config, run, runner.res, plan, st, needs=(7,))
    runner.run(9, stage_final_verification, page, Config, run, runner.res, st, needs=(5,))
    return st
