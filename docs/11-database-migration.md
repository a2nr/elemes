# Migrasi Database: CSV → PostgreSQL

> Status: **SELESAI — live di PostgreSQL** (cutover Agustus 2026).
> Backend CSV sudah **dicabut** dan `tokens_siswa.csv` **tidak lagi menjadi
> source of truth** — PostgreSQL adalah satu-satunya backend penyimpanan.
> Dokumen ini menjelaskan arsitektur, riwayat migrasi, dan operasional.

## 1. Kenapa migrasi?

Penyimpanan lama berbasis file CSV (satu baris = satu siswa, satu kolom per lesson):

| Masalah | Dampak |
|---|---|
| `read-modify-write` dengan file lock | Race condition saat banyak siswa submit bersamaan |
| Token siswa **plaintext** di file + bocor ke log & payload report | Kebocoran credential |
| Tidak ada relasi / constraint | Progress rusak tanpa error |
| Satu file membesar seiring lesson & siswa | Semakin lambat dibaca setiap request |
| Role guru = "baris pertama" | Fragile & ambigu |

PostgreSQL + SQLAlchemy menyelesaikan semuanya: transaksi ACID, relasi,
constraint, index, token **hanya disimpan sebagai HMAC-SHA256 digest**.

## 2. Stack

| Komponen | Teknologi | Versi (verified) |
|---|---|---|
| Database | PostgreSQL | 18 (image `postgres:18-alpine`) |
| ORM | SQLAlchemy | 2.0.51 |
| Migrasi schema | Alembic | 1.19.0 |
| Driver | psycopg | 3.3.4 (`psycopg[binary]`) |
| Hashing token | HMAC-SHA256 + pepper (`TOKEN_PEPPER`) | — |

## 3. Arsitektur

```
Flask routes (auth, progress, lessons, compile)
        │  (hanya kenal facade)
        ▼
services/token_service.py  ← facade, kontrak publik
        │
        ▼
services/storage/  (backend tunggal — CSV sudah dicabut)
   └── postgres_backend.py  → repositories → SQLAlchemy → PostgreSQL
```

- `services/models.py` — `users`, `access_tokens` (token_hash unik),
  `lessons` (registry metadata), `student_progress` (unique user+lesson).
- `migrations/` — Alembic; `0001_initial_schema.py` (hand-written, deterministik).
- ~~`services/csv_importer.py`~~ — import idempotent CSV → PG
  (`3/4` legacy → `state=scored, score_earned=3, score_total=4`).
  **File dihapus pasca cutover** — migrasi CSV hanya satu kali; siswa baru
  ditambahkan via Import CSV di webapp (`student_roundtrip`).
- `services/lesson_registry.py` — sync daftar lesson dari `home.md`
  (lesson hilang → `is_active=false`, **bukan dihapus**). Sync ini berjalan
  **otomatis** setiap kali aplikasi start.

### Keamanan token

- Token mentah **tidak pernah** disimpan: `access_tokens.token_hash =
  HMAC-SHA256(token, TOKEN_PEPPER)` — deterministik untuk lookup, tak reversibel.
- Pepper (`TOKEN_PEPPER`) di `.env`, **di luar database**. Hilang =
  semua token invalid (regenerate & import ulang).
- Report & export **tidak menyertakan token mentah**; reset memakai
  `student_id` anonim (`user.id` di PG).

## 4. Alur migrasi (Agustus 2026 — selesai)

Cutover CSV → PostgreSQL **sudah selesai** dan tidak bisa diulang atau
di-rollback (backend CSV dicabut). Alur yang dijalankan saat itu, untuk
referensi:

1. Tambahkan variabel database di `../.env` (lihat `.env.example`):
   `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` (strong!),
   `DATABASE_URL=postgresql+psycopg://<user>:<pass>@127.0.0.1:5432/<db>`,
   `TOKEN_PEPPER=<random 48 hex>` (JANGAN hilangkan — hash bergantung padanya),
   `STORAGE_BACKEND=postgresql`.
2. `./elemes.sh runclearbuild` — build image (SQLAlchemy, Alembic, psycopg) + start postgres.
3. `./elemes.sh dbupgrade` — buat schema.
4. Impor data siswa dari CSV lama (script `scripts/migrate_csv_to_postgres.py`).
5. `./elemes.sh dbbackup` — backup pertama.

Sekarang langkah-langkah itu sudah **otomatis**: `runbuild`/`run`/`runclearbuild`
menjalankan migrasi schema + bootstrap akun guru saat start, dan daftar lesson
disinkronkan otomatis dari `home.md`. Tidak ada lagi file CSV token yang dibaca
aplikasi — token & progress hanya ada di PostgreSQL.

## 5. Operasional harian

| Perintah | Fungsi |
|---|---|
| `./elemes.sh dbupgrade` | Jalankan migrasi schema (alembic upgrade head) — juga otomatis saat start |
| `./elemes.sh dbstatus` | Versi schema aktif & head |
| `./elemes.sh teacher` | Buat/update akun guru canonical (upsert; prompt nama & token tersembunyi) |
| `./elemes.sh dbbackup` | `pg_dump` → `backups/elemes_<ts>.sql` |
| `./elemes.sh dbrestore` | Restore backup terbaru |

Sinkronisasi daftar lesson dari `home.md` berjalan **otomatis** setiap kali
aplikasi start — tidak ada perintah sinkronisasi manual.

## 6. Rollback

Tidak ada rollback ke backend CSV — backend CSV sudah **dicabut** dan
`STORAGE_BACKEND` hanya menerima `postgresql`. Pemulihan data dilakukan lewat
backup: `./elemes.sh dbbackup` (rutin) dan `./elemes.sh dbrestore`.

## 7. Load test endpoint database

```bash
cd elemes/load-test
# (set DATABASE_URL dulu bila ingin token sintetis di-seed ke PostgreSQL)
python content_parser.py --content-dir ../../content --num-tokens 50
locust -f locustfile_db.py    # set host ke URL Elemes
```

Skenario: login/validate-token, baca lesson, track-progress (siswa),
progress-report + export-csv (guru).

## 8. Test

```bash
# Unit & kontrak (host): backend aktif = postgresql (butuh DATABASE_URL ter-set)
PYTHONPATH=services python -m pytest services/tests -q

# Integrasi (butuh DATABASE_URL + postgres hidup): jalankan di dalam container
# service `elemes` via podman-compose. Nama container mengikuti PROJECT_NAME
# (= basename folder parent: lms-dev → lms-dev_elemes_1) — jangan hard-code
# nama container, cukup sebut nama service:
podman-compose -p <PROJECT_NAME> exec -T -w /app -e PYTHONPATH=services elemes \
  python -m pytest services/tests -q
# <PROJECT_NAME> = nama folder deploy (mis. lms-dev / sinau-c); elemes.sh
# menghitungnya otomatis dari basename folder parent.
```

Suite round-trip siswa (`test_student_roundtrip.py`, `test_repositories.py`,
`test_student_management_routes.py`) dijalankan pada **DB test terpisah**
(`elemes_test`):

```bash
podman-compose -p <PROJECT_NAME> exec -T -w /app \
  -e PYTHONPATH=services \
  -e DATABASE_URL="$DATABASE_URL_TEST" \
  elemes python -m pytest services/tests/test_student_roundtrip.py \
    services/tests/test_repositories.py services/tests/test_student_management_routes.py -q
```

> Jangan pernah menjalankan integration test dengan `DATABASE_URL` produksi —
> fixture conftest me-TRUNCATE semua tabel sebelum tiap test.

## 9. Manajemen Siswa: Round-Trip CSV (export → edit → import)

Sejak Agustus 2026, halaman `/progress` memakai **satu format CSV round-trip**
untuk export dan import siswa, menggantikan rancangan "download template":

```csv
student_id;token;nama_siswa;<lesson_slugs...>
```

### Export (`POST /students/export-csv`, teacher-only)

- Export siswa **terpilih** bila ada selection; **seluruh siswa** bila selection
  kosong. Teacher tidak pernah ikut.
- Kolom `token` **selalu kosong** — PostgreSQL hanya menyimpan
  `HMAC-SHA256(token, TOKEN_PEPPER)` dan **tidak ada recovery/export token**.
- Encoding UTF-8 BOM, delimiter `;`, filename `data_siswa_YYYYMMDD_HHMMSS.csv`.
- Duplicate/malformed/unknown/teacher ID pada selection membuat seluruh
  request gagal.

### Import (`/students/import/preview` & `/students/import`, teacher-only)

- **Create + restore/update, all-or-nothing**: seluruh row divalidasi dulu;
  satu saja baris bermasalah → seluruh file ditolak tanpa write.
- Baris dengan `student_id` terisi = siswa existing: user wajib sudah ada dan
  ber-role student. Token **boleh kosong** (hasil export) → user & token lama
  **dipertahankan**, nama & progress diperbarui (restore/update, bukan
  create). Mengisi token pada baris existing ditolak sebagai konflik/ambigu.
- Baris dengan `student_id` kosong = siswa baru: token wajib non-kosong;
  dibuatkan user + access-token digest. `student_id` terisi yang tidak dikenal
  ditolak (tidak ada create-with-ID diam-diam); teacher tidak pernah bisa
  diubah lewat import siswa.
- Setelah siswa dihapus, UUID lama tidak bisa langsung dipakai ulang untuk
  create (ditolak sebagai ID tak dikenal) — buat baris baru dengan
  `student_id` kosong agar UUID baru dibuat server.
- Progress `completed`/`<earned>/<total>` diterapkan via `set_progress()`;
  `not_started`/kosong tetap sparse (tidak ada row), dan progress lama yang
  tidak ada di CSV tidak dihapus (merge, bukan snapshot penuh).
- Upload diproses in-memory; preview/response/log **tidak pernah** memuat
  token plaintext maupun hash.
- File CSV berisi token yang diisi guru adalah **satu-satunya salinan
  plaintext** token.

### Bulk delete (`POST /students/bulk-delete`, teacher-only)

- Menerima 1–1000 UUID; seluruh target divalidasi sebelum delete pertama
  (duplicate/malformed/unknown/teacher ID → zero delete).
- Menghapus permanen user + cascade token & progress; lesson tidak terpengaruh.
- Setelah commit, siswa tidak lagi ada; UUID lama tidak bisa dipakai ulang
  oleh importer (ditolak sebagai ID tak dikenal). Untuk memperbarui
  nama/progress tanpa menghapus, cukup re-import hasil export (token kosong);
  untuk menambah siswa baru, gunakan baris dengan `student_id` kosong.

### Berkas kunci

- `services/student_roundtrip.py` — parser/serializer murni (schema + validasi).
- `services/progress_status.py` — parse/format status legacy bersama
  (dipakai importer & `postgres_backend` agar tidak divergen).
- `services/repositories.py` — `list_students_for_export`, `preview_student_import`,
  `run_student_import`, `delete_students`, `create_user(user_id=...)`.
- `routes/student_management.py` — 4 endpoint teacher-only (cookie HttpOnly
  `student_token` + validasi Origin).
- Frontend: selection berbasis UUID, dialog import preview, dialog bulk delete
  (`src/routes/progress/+page.svelte` + komponen di `src/lib/components/`).

Out of scope: mengganti token siswa existing lewat import, export/recovery
  token, vault, soft delete, dan import format lama (CSV migrasi).

- Kontrak suite (`test_token_service_contract.py`, `test_auth_routes.py`,
  `test_progress_routes.py`) dijalankan terhadap **PostgreSQL** (backend CSV
  sudah dicabut).
- Test integrasi (`test_repositories.py`, `test_lesson_registry.py`,
  `test_teacher_bootstrap.py`, dan suite kontrak di atas) otomatis skip bila
  `DATABASE_URL` tidak diset.
- Isolasi antar test (DB bersama): conftest punya fixture `autouse` yang TRUNCATE
  semua tabel sebelum tiap test; `CONTENT_DIR` di-**PAKSA** ke fixture
  (jangan `setdefault` — env container membawa path produksi). Integration test
  dijalankan di DB terpisah (mis. `elemes_test`): `CREATE DATABASE` + `alembic upgrade`.
- Script di `/app/scripts` (mis. `bootstrap_teacher.py`) butuh `PYTHONPATH=/app`
  (bukan `services`) agar `from services...` resolve — sudah di-apply di `elemes.sh`.
