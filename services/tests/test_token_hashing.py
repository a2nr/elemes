"""Unit test hashing token — murni, tanpa DB."""

from services.token_hashing import hash_token, pepper_set


def test_hash_deterministic(monkeypatch):
    monkeypatch.setenv("TOKEN_PEPPER", "pepper-uji")
    assert hash_token("ABC123") == hash_token("ABC123")
    assert len(hash_token("ABC123")) == 64  # sha256 hex


def test_hash_differs_by_pepper(monkeypatch):
    monkeypatch.setenv("TOKEN_PEPPER", "pepper-a")
    a = hash_token("SAMA")
    monkeypatch.setenv("TOKEN_PEPPER", "pepper-b")
    b = hash_token("SAMA")
    assert a != b


def test_hash_not_plaintext(monkeypatch):
    monkeypatch.setenv("TOKEN_PEPPER", "pepper-uji")
    assert "ABC123" not in hash_token("ABC123")


def test_explicit_pepper_overrides_env(monkeypatch):
    monkeypatch.setenv("TOKEN_PEPPER", "env-pepper")
    explicit = hash_token("X", pepper="eksplisit")
    assert explicit == hash_token("X", pepper="eksplisit")
    assert explicit != hash_token("X")


def test_pepper_set_flag(monkeypatch):
    monkeypatch.delenv("TOKEN_PEPPER", raising=False)
    assert pepper_set() is False
    monkeypatch.setenv("TOKEN_PEPPER", "ada")
    assert pepper_set() is True
