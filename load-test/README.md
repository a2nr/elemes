# Elemes Load Test

Load test E2E menggunakan [Locust](https://locust.io/) yang otomatis di-generate dari folder `content/`.

## Cara Pakai

```bash
cd elemes/load-test

# 0. Virtual Environment
python3 -m venv ./env
source ./env/bin/activate

# 1. Install dependency
pip install -r requirements.txt

# 2. Generate test data dari content/ (konten ada di subfolder dasar/, arduino/, circuit/)
#    Token sintetis LOCUST_TEST_* otomatis di-seed ke PostgreSQL bila env DATABASE_URL ter-set
export DATABASE_URL=postgresql+psycopg://elemes:<password>@127.0.0.1:5432/elemes
python content_parser.py --content-dir ../../content --num-tokens 50

# 3. Jalankan Locust (opsional: set VELXIO_HOST jika Velxio bukan di localhost:8001)
export VELXIO_HOST=http://localhost:8001
locust -f locustfile.py
```

Buka **http://localhost:8089**, masukkan URL backend Elemes (misalnya `http://localhost:3000`), lalu mulai test.

## File

| File | Fungsi |
|------|--------|
| `content_parser.py` | Parse `content/**/*.md` (rekursif subfolder) → `test_data.json` + seed token `LOCUST_TEST_*` ke PostgreSQL |
| `locustfile.py` | Locust script (task weighted) yang baca `test_data.json` |
| `test_data.json` | Auto-generated, **jangan di-commit** |
| `requirements.txt` | Dependency (`locust`) |
| `e2e_session_check.py` | Smoke-test alur interaktif (PTY session) via Flask proxy — jalan di container |

## Test Scenarios (9 Tasks)

| # | Task | Weight | Target | Deskripsi |
|---|------|--------|--------|----------|
| 1 | Browse Lessons | 3 | Elemes | GET `/lessons`, validasi jumlah lesson |
| 2 | View Detail | 5 | Elemes | GET `/lesson/{slug}.json`, validasi field per tipe |
| 3 | Compile C | 4 | Elemes | POST `/compile`, validasi output vs expected |
| 4 | Compile Python | 3 | Elemes | POST `/compile`, validasi output vs expected |
| 5 | **Interactive Session Python** | **4** | **Elemes** | POST `/compile/sessions` → poll prompt → POST `/input` → verifikasi output → DELETE |
| 6 | Verify Arduino | 2 | Elemes | GET lesson Arduino, validasi JSON structure |
| 7 | Complete Flow | 2 | Both | fetch → compile → track-progress |
| 8 | Progress Report | 1 | Elemes | Login guru → GET `/progress-report.json` |
| 9 | **Compile Arduino** | **3** | **Velxio** | POST `/api/compile`, validasi hex_content |

> **Task 5 (interactive session)** menguji alur baru playground: Run → prompt muncul → ketik jawaban → Enter → output. Skrip memakai token (login) agar lolos rate-limit anonymous dan benar-benar mengukur kapasitas compiler worker (max 50 sesi, 2 compile bersamaan, queue timeout 20 s).

## Load Test 50 Pengguna (2 Device)

Host hanya 4-core/3.5 GiB — 50 kompilasi berat bersamaan tidak realistis, tapi 50 sesi yang **menunggu input** aman (proses idle tidak makan CPU). Batas worker: `INTERACTIVE_MAX_SESSIONS=50`, `INTERACTIVE_MAX_COMPILES=2`, `INTERACTIVE_QUEUE_TIMEOUT_SECONDS=20`.

### Device A — Locust Master (jalankan UI di sini)

```bash
cd elemes/load-test
source ./env/bin/activate
locust -f locustfile.py --master --web-port 8089
```

### Device B (atau beberapa device) — Locust Worker

```bash
cd elemes/load-test
source ./env/bin/activate
# Ganti <IP_MASTER> dengan IP device A (di jaringan/Tailscale yang sama)
locust -f locustfile.py --worker --master-host <IP_MASTER>
```

### Mulai Test

1. Buka `http://<IP_MASTER>:8089` di browser device A.
2. **Host**: URL app yang diuji, misal `https://sinau-c-dev.manakin-gentoo.ts.net` (Tailscale Funnel) atau `http://localhost:3000`.
3. **Number of users**: 50 · **Spawn rate**: 5–10/s (ramp-up ~5–10 detik agar hampir bersamaan) · **Duration**: 5–10 menit.
4. Amati di tab Charts: RPS per endpoint, response time `/compile/sessions` & `/input`, dan failure rate.
5. Skenario `/compile/sessions [Python interactive]` wajib ≥95% sukses; failure `429` pada create menandakan anon rate limit (bukan kapasitas) — gunakan token.

> Catatan: task compile biasa (`/compile`) tetap kena anon rate limit `1 per 2 menit` bila token tidak ikut — login di `on_start` menyimpan cookie, jadi user ber-token exempt.

## Re-generate Setelah Tambah Lesson Baru

Setiap kali ada lesson baru di `content/`, cukup jalankan ulang:

```bash
python content_parser.py --content-dir ../../content --num-tokens 50
```

`test_data.json` akan di-update otomatis dan Locust langsung test lesson baru.

## E2E Smoke Test (container)

Verifikasi cepat alur interaktif tanpa browser — jalan di dalam container backend:

```bash
podman cp elemes/load-test/e2e_session_check.py lms-dev_elemes_1:/tmp/
podman exec -e E2E_TOKEN=<token_siswa> lms-dev_elemes_1 python3 /tmp/e2e_session_check.py
# Contoh token: LOCUST_TEST_xxxx — token sintetis yang di-seed ke PostgreSQL
# oleh content_parser.py (jalankan langkah 2 dengan DATABASE_URL ter-set).
```

Tanpa `E2E_TOKEN` skrip tetap jalan tapi hanya 2 create session (anon rate limit 1/2 menit).
