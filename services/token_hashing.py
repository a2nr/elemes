"""
Hash token akses: HMAC-SHA256 + server-side pepper.

- Token mentah TIDAK pernah disimpan ke database maupun log.
- Digest deterministik (token sama → hash sama) supaya lookup cepat via index.
- Pepper hidup di environment (TOKEN_PEPPER), bukan di DB.
  Pepper hilang = seluruh token invalid → semua user perlu token baru.
"""

import hashlib
import hmac
import os


def hash_token(raw_token: str, pepper: str | None = None) -> str:
    pepper_value = os.environ.get("TOKEN_PEPPER", "") if pepper is None else pepper
    return hmac.new(
        pepper_value.encode("utf-8"), raw_token.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def pepper_set() -> bool:
    return bool(os.environ.get("TOKEN_PEPPER", ""))
