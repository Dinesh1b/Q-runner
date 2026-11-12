"""
Finish → Declaration → Resolution → Complete — end of the audit lifecycle.

run_finish_complete() creates a fresh Complete/Dynamic audit, sets it up, counts
the `fc_counts` sheet with A_SA and then runs finish_complete_flow(), which drives
the owner's side of the flow and cross-checks every screen. Each step is its own
file in audit/:

  1. Stock Audit > Finish audit > Audit Declaration (notes from `finish_flow`)
       -> finish_audit.py
  2. Audit Summary > Complete Audit > 3-step popup (force / unverified / resolution)
       -> complete_audit_popup.py
  3. Resolution actions (Accept / Recount / Investigate per `finish_flow`)
       -> resolution_actions.py
  4. Recount sub-audit (static page) > Recount review (approve)
       -> recount.py
  5. Resolution summary > Adjustment report > Complete Audit > Audit History
       -> resolution_summary.py

Selectors, the `finish_flow` plan sheet and the navigation helpers shared by the
steps are in finish_common.py. The names below are also imported from this module by
Audit.py, e2e_*.py, settings_tests.py, summary_page_tests.py and stock_audit_checks.py.

The audit is closed for good by the last step, which is why a new one is made per run.
"""
from datetime import datetime

from audit.finish_common import (  # noqa: F401  (re-exported for the modules above)
    DECLARATION, FINISH_BTN, FLOW_POPUP, STATIC_AUDIT, SUMMARY, SWAL,
    _audit_list, _close_guide, _confirm_swal, _entry, _list_row, _list_status, _open_audit, _pick, _row,
    load_finish_plan,
)
from audit.finish_audit import step_declaration                                  # 1
from audit.complete_audit_popup import _enter_resolution, step_start_resolution  # 2  # noqa: F401
from audit.resolution_actions import step_resolution_actions                     # 3
from audit.recount import step_recount, step_recount_review                      # 4
from audit.resolution_summary import (                                           # 5  # noqa: F401
    _go_to_resolution_summary, _matched_codes, st_codes, step_complete, step_resolution_summary,
    watch_adjustment_context,
)
from audit.stock_audit_checks import Results


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
