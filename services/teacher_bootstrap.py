"""
Bootstrap/manajemen akun guru canonical (satu-satunya user teacher).

Kontrak:
- Database mempertahankan TEPAT SATU akun guru (role='teacher').
- Jika belum ada guru  → buat satu user + satu access token.
- Jika sudah ada guru  → update display_name + revoke token lama + buat
  token baru pada user/UUID yang sama (upsert), tanpa menambah jumlah guru.
- Token yang sama dengan token aktif guru → update nama saja (idempotent).
- Token yang sudah dimiliki siswa → tolak seluruh operasi.
- Lebih dari satu guru (data legacy) → fail closed, minta normalisasi manual.

Keamanan:
- Tidak pernah mencetak raw token maupun digest.
- Satu transaksi; error → rollback total.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.models import AccessToken, User
from services.repositories import (
    create_access_token,
    create_user,
    find_user_by_raw_token,
    hash_token,
    revoke_all_tokens,
)

_MAX_NAME_LEN = 255


class TeacherBootstrapError(RuntimeError):
    """Penolakan operasional; pesan aman untuk ditampilkan (tanpa secret)."""


def _teacher_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).where(User.role == "teacher")))


def _is_active_token_of(db: Session, user_id: str, raw_token: str) -> bool:
    digest = hash_token(raw_token)
    token = db.scalar(
        select(AccessToken).where(
            AccessToken.token_hash == digest,
            AccessToken.user_id == user_id,
            AccessToken.revoked_at.is_(None),
        )
    )
    return token is not None


def _ensure_token_for_teacher(db: Session, user_id: str, raw_token: str) -> None:
    """Aktifkan token untuk guru; reactivate bila baris digest sudah ada.

    Digest bersifat unik (`uq_access_tokens_token_hash`), jadi token yang
    pernah di-revoke TIDAK boleh dibuat ulang sebagai baris baru — cukup
    re-activate baris lama. Token milik user lain (siswa) sudah ditolak
    oleh pemanggil sebelum sampai sini.
    """
    digest = hash_token(raw_token)
    existing = db.scalar(
        select(AccessToken).where(
            AccessToken.token_hash == digest,
            AccessToken.user_id == user_id,
        )
    )
    if existing is not None:
        existing.revoked_at = None
        return
    create_access_token(db, user_id=user_id, raw_token=raw_token)


def upsert_teacher(db: Session, *, display_name: str, raw_token: str) -> dict:
    """Upsert satu akun guru canonical; commit/rollback dikelola di sini.

    Returns dict {"action": "created"|"updated"|"unchanged", "message": str}
    — tanpa secret apa pun.

    Raises:
        TeacherBootstrapError — penolakan dengan pesan aman untuk ditampilkan.
        Exception lain — kegagalan tak terduga (sudah di-rollback).
    """
    display_name = (display_name or "").strip()
    raw_token = (raw_token or "").strip()
    if not display_name:
        raise TeacherBootstrapError("Nama guru tidak boleh kosong.")
    if len(display_name) > _MAX_NAME_LEN:
        raise TeacherBootstrapError(
            f"Nama guru terlalu panjang (maksimal {_MAX_NAME_LEN} karakter)."
        )
    if not raw_token:
        raise TeacherBootstrapError("Token guru tidak boleh kosong.")

    try:
        teachers = _teacher_users(db)
        if len(teachers) > 1:
            raise TeacherBootstrapError(
                "Ditemukan lebih dari satu akun guru di database. "
                "Normalisasi data secara manual terlebih dahulu; "
                "operasi tidak memilih atau menghapus guru secara otomatis."
            )

        owner = find_user_by_raw_token(db, raw_token)
        if owner is not None and owner.role == "student":
            raise TeacherBootstrapError(
                "Token tersebut sudah dimiliki akun siswa; "
                "operasi dibatalkan tanpa mengubah data guru."
            )

        if not teachers:
            user = create_user(db, display_name=display_name, role="teacher")
            create_access_token(db, user_id=user.id, raw_token=raw_token)
            db.commit()
            return {
                "action": "created",
                "message": "Akun guru dibuat: nama dan token aktif tersimpan.",
            }

        teacher = teachers[0]
        token_changed = not _is_active_token_of(db, teacher.id, raw_token)
        name_changed = teacher.display_name != display_name

        if name_changed:
            teacher.display_name = display_name
        if token_changed:
            revoke_all_tokens(db, user_id=teacher.id)
            _ensure_token_for_teacher(db, user_id=teacher.id, raw_token=raw_token)
        db.commit()

        if not (token_changed or name_changed):
            return {"action": "unchanged", "message": "Data guru tidak berubah."}
        if token_changed and name_changed:
            return {
                "action": "updated",
                "message": "Data guru diperbarui: nama baru + token dirotasi.",
            }
        if token_changed:
            return {"action": "updated", "message": "Data guru diperbarui: token dirotasi."}
        return {"action": "updated", "message": "Data guru diperbarui: nama baru."}
    except TeacherBootstrapError:
        if db is not None:
            db.rollback()
        raise
    except Exception:
        if db is not None:
            db.rollback()
        raise
