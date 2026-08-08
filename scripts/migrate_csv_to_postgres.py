#!/usr/bin/env python3
"""
CLI migrasi CSV → PostgreSQL.

Contoh:
  python scripts/migrate_csv_to_postgres.py --csv ../tokens_siswa.csv --dry-run
  python scripts/migrate_csv_to_postgres.py --csv ../tokens_siswa.csv

Membaca konfigurasi dari .env (repo root) bila DATABASE_URL belum di-set.
"""

import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from services.csv_importer import parse_csv, run_import, validate_and_plan  # noqa: E402
from services.database import SessionLocal  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import tokens_siswa.csv ke PostgreSQL")
    parser.add_argument("--csv", required=True, help="Path ke file CSV (delimiter ';')")
    parser.add_argument("--dry-run", action="store_true", help="Validasi tanpa menulis")
    args = parser.parse_args()

    if SessionLocal is None:
        print("❌ DATABASE_URL belum diset — periksa .env")
        return 1

    rows = parse_csv(args.csv)
    plan = validate_and_plan(rows)
    if not plan.ok:
        print(f"❌ Validasi gagal ({len(plan.errors)} error):")
        for err in plan.errors[:50]:
            print(f"   - {err}")
        return 1

    db = SessionLocal()
    try:
        report = run_import(db, plan, dry_run=args.dry_run)
    finally:
        db.close()

    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    if not report.errors:
        print("✅ Import", "DIVERIFIKASI (dry-run)" if args.dry_run else "SELESAI")
        return 0
    print("❌ Ada error — cek laporan di atas")
    return 1


if __name__ == "__main__":
    sys.exit(main())
