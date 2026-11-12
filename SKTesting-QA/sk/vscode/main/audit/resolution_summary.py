"""
Step 5 — Resolution summary > Adjustment report > Complete Audit > Audit History.
"""
import base64
import io
import re

import pandas as pd

from audit.finish_common import SWAL, _audit_list, _entry, _list_status
from audit.complete_audit_popup import _enter_resolution
from audit.stock_audit_checks import _clean, _num, _table


# --------------------------------------------------------------
# RESOLUTION SUMMARY + ADJUSTMENT REPORT
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
# COMPLETE AUDIT > AUDIT HISTORY
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
