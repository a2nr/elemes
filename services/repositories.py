"""
Repository layer — seluruh akses data PostgreSQL lewat SQLAlchemy session.

Dipanggil oleh service/facade; session & commit dikelola pemanggil
(mis. get_db() per request). Kontrak perilaku dijamin test integrasi
terhadap PostgreSQL nyata (test_repositories.py) dan suite kontrak
(test_token_service_contract.py) yang sama untuk kedua backend.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.models import AccessToken, Lesson, StudentProgress, User
from services.progress_status import ParsedProgress
from services.student_roundtrip import (
    RoundTripImportError,
    StudentRoundTripRow,
    is_canonical_uuid,
    serialize_export_csv,
)
from services.token_hashing import hash_token


def _uuid() -> str:
    return str(uuid4())


# ── users & access_tokens ─────────────────────────────────────────


def get_user_by_id(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def get_user_by_token(db: Session, raw_token: str) -> User | None:
    """Lookup user dari token mentah. Update last_used_at (tanpa commit)."""
    digest = hash_token(raw_token)
    token = db.scalar(
        select(AccessToken).where(
            AccessToken.token_hash == digest,
            AccessToken.revoked_at.is_(None),
        )
    )
    if token is None:
        return None
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        return None
    token.last_used_at = datetime.now(timezone.utc)
    return user


def find_user_by_raw_token(db: Session, raw_token: str) -> User | None:
    """Lookup user dari token mentah TANPA side-effect (untuk importer/verifikasi)."""
    digest = hash_token(raw_token)
    token = db.scalar(select(AccessToken).where(AccessToken.token_hash == digest))
    if token is None:
        return None
    return db.get(User, token.user_id)


def create_user(
    db: Session,
    *,
    display_name: str,
    role: str,
    is_active: bool = True,
    user_id: str | None = None,
) -> User:
    """Buat user baru; `user_id` opsional (create-with-ID untuk import round-trip).

    Caller existing tidak berubah — parameter baru bersifat opsional.
    """
    kwargs: dict = {"display_name": display_name, "role": role, "is_active": is_active}
    if user_id is not None:
        kwargs["id"] = user_id
    user = User(**kwargs)
    db.add(user)
    db.flush()
    return user


def create_access_token(
    db: Session, *, user_id: str, raw_token: str
) -> AccessToken:
    token = AccessToken(id=_uuid(), user_id=user_id, token_hash=hash_token(raw_token))
    db.add(token)
    db.flush()
    return token


def revoke_token(db: Session, *, user_id: str, raw_token: str) -> bool:
    digest = hash_token(raw_token)
    token = db.scalar(
        select(AccessToken).where(
            AccessToken.token_hash == digest,
            AccessToken.user_id == user_id,
        )
    )
    if token is None:
        return False
    token.revoked_at = datetime.now(timezone.utc)
    return True


def revoke_all_tokens(db: Session, *, user_id: str) -> int:
    tokens = list(
        db.scalars(
            select(AccessToken).where(
                AccessToken.user_id == user_id,
                AccessToken.revoked_at.is_(None),
            )
        )
    )
    for token in tokens:
        token.revoked_at = datetime.now(timezone.utc)
    return len(tokens)


# ── lessons ────────────────────────────────────────────────────────


def list_lessons(db: Session) -> list[Lesson]:
    return list(db.scalars(select(Lesson).order_by(Lesson.order_index, Lesson.slug)))


def list_active_lessons(db: Session) -> list[Lesson]:
    return list(
        db.scalars(select(Lesson).where(Lesson.is_active.is_(True)).order_by(Lesson.order_index, Lesson.slug))
    )


def get_lesson_by_slug(db: Session, slug: str) -> Lesson | None:
    return db.scalar(select(Lesson).where(Lesson.slug == slug))


def upsert_lesson(db: Session, *, slug: str, title: str, order_index: int) -> Lesson:
    lesson = get_lesson_by_slug(db, slug)
    if lesson is None:
        lesson = Lesson(slug=slug, title=title, order_index=order_index)
        db.add(lesson)
    else:
        lesson.title = title
        lesson.order_index = order_index
        lesson.is_active = True
    db.flush()
    return lesson


def deactivate_missing_lessons(db: Session, active_slugs: set[str]) -> int:
    """Lesson yang tidak ada lagi di Markdown → is_active=False (bukan dihapus)."""
    lessons = list(db.scalars(select(Lesson).where(Lesson.is_active.is_(True))))
    changed = 0
    for lesson in lessons:
        if lesson.slug not in active_slugs:
            lesson.is_active = False
            changed += 1
    return changed


# ── student_progress ───────────────────────────────────────────────


def get_progress(db: Session, *, user_id: str, lesson_id: str) -> StudentProgress | None:
    return db.scalar(
        select(StudentProgress).where(
            StudentProgress.user_id == user_id,
            StudentProgress.lesson_id == lesson_id,
        )
    )


def list_progress_for_user(db: Session, *, user_id: str) -> list[StudentProgress]:
    return list(
        db.scalars(select(StudentProgress).where(StudentProgress.user_id == user_id))
    )


def set_progress(
    db: Session,
    *,
    user_id: str,
    lesson_id: str,
    state: str,
    score_earned: int | None = None,
    score_total: int | None = None,
) -> StudentProgress | None:
    """Upsert progress (sparse model).

    - state='not_started' → HAPUS row bila ada; tidak ada row = not_started.
    - state='scored' wajib membawa score_earned & score_total.
    """
    if state == "not_started":
        progress = get_progress(db, user_id=user_id, lesson_id=lesson_id)
        if progress is not None:
            db.delete(progress)
            db.flush()
        return None
    if state == "scored":
        if score_earned is None or score_total is None:
            raise ValueError("state='scored' memerlukan score_earned & score_total")
    else:
        score_earned = None
        score_total = None

    progress = get_progress(db, user_id=user_id, lesson_id=lesson_id)
    if progress is None:
        progress = StudentProgress(
            id=_uuid(),
            user_id=user_id,
            lesson_id=lesson_id,
            state=state,
            score_earned=score_earned,
            score_total=score_total,
        )
        db.add(progress)
    else:
        progress.state = state
        progress.score_earned = score_earned
        progress.score_total = score_total
    db.flush()
    return progress


def count_completed_lessons(db: Session, *, user_id: str) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(StudentProgress)
            .where(
                StudentProgress.user_id == user_id,
                StudentProgress.state.in_(("completed", "scored")),
            )
        )
        or 0
    )


# ── export / import round-trip ─────────────────────────────────────


def _validate_id_list(student_ids: list[str], *, field: str) -> set[str]:
    """Validasi array UUID: tipe list, 1-1000 item, canonical, tanpa duplikat.

    Raise ValueError dengan pesan aman (tanpa data sensitif).
    """
    if not isinstance(student_ids, list) or not student_ids:
        raise ValueError(f"{field} wajib berisi 1-1000 UUID")
    if len(student_ids) > 1000:
        raise ValueError(f"Maksimum 1000 UUID pada {field}")
    seen: set[str] = set()
    for sid in student_ids:
        if not is_canonical_uuid(sid):
            raise ValueError(f"UUID tidak valid pada {field}: {sid!r}")
        if sid in seen:
            raise ValueError(f"UUID duplikat pada {field}: {sid!r}")
        seen.add(sid)
    return seen


def list_students_for_export(
    db: Session,
    student_ids: list[str] | None = None,
) -> list[User]:
    """Siswa untuk export — hanya role student, urutan deterministik.

    - `student_ids=None` atau array kosong → seluruh siswa.
    - Array non-kosong → divalidasi ketat: duplicate/malformed/unknown/teacher
      ID membuat seluruh request gagal (bukan diam-diam dilewati).
    """
    if student_ids:
        wanted = _validate_id_list(student_ids, field="student_ids")
        users = list(
            db.scalars(
                select(User)
                .where(User.id.in_(wanted), User.role == "student")
                .order_by(User.created_at, User.id)
            )
        )
        found = {u.id for u in users}
        missing = [sid for sid in student_ids if sid not in found]
        if missing:
            raise ValueError("student_id tidak dikenal atau bukan siswa")
        return users
    return list(
        db.scalars(
            select(User).where(User.role == "student").order_by(User.created_at, User.id)
        )
    )


def export_students_csv(
    db: Session,
    student_ids: list[str] | None = None,
) -> bytes:
    """Export siswa (selection atau seluruh) + progress → CSV round-trip bytes.

    Kolom token selalu kosong; teacher tidak pernah ikut; export tidak mengubah DB.
    """
    users = list_students_for_export(db, student_ids)
    lessons = list_active_lessons(db)
    lesson_slugs = [lesson.slug for lesson in lessons]

    rows: list[StudentRoundTripRow] = []
    for user in users:
        progress_rows = {
            p.lesson_id: p for p in list_progress_for_user(db, user_id=user.id)
        }
        progress: dict[str, ParsedProgress] = {}
        for lesson in lessons:
            p = progress_rows.get(lesson.id)
            if p is None:
                continue
            if p.state == "scored":
                progress[lesson.slug] = ParsedProgress(
                    "scored", p.score_earned, p.score_total
                )
            elif p.state == "completed":
                progress[lesson.slug] = ParsedProgress("completed")
        rows.append(
            StudentRoundTripRow(
                line=0,
                student_id=user.id,
                raw_token="",
                display_name=user.display_name,
                progress=progress,
            )
        )
    return serialize_export_csv(rows, lesson_slugs)


def find_student_import_conflicts(
    db: Session, rows: list[StudentRoundTripRow]
) -> list[str]:
    """Conflict terhadap database saat ini (tanpa write).

    Aturan identitas baris (kontrak round-trip):
    - student_id terisi → user WAJIB sudah ada dan ber-role `student`; siswa
      existing TIDAK boleh menerima token baru (import hanya restore/update
      nama & progress; token lama dipertahankan).
    - student_id kosong (siswa baru) → token wajib non-kosong (dijamin
      parser); HMAC digest token tidak boleh sudah ada di `access_tokens`
      (termasuk token revoked).

    Error tidak pernah menyebut token mentah maupun digest.
    """
    conflicts: list[str] = []

    # Query semua student_id terisi SEKALI, lalu validasi keberadaan & role.
    existing_by_id: dict[str, User] = {}
    ids = [r.student_id for r in rows if r.student_id]
    if ids:
        for user in db.scalars(select(User).where(User.id.in_(ids))):
            existing_by_id[user.id] = user

    new_rows: list[StudentRoundTripRow] = []
    for row in rows:
        if row.student_id:
            user = existing_by_id.get(row.student_id)
            if user is None:
                conflicts.append(
                    f"Baris {row.line}: student_id tidak dikenal atau bukan siswa"
                )
            elif user.role != "student":
                conflicts.append(
                    f"Baris {row.line}: student_id milik teacher — import tidak dapat mengubah teacher"
                )
            elif row.raw_token:
                conflicts.append(
                    f"Baris {row.line}: siswa existing tidak boleh menerima token baru "
                    "(hapus siswa terlebih dahulu untuk membuat ulang)"
                )
        else:
            new_rows.append(row)

    # Hanya siswa baru yang ikut pemeriksaan digest token.
    if new_rows:
        digests = {hash_token(r.raw_token) for r in new_rows}
        existing_digests = set(
            db.scalars(
                select(AccessToken.token_hash).where(
                    AccessToken.token_hash.in_(digests)
                )
            )
        )
        for row in new_rows:
            if hash_token(row.raw_token) in existing_digests:
                conflicts.append(f"Baris {row.line}: token sudah terdaftar di database")
    return conflicts


def preview_student_import(
    db: Session, rows: list[StudentRoundTripRow]
) -> dict:
    """Ringkasan import TANPA menulis apa pun.

    Baris dengan student_id terisi dilaporkan sebagai update/restore
    (bukan create); baris tanpa student_id sebagai siswa baru. Conflict
    dihitung terhadap state DB saat ini; apply akan memvalidasi ulang.
    """
    conflicts = find_student_import_conflicts(db, rows)
    to_create = [r for r in rows if not r.student_id]
    to_update = [r for r in rows if r.student_id]
    return {
        "rows": len(rows),
        "students_to_create": len(to_create),
        "students_to_update": len(to_update),
        "progress_to_create": sum(len(r.progress) for r in to_create),
        "progress_to_restore": sum(len(r.progress) for r in to_update),
        "conflicts": conflicts,
    }


def run_student_import(
    db: Session, rows: list[StudentRoundTripRow]
) -> dict:
    """Import all-or-nothing: siswa baru dibuat, siswa existing di-restore.

    - Memvalidasi ulang conflict terhadap state DB TERBARU (mengalahkan race
      preview→apply); bila ada conflict baru, seluruh import gagal tanpa write.
    - Siswa baru (student_id kosong): buat user role student + access token
      (digest) + progress non-not_started, seperti sebelumnya.
    - Siswa existing (student_id terisi, token kosong): pertahankan user &
      token lama; update display_name sesuai CSV; apply progress
      non-not_started. TIDAK ada token baru yang dibuat/ditimpa.
    - Sparse progress dipertahankan: status kosong/not_started tidak pernah
      menjadi row database, dan progress lama yang tidak ada di CSV TIDAK
      dihapus (merge, bukan snapshot penuh).

    Catatan transaksi: fungsi ini sengaja melakukan COMMIT sekali (kontrak
    all-or-nothing round-trip) — pemanggil (route) TIDAK commit lagi. Ini
    menyimpang dari pola umum repository yang menyerahkan commit ke pemanggil;
    pengecualian ini diperlukan agar seluruh file masuk dalam satu transaksi.
    """
    conflicts = find_student_import_conflicts(db, rows)
    if conflicts:
        raise RoundTripImportError(conflicts)

    user_ids: list[str] = []
    students_created = 0
    students_updated = 0
    progress_created = 0
    progress_restored = 0
    try:
        for row in rows:
            if row.student_id:
                user = db.get(User, row.student_id)
                if user is None or user.role != "student":
                    # Tidak mungkin terjadi pasca-validasi conflict; jaga safety.
                    raise ValueError(
                        f"Baris {row.line}: student_id tidak dikenal atau bukan siswa"
                    )
                user.display_name = row.display_name
                students_updated += 1
            else:
                user = create_user(
                    db,
                    display_name=row.display_name,
                    role="student",
                    is_active=True,
                    user_id=row.student_id,
                )
                create_access_token(db, user_id=user.id, raw_token=row.raw_token)
                students_created += 1

            for slug, parsed in row.progress.items():
                lesson = get_lesson_by_slug(db, slug)
                if lesson is None:
                    raise ValueError(f"Baris {row.line}: lesson tidak dikenal: {slug!r}")
                set_progress(
                    db,
                    user_id=user.id,
                    lesson_id=lesson.id,
                    state=parsed.state,
                    score_earned=parsed.score_earned,
                    score_total=parsed.score_total,
                )
                if row.student_id:
                    progress_restored += 1
                else:
                    progress_created += 1
            user_ids.append(user.id)
        db.commit()
    except IntegrityError:
        # Race: token/UUID bentrok dengan transaksi lain antara validasi & commit
        db.rollback()
        raise RoundTripImportError(
            ["Terjadi konflik data saat menyimpan (perubahan bersamaan) — seluruh import dibatalkan"]
        ) from None
    except Exception:
        db.rollback()
        raise
    return {
        "students_created": students_created,
        "students_updated": students_updated,
        "progress_created": progress_created,
        "progress_restored": progress_restored,
        "user_ids": user_ids,
    }


# ── bulk delete ────────────────────────────────────────────────────


def delete_students(db: Session, student_ids: list[str]) -> list[str]:
    """Hapus permanen siswa terpilih beserta token & progress (cascade).

    - Seluruh ID divalidasi SEBELUM delete pertama: duplicate/malformed/unknown/
      teacher ID membatalkan seluruh request (zero delete).
    - Query wajib `User.role == 'student'`; teacher terlindungi.
    - Tidak commit — transaksi dikelola pemanggil (service/route).
    - Setelah commit, UUID & token target boleh dipakai ulang oleh importer.
    """
    wanted = _validate_id_list(student_ids, field="student_ids")
    users = list(
        db.scalars(select(User).where(User.id.in_(wanted), User.role == "student"))
    )
    found = {u.id for u in users}
    missing = [sid for sid in student_ids if sid not in found]
    if missing:
        raise ValueError("student_id tidak dikenal atau bukan siswa")
    for user in users:
        db.delete(user)
    db.flush()
    return [u.id for u in users]
