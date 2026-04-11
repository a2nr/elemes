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

# 2. Generate test data dari content/
python content_parser.py

# 3. Jalankan Locust (opsional: set VELXIO_HOST jika Velxio bukan di localhost:8001)
export VELXIO_HOST=http://localhost:8001
locust -f locustfile.py
```

Buka **http://localhost:8089**, masukkan URL backend Elemes (misalnya `http://localhost:5000`), lalu mulai test.

## File

| File | Fungsi |
|------|--------|
| `content_parser.py` | Parse `content/*.md` → `test_data.json` + inject token test ke CSV |
| `locustfile.py` | Locust script (7 task weighted) yang baca `test_data.json` |
| `test_data.json` | Auto-generated, **jangan di-commit** |
| `requirements.txt` | Dependency (`locust`) |

## Test Scenarios (8 Tasks)

| # | Task | Weight | Target | Deskripsi |
|---|------|--------|--------|----------|
| 1 | Browse Lessons | 3 | Elemes | GET `/lessons`, validasi jumlah lesson |
| 2 | View Detail | 5 | Elemes | GET `/lesson/{slug}.json`, validasi field per tipe |
| 3 | Compile C | 4 | Elemes | POST `/compile`, validasi output vs expected |
| 4 | Compile Python | 3 | Elemes | POST `/compile`, validasi output vs expected |
| 5 | Verify Arduino | 2 | Elemes | GET lesson Arduino, validasi JSON structure |
| 6 | Complete Flow | 2 | Both | fetch → compile → track-progress |
| 7 | Progress Report | 1 | Elemes | Login guru → GET `/progress-report.json` |
| 8 | **Compile Arduino** | **3** | **Velxio** | POST `/api/compile`, validasi hex_content |

## Re-generate Setelah Tambah Lesson Baru

Setiap kali ada lesson baru di `content/`, cukup jalankan ulang:

```bash
python content_parser.py
```

`test_data.json` akan di-update otomatis dan Locust langsung test lesson baru.
