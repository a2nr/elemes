#!/usr/bin/env python3
"""E2E check alur interaktif playground via proxy Flask (di dalam container)."""
import json
import sys
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:5000"
TOKEN = __import__("os").environ.get("E2E_TOKEN", "").strip()


def _with_token(payload):
    if TOKEN:
        payload = dict(payload)
        payload["token"] = TOKEN
    return payload


def call(method, path, payload=None, params=None):
    url = BASE + path
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body[:200]}


def wait_for(sid, predicate, timeout=15, poll=0.3, cursor=0):
    """Poll output; return (status_dict, final_cursor)."""
    last = None
    t0 = time.time()
    while time.time() - t0 < timeout:
        st, body = call("GET", f"/compile/sessions/{sid}", params={"cursor": cursor})
        if st != 200:
            last = ("ERR", st, body)
            time.sleep(poll)
            continue
        cursor = body.get("cursor", cursor)
        last = body
        if predicate(body):
            return body, cursor
        time.sleep(poll)
    return last, cursor


results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  {detail}" if detail and not cond else ""))


# ── 1. Python interaktif: Run → prompt → input → output ──────────────
st, body = call("POST", "/compile/sessions", _with_token({
    "language": "python",
    "files": [{"name": "main.py", "content": 'nama = input("Siapa nama kamu? ")\nprint(f"Halo, {nama}!")\n'}],
    "active_file": "main.py",
}))
check("py: create session", st in (200, 202) and body.get("session_id"), f"st={st} body={body}")
sid = body.get("session_id", "")

if sid:
    b, cur = wait_for(sid, lambda x: "Siapa nama kamu?" in x.get("output", ""))
    check("py: prompt muncul (tanpa stdin, tetap running)", b.get("status") == "running" and "Siapa nama kamu?" in b.get("output", ""), f"{b.get('status')} out={b.get('output')!r}")

    st, b2 = call("POST", f"/compile/sessions/{sid}/input", {"text": "anggoro"})
    check("py: input kirim OK", st == 200, f"st={st}")

    b3, _ = wait_for(sid, lambda x: x.get("status") in ("exited", "error"), cursor=cur)
    out = b3.get("output", "")
    check("py: output Halo, anggoro!", "Halo, anggoro!" in out and b3.get("exit_code") == 0, f"status={b3.get('status')} exit={b3.get('exit_code')} out={out!r}")
    check("py: tidak ada EOFError", "EOFError" not in out, out[-200:])

    st, _ = call("DELETE", f"/compile/sessions/{sid}")
    check("py: delete idempotent", st in (200, 404), f"st={st}")

# ── 2. C interaktif: scanf prompt → input → output ───────────────────
C_PROMPT = '#include <stdio.h>\nint main() {\n    char nama[64];\n    printf("Nama: ");\n    fflush(stdout);\n    scanf("%63s", nama);\n    printf("Halo, %s!\\n", nama);\n    return 0;\n}\n'
st, body = call("POST", "/compile/sessions", _with_token({
    "language": "c",
    "files": [{"name": "main.c", "content": C_PROMPT}],
    "active_file": "main.c",
}))
check("c: create session", st in (200, 202) and body.get("session_id"), f"st={st} body={body}")
sid = body.get("session_id", "")
if sid:
    b, cur = wait_for(sid, lambda x: "Nama:" in x.get("output", ""), timeout=20)
    check("c: prompt Nama: muncul", b.get("status") == "running" and "Nama:" in b.get("output", ""), f"{b.get('status')} out={b.get('output')!r}")
    st, _ = call("POST", f"/compile/sessions/{sid}/input", {"text": "Budi"})
    b3, _ = wait_for(sid, lambda x: x.get("status") in ("exited", "error"), cursor=cur, timeout=20)
    check("c: output Halo, Budi!", "Halo, Budi!" in b3.get("output", "") and b3.get("exit_code") == 0, f"status={b3.get('status')} out={b3.get('output')!r}")
    call("DELETE", f"/compile/sessions/{sid}")

# ── 3. C multi-file dengan foo.h (include header) ────────────────────
FILES = [
    {"name": "main.c", "content": '#include <stdio.h>\n#include "foo.h"\nint main() {\n    printf("Hasil: %d\\n", tambah(7, 8));\n    return 0;\n}\n'},
    {"name": "foo.h", "content": "#ifndef FOO_H\n#define FOO_H\nstatic inline int tambah(int a, int b) { return a + b; }\n#endif\n"},
]
st, body = call("POST", "/compile/sessions", _with_token({"language": "c", "files": FILES, "active_file": "main.c"}))
check("c-multi: create session", st in (200, 202) and body.get("session_id"), f"st={st} body={body}")
sid = body.get("session_id", "")
if sid:
    b, _ = wait_for(sid, lambda x: x.get("status") in ("exited", "error"), timeout=25)
    out = b.get("output", "")
    check("c-multi: foo.h ikut dikompilasi (Hasil: 15)", "Hasil: 15" in out and b.get("exit_code") == 0, f"status={b.get('status')} out={out!r}")

# ── 4. Python tanpa stdin: tetap aktif, bukan EOFError ───────────────
st, body = call("POST", "/compile/sessions", _with_token({
    "language": "python",
    "files": [{"name": "main.py", "content": 'x = input("Angka: ")\nprint(x)\n'}],
}))
sid = body.get("session_id", "")
if sid:
    b, _ = wait_for(sid, lambda x: "Angka:" in x.get("output", ""), timeout=15)
    check("py-nostdin: prompt tetap aktif (bukan EOF)", b.get("status") == "running", f"status={b.get('status')}")
    call("DELETE", f"/compile/sessions/{sid}")

# ── 5. Error handling: sesi invalid → 404 ────────────────────────────
st, body = call("GET", "/compile/sessions/tidak-ada")
check("404 session unknown", st == 404, f"st={st}")

fails = [r for r in results if not r[1]]
print("\n===== HASIL =====")
print(f"{len(results) - len(fails)}/{len(results)} PASS")
if fails:
    print("FAIL:", [(r[0], r[2]) for r in fails])
    sys.exit(1)
