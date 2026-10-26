"""The Create Group workflow uses the run's own Config (the UI values) and only the selected sub-options."""

from backend.workflows import create_group as create_wf


class RunConfig:
    group_name = "UI_Group"
    run_create_group = False
    run_update_group = True


def _record(monkeypatch):
    calls = []
    monkeypatch.setattr(create_wf, "_create_group", lambda page, cfg: calls.append(("create", cfg)))
    monkeypatch.setattr(create_wf, "_update_group", lambda page, cfg: calls.append(("update", cfg)))
    return calls


def test_create_group_runs_only_the_selected_sub_options(monkeypatch):
    calls = _record(monkeypatch)
    create_wf.create_group(None, RunConfig)
    assert calls == [("update", RunConfig)]


def test_create_runs_before_update(monkeypatch):
    calls = _record(monkeypatch)
    both = type("Both", (RunConfig,), {"run_create_group": True})
    create_wf.create_group(None, both)
    assert calls == [("create", both), ("update", both)]
