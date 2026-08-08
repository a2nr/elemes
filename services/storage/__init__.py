"""
Storage backends — seleksi backend aktif berdasarkan STORAGE_BACKEND.

- 'csv'        : penyimpanan lama (tokens_siswa.csv), untuk transisi/rollback.
- 'postgresql' : source of truth baru (users/tokens/lessons/progress).

Default: 'postgresql' bila DATABASE_URL tersedia, selain itu 'csv'.
Kedua backend mengimplementasikan kontrak yang sama (lihat token_service facade).
"""

import os


def active_backend_name() -> str:
    explicit = os.environ.get("STORAGE_BACKEND", "").strip().lower()
    if explicit:
        return explicit
    from services.database import SessionLocal

    return "postgresql" if SessionLocal is not None else "csv"


def get_backend_module():
    name = active_backend_name()
    if name == "postgresql":
        from services.storage import postgres_backend

        return postgres_backend
    if name == "csv":
        from services.storage import csv_backend

        return csv_backend
    raise ValueError(f"STORAGE_BACKEND tidak dikenal: {name!r}")
