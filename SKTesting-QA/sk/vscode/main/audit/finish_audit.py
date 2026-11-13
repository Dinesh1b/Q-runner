"""
Step 1 — Stock Audit > Finish audit > Audit Declaration (notes from `finish_flow`).
"""
import re

from audit.finish_common import (
    DECLARATION, FINISH_BTN, _confirm_swal, _entry, _open_audit, _pick, _row,
)
from audit.stock_audit_checks import _clean, _num, _table


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
    # After Finish Audit the auditor's own status stays IN PROGRESS, with one or two auditors; COMPLETED belongs
    # only to after Complete Audit, when the audit is In Resolution (user, 2026-11-13). The finished count
    # shows as the Finish button turning disabled.
    status = _clean(page.locator("app-audit-stock-v2 .asv2-status-value").inner_text())
    finish_off = page.locator(FINISH_BTN).is_disabled()
    res.check(area, "Count finished (status IN PROGRESS, Finish disabled)",
              status.upper() == "IN PROGRESS" and finish_off,
              f"status={status}, Finish {'disabled' if finish_off else 'enabled'}")
