"""Smoke test live app — panggil endpoint dari dalam container backend."""
import json
import urllib.error
import urllib.request

BASE = "http://localhost:5000"


def post(path: str, payload: dict):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode() or "{}"
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {}


status, body = post("/login", {"token": "TOKEN_BOGUS_SMOKE"})
print("login-bogus:", status, body.get("success"))

status2, body2 = post("/lesson-progress", {"token": "TOKEN_BOGUS_SMOKE", "lesson_name": "hello_world", "type": "exercise"})
print("track-bogus:", status2, body2.get("success"))

try:
    with urllib.request.urlopen(BASE + "/lessons", timeout=10) as r:
        print("lessons:", r.status, "ok")
except urllib.error.HTTPError as e:
    print("lessons:", e.code)
