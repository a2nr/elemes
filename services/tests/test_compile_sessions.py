"""
Tests untuk proxy session interaktif di routes/compile.py.

Dijalankan di container backend (flask terpasang):
    podman exec -w /app -e PYTHONPATH=services lms-dev_elemes_1 \
        python -m pytest services/tests/test_compile_sessions.py -q

Di host tanpa flask, test di-skip otomatis (importorskip).
"""

import pytest

# Skip seluruh modul bila flask tidak tersedia (host tanpa deps backend)
pytest.importorskip("flask")

from unittest.mock import patch  # noqa: E402

from routes.compile import (  # noqa: E402
    compile_bp,
    create_compile_session,
    get_compile_session,
    send_compile_session_input,
    stop_compile_session,
    _anon_session_slot_path,
)

from app import create_app  # noqa: E402


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _files_payload():
    return {
        "language": "c",
        "files": [{"name": "main.c", "content": "int main(){return 0;}"}],
        "active_file": "main.c",
    }


# ── Unit: handler langsung dengan requests mock ─────────────────────


def test_create_session_forwards_files_without_token(client, monkeypatch):
    fake = _FakeResponse({"session_id": "sess-1", "status": "queued", "output": "", "cursor": 0}, 202)
    calls = {}

    def fake_post(url, json=None, timeout=None):
        calls["url"] = url
        calls["json"] = json
        return fake

    monkeypatch.setattr("routes.compile.requests.post", fake_post)

    resp = client.post(
        "/api/compile/sessions",
        json={**_files_payload(), "token": "valid-token"},
    )
    assert resp.status_code == 202
    body = resp.get_json()
    assert body["session_id"] == "sess-1"
    assert calls["url"].endswith("/sessions")
    assert calls["json"]["language"] == "c"
    assert calls["json"]["files"][0]["name"] == "main.c"
    assert "token" not in calls["json"]


def test_create_session_rejects_invalid_token(client, monkeypatch):
    monkeypatch.setattr("routes.compile.validate_token", lambda t: t == "valid-token")
    resp = client.post(
        "/api/compile/sessions",
        json={**_files_payload(), "token": "bad-token"},
    )
    assert resp.status_code == 401
    assert "Unauthorized" in resp.get_json()["error"]


def test_create_session_requires_files(client):
    resp = client.post("/api/compile/sessions", json={"language": "c", "files": []})
    assert resp.status_code == 400


def test_create_session_anonymous_acquires_slot(client, monkeypatch):
    fake = _FakeResponse({"session_id": "sess-anon", "status": "running", "output": "", "cursor": 0}, 202)

    monkeypatch.setattr("routes.compile.acquire_anon_slot", lambda: "/tmp/elemes_anon_queue/slot-1")

    def fake_post(url, json=None, timeout=None):
        return fake

    monkeypatch.setattr("routes.compile.requests.post", fake_post)
    monkeypatch.setattr("os.replace", lambda src, dst: None)

    resp = client.post("/api/compile/sessions", json=_files_payload())
    assert resp.status_code == 202
    assert resp.get_json()["session_id"] == "sess-anon"


def test_create_session_anonymous_full_429(client, monkeypatch):
    monkeypatch.setattr("routes.compile.acquire_anon_slot", lambda: None)
    resp = client.post("/api/compile/sessions", json=_files_payload())
    assert resp.status_code == 429
    assert "tunggu beberapa saat" in resp.get_json()["error"]


def test_get_session_forwards_cursor_and_releases_on_terminal(client, monkeypatch):
    fake = _FakeResponse(
        {"status": "exited", "output": "hi", "cursor": 5, "exit_code": 0, "error": None}, 200
    )
    calls = {}

    def fake_get(url, params=None, timeout=None):
        calls["params"] = params
        return fake

    monkeypatch.setattr("routes.compile.requests.get", fake_get)
    monkeypatch.setattr("routes.compile._release_anon_session_slot", lambda sid: None)

    resp = client.get("/api/compile/sessions/sess-1?cursor=5")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "exited"
    assert calls["params"] == {"cursor": "5"}


def test_get_session_touches_slot_when_active(client, monkeypatch):
    fake = _FakeResponse({"status": "running", "output": "", "cursor": 0, "error": None}, 200)
    monkeypatch.setattr("routes.compile.requests.get", lambda *a, **k: fake)
    touched = []
    monkeypatch.setattr("routes.compile._touch_anon_session_slot", lambda sid: touched.append(sid))

    resp = client.get("/api/compile/sessions/sess-1")
    assert resp.status_code == 200
    assert touched == ["sess-1"]


def test_send_input_forwards_text(client, monkeypatch):
    fake = _FakeResponse({"status": "running", "output": "", "cursor": 0, "error": None}, 200)
    calls = {}

    def fake_post(url, json=None, timeout=None):
        calls["url"] = url
        calls["json"] = json
        return fake

    monkeypatch.setattr("routes.compile.requests.post", fake_post)

    resp = client.post("/api/compile/sessions/sess-1/input", json={"text": "anggoro"})
    assert resp.status_code == 200
    assert calls["url"].endswith("/sessions/sess-1/input")
    assert calls["json"] == {"text": "anggoro"}


def test_stop_session_releases_slot(client, monkeypatch):
    fake = _FakeResponse({"status": "stopped", "error": None}, 200)
    monkeypatch.setattr("routes.compile.requests.delete", lambda *a, **k: fake)
    released = []
    monkeypatch.setattr("routes.compile._release_anon_session_slot", lambda sid: released.append(sid))

    resp = client.delete("/api/compile/sessions/sess-1")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "stopped"
    assert released == ["sess-1"]


def test_worker_unavailable_returns_502(client, monkeypatch):
    import requests as _requests

    def boom(*a, **k):
        raise _requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr("routes.compile.requests.post", boom)

    resp = client.post("/api/compile/sessions", json={**_files_payload(), "token": "valid-token"})
    assert resp.status_code == 502
    assert "Compiler service unavailable" in resp.get_json()["error"]


# ── Unit: helper slot path ──────────────────────────────────────────


def test_anon_session_slot_path_sanitizes():
    assert _anon_session_slot_path("abc-123").endswith("sess-abc-123")
    assert "/" not in _anon_session_slot_path("../evil")
    assert _anon_session_slot_path("../evil").endswith("sess-.._evil")


def test_routes_registered():
    app = create_app()
    urls = sorted(str(r) for r in app.url_map.iter_rules() if "/compile/sessions" in str(r))
    assert any(u.endswith("/compile/sessions") for u in urls)
    assert any("/compile/sessions/<session_id>" in u for u in urls)
    assert any("/compile/sessions/<session_id>/input" in u for u in urls)
