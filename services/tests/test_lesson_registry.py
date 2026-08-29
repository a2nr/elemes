"""
Lesson registry: parsing specs dari home.md (unit, host) + sinkronisasi DB
(integrasi — skip bila DATABASE_URL tidak diset).
"""

import os

import pytest

pytestmark = pytest.mark.integration

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
    lesson_service.find_lesson_file.cache_clear()

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
    lesson_service.find_lesson_file.cache_clear()
    assert lesson_specs() == []


@pytest.mark.skipif(not DB_REQUIRED, reason="butuh DATABASE_URL (PostgreSQL nyata)")
def test_sync_creates_and_deactivates_lessons(tmp_path, monkeypatch):
    from services.database import SessionLocal
    from services import repositories

    _write_content(tmp_path)
    monkeypatch.setattr("services.lesson_service.CONTENT_DIR", str(tmp_path))
    lesson_service.find_lesson_file.cache_clear()

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
        lesson_service.find_lesson_file.cache_clear()
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


@pytest.mark.skipif(not DB_REQUIRED, reason="butuh DATABASE_URL (PostgreSQL nyata)")
def test_sync_includes_sub_bab_lessons(tmp_path, monkeypatch):
    """Lesson yang hanya ada di sub-home.md (bukan di home.md root) tetap
    ter-sync ke DB sebagai lesson aktif — agar kolom CSV guru/sub-bab lengkap.

    Regression test untuk bug: sync_lesson_registry hanya membaca home.md root
    sehingga materi sub-bab tidak muncul sebagai kolom saat guru import siswa.
    """
    from services.database import SessionLocal
    from services import repositories

    (tmp_path / "home.md").write_text(
        "# Home\n\n---Available_Lessons---\n- [Hello World](hello_world.md)\n",
        encoding="utf-8",
    )
    (tmp_path / "hello_world.md").write_text("# Hello World\nisi", encoding="utf-8")

    # Buat folder sub-bab dengan sub-home.md yang merujuk lesson unik
    # (sub_bab_only) yang TIDAK ada di home.md root.
    bab = tmp_path / "dasar"
    bab.mkdir()
    (bab / "sub-home.md").write_text(
        "# Dasar\n\n---Available_Lessons---\n- [Sub Bab Only](sub_bab_only.md)\n",
        encoding="utf-8",
    )
    (bab / "sub_bab_only.md").write_text("# Sub Bab Only\nisi", encoding="utf-8")

    monkeypatch.setattr("services.lesson_service.CONTENT_DIR", str(tmp_path))
    lesson_service.get_lessons.cache_clear()
    lesson_service.find_lesson_file.cache_clear()

    db = SessionLocal()
    try:
        result = sync_lesson_registry(db)
        assert result["specs"] == 2  # hello_world (root) + sub_bab_only (sub-bab)

        active_slugs = {lesson.slug for lesson in repositories.list_active_lessons(db)}
        assert "hello_world" in active_slugs
        assert "sub_bab_only" in active_slugs  # <-- regression assertion
    finally:
        # Bersihkan: non-aktifkan lesson yang mungkin tertinggal (sub_bab_only)
        # agar test idempotent & tidak mengganggu test lain.
        repositories.deactivate_missing_lessons(db, {"hello_world", "sub_bab_only"})
        db.commit()
        db.close()


def test_specs_union_root_and_sub_bab_no_db(tmp_path, monkeypatch):
    """Unit (host, tanpa DB): lesson_specs() mengembalikan union root + sub-bab
    dengan dedupe slug (root menang atas sub-bab bila collision)."""
    (tmp_path / "home.md").write_text(
        "# Home\n\n---Available_Lessons---\n"
        "- [Root Only](root_only.md)\n"
        "- [Shared](shared.md)\n",
        encoding="utf-8",
    )
    for slug, title in [("root_only", "Root Only"), ("shared", "Shared")]:
        (tmp_path / f"{slug}.md").write_text(f"# {title}\nisi", encoding="utf-8")

    bab = tmp_path / "dasar"
    bab.mkdir()
    (bab / "sub-home.md").write_text(
        "# Dasar\n\n---Available_Lessons---\n"
        "- [Shared](shared.md)\n"           # collision — root priority\n"
        "- [Sub Only](sub_only.md)\n",      # hanya ada di sub-bab\n"
        encoding="utf-8",
    )
    (bab / "sub_only.md").write_text("# Sub Only\nisi", encoding="utf-8")

    monkeypatch.setattr("services.lesson_service.CONTENT_DIR", str(tmp_path))
    lesson_service.get_lessons.cache_clear()

    specs = lesson_specs()
    slugs = [s for s, _, _ in specs]

    # Tiga lesson unik: root_only, shared, sub_only
    assert slugs == ["root_only", "shared", "sub_only"]

    # Slug collision: root title (Shared) menang, bukan sub-bab title
    title_by_slug = {s: t for s, t, _ in specs}
    assert title_by_slug["shared"] == "Shared"
    assert title_by_slug["sub_only"] == "Sub Only"
