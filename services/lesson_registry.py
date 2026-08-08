"""
Lesson registry — sinkron metadata lesson dari Markdown (home.md) ke tabel `lessons`.

Konten tetap dari Markdown (lesson_service); DB hanya menyimpan metadata
(slug, title, urutan, status aktif). Lesson yang hilang dari home.md
ditandai is_active=False, BUKAN dihapus — history progress tetap utuh.
"""

import logging

from sqlalchemy.orm import Session

from services import lesson_service
from services.repositories import deactivate_missing_lessons, list_lessons, upsert_lesson

logger = logging.getLogger(__name__)


def lesson_specs() -> list[tuple[str, str, int]]:
    """Daftar (slug, title, order_index) dari home.md — fresh, tanpa cache.

    Urutan mengikuti daftar Available_Lessons di home.md.
    """
    lesson_service.get_lessons.cache_clear()
    lessons = lesson_service.get_lessons()
    specs = []
    for idx, lesson in enumerate(lessons):
        slug = lesson["filename"]
        if slug.endswith(".md"):
            slug = slug[:-3]
        specs.append((slug, lesson["title"], idx))
    return specs


def sync_lesson_registry(db: Session) -> dict:
    """Upsert semua lesson aktif dari Markdown; nonaktifkan yang hilang.

    Idempotent — aman dipanggil berulang (startup, command, atau cron).
    """
    specs = lesson_specs()
    active_slugs = {slug for slug, _, _ in specs}
    upserted = 0
    for slug, title, order_index in specs:
        upsert_lesson(db, slug=slug, title=title, order_index=order_index)
        upserted += 1
    deactivated = deactivate_missing_lessons(db, active_slugs)
    db.commit()
    all_lessons = list_lessons(db)
    return {
        "specs": len(specs),
        "upserted": upserted,
        "deactivated": deactivated,
        "total": len(all_lessons),
        "active": sum(1 for lesson in all_lessons if lesson.is_active),
    }


def maybe_sync_on_startup():
    """Auto-sync saat app init (storage PostgreSQL). Error DB hanya di-log —
    aplikasi tetap jalan; sinkronisasi bisa diulang via `elemes.sh synclessons`."""
    from services.database import SessionLocal  # lazy: tanpa DB tidak dipanggil

    if SessionLocal is None:
        return
    try:
        db = SessionLocal()
        try:
            result = sync_lesson_registry(db)
            logger.info("Lesson registry disinkronkan: %s", result)
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 — startup tidak boleh crash karena DB
        logger.warning("Sync lesson registry gagal (akan dicoba lagi nanti): %s", exc)
