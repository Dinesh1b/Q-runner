"""API tests using Flask's test client. No real automation run is started."""

import pytest

from backend.app import create_app
from backend.blueprints import runner as runner_bp


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    runner_bp.running = False
    runner_bp.current_run_id = None
    return app.test_client()


def test_api_modules_returns_registry(client):
    res = client.get("/api/modules")
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["modules"]) == 16
    assert len(data["groups"]) == 3
    # No module may be enabled by default.
    assert not any(m.get("enabled") for m in data["modules"])


def test_run_rejects_non_json_body_without_locking(client):
    res = client.post("/run", data="not json", content_type="text/plain")
    assert res.status_code == 400
    assert runner_bp.running is False


def test_run_with_no_enabled_modules_is_400_and_not_locked(client):
    res = client.post("/run", json={"run_Q_audit": True, "run_q_setting": False})
    assert res.status_code == 400
    assert "No modules enabled" in res.get_json()["error"]
    assert runner_bp.running is False


def test_run_lock_is_released_when_start_fails(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(runner_bp, "execute_run", boom)
    assert client.post("/run", json={}).status_code == 500
    # A follow-up run must not be blocked with 409.
    assert client.post("/run", json={}).status_code == 500
    assert runner_bp.running is False


def test_stale_run_cannot_clear_newer_run_state():
    runner_bp.running = True
    runner_bp.current_run_id = "new"
    runner_bp._set_running(False, "old")
    assert runner_bp.running is True
    runner_bp._set_running(False, "new")
    assert runner_bp.running is False
