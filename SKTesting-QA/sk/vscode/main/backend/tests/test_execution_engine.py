"""Regression tests for module selection and group gating (services/execution_engine.py)."""

import threading

import pytest

from backend.services import execution_engine as engine
from backend.services.execution_engine import (
    NoModulesEnabled,
    _disable_modules_in_off_groups,
    execute_run,
)

IDX6_FLAGS = ("run_create_audit", "run_create_Ad_hoc_Audit", "run_timezone", "run_update_audit")


class _NoStartThread:
    """Stand-in for threading.Thread so execute_run never launches a real browser run."""

    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        pass


@pytest.fixture
def no_thread(monkeypatch):
    monkeypatch.setattr(engine.threading, "Thread", _NoStartThread)


class _Log:
    def __init__(self):
        self.lines = []

    def log(self, msg):
        self.lines.append(msg)


def _run(cfg):
    return execute_run(
        cfg, "test", _Log(),
        state_lock=threading.Lock(),
        get_active_proc=lambda: None,
        set_active_proc=lambda p: None,
        set_running=lambda v: None,
    )


@pytest.mark.parametrize("group_on, module_on, expected", [
    (False, False, False),
    (False, True, False),   # group OFF: module must not execute even if its flag is set
    (True, False, False),
    (True, True, True),
])
def test_group_module_matrix(group_on, module_on, expected):
    cfg = {"run_Q_audit": group_on, "run_q_setting": module_on}
    _disable_modules_in_off_groups(cfg, IDX6_FLAGS)
    assert cfg["run_q_setting"] is expected


def test_group_off_clears_audit_plan_sub_flags():
    cfg = {"run_Audit_plan": False, "run_timezone": True, "run_update_audit": True,
           "run_create_Ad_hoc_Audit": True, "run_stock_audit2": True}
    _disable_modules_in_off_groups(cfg, IDX6_FLAGS)
    assert not any(cfg[f] for f in ("run_timezone", "run_update_audit",
                                     "run_create_Ad_hoc_Audit", "run_stock_audit2"))


def test_off_group_does_not_affect_other_groups():
    cfg = {"run_Q_audit": False, "run_inventory": True, "run_q_setting": True, "run_create_group": True}
    _disable_modules_in_off_groups(cfg, IDX6_FLAGS)
    assert cfg["run_q_setting"] is False
    assert cfg["run_create_group"] is True


def test_no_enabled_modules_is_rejected(no_thread):
    with pytest.raises(NoModulesEnabled):
        _run({"run_Q_audit": True, "run_Audit_plan": True, "run_inventory": True})


def test_enabled_module_in_off_group_is_rejected(no_thread):
    with pytest.raises(NoModulesEnabled):
        _run({"run_Q_audit": False, "run_q_setting": True, "MODULE_RUN_ORDER": [0]})


def test_non_dict_payload_is_rejected():
    with pytest.raises(ValueError):
        _run(None)


def test_string_sub_flags_are_coerced(no_thread):
    # "false" strings must not enable the Audit Plan step (idx 6).
    with pytest.raises(NoModulesEnabled):
        _run({"run_Audit_plan": True, "run_timezone": "false", "run_update_audit": "false"})


def test_run_order_and_skipping(no_thread):
    total, active = _run({
        "run_Q_audit": True, "run_inventory": True,
        "run_q_setting": True, "run_Q_SA": False, "run_create_group": True,
        "MODULE_RUN_ORDER": [13, 1, 0],
    })
    assert [flag for flag, _ in active] == ["run_create_group", "run_q_setting"]
    assert total == 2


def test_legacy_location_setup_key_is_honoured(no_thread):
    total, active = _run({"run_inventory": True, "run_locatio_setup": "true"})
    assert [flag for flag, _ in active] == ["run_location_setup"]


def test_create_group_runs_with_only_update_selected(no_thread):
    # Run Update is a sub-option (alt_flag) of the Create Group module (idx 13)
    total, active = _run({"run_inventory": True, "run_create_group": False, "run_update_group": True,
                          "MODULE_RUN_ORDER": [13]})
    assert [flag for flag, _ in active] == ["run_create_group"]
    assert total == 1


def test_create_and_update_count_as_one_module(no_thread):
    total, active = _run({"run_inventory": True, "run_create_group": True, "run_update_group": True})
    assert [flag for flag, _ in active] == ["run_create_group"]
    assert total == 1


def test_group_off_clears_update_group():
    cfg = {"run_inventory": False, "run_create_group": True, "run_update_group": True}
    _disable_modules_in_off_groups(cfg, IDX6_FLAGS)
    assert cfg["run_create_group"] is False
    assert cfg["run_update_group"] is False


def test_create_group_name_means_create_not_update(no_thread):
    cfg = {"run_inventory": True, "modules": ["Create_Group"]}
    total, active = _run(cfg)
    assert cfg["run_create_group"] is True
    assert not cfg.get("run_update_group")
    assert [flag for flag, _ in active] == ["run_create_group"]
