"""
Finish → Declaration → Resolution → Complete — end of the audit lifecycle.

Audit.py runs these as its steps 5-10 on Config.ap_audit_name, with its own settings
(one switch per step; FinishFlow keeps what the steps share). Audit.py creates, sets up
and counts the audit itself (run_create_Ad_hoc_Audit / run_setup_Audit / run_stock_audit /
run_stock_audit2). Each step is its own file in audit/:

  5. Stock audit (Auditor 1) > Finish audit > Audit Declaration (notes from `finish_flow`)
       -> finish_audit.py                                   (run_finish_audit1)
  6. Stock audit (Auditor 2) > Finish audit > Audit Declaration
       -> finish_audit.py                                   (run_finish_audit2)
  7. Audit Summary > Complete Audit > 3-step popup (force / unverified / resolution;
     Keep as Unverified or Move to Not Found = Config.complete_choice)
       -> complete_audit_popup.py                           (run_complete_audit)
  8. Resolution actions (Accept / Recount / Investigate per `finish_flow`)
       -> resolution_actions.py                             (run_resolution_actions)
  9. Recount sub-audit (static page) > Recount review (approve), only if step 8 chose Recount
       -> recount.py                                        (run_recount)
 10. Resolution summary > Adjustment report > Complete Audit > Audit History
       -> resolution_summary.py                             (run_resolution_summary)

Selectors, the `finish_flow` plan sheet and the navigation helpers shared by the
steps are in finish_common.py. The names below are also imported from this module by
Audit.py, settings_tests.py and stock_audit_checks.py.

The audit is closed for good by the last step.
"""
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


class FinishFlow:
    """What steps 5-10 share when Audit.py runs them one by one: the `finish_flow` plan, the PASS/FAIL
    results and the state the later steps read (declared notes, summary, actions, ...). Each method runs
    one step with Audit.py's settings as they are, on Config.ap_audit_name."""

    def __init__(self, Config):
        self.plan = load_finish_plan(Config)
        self.res, self.st = Results(), {}
        self._watched = None

    def _watch(self, page):
        # the Resolution summary loads the adjustment context on arrival: listen on the page in use
        if self._watched is not page:
            watch_adjustment_context(page, self.st)
            self._watched = page

    def finish_audit(self, page, Config, who):                       # steps 5 / 6
        """Stock audit > Finish audit > Audit Declaration as the logged-in auditor (notes from finish_flow).
        The declarations of both auditors are kept together for step 7's carry-over check."""
        declaration, declared = dict(self.st.get("declaration", {})), dict(self.st.get("declared", {}))
        self.res.section(f"Declaration ({who})", step_declaration, page, Config, self.res, self.plan, self.st)
        self.st["declaration"] = {**declaration, **self.st.get("declaration", {})}
        self.st["declared"] = {**declared, **self.st.get("declared", {})}

    def complete_audit(self, page, Config):                          # step 7
        self._watch(page)
        self.res.section("Start resolution", step_start_resolution, page, Config, self.res, self.st)

    def resolution_actions(self, page, Config):                      # step 8
        self._watch(page)
        self.res.section("Resolution actions", step_resolution_actions, page, Config, self.res, self.plan, self.st)

    def recount(self, page, Config):                                 # step 9
        if "Recount" not in self.st.get("actions", {}).values():
            print(" recount skipped: no Recount action in step 8")
            return
        self._watch(page)
        self.res.section("Recount sub-audit", step_recount, page, Config, self.res, self.plan, self.st)
        self.res.section("Recount review", step_recount_review, page, Config, self.res, self.plan, self.st)

    def resolution_summary(self, page, Config):                      # step 10
        self._watch(page)
        self.res.section("Resolution summary", step_resolution_summary, page, Config, self.res, self.plan, self.st)
        self.res.section("Complete audit", step_complete, page, Config, self.res, self.st)

    def report(self, Config) -> bool:
        return self.res.report(f"FINISH → RESOLUTION → COMPLETE — {Config.ap_audit_name}")
