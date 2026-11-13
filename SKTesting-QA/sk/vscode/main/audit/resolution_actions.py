"""
Step 3 — Resolution actions (Accept / Recount / Investigate per `finish_flow`).
"""
from audit.finish_common import SWAL, _entry, _pick, _row
from audit.stock_audit_checks import _clean, _num, _table


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
        # The declared note is not preselected on the resolution page: "Select" is correct (user, 2026-11-13)
        declared = st.get("declared", {}).get(code)
        if declared:
            shown = _clean(r[idx["DECLARATION NOTE"]])
            res.check(area, f"{code} declaration note not preselected (Select)", shown in ("Select", "", "-"),
                      f"declared={declared!r} page={shown!r}")

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
