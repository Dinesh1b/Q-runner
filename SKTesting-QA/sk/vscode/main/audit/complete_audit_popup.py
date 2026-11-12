"""
Step 2 — Audit Summary > Complete Audit > 3-step popup (force / unverified / resolution).

_enter_resolution() answers the popup; the recount review (recount.py) and the resolution
summary (resolution_summary.py) are reached through the same popup and reuse it.
"""
import re

from audit.A_audit_Summary import Config as SummaryCfg, click_badge, collect_all
from audit.finish_common import FLOW_POPUP, SUMMARY, _open_audit
from audit.stock_audit_checks import _clean


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
