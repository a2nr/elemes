"""
Shared fixtures untuk suite services.

Environment (TOKENS_FILE / CONTENT_DIR) di-set di import-time conftest,
SEBELUM `app`/`token_service` di-import, supaya seluruh test menunjuk data
uji terpisah — bukan file produksi (`../tokens_siswa.csv`).
"""

import csv
import os
import pathlib

import pytest

_TEST_ROOT = "/tmp/lms-contract"
_TEST_TOKENS = f"{_TEST_ROOT}/tokens.csv"
_TEST_CONTENT = f"{_TEST_ROOT}/content"

TEACHER_TOKEN = "TOKEN_GURU_001"
STUDENT_TOKEN = "TOKEN_SISWA_001"
STUDENT2_TOKEN = "TOKEN_SISWA_002"


def _write_tokens() -> None:
    pathlib.Path(_TEST_ROOT).mkdir(parents=True, exist_ok=True)
    pathlib.Path(_TEST_CONTENT).mkdir(parents=True, exist_ok=True)
    with open(_TEST_TOKENS, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["token", "nama_siswa", "hello_world", "quiz_test"])
        writer.writerow([TEACHER_TOKEN, "Pak Guru", "completed", "completed"])
        writer.writerow([STUDENT_TOKEN, "Budi Santoso", "completed", "3/4"])
        writer.writerow([STUDENT2_TOKEN, "Siti Aminah", "not_started", ""])


_write_tokens()

# PAKSA path fixture (bukan setdefault) — env container (.env) membawa
# TOKENS_FILE/CONTENT_DIR produksi ("tokens.csv"/"content") yang membuat
# contract tests membaca data asli. Test harus selalu terisolasi.
os.environ["TOKENS_FILE"] = _TEST_TOKENS
os.environ["CONTENT_DIR"] = _TEST_CONTENT
os.environ["ORIGIN"] = "*"


@pytest.fixture()
def app():
    from app import create_app

    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _isolate_database():
    """Isolasi integration test: truncate semua tabel sebelum SETIAP test.

    Test importer/lesson-registry/progress berbagi DATABASE_URL yang sama;
    tanpa reset, data sisa antar test saling mengotori (mis. total lessons
    bertambah). Contract tests (backend CSV) tidak terpengaruh — SessionLocal
    None bila DATABASE_URL tidak diset.
    """
    from sqlalchemy import text

    from services.database import SessionLocal

    if SessionLocal is None:
        yield
        return
    db = SessionLocal()
    try:
        db.execute(
            text(
                "TRUNCATE student_progress, access_tokens, lessons, users "
                "RESTART IDENTITY CASCADE"
            )
        )
        db.commit()
    finally:
        db.close()
    yield
