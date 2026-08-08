"""
Lesson registry: parsing specs dari home.md (unit, host) + sinkronisasi DB
(integrasi — skip bila DATABASE_URL tidak diset).
"""

import os

import pytest

from services import lesson_service
from services.lesson_registry import lesson_specs, sync_lesson_registry

DB_REQUIRED = os.environ.get("DATABASE_URL", "").strip()


def _write_content(tmp_path):
    home = tmp_path / "home.md"
    home.write_text(
        "# Home\n\n"
        "---Available_Lessons---\n"
        "- [Hello World](hello_world.md)\n"
        "- [Quiz C](quiz_test)\n"
        "- [Sub Bab](sub-home.md)\n",
        encoding="utf-8",
    )
    (tmp_path / "hello_world.md").write_text("# Hello World\nisi", encoding="utf-8")
    (tmp_path / "quiz_test.md").write_text("# Quiz C\nisi", encoding="utf-8")
    (tmp_path / "sub-home.md").write_text("# Sub\nisi", encoding="utf-8")
    return home


def test_specs_parse_from_home_md(tmp_path, monkeypatch):
    _write_content(tmp_path)
    monkeypatch.setattr("services.lesson_service.CONTENT_DIR", str(tmp_path))
    lesson_service.get_lessons.cache_clear()

    specs = lesson_specs()

    # sub-home.md harus di-skip; urutan sesuai home.md; slug tanpa .md
    assert [(s, t) for s, t, _ in specs] == [
        ("hello_world", "Hello World"),
        ("quiz_test", "Quiz C"),
    ]
    assert [order for _, _, order in specs] == [0, 1]


def test_specs_empty_without_available_lessons(tmp_path, monkeypatch):
    (tmp_path / "home.md").write_text("# Home\nno lessons section\n", encoding="utf-8")
    monkeypatch.setattr("services.lesson_service.CONTENT_DIR", str(tmp_path))
    lesson_service.get_lessons.cache_clear()
    assert lesson_specs() == []


@pytest.mark.skipif(not DB_REQUIRED, reason="butuh DATABASE_URL (PostgreSQL nyata)")
def test_sync_creates_and_deactivates_lessons(tmp_path, monkeypatch):
    from services.database import SessionLocal

    _write_content(tmp_path)
    monkeypatch.setattr("services.lesson_service.CONTENT_DIR", str(tmp_path))

    db = SessionLocal()
    try:
        first = sync_lesson_registry(db)
        assert first["specs"] == 2
        assert first["deactivated"] == 0

        # Hapus satu lesson dari home.md → di-deactivate, bukan dihapus
        (tmp_path / "home.md").write_text(
            "# Home\n\n---Available_Lessons---\n- [Hello World](hello_world.md)\n",
            encoding="utf-8",
        )
        lesson_service.get_lessons.cache_clear()
        second = sync_lesson_registry(db)
        assert second["deactivated"] == 1
        assert second["total"] == 2  # row quiz_test masih ada
        assert second["active"] == 1

        # Sinkronisasi idempotent — ketiga kalinya tidak mengubah apa pun
        third = sync_lesson_registry(db)
        assert third["deactivated"] == 0
        assert third["total"] == 2
    finally:
        db.close()
