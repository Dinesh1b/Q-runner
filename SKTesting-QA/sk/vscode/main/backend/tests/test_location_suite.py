"""Tests for the Warehouse test suite in inventory/location.py (no browser: the page work is replaced by fakes)."""

import pytest

from inventory import location


class Cfg:
    pass


def make_cfg(**values):
    return type("Cfg", (Cfg,), values)


@pytest.fixture
def calls(monkeypatch):
    seen = []
    monkeypatch.setattr(location, "add_locations", lambda page, cfg: seen.append("setup"))
    monkeypatch.setattr(location, "run_warehouse_tests", lambda page, cfg: seen.append("tests") or False)
    return seen


def test_settings_only_adds_locations_by_default(calls):
    assert location.settings(None, make_cfg()) is None
    assert calls == ["setup"]


def test_settings_runs_the_tests_and_returns_their_result(calls):
    assert location.settings(None, make_cfg(ls_run_setup=False, ls_run_tests=True)) is False
    assert calls == ["tests"]


def test_all_forty_cases_are_registered_once():
    ids = [c[0] for c in location.WAREHOUSE_CASES]
    assert ids == [f"WH_{i:03d}" for i in range(1, 41)]
    groups = [c[1] for c in location.WAREHOUSE_CASES]
    assert (groups.count("functional"), groups.count("validation"), groups.count("ui")) == (20, 10, 10)


def test_cases_are_selected_by_group_and_id():
    ids = lambda cfg: [c[0] for c in location.selected_cases(cfg)]
    assert len(ids(make_cfg())) == 40
    assert ids(make_cfg(ls_test_groups=["validation"])) == [f"WH_{i:03d}" for i in range(21, 31)]
    assert ids(make_cfg(ls_test_cases=[" wh_007", "WH_031"])) == ["WH_007", "WH_031"]
    assert ids(make_cfg(ls_test_groups=["ui"], ls_test_cases=["WH_007", "WH_031"])) == ["WH_031"]


class FakePage:
    def screenshot(self, path, full_page=False):
        with open(path, "wb") as f:
            f.write(b"png")


class FakeRun:
    cleaned = False

    def __init__(self, page, prefix):
        self.page = page

    def fresh(self):
        pass

    def cleanup(self):
        FakeRun.cleaned = True
        return 2


def test_suite_reports_pass_fail_skip_and_writes_the_report(monkeypatch, tmp_path, capsys):
    def passes(run):
        return "fine"

    def fails(run):
        assert False, "the row is missing"

    def skips(run):
        raise location.Skip("needs Advance")

    monkeypatch.setattr(location, "ROOT_DIR", str(tmp_path))
    monkeypatch.setattr(location, "open_warehouse", lambda page: None)
    monkeypatch.setattr(location, "WarehouseRun", FakeRun)
    monkeypatch.setattr(location, "WAREHOUSE_CASES", [("WH_A", "functional", "Passes", passes),
                                                     ("WH_B", "validation", "Fails", fails),
                                                     ("WH_C", "ui", "Skips", skips)])

    assert location.run_warehouse_tests(FakePage(), make_cfg()) is False

    out = capsys.readouterr().out
    assert "[PASS] WH_A Passes — fine" in out
    assert "[FAIL] WH_B Fails — the row is missing" in out
    assert "[SKIP] WH_C Skips — needs Advance" in out
    assert "Warehouse tests: passed=1 failed=1 skipped=1" in out
    assert FakeRun.cleaned
    [report_dir] = (tmp_path / "reports" / "warehouse").iterdir()
    assert (report_dir / "warehouse_report.html").is_file()
    assert (report_dir / "WH_B.png").is_file()          # screenshot of the failed case only
    assert not (report_dir / "WH_A.png").exists()


def test_suite_without_failures_returns_true(monkeypatch, tmp_path):
    monkeypatch.setattr(location, "ROOT_DIR", str(tmp_path))
    monkeypatch.setattr(location, "open_warehouse", lambda page: None)
    monkeypatch.setattr(location, "WarehouseRun", FakeRun)
    monkeypatch.setattr(location, "WAREHOUSE_CASES", [("WH_A", "functional", "Passes", lambda run: None)])
    assert location.run_warehouse_tests(FakePage(), make_cfg(ls_test_cleanup=False)) is True
