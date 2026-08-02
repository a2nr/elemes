"""Regression tests for compiler_worker app (Task 4).

Tests:
- Legacy /execute endpoint (backward compatible)
- Interactive session endpoints: POST /sessions, GET, POST input, DELETE stop
- Health endpoint
- Error responses: 404, 409, 429, 400, 500
"""
import os
import time
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app, get_session_mgr  # noqa: E402
import app as app_module  # noqa: E402
from session_manager import SessionManager  # noqa: E402

# Create Flask test client
client = create_app().test_client()


# ------------------------------------------------------------------
# Legacy batch endpoints
# ------------------------------------------------------------------


def test_legacy_execute_python():
    resp = client.post(
        "/execute",
        json={"code": 'print("halo")\n', "language": "python"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "halo" in data["output"]


def test_legacy_execute_c():
    code = 'int main() { printf("hai"); return 0; }\n'
    resp = client.post("/execute", json={"code": code, "language": "c"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "hai" in data["output"]


# ------------------------------------------------------------------
# Session endpoints
# ------------------------------------------------------------------


def _cleanup_all_sessions():
    """Best-effort cleanup of existing sessions before tests."""
    mgr = get_session_mgr()
    stats = mgr.stats()
    for _ in range(stats.get("active_sessions", 0)):
        try:
            mgr.stop(list(mgr._sessions.keys())[0])
        except Exception:
            break


def wait_for_output(client, session_id, text=None, timeout=10.0):
    """Poll GET until condition met or timeout."""
    cursor = 0
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/sessions/{session_id}?cursor={cursor}")
        assert resp.status_code == 200
        data = resp.get_json()
        got = data["output"]
        if text is None or text in got:
            return data, got
        cursor = data["cursor"]
        time.sleep(0.05)
    raise TimeoutError(f"timeout waiting for output; status={data.get('status')}, got={got!r}")


def test_session_create_returns_202_and_running():
    resp = client.post(
        "/sessions",
        json={
            "language": "python",
            "files": [{"name": "main.py", "content": 'print("start")\n'}],
        },
    )
    assert resp.status_code == 202
    data = resp.get_json()
    assert data["status"] in ("queued", "compiling", "running")
    assert len(data["session_id"]) >= 40


def test_session_poll_get_delta():
    resp = client.post(
        "/sessions",
        json={
            "language": "python",
            "files": [{"name": "main.py", "content": 'print("hello-world")\n'}],
        },
    )
    assert resp.status_code == 202
    sid = resp.get_json()["session_id"]
    data, got = wait_for_output(client, sid, "hello-world")
    assert data["status"] == "exited"
    assert data["exit_code"] == 0
    assert "hello-world" in got


def test_session_input_produces_halo():
    py_code = 'nama = input("Siapa nama kamu? ")\nprint(f"Halo, {nama}!")\n'
    resp = client.post(
        "/sessions",
        json={
            "language": "python",
            "files": [{"name": "main.py", "content": py_code}],
        },
    )
    assert resp.status_code == 202
    sid = resp.get_json()["session_id"]

    # Wait for prompt
    data, got = wait_for_output(client, sid, "Siapa nama kamu")
    assert data["status"] == "running"

    # Send input
    resp2 = client.post(
        f"/sessions/{sid}/input",
        json={"text": "Anggoro\n"},
    )
    assert resp2.status_code == 200

    # Wait for output
    data2, got2 = wait_for_output(client, sid, "Halo, Anggoro!")
    assert data2["status"] == "exited"
    assert "Halo, Anggoro!" in got2
    assert "EOFError" not in got2


def test_session_stop_is_idempotent():
    resp = client.post(
        "/sessions",
        json={
            "language": "python",
            "files": [
                {"name": "main.py", "content": 'import time\ntime.sleep(60)\n'}
            ],
        },
    )
    sid = resp.get_json()["session_id"]
    # Stop once
    resp1 = client.delete(f"/sessions/{sid}")
    assert resp1.status_code == 200

    # Stop again — should still succeed
    resp2 = client.delete(f"/sessions/{sid}")
    assert resp2.status_code == 200


def test_session_404_unknown():
    resp = client.get("/sessions/zzz_nonexistent_session_id_zzz")
    assert resp.status_code == 404


def test_session_input_409_not_running():
    # Create a session that exits immediately
    resp = client.post(
        "/sessions",
        json={
            "language": "python",
            "files": [{"name": "main.py", "content": 'print("done")\n'}],
        },
    )
    sid = resp.get_json()["session_id"]
    # Wait for exit
    wait_for_output(client, sid, "done")
    # Try to send input
    resp2 = client.post(
        f"/sessions/{sid}/input",
        json={"text": "x\n"},
    )
    assert resp2.status_code == 409


def test_session_429_capacity_full(monkeypatch):
    # Inject a manager with a small capacity to trigger 429 deterministically.
    orig_mgr = app_module._session_mgr

    tiny = SessionManager(max_sessions=5, autostart_sweeper=False,
                          terminal_retention=0.2)
    monkeypatch.setattr(app_module, "_session_mgr", tiny)
    sids = []
    try:
        for i in range(5):
            resp = client.post(
                "/sessions",
                json={
                    "language": "python",
                    "files": [{"name": "main.py", "content": 'import time\ntime.sleep(5)\n'}],
                },
            )
            assert resp.status_code == 202
            sids.append(resp.get_json()["session_id"])
        # Next one should fail with 429
        resp_bad = client.post(
            "/sessions",
            json={
                "language": "python",
                "files": [{"name": "main.py", "content": 'print("fail")\n'}],
            },
        )
        assert resp_bad.status_code == 429
    finally:
        for sid in sids:
            client.delete(f"/sessions/{sid}")
        monkeypatch.setattr(app_module, "_session_mgr", orig_mgr)
        tiny.shutdown()


def test_session_400_invalid_language():
    resp = client.post(
        "/sessions",
        json={
            "language": "fortran",
            "files": [{"name": "prog.f", "content": ""}],
        },
    )
    assert resp.status_code == 400


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "active_sessions" in data
    assert "limits" in data


# ------------------------------------------------------------------
# C interactive via REST
# ------------------------------------------------------------------


def test_c_session_with_header_include():
    files = [
        {
            "name": "main.c",
            "content": '#include <stdio.h>\n#include "foo.h"\nint main() {\n    printf("Hasil: %d\\n", tambah(7, 8));\n    return 0;\n}\n',
        },
        {
            "name": "foo.h",
            "content": "#ifndef FOO_H\n#define FOO_H\nstatic inline int tambah(int a, int b) { return a + b; }\n#endif\n",
        },
    ]
    resp = client.post("/sessions", json={"language": "c", "files": files})
    assert resp.status_code == 202
    sid = resp.get_json()["session_id"]
    data, got = wait_for_output(client, sid, "Hasil: 15")
    assert data["status"] == "exited"
    assert "Hasil: 15" in got


def test_c_compile_error_via_rest():
    files = [
        {
            "name": "bad.c",
            "content": "int main() { syntax error here too }\n",
        },
    ]
    resp = client.post("/sessions", json={"language": "c", "files": files})
    assert resp.status_code == 202
    sid = resp.get_json()["session_id"]
    data, got = wait_for_output(client, sid)
    assert data["status"] == "error"
    assert data["error"] == "compilation failed"
