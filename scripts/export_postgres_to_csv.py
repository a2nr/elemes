#!/usr/bin/env python3
"""
Ekspor snapshot PostgreSQL → CSV (tanpa token mentah).

Token RAW sengaja TIDAK diekspor: sejak migrasi, token hanya disimpan
sebagai HMAC-SHA256 digest (lihat services/token_hashing.py) — tidak
reversibel. Kolom pertama = id (user.id), berguna untuk laporan/reset
via student_id dan untuk membandingkan snapshot antar waktu.

Contoh:
  python scripts/export_postgres_to_csv.py --out /tmp/pg_snapshot.csv
"""

import argparse
import csv
import os
import sys

from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='pg_snapshot.csv')
    parser.add_argument('--env', default=None)
    args = parser.parse_args()

    if args.env:
        load_dotenv(args.env)

    from sqlalchemy import select

    from services.database import SessionLocal
    from services.models import Lesson, User
    from services.repositories import count_completed_lessons, list_progress_for_user

    if SessionLocal is None:
        print('❌ DATABASE_URL tidak diset')
        sys.exit(2)

    db = SessionLocal()
    lessons = list(db.scalars(select(Lesson).order_by(Lesson.order_index, Lesson.slug)))
    users = list(db.scalars(select(User).order_by(User.created_at)))

    fieldnames = ['id', 'nama_siswa'] + [l.slug for l in lessons] + ['completed_count']
    with open(args.out, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        for user in users:
            rows = {p.lesson_id: p for p in list_progress_for_user(db, user_id=user.id)}
            row = {'id': user.id, 'nama_siswa': user.display_name}
            for lesson in lessons:
                p = rows.get(lesson.id)
                if p is None:
                    row[lesson.slug] = ''
                elif p.state == 'scored':
                    row[lesson.slug] = f'{p.score_earned}/{p.score_total}'
                else:
                    row[lesson.slug] = p.state
            row['completed_count'] = count_completed_lessons(db, user_id=user.id)
            writer.writerow(row)
    db.close()

    print(f'✅ Snapshot {len(users)} user, {len(lessons)} lesson → {args.out}')
    print('   Catatan: token mentah tidak diekspor (hanya hash disimpan).')


if __name__ == '__main__':
    main()
