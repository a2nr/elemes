#!/usr/bin/env python3
"""
Verifikasi parity CSV ↔ PostgreSQL — WAJIB lulus sebelum cutover storage.

Cek:
  1. Setiap token di CSV terdaftar di PG (users + access_tokens via hash).
  2. Baris pertama CSV (guru) → role 'teacher'; baris lain → 'student'.
  3. Status tiap lesson identik ('' / 'not_started' dianggap sama).

Exit code: 0 = parity OK, 1 = ada mismatch, 2 = tidak bisa connect.

Contoh:
  python scripts/verify_database_migration.py --csv tokens.csv
"""

import argparse
import csv
import os
import sys

from dotenv import load_dotenv


def load_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        return (reader.fieldnames or []), list(reader)


def normalize(status: str) -> str:
    """'' dan 'not_started' dianggap sama (belum dikerjakan)."""
    status = (status or '').strip()
    return '' if status in ('', 'not_started') else status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', default='tokens.csv', help='CSV sumber (default: tokens.csv)')
    parser.add_argument('--env', default=None, help='Path .env untuk DATABASE_URL (opsional)')
    args = parser.parse_args()

    if args.env:
        load_dotenv(args.env)

    from sqlalchemy import select

    from services.database import SessionLocal
    from services.models import AccessToken, Lesson, User
    from services.token_hashing import hash_token

    if SessionLocal is None:
        print('❌ DATABASE_URL tidak diset — PostgreSQL tidak aktif')
        sys.exit(2)

    fieldnames, rows = load_csv(args.csv)
    lesson_slugs = [c for c in fieldnames if c not in ('token', 'nama_siswa')]
    print(f'📄 CSV: {len(rows)} baris, {len(lesson_slugs)} lesson: {lesson_slugs}')

    db = SessionLocal()
    problems = []

    for idx, row in enumerate(rows):
        raw = row.get('token', '')
        digest = hash_token(raw)
        tok = db.scalar(select(AccessToken).where(AccessToken.token_hash == digest))
        if tok is None:
            problems.append(f'row {idx}: token {raw[:6]}... tidak ditemukan di PG')
            continue
        user = db.get(User, tok.user_id)
        if user is None:
            problems.append(f'row {idx}: user token {raw[:6]}... tidak ada')
            continue
        expected_role = 'teacher' if idx == 0 else 'student'
        if user.role != expected_role:
            problems.append(f'row {idx} ({user.display_name}): role {user.role} != {expected_role}')

        progress_rows = {}
        for p in user.progress:
            progress_rows[p.lesson_id] = p
        for slug in lesson_slugs:
            lesson = db.scalar(select(Lesson).where(Lesson.slug == slug))
            if lesson is None:
                problems.append(f'row {idx}: lesson "{slug}" tidak terdaftar di registry')
                continue
            p = progress_rows.get(lesson.id)
            csv_status = normalize(row.get(slug, ''))
            if p is None:
                pg_status = ''
            elif p.state == 'scored':
                pg_status = f'{p.score_earned}/{p.score_total}'
            else:
                pg_status = p.state
            pg_status = normalize(pg_status)
            if csv_status != pg_status:
                problems.append(
                    f'row {idx} ({user.display_name}), lesson {slug}: CSV={csv_status!r} PG={pg_status!r}'
                )

    db.close()

    if problems:
        print(f'❌ Parity GAGAL — {len(problems)} mismatch:')
        for msg in problems[:30]:
            print(f'   - {msg}')
        if len(problems) > 30:
            print(f'   … dan {len(problems) - 30} lainnya')
        sys.exit(1)

    print('✅ Parity OK — CSV dan PostgreSQL identik (token, role, progress).')
    sys.exit(0)


if __name__ == '__main__':
    main()
