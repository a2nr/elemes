"""
Integration test untuk endpoint sub-home / bab:

1. `GET /bab/<folder>` — mengembalikan JSON isi sub-home.md.
2. `GET /lesson/<slug>.json` — `ordered_lessons` diambil dari sub-home.md
   bila folder memiliki file tersebut (fallback ke home.md bila tidak).

Menggunakan Flask test client (`app`/`client` fixture dari conftest) dengan
CONTENT_DIR yang di-point ke direktori test sementara.
"""

import os

import pytest

from services import lesson_service


@pytest.fixture()
def content_dir(tmp_path, monkeypatch):
    """Buat struktur content test: home.md + bab1/ dengan sub-home.md & 3 lesson."""
    bab = tmp_path / "bab1"
    bab.mkdir()
    (bab / "sub-home.md").write_text(
        "# Bab Satu\n\nIntro bab satu.\n\n"
        "----Available_Lessons----\n"
        "1. [Hello, World!](lesson/hello_world.md)\n"
        "2. [Variabel](lesson/variabel.md)\n"
        "3. [Percabangan](lesson/percabangan.md)\n",
        encoding="utf-8",
    )
    for name in ("hello_world", "variabel", "percabangan"):
        (bab / f"{name}.md").write_text(f"# {name.replace('_', ' ').title()}\nMateri.\n", encoding="utf-8")

    (tmp_path / "home.md").write_text(
        "# Home\n\n----Available_Lessons----\n"
        "1. [Hello, World!](lesson/hello_world.md)\n"
        "2. [Variabel](lesson/variabel.md)\n"
        "3. [Percabangan](lesson/percabangan.md)\n"
        "4. [Lesson Global](lesson/lesson_global.md)\n",
        encoding="utf-8",
    )
    (tmp_path / "lesson_global.md").write_text("# Lesson Global\nMateri global.\n", encoding="utf-8")

    monkeypatch.setattr("services.lesson_service.CONTENT_DIR", str(tmp_path))
    lesson_service.find_lesson_file.cache_clear()
    lesson_service.get_lessons.cache_clear()
    lesson_service.get_lesson_names.cache_clear()
    lesson_service.get_lessons_with_learning_objectives.cache_clear()
    yield tmp_path
    lesson_service.find_lesson_file.cache_clear()
    lesson_service.get_lessons.cache_clear()
    lesson_service.get_lesson_names.cache_clear()
    lesson_service.get_lessons_with_learning_objectives.cache_clear()


def test_bab_endpoint_returns_sub_home_json(client, content_dir):
    resp = client.get("/bab/bab1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Bab Satu"
    assert "Intro bab satu" in data["intro_html"]
    assert data["folder"] == "bab1"
    assert [l["filename"] for l in data["lessons"]] == [
        "hello_world.md",
        "variabel.md",
        "percabangan.md",
    ]


def test_bab_endpoint_missing_folder_404(client, content_dir):
    resp = client.get("/bab/tidak-ada")
    assert resp.status_code == 404


def test_lesson_ordered_lessons_scoped_to_sub_home(client, content_dir):
    resp = client.get("/lesson/variabel.json")
    assert resp.status_code == 200
    data = resp.get_json()
    # Lesson di dalam folder dengan sub-home.md → ordered_lessons dari sub-home.md
    assert [l["filename"] for l in data["ordered_lessons"]] == [
        "hello_world.md",
        "variabel.md",
        "percabangan.md",
    ]
    assert data["sub_home"] is not None
    assert data["sub_home"]["folder"] == "bab1"


def test_lesson_outside_sub_home_uses_home_fallback(client, content_dir):
    resp = client.get("/lesson/lesson_global.json")
    assert resp.status_code == 200
    data = resp.get_json()
    # Lesson di luar folder sub-home → ordered_lessons fallback ke home.md (semua)
    assert [l["filename"] for l in data["ordered_lessons"]] == [
        "hello_world.md",
        "variabel.md",
        "percabangan.md",
        "lesson_global.md",
    ]
    assert data["sub_home"] is None


def test_lesson_prev_next_within_sub_home(client, content_dir):
    resp = client.get("/lesson/variabel.json")
    data = resp.get_json()
    assert data["prev_lesson"]["filename"] == "hello_world.md"
    assert data["next_lesson"]["filename"] == "percabangan.md"
