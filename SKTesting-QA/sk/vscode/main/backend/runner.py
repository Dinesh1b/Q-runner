"""
runner.py — Automation Entry Point.

Replaces the old main.py. Uses module_registry for dynamic workflow loading
instead of 17 hardcoded imports.
"""

import os
import sys
import importlib
import importlib.util
from pathlib import Path

# Ensure UTF-8 output encoding across platforms (prevents Windows cp1252 charmap errors)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root is on sys.path
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from playwright.sync_api import sync_playwright

from backend.pages.login_page import login
from backend.shared.timezone_helper import timezone
from backend.models.module_registry import get_all_modules, get_flag_to_idx_map
def _load_runtime_config():
    """
    Load per-run config from a generated file when provided.
    Falls back to backend.Config for static/default execution paths.
    """
    cfg_path = os.getenv("QA_RUNNER_CONFIG_PATH", "").strip()
    if cfg_path:
        spec = importlib.util.spec_from_file_location("qa_runner_runtime_config", cfg_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load runtime config from: {cfg_path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.Config

    from backend.Config import Config as DefaultConfig
    return DefaultConfig


Config = _load_runtime_config()


def _load_workflow(workflow_ref: str):
    """
    Dynamically import a workflow function from modules.json 'workflow' field.
    E.g. 'q_setting.Q_setting' → import backend.workflows.q_setting, getattr(mod, 'Q_setting')
    """
    mod_path, func_name = workflow_ref.rsplit(".", 1)
    try:
        mod = importlib.import_module(f"backend.workflows.{mod_path}")
    except ModuleNotFoundError as exc:
        workflows_dir = Path(_HERE) / "workflows"
        wanted = f"{mod_path}.py".lower()
        for candidate in workflows_dir.glob("*.py"):
            if candidate.name.lower() == wanted:
                mod = importlib.import_module(f"backend.workflows.{candidate.stem}")
                break
        else:
            raise exc
    return getattr(mod, func_name)


FLAG_TO_IDX = get_flag_to_idx_map()
DEFAULT_ORDER = list(range(16))


def _enabled_order():
    raw_order = getattr(Config, "MODULE_RUN_ORDER", []) or []
    order = []
    for item in raw_order:
        if isinstance(item, int):
            idx = item
        elif isinstance(item, str):
            idx = FLAG_TO_IDX.get(item)
            if idx is None:
                try:
                    idx = int(item)
                except ValueError:
                    idx = None
        else:
            idx = None
        if idx is not None and idx not in order:
            order.append(idx)
    if not order:
        order = DEFAULT_ORDER[:]
    return [idx for idx in order if _is_enabled(idx)]


def _is_enabled(idx):
    """Check if module at given index is enabled in Config."""
    all_modules = get_all_modules()
    for m in all_modules:
        if m["idx"] == idx:
            flag = m["flag"]
            enabled = bool(getattr(Config, flag, False))
            # Special case: idx 6 can be either audit_plan or ad_hoc
            if m.get("alt_flag"):
                enabled = enabled or bool(getattr(Config, m["alt_flag"], False))
            if idx == 6:
                enabled = enabled or bool(getattr(Config, "run_timezone", False)) \
                                   or bool(getattr(Config, "run_update_audit", False))
            return enabled
    return False


PASSED, FAILED, SKIPPED = "PASSED", "FAILED", "SKIPPED"


def _run_isolated(fn):
    """
    Run one module so that its failure cannot stop the modules after it.
    Returns (status, detail). Workflows that call sys.exit() or return False count as failed.
    """
    try:
        result = fn()
    except SystemExit as e:
        if e.code in (None, 0):
            return PASSED, ""
        return FAILED, f"exited with code {e.code}"
    except Exception as e:
        import traceback
        traceback.print_exc()
        return FAILED, f"{type(e).__name__}: {e}"
    if result is False:
        return FAILED, "workflow reported failure"
    return PASSED, ""


def _print_summary(results):
    print("─" * 52)
    counts = {s: sum(1 for _, st, _ in results if st == s) for s in (PASSED, FAILED, SKIPPED)}
    print(f"[SUMMARY] passed={counts[PASSED]} failed={counts[FAILED]} skipped={counts[SKIPPED]}")
    for name, status, detail in results:
        print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))


def main():
    all_modules = get_all_modules()
    # Build module index → definition lookup
    idx_to_module = {m["idx"]: m for m in all_modules}
    results = []

    with sync_playwright() as p:
        browser, page = None, None
        current_session = None

        def close_session():
            nonlocal browser, page, current_session
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass
            browser, page, current_session = None, None, None

        def ensure_session(session_type):
            nonlocal browser, page, current_session
            if current_session == session_type and page is not None and not page.is_closed():
                return

            if browser:
                print(f"Switching session to: {session_type}")
            close_session()

            cred_email = Config.email if session_type == "auditor1" else Config.email2
            cred_pass = Config.password if session_type == "auditor1" else Config.password2

            print(f"Logging in ({session_type})...")
            browser, page = login(
                p,
                browser_name=Config.browsername,
                environment=Config.environments,
                email=cred_email,
                password=cred_pass,
                company_name=getattr(Config, "company_name", None),
            )
            page.set_default_timeout(45000)
            current_session = session_type

        def run_create_audit():
            if Config.Audit_mode == "Ad_hoc":
                wf = _load_workflow("ad_hoc_audit.Ad_hoc_Audit")
                wf(page, Config)
                return
            if Config.Audit_mode == "Audit_plan":
                if Config.run_timezone and Config.frequency.lower() != "manual":
                    timezone(page)
                if Config.run_create_audit:
                    wf = _load_workflow("audit_plan.create_audit")
                    wf(page, Config)
                if Config.run_update_audit:
                    wf = _load_workflow("audit_plan_update_ui.update_audit")
                    wf(page, Config)
                return

        def run_one(idx, mod_def):
            # Determine session
            ensure_session(mod_def.get("session", "auditor1"))

            # Special case: idx 6 has Audit Plan / Ad-hoc branching
            if idx == 6:
                return run_create_audit()
            wf_func = _load_workflow(mod_def["workflow"])
            # Some workflows take (page, Config), some take just (page)
            # Location setup (idx 14) only takes page
            if idx == 14:
                return wf_func(page)
            return wf_func(page, Config)

        try:
            order = _enabled_order()
            for idx in order:
                mod_def = idx_to_module.get(idx)
                if not mod_def:
                    continue

                print(f"Running module index: {idx} ({mod_def['display']})")
                status, detail = _run_isolated(lambda: run_one(idx, mod_def))
                results.append((mod_def["display"], status, detail))

                if status == FAILED:
                    print(f"[FAIL] {mod_def['display']}: {detail} — continuing with next module")
                    # Start the next module from a clean, freshly logged-in browser.
                    close_session()

            for m in all_modules:
                if m["idx"] not in order:
                    results.append((m["display"], SKIPPED, "not enabled"))
        finally:
            close_session()

    _print_summary(results)
    if any(status == FAILED for _, status, _ in results):
        print("Automation completed with failures.")
        sys.exit(1)
    print("Automation completed successfully.")


if __name__ == "__main__":
    main()
