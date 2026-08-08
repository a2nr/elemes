"""
CSV importer — migrasi `tokens_siswa.csv` → PostgreSQL
(users / access_tokens / lessons / student_progress).

Format CSV (delimiter ';'):
  baris 1 : header  → token;nama_siswa;<lesson_1>;...;<lesson_n>
  baris 2 : GURU    (baris pertama data)  → role = teacher
  baris 3+ : siswa  → role = student
Nilai status per lesson:
  '' | not_started | completed | legacy '<n>/<m>' (skor quiz → state='scored')

Jaminan:
- dry_run        : parse + validasi penuh tanpa menulis apa pun.
- idempotent     : token & slug lesson yang sudah ada di-update, bukan duplikat.
- transactional  : seluruh import satu transaksi; error parah → rollback penuh.
- legacy '3/4'   : dipreservasi sebagai state='scored' + score_earned/score_total.
- laporan hanya berisi hitungan & pesan error — TIDAK pernah log token mentah.
"""

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.models import AccessToken, Lesson
from services.repositories import (
    create_access_token,
    create_user,
    find_user_by_raw_token,
    get_lesson_by_slug,
    set_progress,
    upsert_lesson,
)

logger = logging.getLogger(__name__)

VALID_FLAT_STATUSES = {"", "not_started", "completed"}
TOKEN_COL = "token"
NAME_COL = "nama_siswa"


@dataclass
class ProgressCell:
    state: str  # not_started | completed | scored
    score_earned: int | None = None
    score_total: int | None = None


@dataclass
class UserRow:
    role: str  # teacher | student
    display_name: str
    raw_token: str
    progress: dict[str, ProgressCell] = field(default_factory=dict)


@dataclass
class ImportPlan:
    users: list[UserRow] = field(default_factory=list)
    lesson_slugs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class ImportReport:
    total_rows: int = 0
    users_created: int = 0
    users_updated: int = 0
    tokens_created: int = 0
    lessons_created: int = 0
    progress_upserted: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "total_rows": self.total_rows,
            "users_created": self.users_created,
            "users_updated": self.users_updated,
            "tokens_created": self.tokens_created,
            "lessons_created": self.lessons_created,
            "progress_upserted": self.progress_upserted,
            "errors": self.errors,
            "ok": self.ok,
        }


# ── parse ──────────────────────────────────────────────────────────


def parse_csv(path: str | Path) -> list[dict]:
    """Baca CSV delimiter ';' menjadi list dict (keys = header)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSV tidak ditemukan: {path}")
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        if not reader.fieldnames:
            raise ValueError("CSV kosong (tanpa header)")
        rows = [row for row in reader]
    return rows


def _normalize_cell(value: str | None) -> str:
    return (value or "").strip()


def _parse_score(value: str) -> tuple[int, int] | None:
    """'3/4' → (3, 4); bukan format skor → None."""
    parts = value.split("/")
    if len(parts) != 2:
        return None
    try:
        earned, total = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if total <= 0 or earned < 0 or earned > total:
        return None
    return earned, total


def validate_and_plan(rows: list[dict]) -> ImportPlan:
    """Validasi & normalisasi seluruh baris → plan (tanpa menyentuh DB)."""
    plan = ImportPlan(errors=[])
    if not rows:
        plan.errors.append("CSV tidak punya baris data (hanya header?)")
        return plan

    seen_tokens: set[str] = set()
    lesson_slugs: list[str] = []

    for row_index, row in enumerate(rows):
        line = row_index + 2  # +1 header +1 zero-based
        token = _normalize_cell(row.get(TOKEN_COL))
        name = _normalize_cell(row.get(NAME_COL))

        if not token:
            plan.errors.append(f"Baris {line}: token kosong")
            continue
        if token in seen_tokens:
            plan.errors.append(f"Baris {line}: token duplikat (sudah ada di baris lain)")
            continue
        seen_tokens.add(token)

        if not name:
            plan.errors.append(f"Baris {line}: nama_siswa kosong untuk token")

        role = "teacher" if row_index == 0 else "student"
        user = UserRow(role=role, display_name=name, raw_token=token)

        for slug, raw in row.items():
            slug = _normalize_cell(slug)
            if slug in ("", TOKEN_COL, NAME_COL):
                continue
            if slug not in lesson_slugs:
                lesson_slugs.append(slug)
            value = _normalize_cell(raw)
            if value in VALID_FLAT_STATUSES:
                user.progress[slug] = ProgressCell(
                    state="not_started" if value in ("", "not_started") else "completed"
                )
                continue
            score = _parse_score(value)
            if score is None:
                plan.errors.append(
                    f"Baris {line}: status tidak dikenal untuk '{slug}': {value!r}"
                )
                continue
            user.progress[slug] = ProgressCell(
                state="scored", score_earned=score[0], score_total=score[1]
            )

        plan.users.append(user)

    plan.lesson_slugs = lesson_slugs
    return plan


# ── import ──────────────────────────────────────────────────────────


def run_import(db: Session, plan: ImportPlan, *, dry_run: bool = False) -> ImportReport:
    """Eksekusi plan ke PostgreSQL. dry_run=True → hitung tanpa menulis."""
    report = ImportReport(total_rows=len(plan.users))
    if not plan.ok:
        report.errors.extend(plan.errors)
        return report
    if dry_run:
        # Estimasi: user baru & progress yang BENAR-BENAR di-materialkan.
        # Sparse model: not_started tidak membuat row.
        report.users_created = len(plan.users)
        report.progress_upserted = sum(
            1 for u in plan.users for c in u.progress.values() if c.state != "not_started"
        )
        return report

    try:
        existing_slugs: set[str] = set()
        if plan.lesson_slugs:
            existing_slugs = set(
                db.scalars(
                    select(Lesson.slug).where(Lesson.slug.in_(plan.lesson_slugs))
                ).all()
            )

        for slug_index, slug in enumerate(plan.lesson_slugs):
            upsert_lesson(db, slug=slug, title=slug, order_index=slug_index)
            if slug not in existing_slugs:
                report.lessons_created += 1

        for user_row in plan.users:
            user = find_user_by_raw_token(db, user_row.raw_token)
            if user is None:
                user = create_user(
                    db, display_name=user_row.display_name, role=user_row.role
                )
                report.users_created += 1
            else:
                user.display_name = user_row.display_name
                user.role = user_row.role
                report.users_updated += 1

            if not _token_exists(db, user_row.raw_token):
                create_access_token(db, user_id=user.id, raw_token=user_row.raw_token)
                report.tokens_created += 1

            for slug, cell in user_row.progress.items():
                lesson = get_lesson_by_slug(db, slug)
                if lesson is None:
                    report.errors.append(f"Lesson {slug!r} tidak terdaftar — skip progress")
                    continue
                if cell.state == "not_started":
                    # sparse model: not_started = tidak ada row (hapus sisa row lama)
                    set_progress(
                        db,
                        user_id=user.id,
                        lesson_id=lesson.id,
                        state="not_started",
                    )
                    continue
                set_progress(
                    db,
                    user_id=user.id,
                    lesson_id=lesson.id,
                    state=cell.state,
                    score_earned=cell.score_earned,
                    score_total=cell.score_total,
                )
                report.progress_upserted += 1

        db.commit()
    except Exception as exc:  # noqa: BLE001 — laporan, bukan crash
        db.rollback()
        logger.exception("Import CSV gagal — rollback transaksi")
        report.errors.append(f"Import dibatalkan: {exc}")
    return report


def _token_exists(db: Session, raw_token: str) -> bool:
    from services.token_hashing import hash_token

    digest = hash_token(raw_token)
    return db.scalar(select(AccessToken.id).where(AccessToken.token_hash == digest)) is not None
