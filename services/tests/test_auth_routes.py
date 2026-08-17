"""
Kontrak route autentikasi. Token asli siswa tetap dipakai untuk login;
response dan log tidak boleh mengekspos credential.

Integrasi PostgreSQL (butuh DATABASE_URL) — backend CSV sudah dicabut.
"""

import os

import pytest

from services.tests.conftest import STUDENT_TOKEN, TEACHER_TOKEN

pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("DATABASE_URL"), reason="butuh PostgreSQL nyata"
    ),
    pytest.mark.integration,
]


@pytest.fixture(autouse=True)
def _seed(seed_demo_users):
    yield


def test_login_success_sets_httponly_cookie(client):
    resp = client.post("/login", json={"token": STUDENT_TOKEN})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["student_name"] == "Budi Santoso"
    assert body["is_teacher"] is False
    set_cookie = resp.headers.get("Set-Cookie", "")
    assert "student_token=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_login_teacher(client):
    resp = client.post("/login", json={"token": TEACHER_TOKEN})
    assert resp.get_json()["is_teacher"] is True


def test_login_invalid_token(client):
    resp = client.post("/login", json={"token": "TOKEN_SALAH"})
    assert resp.status_code == 200
    assert resp.get_json()["success"] is False


def test_validate_token_route(client):
    resp = client.post("/validate-token", json={"token": TEACHER_TOKEN})
    body = resp.get_json()
    assert body["success"] is True
    assert body["is_teacher"] is True


def test_validate_token_from_cookie(client):
    client.set_cookie("student_token", STUDENT_TOKEN)
    resp = client.post("/validate-token", json={})
    assert resp.get_json()["success"] is True
    assert resp.get_json()["student_name"] == "Budi Santoso"
