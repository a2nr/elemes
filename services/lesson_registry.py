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
    """Daftar (slug, title, order_index) dari **seluruh** lesson aktif —

    root home.md ditambah setiap sub-home.md (bab/<folder>/sub-home.md).

    Urutan: root home.md dulu (indeks lokal), lalu sub-bab (indeks lokal).
    Slug didedupe (root selalu menang atas sub-bab bila collision) sehingga
    satu lesson ≡ satu baris di tabel `lessons`, tak tergantung dari halaman
    mana siswa/guru mengakses materi tersebut.

    Tidak pakai cache — fresh setiap panggilan agar perubahan home.md/sub-home.md
    yang belum trigger restart tetap terpantau pada sync berikutnya.
    """
    lesson_service.get_lessons.cache_clear()
    specs: dict[str, tuple[str, str, int]] = {}

    # 1) Root home.md — prioritas utama, urutan index-nya menjadi acuan.
    root_lessons = lesson_service.get_lessons()
    for idx, lesson in enumerate(root_lessons):
        slug = lesson["filename"]
        if slug.endswith(".md"):
            slug = slug[:-3]
        specs[slug] = (slug, lesson["title"], idx)

    # 2) Tiap folder level-1 yang punya sub-home.md.
    for folder in lesson_service.find_all_sub_home_folders():
        path = lesson_service.get_sub_home_path(folder)
        if not path:
            continue
        sub_lessons = lesson_service.get_lessons(source_path=path)
        for idx, lesson in enumerate(sub_lessons):
            slug = lesson["filename"]
            if slug.endswith(".md"):
                slug = slug[:-3]
            # root selamat: setdefault agar urutan root tidak tertimpa.
            specs.setdefault(slug, (slug, lesson["title"], idx))

    return list(specs.values())


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
    aplikasi tetap jalan; sync berjalan lagi saat startup berikutnya
    (command manual `synclessons` sudah dihapus)."""
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
