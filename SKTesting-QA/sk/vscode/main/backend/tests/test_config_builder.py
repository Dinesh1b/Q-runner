"""Regression tests for the generated runtime Config (services/config_builder.py)."""

from backend.models.module_registry import get_all_modules
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


def test_update_group_flag_is_written():
    config = _load({"run_update_group": True})
    assert config.run_update_group is True
    assert config.run_inventory is True
    assert _load({}).run_update_group is False


def test_item_group_settings_are_written():
    payload = {
        "inv_accounting_mode": "Inventory Accounting Mode",
        "inv_costing_method": "Weighted Average",
        "inv_accounting_accounts": {"COGSAccountId": "Cost of Goods Sold (COGS)"},
        "inv_advanced_toggles": {"AllowDiscount": True, "EditSalePrice": False},
        "inv_enable_uom_conversions": False,
        "inv_primary_uom": "Bale",
        "inv_uom_value_type": "Decimal",
        "inv_secondary_uoms": [{"uom": "Box", "quantity": 12}],
        "inv_tertiary_uoms": [{"uom": "Pallet", "quantity": 2.5, "base": "Box"}],
        "inv_default_uom": "Box",
    }
    config = _load(payload)
    for key, value in payload.items():
        assert getattr(config, key[len("inv_"):]) == value, key


def test_item_group_settings_left_blank_are_skipped():
    config = _load({"inv_primary_uom": "", "inv_accounting_accounts": {}, "inv_secondary_uoms": [],
                    "inv_enable_uom_conversions": None})
    for key in ("accounting_mode", "accounting_accounts", "advanced_toggles", "enable_uom_conversions",
                "primary_uom", "secondary_uoms", "default_uom"):
        assert getattr(config, key) is None, key


def test_item_group_values_stay_plain_strings():
    payload = '"); import os; os.system("echo pwned"); ("'
    config = _load({"inv_accounting_accounts": {payload: payload},
                    "inv_secondary_uoms": [{"uom": payload, "quantity": float("nan")}]})
    assert config.accounting_accounts == {payload: payload}
    assert config.secondary_uoms == [{"uom": payload, "quantity": None}]


def test_location_setup_lists_are_written():
    config = _load({"ls_zones": "SA, SB", "ls_aisles": "A1,A2", "ls_bays": "B1", "ls_levels": ""})
    assert config.zones == ["SA", "SB"]
    assert config.aisles == ["A1", "A2"]
    assert config.bays == ["B1"]
    assert config.levels == ["L1", "L2", "L3", "L4", "L5"]  # blank falls back to the default


def test_location_setup_run_options_default_to_setup_only():
    config = _load({})
    assert config.ls_run_setup is True and config.ls_run_tests is False
    assert config.ls_test_groups == ["functional", "validation", "ui"]
    assert config.ls_test_cases == [] and config.ls_test_prefix == "QA" and config.ls_test_cleanup is True


def test_location_setup_run_options_are_written():
    config = _load({"ls_run_setup": False, "ls_run_tests": True, "ls_test_groups": ["validation"],
                    "ls_test_cases": "WH_021, WH_022", "ls_test_prefix": "T1", "ls_test_cleanup": False})
    assert config.ls_run_setup is False and config.ls_run_tests is True
    assert config.ls_test_groups == ["validation"]
    assert config.ls_test_cases == ["WH_021", "WH_022"]
    assert config.ls_test_prefix == "T1" and config.ls_test_cleanup is False


def test_every_module_flag_is_written():
    # A flag missing from the template is read as False by the runner and its module is silently skipped
    config = _load({})
    for module in get_all_modules():
        for flag in (module["flag"], module.get("alt_flag")):
            if flag:
                assert hasattr(config, flag), flag
