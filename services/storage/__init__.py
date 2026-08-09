"""
Storage backend — PostgreSQL adalah satu-satunya backend aktif.

Backend CSV (tokens_siswa.csv) sudah dicabut setelah cutover penuh ke
PostgreSQL. Nilai STORAGE_BACKEND selain 'postgresql' ditolak eksplisit
(fail-loud), bukan di-rollback diam-diam ke perilaku lama.
"""

import os


def active_backend_name() -> str:
    explicit = os.environ.get("STORAGE_BACKEND", "").strip().lower()
    if explicit and explicit != "postgresql":
        raise ValueError(
            f"STORAGE_BACKEND={explicit!r} tidak didukung lagi; "
            "satu-satunya backend yang tersedia adalah 'postgresql'."
        )
    return "postgresql"


def get_backend_module():
    active_backend_name()  # validasi nilai env
    from services.storage import postgres_backend

    return postgres_backend
