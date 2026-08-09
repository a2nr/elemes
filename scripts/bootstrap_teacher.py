#!/usr/bin/env python3
"""
CLI bootstrap akun guru — dipanggil dari `./elemes.sh teacher`.

Nama guru diberikan sebagai argv[1] (non-secret). Token guru dibaca dari
stdin (baris pertama, spasi tepi di-strip) sehingga tidak pernah muncul
di process list maupun shell history. Jalur yang sama dipakai oleh
first-run otomatis yang mengirim TEACHER_TOKEN dari .env via stdin.

Exit codes:
  0  sukses (created / updated / unchanged)
  1  penolakan / kesalahan operasional
  2  database tidak tersedia (DATABASE_URL kosong)
"""

import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.database import SessionLocal  # noqa: E402
from services.teacher_bootstrap import TeacherBootstrapError, upsert_teacher  # noqa: E402

logging.basicConfig(level=logging.ERROR, stream=sys.stderr)


def main() -> int:
    if len(sys.argv) < 2:
        print("Error: nama guru tidak diberikan.", file=sys.stderr)
        return 1
    display_name = sys.argv[1].strip()

    raw_token = ""
    line = sys.stdin.readline()
    if line:
        raw_token = line.strip()
    if not raw_token:
        print("Error: token guru kosong (kirim token lewat stdin).", file=sys.stderr)
        return 1

    if SessionLocal is None:
        print(
            "Error: database tidak tersedia (DATABASE_URL kosong). "
            "Jalankan ./elemes.sh run terlebih dahulu.",
            file=sys.stderr,
        )
        return 2

    db = SessionLocal()
    try:
        result = upsert_teacher(db, display_name=display_name, raw_token=raw_token)
    except TeacherBootstrapError as exc:
        print(f"Penolakan: {exc}", file=sys.stderr)
        return 1
    except Exception:  # noqa: BLE001 — CLI boundary; detail hanya ke log
        logging.getLogger("bootstrap_teacher").exception("Bootstrap guru gagal")
        print("Error: operasi gagal. Lihat log aplikasi untuk detail.", file=sys.stderr)
        return 1
    finally:
        db.close()

    print(result["message"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
