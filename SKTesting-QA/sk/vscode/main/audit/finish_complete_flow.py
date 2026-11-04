"""
Finish → Declaration → Resolution → Complete — end of the audit lifecycle.

run_finish_complete() creates a fresh Complete/Dynamic audit, sets it up, counts
the `fc_counts` sheet with A_SA and then runs finish_complete_flow(), which drives
the owner's side of the flow and cross-checks every screen:

  Stock Audit > Finish audit > Audit Declaration (notes from `finish_flow`)
  Audit Summary > Complete Audit > 3-step popup (force / unverified / resolution)
  Resolution actions (Accept / Recount / Investigate per `finish_flow`)
  Recount sub-audit (static page) > Recount review (approve)
  Resolution summary > Adjustment report > Complete Audit > Audit History

The audit is closed for good by the last step, which is why a new one is made per run.
"""
import base64
import io
import re
from datetime import datetime
from typing import Dict, List

import pandas as pd

from audit.A_audit_Summary import (
    Config as SummaryCfg, click_badge, collect_all, select_branch, select_navigation_option,
)
from audit.stock_audit_checks import Results, _clean, _num, _table

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


def _enter_resolution(page, Config, res, st):
    """Audit Summary > Complete Audit; answers the 3-step popup the first time."""
    _open_audit(page, Config, "Audit Summary")
    page.locator(f"{SUMMARY} button.text-app-primary", has_text="Complete Audit").first.click()
    page.wait_for_timeout(3000)
    for _ in range(4):
        popup = page.locator(FLOW_POPUP)
        if popup.count() == 0:
            break
        text = _clean(popup.inner_text())
        if "force complete" in text:
            res.check("Complete popup", "Other auditors unfinished -> force complete", True, text[:60])
            popup.locator("button", has_text="Yes").click()
        elif "complete the Audit" in text:          # every auditor has finished
            res.check("Complete popup", "Confirm complete -> Yes", True, text[:60])
            popup.locator("button", has_text="Yes").click()
        elif "Unverified items" in text:
            m = re.search(r"There are (\d+) items not counted", text)
            st["unverified"] = int(m.group(1)) if m else 0
            choice = getattr(Config, "fc_unverified_choice", "Move to Not Found")
            res.check("Complete popup", f"Unverified step -> {choice}", True, f"{st['unverified']} items not counted")
            popup.locator("button", has_text=choice).click()
        elif "Proceed to Resolution" in text:
            res.check("Complete popup", "Variance step -> Proceed to Resolution", True)
            popup.locator("button", has_text="Proceed to Resolution").click()
        page.wait_for_timeout(3000)
    try:
        page.wait_for_url(re.compile(r"auditresolution"), timeout=20000)
    except Exception:
        pass
    return page.url


# --------------------------------------------------------------
# 1. FINISH AUDIT > DECLARATION
# --------------------------------------------------------------
def step_declaration(page, Config, res, plan, st):
    area = "Declaration"
    _open_audit(page, Config, "Stock Audit")
    page.wait_for_selector("app-audit-stock-v2 header.asv2-toolbar", timeout=30000)
    page.wait_for_timeout(1500)
    if page.locator(FINISH_BTN).is_disabled():      # resumed run: count was finished earlier
        res.check(area, "Count already finished (resumed run)", True,
                  _clean(page.locator("app-audit-stock-v2 .asv2-status-value").inner_text()))
        st["declared"] = {}
        return
    page.locator(FINISH_BTN).click()
    page.locator(DECLARATION).wait_for(state="visible", timeout=15000)
    page.wait_for_timeout(2000)

    idx, rows = _table(page, DECLARATION)
    st["declaration"] = {}
    for r in rows:
        code = r[idx["ITEM CODE"]]
        stock, audited = _num(r[idx["STOCK QTY"]]), _num(r[idx["AUDITED QTY"]])
        kind = r[idx["DISCREPANCY TYPE"]]
        st["declaration"][code] = {"stock": stock, "audited": audited, "type": kind}
        if "un verified" in kind.lower():
            res.check(area, f"{code} uncounted -> auto note", r[idx["DECLARATION NOTE"]] == "Non-Audited Items",
                      r[idx["DECLARATION NOTE"]])
            continue
        if "positive" in kind.lower() or "negative" in kind.lower():
            res.check(area, f"{code} variance in type", f"({audited - stock:g})" in kind, f"{stock:g} -> {audited:g}: {kind}")
        else:
            res.check(area, f"{code} excess type", stock == 0 and audited > 0 and "excess" in kind.lower(), kind)

    st["declared"] = {}
    for code, info in st["declaration"].items():
        dd = _row(page, DECLARATION, code).locator("p-dropdown")
        if "un verified" in info["type"].lower() or dd.count() == 0:
            continue
        note = _entry(plan, code)["note"]
        ok = bool(note) and _pick(page, dd, note)
        st["declared"][code] = note if ok else ""
        res.check(area, f"{code} note '{note}'", ok, "" if ok else "note missing in sheet or not an option")

    head = _clean(page.locator(DECLARATION).inner_text())
    prog = re.search(r"(\d+)\s+of\s+(\d+)\s+discrepancies declared", head)
    res.check(area, "All discrepancies declared", bool(prog) and prog.group(1) == prog.group(2),
              prog.group(0) if prog else head[:60])

    page.locator(f"{DECLARATION} button.ad-btn--primary", has_text="Finish Audit").click()
    _confirm_swal(page, "finish the audit")
    page.reload()
    page.wait_for_selector("app-audit-stock-v2 header.asv2-toolbar", timeout=30000)
    page.wait_for_timeout(2000)
    status = _clean(page.locator("app-audit-stock-v2 .asv2-status-value").inner_text())
    res.check(area, "Count finished (status COMPLETED, Finish disabled)",
              status.upper() == "COMPLETED" and page.locator(FINISH_BTN).is_disabled(), status)


# --------------------------------------------------------------
# 2. AUDIT SUMMARY > COMPLETE AUDIT > RESOLUTION
# --------------------------------------------------------------
def step_start_resolution(page, Config, res, st):
    area = "Summary before resolution"
    _open_audit(page, Config, "Audit Summary")
    cfg = SummaryCfg()
    click_badge(page, cfg, "All")
    st["summary"] = {r["Item Code"].upper(): r for r in collect_all(page, cfg)}
    for code, note in st.get("declared", {}).items():
        shown = st["summary"].get(code.upper(), {}).get("Reason", "")
        res.check(area, f"{code} declaration note carried to summary", shown.lower() == note.lower(),
                  f"declared={note!r} summary={shown!r}")

    url = _enter_resolution(page, Config, res, st)
    res.check("Complete popup", "Opens resolution", "auditresolutionaction" in url, url.split("/")[-1])


# --------------------------------------------------------------
# 3. RESOLUTION ACTIONS
# --------------------------------------------------------------
def step_resolution_actions(page, Config, res, plan, st):
    area = "Resolution actions"
    if "auditresolutionaction" not in page.url:
        raise RuntimeError(f"not on the resolution page ({page.url.split('/')[-1]})")
    page.wait_for_selector("app-layout table tbody tr", timeout=20000)
    page.wait_for_timeout(2000)
    idx, rows = _table(page, "app-layout")
    codes = [r[idx["ITEM CODE"]] for r in rows]
    summary = st.get("summary", {})
    expected = {c for c, r in summary.items() if _num(r.get("Variance")) != 0}
    res.check(area, "Rows = summary items with variance", {c.upper() for c in codes} == expected,
              f"page={sorted(codes)} summary={sorted(expected)}")
    for r in rows:
        code = r[idx["ITEM CODE"]]
        srow = summary.get(code.upper(), {})
        res.check(area, f"{code} variance = summary", _num(r[idx["VARIANCE"]]) == _num(srow.get("Variance")),
                  f"page={r[idx['VARIANCE']]} summary={srow.get('Variance')}")
        res.check(area, f"{code} variance value = summary",
                  _num(r[idx["VARIANCE VALUE"]]) == _num(srow.get("Variance Value")),
                  f"page={r[idx['VARIANCE VALUE']]} summary={srow.get('Variance Value')}")
        cost = st.get("cost", {}).get(code.upper())
        if cost is not None:
            want = _num(r[idx["VARIANCE"]]) * cost
            res.check(area, f"{code} variance value = variance x cost price",
                      _num(r[idx["VARIANCE VALUE"]]) == want,
                      f"page={r[idx['VARIANCE VALUE']]} expected={r[idx['VARIANCE']]} x {cost:g} = {want:g}")
        declared = st.get("declared", {}).get(code)
        if declared:
            res.check(area, f"{code} declaration note carried over", r[idx["DECLARATION NOTE"]] == declared,
                      f"declared={declared!r} page={r[idx['DECLARATION NOTE']]!r}")

    st["actions"] = {}
    for code in codes:
        e = _entry(plan, code)
        row = _row(page, "app-layout", code)
        dds = row.locator("p-dropdown")
        if e["note"]:
            _pick(page, dds.nth(0), e["note"])
        if e["remarks"]:
            row.locator("input[placeholder='Add Remarks']").fill(e["remarks"])
        ok = _pick(page, dds.nth(1), e["action"])
        st["actions"][code] = e["action"]
        res.check(area, f"{code} -> {e['action']}", ok)
        if e["action"] == "Recount":
            # Choosing the assignee is what creates the "Recount Audit" sub-audit
            auditor = getattr(Config, "fc_auditor", None) or ""
            if not (auditor and _pick(page, dds.nth(2), auditor)):
                dds.nth(2).click()
                first = page.locator(".p-dropdown-panel:visible li.p-dropdown-item").first
                if first.count():
                    first.click()
                else:
                    page.keyboard.press("Escape")
            assignee = ""
            for _ in range(10):
                page.wait_for_timeout(800)
                assignee = _clean(row.locator("td").last.inner_text())
                if assignee and assignee != "Unassigned":
                    break
            res.check(area, f"{code} recount assigned", assignee and assignee != "Unassigned", assignee)

    page.locator("app-layout button", has_text="Next").first.click()
    page.wait_for_timeout(4000)
    popup = page.locator(SWAL)
    if popup.count():
        text = _clean(popup.last.inner_text())
        res.check(area, "Next accepted", False, text[:100])
        popup.last.locator("button.swal2-confirm, button.swal2-cancel").first.click()


# --------------------------------------------------------------
# 4. RECOUNT SUB-AUDIT (static counting page)
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


# --------------------------------------------------------------
# 5. RESOLUTION SUMMARY + ADJUSTMENT REPORT
# --------------------------------------------------------------
def _go_to_resolution_summary(page, Config, res, st):
    if "auditresolutionsummary" in page.url:
        return
    _enter_resolution(page, Config, res, st)
    for _ in range(3):
        if "auditresolutionsummary" in page.url:
            break
        page.locator("app-layout button:visible", has_text="Next").first.click()
        page.wait_for_timeout(4000)


def watch_adjustment_context(page, st):
    """Keep the latest AuditAdjustment/GetContext reply (the summary page loads it on arrival)."""
    st["adjustment_context"] = {}

    def on_response(r):
        if "AuditAdjustment/GetContext" in r.url:
            try:
                st["adjustment_context"].update(r.json().get("data") or {})
            except Exception:
                pass
    page.on("response", on_response)


def _matched_codes(st):
    """Items whose Audit Summary variance is 0 (they are not part of resolution)."""
    return sorted(c for c, r in st.get("summary", {}).items()
                  if r.get("Variance", "").strip() != "-" and _num(r.get("Variance")) == 0)


def st_codes(rows, idx):
    return [r[idx["ITEM CODE"]] for r in rows]


def step_resolution_summary(page, Config, res, plan, st):
    area = "Resolution summary"
    _go_to_resolution_summary(page, Config, res, st)
    page.wait_for_selector("app-layout table tbody tr", timeout=20000)
    page.wait_for_timeout(2500)
    text = _clean(page.locator("app-layout").first.inner_text())

    actions = st.get("actions", {})
    want = {a: sum(1 for v in actions.values() if v == a) for a in ("Accept", "Recount", "Investigate")}
    m = re.search(r"Total Variance Lines (\d+) Accept (\d+) Recount (\d+) Investigate (\d+)", text)
    if m:
        total, acc, rec, inv = map(int, m.groups())
        res.check(area, "Accept / Recount / Investigate counts", (acc, rec, inv) == (want["Accept"], want["Recount"], want["Investigate"]),
                  f"page={acc}/{rec}/{inv} sheet={want['Accept']}/{want['Recount']}/{want['Investigate']}")
        res.check(area, "Total variance lines = actioned lines", total == acc + rec + inv,
                  f"total={total} actioned={acc + rec + inv}"
                  + (f" (matched items counted: {_matched_codes(st)})" if total > acc + rec + inv else ""))
    else:
        res.check(area, "Summary cards shown", False, text[:60])

    idx, rows = _table(page, "app-layout")
    expect_status = {"Accept": "Accepted", "Recount": "Recount Accepted", "Investigate": "Under Investigation"}
    pending = []
    for r in rows:
        code, status = r[idx["ITEM CODE"]], r[idx["STATUS"]]
        if status == "Pending":
            pending.append(code)
            continue
        action = actions.get(code)
        res.check(area, f"{code} status", action and status == expect_status[action], f"{action} -> {status}")
        expected, actual = _num(r[idx["EXPECTED"]]), _num(r[idx["ACTUAL"]])
        if action == "Recount":
            qty = _entry(plan, code)["recount"]
            res.check(area, f"{code} actual = recount", actual == qty, f"{actual:g} vs {qty}")
        res.check(area, f"{code} variance = actual - expected", _num(r[idx["VARIANCE"]]) == actual - expected,
                  f"{r[idx['VARIANCE']]} vs {actual - expected:g}")
        note = _entry(plan, code)["note"]
        if note:
            res.check(area, f"{code} note", r[idx["DECLARATION NOTE"]] == note, r[idx["DECLARATION NOTE"]])
    # Matched items (variance 0) are not part of resolution by design
    matched = set(_matched_codes(st))
    listed = sorted(c for c in st_codes(rows, idx) if c.upper() in matched)
    res.check(area, "Matched items not listed in the resolution summary", not listed,
              f"matched items shown as Pending: {listed}" if listed else "")
    variance_pending = [c for c in pending if c.upper() not in matched]
    res.check(area, "No variance item left Pending", not variance_pending,
              f"pending={variance_pending}" if variance_pending else "")
    st["resolution_rows"] = {r[idx["ITEM CODE"]]: r for r in rows}
    st["resolution_idx"] = idx

    # ---- Adjustment report (export) vs resolution
    area = "Adjustment report"
    ctx = st["adjustment_context"]
    res.check(area, "Adjustment context loaded", bool(ctx),
              f"source={ctx.get('sourceMode')} status={ctx.get('status')} requires={ctx.get('requiresAdjustment')}")
    with page.expect_response(lambda r: "AuditAdjustment/Export" in r.url, timeout=20000) as info:
        page.locator("app-layout button", has_text="Adjustment Report").first.click()
    data = (info.value.json().get("data") or {}).get("base64String")
    if not data:
        res.check(area, "Report exported", False, "empty response")
        return
    df = pd.read_excel(io.BytesIO(base64.b64decode(data)))
    res.check(area, "Report exported", True, f"{len(df)} line(s)")
    if ctx.get("sourceMode") == "Excel":
        res.check(area, "Excel source: nothing posted", set(df["Post Status"].astype(str)) <= {"Not applicable"},
                  str(sorted(set(df["Post Status"].astype(str)))))
    for code, r in st["resolution_rows"].items():
        if r[idx["STATUS"]] not in ("Accepted", "Recount Accepted"):
            continue
        lines = df[df["Item Code"].astype(str).str.upper() == code.upper()]
        adj = float(lines["Adjustment Qty"].sum()) if len(lines) else 0.0
        res.check(area, f"{code} adjustment = variance", adj == _num(r[idx["VARIANCE"]]),
                  f"adjust={adj:g} variance={r[idx['VARIANCE']]} lines="
                  f"{list(zip(lines['Location'].astype(str), lines['Adjustment Qty']))}")
        for _, line in lines.iterrows():
            qty, unit, value = float(line["Adjustment Qty"]), float(line["Unit Cost Price"]), float(line["Adjustment Value"])
            res.check(area, f"{code} adjustment value = qty x unit cost", value == qty * unit,
                      f"{line['Location']}: {value:g} vs {qty:g} x {unit:g}")
        cost = st.get("cost", {}).get(code.upper())
        if cost is not None and len(lines):
            units = sorted(set(lines["Unit Cost Price"].astype(float)))
            res.check(area, f"{code} unit cost = item cost price", units == [cost], f"report={units} item={cost:g}")


# --------------------------------------------------------------
# 6. COMPLETE AUDIT > AUDIT HISTORY
# --------------------------------------------------------------
def step_complete(page, Config, res, st):
    area = "Complete audit"
    _go_to_resolution_summary(page, Config, res, st)
    page.locator("app-layout textarea").first.fill(getattr(Config, "fc_closure_note", "QA automated finish/complete run"))
    page.locator("app-layout button", has_text="Complete Audit").first.click()
    page.wait_for_timeout(3000)
    popup = page.locator(SWAL)
    if popup.count():
        text = _clean(popup.last.inner_text())
        if "Pending" in text:
            rows = st.get("resolution_rows", {})
            idx = st.get("resolution_idx", {})
            pending = [c for c, r in rows.items() if idx and r[idx["STATUS"]] == "Pending"]
            matched = set(_matched_codes(st))
            only_matched = pending and all(c.upper() in matched for c in pending)
            res.check(area, "Complete Audit accepted", False,
                      (f"blocked by matched items that are not part of resolution {pending}: " if only_matched else "")
                      + text[:100])
            popup.last.locator("button.swal2-confirm").click()
            return
        popup.last.locator("button.swal2-confirm").click()
        page.wait_for_timeout(4000)
        res.check(area, "Complete confirmed", True, text[:60])
    _audit_list(page, Config)
    ongoing = _list_status(page, Config, "Ongoing Audits")
    history = _list_status(page, Config, "Audit History")
    res.check(area, "Gone from Ongoing Audits", ongoing is None, str(ongoing))
    res.check(area, "In Audit History as Completed", bool(history) and "Complet" in history, str(history))


# --------------------------------------------------------------
# ENTRY POINTS
# --------------------------------------------------------------
def finish_complete_flow(page, Config) -> bool:
    print("\n" + "-" * 70)
    print(f"🔷 FINISH → DECLARATION → RESOLUTION → COMPLETE   ({Config.ap_audit_name})")
    print("-" * 70)
    plan = load_finish_plan(Config)
    res, st = Results(), {}
    watch_adjustment_context(page, st)
    res.section("Declaration", step_declaration, page, Config, res, plan, st)
    res.section("Start resolution", step_start_resolution, page, Config, res, st)
    res.section("Resolution actions", step_resolution_actions, page, Config, res, plan, st)
    if "Recount" in st.get("actions", {}).values():
        res.section("Recount sub-audit", step_recount, page, Config, res, plan, st)
        res.section("Recount review", step_recount_review, page, Config, res, plan, st)
    res.section("Resolution summary", step_resolution_summary, page, Config, res, plan, st)
    res.section("Complete audit", step_complete, page, Config, res, st)
    return res.report(f"FINISH → RESOLUTION → COMPLETE — {Config.ap_audit_name}")


def run_finish_complete(page, Config, audit_name=None, setup=True, count=True) -> bool:
    """Create a disposable audit, set it up, count it, then run the finish/complete flow.

    audit_name: continue an audit created by an earlier, interrupted run instead of
    creating one; setup=False / count=False skip the settings + stock sheet import and
    the A_SA counting when those already happened.
    """
    from audit.Ad_hoc_Audit import Ad_hoc_Audit
    from audit.Ongo_Audit import Ongo_Audit
    from audit.Auditor_1 import stock_audit

    auditor = getattr(Config, "fc_auditor", None) or Config.Auditor2
    overrides = {
        "ap_audit_name": audit_name or f"{getattr(Config, 'fc_audit_prefix', 'QA_FC')}_{datetime.now():%m%d_%H%M}",
        "Audit_Type": "Complete Audit", "SD_audit_type": "Dynamic",
        "A_Checkboxes_BlindCount": False, "A_Checkboxes_geo": False, "A_Checkboxes_Audit_Damaged": True,
        "oa_photo_type": "None", "oa_sample_size": 0, "AUDIT_MAPPING_TYPE": "Random",
        "oa_Auditor1": auditor, "oa_Auditor2": auditor, "oa_sheet": "Data",
        "EXCEL_SHEET_auditor_1": Config.EXCEL_SHEET_fc_counts,
        "EXCEL_LOCATION_COL1": "locations", "EXCEL_CODE_COL1": "code",
        "EXCEL_AUDITED_COL1": "audited", "EXCEL_DAMAGED_COL1": "damaged",
        "run_new_add_item": False, "run_asv2_checks": False,
    }
    saved = {k: getattr(Config, k, None) for k in overrides}
    try:
        for k, v in overrides.items():
            setattr(Config, k, v)
        if audit_name:
            print(f"\n🔷 Continuing audit: {Config.ap_audit_name}")
        else:
            print(f"\n🔷 New audit for the finish/complete flow: {Config.ap_audit_name}")
            Ad_hoc_Audit(page, Config)
            page.wait_for_timeout(3000)
            nav = page.locator("button[aria-label='Close navigation popup']")   # opens after create
            if nav.count() and nav.is_visible():
                nav.click()
                page.wait_for_timeout(800)
        if setup:
            Ongo_Audit(page, Config)
            _close_guide(page)
        if count:
            stock_audit(page, Config)
        return finish_complete_flow(page, Config)
    finally:
        for k, v in saved.items():
            setattr(Config, k, v)
