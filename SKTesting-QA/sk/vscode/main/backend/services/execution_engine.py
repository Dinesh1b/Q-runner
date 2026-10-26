"""
execution_engine.py — Module orchestration.

Manages the execution of automation modules in a background thread.
Uses module_registry instead of hardcoded MODULE_KEYS.
"""

import os
import sys
import json
import time
import threading
import subprocess
import tempfile

from backend.models.module_registry import (
    get_all_modules,
    get_module_keys,
    get_idx_to_flag_map,
    get_flag_to_idx_map,
)

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RUNTIME_CFG_DIR = os.path.join(tempfile.gettempdir(), "qaudit_runner")


def _write_runtime_config(cfg: dict, rid: str, suffix: str, build_config_py):
    os.makedirs(_RUNTIME_CFG_DIR, exist_ok=True)
    runtime_path = os.path.join(_RUNTIME_CFG_DIR, f"runtime_config_{rid}_{suffix}.py")
    with open(runtime_path, "w", encoding="utf-8") as fp:
        fp.write(build_config_py(cfg))
    return runtime_path


def _alt_flag_maps():
    """
    {main flag: alt_flag} and {alt_flag: main flag} for modules whose alt_flag is a sub-option
    (Create Group: run_create_group / run_update_group). idx 6 keeps its own special handling.
    """
    flag_to_alt = {m["flag"]: m["alt_flag"] for m in get_all_modules() if m.get("alt_flag") and m["idx"] != 6}
    return flag_to_alt, {alt: flag for flag, alt in flag_to_alt.items()}


def _default_active_modules(cfg, MODULE_KEYS, idx6_flags, flag_to_name):
    """Build active_modules when no explicit MODULE_RUN_ORDER is given."""
    flag_to_alt, alt_to_flag = _alt_flag_maps()
    active_modules = []
    idx6_seen = False
    seen = set()
    for k, n in MODULE_KEYS:
        if k in idx6_flags:
            if idx6_seen:
                continue
            if any(cfg.get(f) for f in idx6_flags):
                idx6_seen = True
                active_modules.append(("__idx6__", flag_to_name.get("run_create_audit", "Audit_Plan")))
            continue
        # A module with sub-options runs if either flag is set, and is listed once under its main flag
        flag = alt_to_flag.get(k, k)
        if flag in seen:
            continue
        if cfg.get(flag) or cfg.get(flag_to_alt.get(flag)):
            seen.add(flag)
            active_modules.append((flag, n))
    return active_modules


GROUP_FLAGS = {0: "run_Q_audit", 1: "run_Audit_plan", 2: "run_inventory"}


def _disable_modules_in_off_groups(cfg, idx6_flags):
    """A group switched OFF means none of its modules may run, whatever their own flags say."""
    for m in get_all_modules():
        group_flag = GROUP_FLAGS.get(m["group"])
        if group_flag not in cfg or _is_true(cfg[group_flag]):
            continue
        flags = [m["flag"]] + ([m["alt_flag"]] if m.get("alt_flag") else [])
        if m["idx"] == 6:
            flags += idx6_flags
        for f in flags:
            cfg[f] = False


def _is_true(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes", "on")
    return bool(v)


class NoModulesEnabled(ValueError):
    """Raised when a run request has no enabled module to execute."""


def kill_process_tree(proc):
    """Terminate a runner process together with its Playwright driver / browser children."""
    if proc is None or proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True,
                timeout=15,
            )
        else:
            proc.terminate()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def execute_run(cfg, rid, logger, state_lock, get_active_proc, set_active_proc, set_running,
                is_cancelled=lambda: False):
    """
    Prepare and launch the automation run in a background thread.
    Returns (total_modules, active_modules_list).
    Raises ValueError for an invalid payload and NoModulesEnabled when nothing would run.
    """
    if not isinstance(cfg, dict):
        raise ValueError("Run configuration must be a JSON object")

    MODULE_KEYS = get_module_keys()
    idx_to_flag = get_idx_to_flag_map()
    flag_to_idx = get_flag_to_idx_map()
    name_to_flag = {name: key for key, name in MODULE_KEYS}
    flag_to_name = {key: name for key, name in MODULE_KEYS}
    flag_to_alt, alt_to_flag = _alt_flag_maps()
    # For a module with sub-options, its name means its main flag (run_create_group), not the alt_flag
    name_to_flag.update({flag_to_name[flag]: flag for flag in flag_to_alt})

    # Special case: idx 6 covers Audit_Plan (timezone/create/update) OR Ad_hoc
    idx6_flags = ("run_create_audit", "run_create_Ad_hoc_Audit", "run_timezone", "run_update_audit")

    # Handle legacy key: run_locatio_setup → run_location_setup
    if "run_locatio_setup" in cfg and "run_location_setup" not in cfg:
        cfg["run_location_setup"] = cfg.pop("run_locatio_setup")

    # Coerce all module flags (and idx 6 sub-flags) to real booleans early.
    for key in [k for k, _ in MODULE_KEYS] + list(idx6_flags):
        if key in cfg:
            cfg[key] = _is_true(cfg.get(key))

    # Normalise cfg.modules → boolean flags (backward compat)
    modules_list = cfg.get("modules")
    if modules_list and isinstance(modules_list, list):
        for item in modules_list:
            if isinstance(item, str) and item in name_to_flag:
                cfg[name_to_flag[item]] = True

    _disable_modules_in_off_groups(cfg, idx6_flags)

    def _idx6_enabled(cfg: dict) -> bool:
        return any(cfg.get(f) for f in idx6_flags)

    # Build active_modules in drag priority order
    order = cfg.get("MODULE_RUN_ORDER")
    active_modules: list[tuple[str, str]] = []

    if order and isinstance(order, list):
        seen: set[str] = set()
        for item in order:
            flag = None
            if isinstance(item, int):
                if item == 6:
                    if item in seen or not _idx6_enabled(cfg):
                        continue
                    seen.add(item)
                    active_modules.append(("__idx6__", flag_to_name.get("run_create_audit", "Audit_Plan")))
                    continue
                else:
                    flag = idx_to_flag.get(item)
            elif isinstance(item, str):
                flag = item if item.startswith("run_") else name_to_flag.get(item)
                flag = alt_to_flag.get(flag, flag)

            if not flag or flag in seen:
                continue
            seen.add(flag)

            # A module with sub-options runs if either of its flags is set
            if cfg.get(flag) or cfg.get(flag_to_alt.get(flag)):
                active_modules.append((flag, flag_to_name.get(flag, flag)))

        if not active_modules:
            active_modules = _default_active_modules(cfg, MODULE_KEYS, idx6_flags, flag_to_name)
    else:
        active_modules = _default_active_modules(cfg, MODULE_KEYS, idx6_flags, flag_to_name)

    if not active_modules:
        raise NoModulesEnabled("No modules enabled — enable at least one module in an active group")

    total = len(active_modules)

    def _launch(launch_cmd, env):
        """Start the runner process unless the run was stopped; returns None when cancelled."""
        if is_cancelled():
            return None
        proc = subprocess.Popen(
            launch_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=_BASE,
            env=env,
            bufsize=1,
        )
        with state_lock:
            set_active_proc(proc)
            cancelled = is_cancelled()
        if cancelled:
            # /stop arrived while the process was being created.
            kill_process_tree(proc)
            return None
        return proc

    def execute():
        from backend.services.db import db_start_run, db_insert_step, db_finish_run
        from backend.services.config_builder import build_config_py
        terminal_marker = "__ERROR__"

        try:
            db_start_run(rid)
            logger.log(json.dumps({
                "type": "init",
                "run_id": rid,
                "total": total,
                "modules": [n for _, n in active_modules],
            }))

            single_process = os.getenv("QA_RUNNER_SINGLE_PROCESS", "1").strip().lower() in ("1", "true", "yes", "on")

            if single_process:
                cfg["MODULE_RUN_ORDER"] = [6 if flag == "__idx6__" else flag for flag, n in active_modules]
                runtime_cfg_path = _write_runtime_config(cfg, rid, "full", build_config_py)

                logger.log("\n[INFO]  Launching: Full flow (single process)")
                logger.log("─" * 52)

                runner_path = os.path.join(_BASE, "runner.py")
                launch_cmd = [sys.executable, "-u", runner_path]

                env = dict(os.environ)
                env["PYTHONUNBUFFERED"] = "1"
                env["PYTHONIOENCODING"] = "utf-8"
                env["PYTHONUTF8"] = "1"
                env["QA_RUNNER_CONFIG_PATH"] = runtime_cfg_path

                proc = _launch(launch_cmd, env)
                if proc is None:
                    db_finish_run(rid, "stopped")
                    return

                for line in iter(proc.stdout.readline, ""):
                    stripped = line.rstrip()
                    logger.log(stripped)

                proc.wait()

                if is_cancelled():
                    db_finish_run(rid, "stopped")
                    return

                if proc.returncode != 0:
                    logger.log(f" Run finished with failures (exit {proc.returncode})")
                    db_insert_step(rid, "Full flow", "error", 100)
                    db_finish_run(rid, "error")
                    return

                db_insert_step(rid, "Full flow", "done", 100)
            else:
                done_count = 0
                failed_modules = []
                for flag, mname in active_modules:
                    module_cfg = dict(cfg)
                    for k, _ in MODULE_KEYS:
                        if module_cfg.get(k):
                            module_cfg[k] = False

                    if flag == "__idx6__":
                        # Audit Plan sequence: preserve the timezone/create/update
                        # sub-toggles as configured instead of forcing a single flag.
                        for f in idx6_flags:
                            module_cfg[f] = bool(cfg.get(f))
                        target_idx = 6
                    elif flag in flag_to_alt:
                        # Sub-options (Create Group: create / update) stay as configured
                        # instead of forcing the main flag on.
                        module_cfg[flag] = bool(cfg.get(flag))
                        module_cfg[flag_to_alt[flag]] = bool(cfg.get(flag_to_alt[flag]))
                        target_idx = flag_to_idx.get(flag)
                    else:
                        module_cfg[flag] = True
                        target_idx = flag_to_idx.get(flag)

                    module_cfg["MODULE_RUN_ORDER"] = [target_idx] if target_idx is not None else []
                    runtime_cfg_path = _write_runtime_config(
                        module_cfg,
                        rid,
                        str(target_idx if target_idx is not None else flag),
                        build_config_py,
                    )

                    logger.log(f"\n[INFO]  Launching: {mname}")
                    logger.log("─" * 52)

                    runner_path = os.path.join(_BASE, "runner.py")
                    launch_cmd = [sys.executable, "-u", runner_path]

                    env = dict(os.environ)
                    env["PYTHONUNBUFFERED"] = "1"
                    env["PYTHONIOENCODING"] = "utf-8"
                    env["PYTHONUTF8"] = "1"
                    env["QA_RUNNER_CONFIG_PATH"] = runtime_cfg_path

                    proc = _launch(launch_cmd, env)
                    if proc is None:
                        db_finish_run(rid, "stopped")
                        return

                    module_failed = False
                    for line in iter(proc.stdout.readline, ""):
                        stripped = line.rstrip()
                        logger.log(stripped)
                        sl = stripped.lower()
                        if ("playwright error" in sl
                                or "unexpected error" in sl
                                or ("error" in sl and "audit name already exists" in sl)):
                            module_failed = True

                    proc.wait()

                    if is_cancelled():
                        db_finish_run(rid, "stopped")
                        return

                    done_count = min(done_count + 1, total)
                    pct = int(done_count / total * 100)

                    # A failed module is recorded and the remaining modules still run.
                    step_status = "done"
                    if proc.returncode != 0 or module_failed:
                        logger.log(f"[FAIL]  {mname} failed (exit {proc.returncode}) — continuing with next module")
                        failed_modules.append(mname)
                        step_status = "error"

                    logger.log(json.dumps({
                        "type": "progress",
                        "step": mname,
                        "progress": pct,
                        "done": done_count,
                        "total": total,
                    }))

                    db_insert_step(rid, mname, step_status, pct)

                if failed_modules:
                    logger.log("─" * 52)
                    logger.log(f" Run finished with failures: {', '.join(failed_modules)}")
                    db_finish_run(rid, "error")
                    return

            logger.log("─" * 52)
            logger.log("[OK] Run completed successfully.")
            logger.log(json.dumps({
                "type": "progress",
                "progress": 100,
                "done": total,
                "total": total,
            }))
            db_finish_run(rid, "done")
            terminal_marker = "__DONE__"

        except Exception as e:
            logger.log(f"[ERROR] {e}")
            from backend.services.db import db_finish_run
            db_finish_run(rid, "error")
        finally:
            logger.log(terminal_marker)
            set_running(False)

    threading.Thread(target=execute, daemon=True).start()
    return total, active_modules
