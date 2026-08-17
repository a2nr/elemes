"""
Shared fixtures untuk suite services.

CONTENT_DIR di-set di import-time conftest, SEBELUM `app`/`lesson_service`
di-import, supaya test menunjuk data uji terpisah — bukan content produksi.

Token & progress siswa kini dikelola sepenuhnya di PostgreSQL (backend CSV
sudah dicabut); konstanta token uji di bawah tetap dipakai untuk seeding
via repositories di test integrasi.
"""

import os
import pathlib

import pytest

_TEST_ROOT = "/tmp/lms-contract"
_TEST_CONTENT = f"{_TEST_ROOT}/content"

TEACHER_TOKEN = "TOKEN_GURU_001"
STUDENT_TOKEN = "TOKEN_SISWA_001"
STUDENT2_TOKEN = "TOKEN_SISWA_002"

pathlib.Path(_TEST_CONTENT).mkdir(parents=True, exist_ok=True)

# PAKSA path fixture (bukan setdefault) — env container (.env) membawa
# CONTENT_DIR produksi ("content") yang membuat lesson tests membaca data asli.
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


@pytest.fixture()
def seed_demo_users():
    """Reset + seed data uji route auth/progress: 1 guru, 2 siswa, 1 lesson.

    Opt-in: modul yang butuh data ini meminta fixture via wrapper autouse.
    """
    from sqlalchemy import text

    from services import repositories as repo
    from services.database import SessionLocal
    from services.models import Lesson

    if SessionLocal is None:
        pytest.skip("butuh PostgreSQL nyata")
    db = SessionLocal()
    try:
        db.execute(
            text(
                "TRUNCATE quiz_attempts, student_progress, access_tokens, lessons, users "
                "RESTART IDENTITY CASCADE"
            )
        )
        teacher = repo.create_user(db, display_name="Pak Guru", role="teacher")
        repo.create_access_token(db, user_id=teacher.id, raw_token=TEACHER_TOKEN)
        budi = repo.create_user(db, display_name="Budi Santoso", role="student")
        repo.create_access_token(db, user_id=budi.id, raw_token=STUDENT_TOKEN)
        siti = repo.create_user(db, display_name="Siti Aminah", role="student")
        repo.create_access_token(db, user_id=siti.id, raw_token=STUDENT2_TOKEN)
        db.add(Lesson(slug="hello_world", title="Hello World", order_index=0))
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _isolate_database(request):
    """Isolasi integration test: truncate semua tabel sebelum SETIAP test.

    Test importer/lesson-registry/progress berbagi DATABASE_URL yang sama;
    tanpa reset, data sisa antar test saling mengotori (mis. total lessons
    bertambah). Contract test (backend CSV) tidak terpengaruh — SessionLocal
    None bila DATABASE_URL tidak diset.

    Test bertanda `unit` tidak pernah menyentuh DB — lewati isolasi sepenuhnya
    supaya `make test-unit` tetap jalan cepat & tanpa DB walau DATABASE_URL
    diset di environment (atau server PostgreSQL sedang mati).
    """
    if request.node.get_closest_marker("unit") is not None:
        yield
        return

    from sqlalchemy import text

    from services.database import SessionLocal

    if SessionLocal is None:
        yield
        return
    db = SessionLocal()
    try:
        db.execute(
            text(
                "TRUNCATE quiz_attempts, student_progress, access_tokens, lessons, users "
                "RESTART IDENTITY CASCADE"
            )
        )
        db.commit()
    finally:
        db.close()
    yield
