"""Regression tests for the generated runtime Config (services/config_builder.py)."""

from backend.services.config_builder import build_config_py

BS = chr(92)  # backslash


def _load(cfg):
    ns = {}
    exec(compile(build_config_py(cfg), "runtime_config", "exec"), ns)
    return ns["Config"]


def test_default_config_compiles():
    config = _load({})
    assert config.run_q_setting is False
    assert config.MODULE_RUN_ORDER == []


def test_strings_with_quotes_and_backslashes_are_escaped():
    password = 'p"a' + BS + "ss\nimport os"
    config = _load({"USE_CUSTOM_LOGIN": True, "email": "user" + BS, "password": password})
    assert config.password == password
    assert config.email == "user" + BS


def test_injection_attempt_stays_a_string():
    payload = '"; import os; os.system("echo pwned"); x = "'
    config = _load({"audit_name": payload})
    assert config.audit_name == payload


def test_blank_or_invalid_numbers_fall_back_to_defaults():
    config = _load({"aud_qty1": "", "Day_s": "abc", "Item_CP": "12.5", "DEFAULT_TIMEOUT": "7000"})
    assert config.aud_qty1 == 0
    assert config.Day_s == 30
    assert config.Item_CP == 12.5
    assert config.DEFAULT_TIMEOUT == 7000


def test_zero_quantity_is_preserved():
    config = _load({"audited_qty1": 0, "audited_qty2": 0})
    assert config.audited_qty1 == 0
    assert config.audited_qty2 == 0


def test_auditor2_table_flag_matches_modules_json():
    # modules.json idx 10 uses flag run_A_as_table; the runner reads that exact name.
    assert _load({"run_A_as_table": True}).run_A_as_table is True
    assert _load({}).run_A_as_table is False


def test_frequency_is_written():
    assert _load({"frequency": "Weekly"}).frequency == "Weekly"
