"""Tests for session_manager.py — Tasks 1-3 of Interactive Playground A1.

Covers:
- Task 1: InteractiveSession model, bounded output buffer, capacity, stop idempotency,
  retention cleanup, sweeper daemon thread.
- Task 2: PTY process lifecycle for Python (prompt, input, two sequential prompts).
- Task 3: PTY process lifecycle for C + compile queue (validation, gcc, semaphore).
"""

import os
import re
import sys
import time
import threading
import types

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

import session_manager as sm  # noqa: E402


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def wait_for(mgr, session_id, check, timeout=12.0):
    """Poll get_delta() accumulating output via cursor until check(state, got)."""
    got = ""
    cursor = 0
    state = None
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            state = mgr.get_delta(session_id, cursor=cursor)
        except sm.SessionNotFoundError:
            time.sleep(0.03)
            continue
        got += state["output"]
        cursor = state["cursor"]
        if check(state, got):
            return state, got
        time.sleep(0.03)
    raise TimeoutError(
        f"condition not met within {timeout}s; status={state and state.get('status')}, "
        f"exit_code={state and state.get('exit_code')}, got={got!r}"
    )


@pytest.fixture
def mgr():
    """Factory for SessionManager instances; shutdown() in teardown."""
    managers = []

    def make(**kwargs):
        kwargs.setdefault("autostart_sweeper", False)
        m = sm.SessionManager(**kwargs)
        managers.append(m)
        return m

    yield make
    for m in managers:
        m.shutdown()


PY_PROMPT_CODE = 'nama = input("Siapa nama kamu? ")\nprint(f"Halo, {nama}!")\n'

C_PROMPT_CODE = (
    '#include <stdio.h>\n'
    'int main() {\n'
    '    char nama[32];\n'
    '    printf("Nama: ");\n'
    '    fflush(stdout);\n'
    '    if (scanf("%31s", nama) != 1) return 1;\n'
    '    printf("Halo, %s!\\n", nama);\n'
    '    return 0;\n'
    '}\n'
)


# --------------------------------------------------------------------------
# Task 1 — Session model
# --------------------------------------------------------------------------

def test_session_id_unique_and_opaque(mgr):
    m = mgr(max_sessions=10)
    s1 = m.create("python", [{"name": "main.py", "content": "print(1)"}])
    s2 = m.create("python", [{"name": "main.py", "content": "print(2)"}])
    assert s1.session_id != s2.session_id
    assert len(s1.session_id) >= 40  # secrets.token_urlsafe(32)
    assert re.fullmatch(r"[A-Za-z0-9_-]+", s1.session_id)  # opaque, URL-safe only


def test_delta_cursor_does_not_repeat_data(mgr):
    m = mgr()
    s = m.create(
        "python",
        [{"name": "main.py", "content": 'print("baris-1")\nprint("baris-2")\nprint("baris-3")'}],
    )
    st, got = wait_for(m, s.session_id, lambda st2, g: "baris-3" in g)
    assert st["status"] == "exited"

    d0 = m.get_delta(s.session_id, cursor=0)
    assert "baris-1" in d0["output"] and "baris-3" in d0["output"]
    assert d0["cursor"] == d0["base_cursor"] + len(d0["output"].encode("utf-8"))

    # Same cursor → no repetition.
    d1 = m.get_delta(s.session_id, cursor=d0["cursor"])
    assert d1["output"] == ""
    assert d1["cursor"] == d0["cursor"]

    # Walking cursors accumulates exactly once.
    acc = ""
    cur = 0
    while cur < d0["cursor"]:
        chunk = m.get_delta(s.session_id, cursor=cur)
        assert chunk["cursor"] > cur  # progress guaranteed
        acc += chunk["output"]
        cur = chunk["cursor"]
    assert acc == d0["output"]


def test_bounded_buffer_evicts_oldest_and_marks_truncated(mgr):
    m = mgr(output_limit_bytes=600)
    s = m.create("python", [{"name": "main.py", "content": "import time\ntime.sleep(2)"}])
    wait_for(m, s.session_id, lambda st, g: st["status"] == "running")
    for _ in range(3):
        m._append_output(s, "A" * 400)

    d = m.get_delta(s.session_id, cursor=0)
    assert d["base_cursor"] > 0  # oldest data evicted
    assert d["truncated"] is True  # cursor 0 fell behind base
    assert len(d["output"].encode("utf-8")) <= 600

    # Catch-up from base → no truncation, no repetition.
    d2 = m.get_delta(s.session_id, cursor=d["base_cursor"])
    assert d2["output"] == d["output"]
    assert d2["truncated"] is False
    m.stop(s.session_id)


def test_max_sessions_rejects_51st(mgr):
    m = mgr(max_sessions=50)
    for i in range(50):
        m.create("python", [{"name": "main.py", "content": f"print({i})"}])
    with pytest.raises(sm.SessionCapacityError) as ei:
        m.create("python", [{"name": "main.py", "content": "print(1)"}])
    assert "50" in str(ei.value)
    assert m.stats()["active_sessions"] == 50


def test_stop_idempotent(mgr):
    m = mgr()
    s = m.create("python", [{"name": "main.py", "content": "import time\ntime.sleep(30)"}])
    wait_for(m, s.session_id, lambda st, g: st["status"] == "running")
    r1 = m.stop(s.session_id)
    assert r1["status"] == "stopped"
    r2 = m.stop(s.session_id)  # second stop: same result, no exception
    assert r2["status"] == "stopped"
    assert r2["session_id"] == s.session_id
    d = m.get_delta(s.session_id, cursor=0)
    assert d["status"] == "stopped"
    assert d["exit_code"] is not None and d["exit_code"] < 0  # killed by signal


def test_terminal_session_cleaned_after_retention(mgr):
    m = mgr(terminal_retention=0.1)
    s = m.create("python", [{"name": "main.py", "content": 'print("selesai")'}])
    wait_for(m, s.session_id, lambda st, g: st["status"] == "exited")
    with m._lock:
        s.last_activity_at = time.time() - 5
    n = m.cleanup_expired()
    assert n >= 1
    with pytest.raises(sm.SessionNotFoundError):
        m.get_delta(s.session_id, cursor=0)


def test_sweeper_is_daemon_and_cleans_automatically():
    m = sm.SessionManager(terminal_retention=0.15, sweeper_interval=0.05)
    try:
        assert any(
            t.name == "session-sweeper" and t.daemon for t in threading.enumerate()
        )
        s = m.create("python", [{"name": "main.py", "content": 'print("x")'}])
        deadline = time.time() + 8
        gone = False
        while time.time() < deadline:
            try:
                st = m.get_delta(s.session_id, cursor=0)
                if st["status"] == "exited":
                    time.sleep(0.05)
                    continue
            except sm.SessionNotFoundError:
                gone = True
                break
            time.sleep(0.02)
        assert gone, "sweeper thread did not remove the terminal session"
    finally:
        m.shutdown()


# --------------------------------------------------------------------------
# Task 2 — PTY lifecycle for Python
# --------------------------------------------------------------------------

def test_python_prompt_appears_without_stdin(mgr):
    m = mgr()
    s = m.create("python", [{"name": "main.py", "content": PY_PROMPT_CODE}])
    st, got = wait_for(m, s.session_id, lambda st2, g: "Siapa nama kamu?" in g)
    assert st["status"] == "running"
    assert "EOFError" not in got


def test_python_input_budi_produces_halo_no_eoferror(mgr):
    m = mgr()
    s = m.create("python", [{"name": "main.py", "content": PY_PROMPT_CODE}])
    st, got = wait_for(m, s.session_id, lambda st2, g: "Siapa nama kamu?" in g)
    m.write_input(s.session_id, "Budi\n")
    st, got = wait_for(m, s.session_id, lambda st2, g: st2["status"] == "exited")
    assert "Halo, Budi!" in got
    assert "EOFError" not in got
    assert st["exit_code"] == 0


def test_python_two_prompts_sequential_single_process(mgr):
    m = mgr()
    code = 'a = input("Nama: ")\nb = input("Umur: ")\nprint(f"{a} berumur {b} tahun")\n'
    s = m.create("python", [{"name": "main.py", "content": code}])
    st, got = wait_for(m, s.session_id, lambda st2, g: "Nama:" in g)
    assert st["status"] == "running"
    m.write_input(s.session_id, "Budi\n")
    st, got = wait_for(m, s.session_id, lambda st2, g: "Umur:" in g)
    assert st["status"] == "running"
    m.write_input(s.session_id, "17\n")
    st, got = wait_for(m, s.session_id, lambda st2, g: st2["status"] == "exited")
    assert "Budi berumur 17 tahun" in got
    assert "Nama:" in got and "Umur:" in got  # same process, one output stream
    assert "EOFError" not in got
    assert st["exit_code"] == 0


def test_prefilled_stdin_written_after_spawn(mgr):
    m = mgr()
    s = m.create(
        "python",
        [{"name": "main.py", "content": PY_PROMPT_CODE}],
        stdin="Budi\n",
    )
    st, got = wait_for(m, s.session_id, lambda st2, g: st2["status"] == "exited")
    assert "Halo, Budi!" in got
    assert "EOFError" not in got


# --------------------------------------------------------------------------
# Task 3 — PTY lifecycle for C + compile queue
# --------------------------------------------------------------------------

def test_c_prompt_appears_before_input_without_newline(mgr):
    m = mgr()
    s = m.create("c", [{"name": "main.c", "content": C_PROMPT_CODE}])
    st, got = wait_for(m, s.session_id, lambda st2, g: "Nama:" in g)
    assert st["status"] == "running"  # prompt flushed, still waiting for input


def test_c_input_budi_produces_halo(mgr):
    m = mgr()
    s = m.create("c", [{"name": "main.c", "content": C_PROMPT_CODE}])
    wait_for(m, s.session_id, lambda st, g: "Nama:" in g)
    m.write_input(s.session_id, "Budi\n")
    st, got = wait_for(m, s.session_id, lambda st2, g: st2["status"] == "exited")
    assert "Halo, Budi!" in got
    assert st["exit_code"] == 0


def test_c_main_includes_header(mgr):
    m = mgr()
    files = [
        {
            "name": "main.c",
            "content": (
                '#include <stdio.h>\n#include "foo.h"\n'
                "int main() { printf(\"Angka: %d\\n\", tambah(2, 3)); return 0; }\n"
            ),
        },
        {
            "name": "foo.h",
            "content": (
                "#ifndef FOO_H\n#define FOO_H\n"
                "static inline int tambah(int a, int b) { return a + b; }\n"
                "#endif\n"
            ),
        },
    ]
    s = m.create("c", files)
    st, got = wait_for(m, s.session_id, lambda st2, g: st2["status"] == "exited")
    assert "Angka: 5" in got


def test_c_two_source_files_linked(mgr):
    m = mgr()
    files = [
        {
            "name": "main.c",
            "content": (
                '#include <stdio.h>\nint dua_kali(int x);\n'
                "int main() { printf(\"Hasil: %d\\n\", dua_kali(21)); return 0; }\n"
            ),
        },
        {"name": "helper.c", "content": "int dua_kali(int x) { return x * 2; }\n"},
    ]
    s = m.create("c", files)
    st, got = wait_for(m, s.session_id, lambda st2, g: st2["status"] == "exited")
    assert "Hasil: 42" in got


@pytest.mark.parametrize(
    "bad_name",
    ["../evil.c", "dir/evil.c", "a\\b.c", "..", "sub/main.c", "/abs/main.c"],
)
def test_c_validation_rejects_non_basename(mgr, bad_name):
    m = mgr()
    with pytest.raises(sm.SessionValidationError):
        m.create("c", [{"name": bad_name, "content": "int main(){return 0;}"}])


def test_c_validation_rejects_duplicate_case_insensitive(mgr):
    m = mgr()
    files = [
        {"name": "main.c", "content": "int main(){return 0;}"},
        {"name": "MAIN.C", "content": "int main(){return 0;}"},
    ]
    with pytest.raises(sm.SessionValidationError, match="[Dd]uplicate"):
        m.create("c", files)


def test_c_validation_rejects_wrong_extension(mgr):
    m = mgr()
    with pytest.raises(sm.SessionValidationError):
        m.create("c", [{"name": "main.py", "content": "x"}])


def test_c_validation_rejects_too_many_files(mgr):
    m = mgr(max_files=20)
    files = [{"name": f"f{i:02d}.c", "content": "int main(){return 0;}"} for i in range(21)]
    with pytest.raises(sm.SessionValidationError):
        m.create("c", files)


def test_c_validation_rejects_oversize_source(mgr):
    m = mgr(max_source_bytes=262144)
    with pytest.raises(sm.SessionValidationError):
        m.create("c", [{"name": "big.c", "content": "x" * 300000}])


def test_c_validation_rejects_no_c_files(mgr):
    m = mgr()
    with pytest.raises(sm.SessionValidationError, match="no .c"):
        m.create("c", [{"name": "only.h", "content": "int x;"}])


def test_c_compile_error_sets_error_status_and_does_not_spawn(mgr):
    m = mgr()
    s = m.create("c", [{"name": "main.c", "content": "int main() { syntax error here }\n"}])
    st, got = wait_for(m, s.session_id, lambda st2, g: st2["status"] == "error")
    assert "error" in got.lower()
    assert st["error"] == "compilation failed"
    assert st["exit_code"] != 0
    assert s.process is None  # never spawned


def test_compile_semaphore_never_exceeds_max_compiles(mgr, monkeypatch):
    m = mgr(max_compiles=2, queue_timeout=15)
    release = threading.Event()
    lock = threading.Lock()
    active, peak = [0], [0]

    def fake_run(cmd, **kw):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        try:
            release.wait(10)
        finally:
            with lock:
                active[0] -= 1
        # Provide a real executable so the PTY spawn succeeds.
        exe = os.path.join(kw.get("cwd", "/tmp"), "program")
        with open(exe, "w") as fh:
            fh.write("#!/bin/sh\necho compiled-ok\n")
        os.chmod(exe, 0o755)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(sm.subprocess, "run", fake_run)

    sessions, errors = [], []

    def do_create():
        try:
            sessions.append(m.create("c", [{"name": "main.c", "content": "int main(){return 0;}"}]))
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=do_create) for _ in range(6)]
    for t in threads:
        t.start()

    st = m.stats()
    deadline = time.time() + 5
    while time.time() < deadline:
        st = m.stats()
        if st["queued"] + st["compiling"] == 6:
            break
        time.sleep(0.05)
    assert st["queued"] + st["compiling"] == 6  # all queued/compiling, none running
    assert st["compiling"] <= 2  # status queued → compiling respects semaphore

    release.set()
    for t in threads:
        t.join(15)
    assert not errors
    assert peak[0] <= 2  # gcc never ran more than MAX_COMPILES concurrently

    for s in sessions:
        d, got = wait_for(m, s.session_id, lambda st2, g: st2["status"] in ("exited", "error"))
        assert "compiled-ok" in got, f"session {s.session_id}: {got!r}"


def test_write_input_requires_running(mgr):
    m = mgr()
    s = m.create("python", [{"name": "main.py", "content": 'print("x")'}])
    wait_for(m, s.session_id, lambda st, g: st["status"] == "exited")
    with pytest.raises(sm.SessionNotRunningError):
        m.write_input(s.session_id, "Budi\n")
