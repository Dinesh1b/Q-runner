"""A failing module must not stop the modules after it (backend/runner.py)."""

import sys

import pytest

from backend import runner


def test_isolated_exception_is_failed():
    def boom():
        raise RuntimeError("selector not found")
    status, detail = runner._run_isolated(boom)
    assert status == runner.FAILED
    assert "selector not found" in detail


@pytest.mark.parametrize("code, expected", [(1, runner.FAILED), (0, runner.PASSED), (None, runner.PASSED)])
def test_isolated_sys_exit(code, expected):
    status, _ = runner._run_isolated(lambda: sys.exit(code))
    assert status == expected


def test_isolated_false_result_is_failed():
    assert runner._run_isolated(lambda: False)[0] == runner.FAILED
    assert runner._run_isolated(lambda: None)[0] == runner.PASSED


class _FakePage:
    def is_closed(self):
        return False

    def set_default_timeout(self, ms):
        pass


class _FakeBrowser:
    closed = 0

    def close(self):
        _FakeBrowser.closed += 1


class _FakePlaywright:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_main_continues_after_failed_module(monkeypatch, capsys):
    calls = []
    logins = []

    def fake_login(p, **kwargs):
        logins.append(kwargs)
        return _FakeBrowser(), _FakePage()

    def fake_load_workflow(ref):
        def wf(page, config):
            calls.append(ref)
            if ref.startswith("q_setting"):
                raise RuntimeError("module 0 broke")
        return wf

    monkeypatch.setattr(runner, "sync_playwright", lambda: _FakePlaywright())
    monkeypatch.setattr(runner, "login", fake_login)
    monkeypatch.setattr(runner, "_load_workflow", fake_load_workflow)
    monkeypatch.setattr(runner, "_enabled_order", lambda: [0, 1])

    with pytest.raises(SystemExit) as exc:
        runner.main()

    assert exc.value.code == 1
    assert calls == ["q_setting.Q_setting", "q_sa.Q_SA"]  # module 1 still ran
    assert len(logins) == 2  # fresh session after the failure
    assert "company_name" in logins[0]
    out = capsys.readouterr().out
    assert "[FAILED] Q_Setting" in out
    assert "[PASSED] Stock Audit A1" in out
    assert "[SKIPPED]" in out
