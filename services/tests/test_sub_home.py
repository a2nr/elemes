"""
Unit test untuk helper sub-home di lesson_service:

- `_read_md_cached`: membaca file dengan cache berbasis mtime; hasil harus
  segar bila file diubah (mtime berubah).
- `find_sub_home_for_lesson`: mendeteksi `sub-home.md` di folder induk satu
  level dari sebuah file lesson (ada / tidak ada).
- `get_sub_home_data`: mem-parsing sub-home.md (title, intro, daftar lesson)
  dan me-refresh hasilnya bila file berubah.
- `get_ordered_lessons_with_learning_objectives(source_path=...)`: daftar
  materi diambil dari sub-home.md bila source_path diberikan, fallback home.md.
"""

import os
import time

import pytest

from services import lesson_service
from services.lesson_service import (
    _read_md_cached,
    find_sub_home_for_lesson,
    get_ordered_lessons_with_learning_objectives,
    get_sub_home_data,
)


@pytest.fixture(autouse=True)
def _clear_caches():
    """Bersihkan cache lintas test supaya hasil tidak basi antar kasus."""
    yield
    lesson_service._file_cache.clear()
    lesson_service._sub_home_cache.clear()
    lesson_service.find_lesson_file.cache_clear()
    lesson_service.get_lessons.cache_clear()
    lesson_service.get_lesson_names.cache_clear()
    lesson_service.get_lessons_with_learning_objectives.cache_clear()


def _touch_mtime(path):
    """Paksa mtime berubah (beberapa FS punya resolusi nanodetik)."""
    old = os.path.getmtime(path)
    os.utime(path, (old + 5, old + 5))


# ---------------------------------------------------------------------------
# _read_md_cached
# ---------------------------------------------------------------------------


def test_read_md_cached_returns_content(tmp_path):
    p = tmp_path / "sub-home.md"
    p.write_text("# Bab Satu\n\n----Available_Lessons----\n", encoding="utf-8")
    assert _read_md_cached(str(p)) == "# Bab Satu\n\n----Available_Lessons----\n"


def test_read_md_cached_refreshes_on_mtime_change(tmp_path):
    p = tmp_path / "sub-home.md"
    p.write_text("versi 1", encoding="utf-8")
    assert _read_md_cached(str(p)) == "versi 1"

    p.write_text("versi 2", encoding="utf-8")
    _touch_mtime(p)
    assert _read_md_cached(str(p)) == "versi 2"


def test_read_md_cached_missing_file_returns_empty(tmp_path):
    assert _read_md_cached(str(tmp_path / "tidak-ada.md")) == ""


# ---------------------------------------------------------------------------
# find_sub_home_for_lesson
# ---------------------------------------------------------------------------


def test_find_sub_home_for_lesson_found(tmp_path):
    bab = tmp_path / "bab1"
    bab.mkdir()
    (bab / "sub-home.md").write_text("# Bab 1", encoding="utf-8")
    lesson = bab / "hello.md"
    lesson.write_text("# Hello", encoding="utf-8")

    sub_home_path, folder_name = find_sub_home_for_lesson(str(lesson))
    assert folder_name == "bab1"
    assert os.path.basename(sub_home_path) == "sub-home.md"


def test_find_sub_home_for_lesson_missing(tmp_path):
    bab = tmp_path / "bab1"
    bab.mkdir()
    lesson = bab / "hello.md"
    lesson.write_text("# Hello", encoding="utf-8")

    assert find_sub_home_for_lesson(str(lesson)) == (None, None)


def test_find_sub_home_for_lesson_none_path():
    assert find_sub_home_for_lesson(None) == (None, None)


# ---------------------------------------------------------------------------
# get_sub_home_data
# ---------------------------------------------------------------------------


def _write_sub_home_fixture(base, folder="bab1"):
    bab = base / folder
    bab.mkdir(parents=True, exist_ok=True)
    (bab / "sub-home.md").write_text(
        "# Bab Satu\n\nIntro bab satu.\n\n"
        "----Available_Lessons----\n"
        "1. [Hello, World!](lesson/hello_world.md)\n"
        "2. [Variabel](lesson/variabel.md)\n"
        "3. [Percabangan](lesson/percabangan.md)\n",
        encoding="utf-8",
    )
    (bab / "hello_world.md").write_text(
        "# Hello, World!\nMateri pertama.\n", encoding="utf-8"
    )
    (bab / "variabel.md").write_text("# Variabel\nMateri kedua.\n", encoding="utf-8")
    (bab / "percabangan.md").write_text("# Percabangan\nMateri ketiga.\n", encoding="utf-8")
    return bab


def test_get_sub_home_data_parses(tmp_path, monkeypatch):
    _write_sub_home_fixture(tmp_path)
    monkeypatch.setattr("services.lesson_service.CONTENT_DIR", str(tmp_path))

    data = get_sub_home_data("bab1")
    assert data is not None
    assert data["title"] == "Bab Satu"
    assert "Intro bab satu" in data["intro_html"]
    assert data["folder"] == "bab1"
    assert data["url"] == "/bab/bab1"
    filenames = [l["filename"] for l in data["lessons"]]
    assert filenames == ["hello_world.md", "variabel.md", "percabangan.md"]


def test_get_sub_home_data_missing_folder_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr("services.lesson_service.CONTENT_DIR", str(tmp_path))
    assert get_sub_home_data("tidak-ada") is None


def test_get_sub_home_data_missing_file_returns_none(tmp_path, monkeypatch):
    (tmp_path / "bab1").mkdir()
    monkeypatch.setattr("services.lesson_service.CONTENT_DIR", str(tmp_path))
    assert get_sub_home_data("bab1") is None


def test_get_sub_home_data_refreshes_on_change(tmp_path, monkeypatch):
    _write_sub_home_fixture(tmp_path)
    monkeypatch.setattr("services.lesson_service.CONTENT_DIR", str(tmp_path))

    data = get_sub_home_data("bab1")
    assert [l["filename"] for l in data["lessons"]] == [
        "hello_world.md",
        "variabel.md",
        "percabangan.md",
    ]

    # Ubah sub-home.md → panggilan berikutnya harus memakai data baru
    bab = tmp_path / "bab1"
    (bab / "sub-home.md").write_text(
        "# Bab Satu\n\n----Available_Lessons----\n"
        "1. [Hello, World!](lesson/hello_world.md)\n",
        encoding="utf-8",
    )
    _touch_mtime(bab / "sub-home.md")

    data2 = get_sub_home_data("bab1")
    assert [l["filename"] for l in data2["lessons"]] == ["hello_world.md"]


# ---------------------------------------------------------------------------
# get_ordered_lessons_with_learning_objectives(source_path=...)
# ---------------------------------------------------------------------------


def test_ordered_lessons_source_path_uses_sub_home(tmp_path, monkeypatch):
    _write_sub_home_fixture(tmp_path)
    # home.md global: hanya 1 lesson agar beda dengan daftar sub-home
    (tmp_path / "home.md").write_text(
        "# Home\n\n----Available_Lessons----\n"
        "1. [Hello, World!](lesson/hello_world.md)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("services.lesson_service.CONTENT_DIR", str(tmp_path))
    lesson_service.get_lessons.cache_clear()

    sub_home_path = str(tmp_path / "bab1" / "sub-home.md")
    lessons = get_ordered_lessons_with_learning_objectives(source_path=sub_home_path)
    filenames = [l["filename"] for l in lessons]
    assert filenames == ["hello_world.md", "variabel.md", "percabangan.md"]


def test_ordered_lessons_without_source_path_uses_home(tmp_path, monkeypatch):
    _write_sub_home_fixture(tmp_path)
    (tmp_path / "home.md").write_text(
        "# Home\n\n----Available_Lessons----\n"
        "1. [Hello, World!](lesson/hello_world.md)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("services.lesson_service.CONTENT_DIR", str(tmp_path))
    lesson_service.get_lessons.cache_clear()

    lessons = get_ordered_lessons_with_learning_objectives()
    filenames = [l["filename"] for l in lessons]
    assert filenames == ["hello_world.md"]


def test_ordered_lessons_with_completion_status(tmp_path, monkeypatch):
    _write_sub_home_fixture(tmp_path)
    (tmp_path / "home.md").write_text(
        "# Home\n\n----Available_Lessons----\n"
        "1. [Hello, World!](lesson/hello_world.md)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("services.lesson_service.CONTENT_DIR", str(tmp_path))
    lesson_service.get_lessons.cache_clear()

    progress = {"hello_world": "completed"}
    lessons = get_ordered_lessons_with_learning_objectives(progress=progress)
    assert lessons[0]["completed"] is True
    assert lessons[0]["filename"] == "hello_world.md"
