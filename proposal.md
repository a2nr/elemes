# Elemes LMS: Sisa Pekerjaan (To-Do List)

Berdasarkan log penyelesaian integrasi Velxio dan dokumen sebelumnya, berikut adalah daftar sisa pekerjaan (TODO) proyek. Terakhir diperbarui: 2026-04-10.

## ✅ Sudah Selesai

- [x] **Verifikasi Penamaan Pin (Pin Naming)**
  - Diverifikasi dari `velxio/frontend/src/data/examples.ts` — konvensi pin sudah benar.
  - Tabel referensi pin terdokumentasi di `README.md` (Arduino Uno, LED, Button, Resistor, RGB LED).
  - `componentId` Arduino Uno = `arduino-uno`, pin GND dinormalisasi oleh `matchWiring()`.
- [x] **Pembuatan Konten Tambahan** — 3 lesson Arduino baru:
  - `hello_serial_arduino.md` — Serial Monitor (tanpa wiring, kode saja)
  - `button_input_arduino.md` — Button + LED (INPUT_PULLUP, 4 expected wiring)
  - `traffic_light_arduino.md` — Lampu Lalu Lintas 3 LED (6 expected wiring)
- [x] **Update Contoh Materi & Dokumentasi Guru**
  - `examples/content/` disinkronkan (8 file, byte-identical dengan `content/`)
  - `README.md` ditambahkan: blok Arduino/Velxio, referensi pin, evaluasi, 3 FAQ baru, tabel jenis materi
  - `home.md` sekarang mendaftarkan 7 lesson
- [x] **Network Config di Docker/Podman**
  - Typo `drive: bridge` → `driver: bridge` di `podman-compose.yml`
  - `network_mode: service:elemes-ts` dihapus karena tidak kompatibel dengan `networks` block
- [x] **Commit semua perubahan**
  - Elemes: 2 commit ahead of origin
  - Velxio: 2 commit ahead of origin

- [x] **Locust E2E Test Suite** — `load-test/` folder:
  - `content_parser.py` — scan `content/*.md`, deteksi tipe, ekstrak test data → `test_data.json`
  - `locustfile.py` — 7 weighted tasks (browse, view detail, compile C, compile Python, verify Arduino, complete flow, progress report)
  - Auto-inject token test (`LOCUST_TEST_*`) ke `tokens_siswa.csv`
  - URL backend dikonfigurasi user melalui Locust web UI

## 🔴 Prioritas Tinggi
- [x] **Testing End-to-End (E2E)**
  - Script Locust sudah disiapkan (di dalam `load-test/`).
  - Bug pada proxy JSON parsing dari frontend ke backend sudah diperbaiki dengan `force=True` dan `silent=True` di `auth.py`, sehingga Login via test suite berhasil.
- [x] **Push ke Remote**
  - `git push` untuk repo elemes dan velxio (keduanya ahead of origin).
- [x] **Hapus file test lama** di root `elemes/`:
  - `rm elemes/content_parser.py elemes/locustfile.py elemes/requirements-test.txt` (sudah dibersihkan sebelumnya, sekarang rapi di `load-test`).


## 🟡 Prioritas Sedang
- [ ] **Tuning Crosshair/UX Mobile**
  - Melakukan *fine-tuning* pada opacity warna dan pola garis *dashed* pada crosshair UI di Velxio agar lebih responsif terhadap device layar sentuh saat dipakai *live*.

## 🟢 Prioritas Rendah (Enhancement Simulator Velxio)
- [ ] **Mengunci Tata Letak (Component Locking)**
  - Menonaktifkan fitur *drag* atau *delete* komponen pada tampilan *embed*, sehingga siswa hanya difokuskan pada kegiatan menarik (*wiring*) kabel saja tanpa mengganggu tatanan dasar board.
- [ ] **Solution Overlay**
  - Mengembangkan tampilan *overlay* solusi/jawaban wiring untuk *review mode*, agar siswa melihat panduan visual kabel mana yang kurang pas.
- [ ] **Perintah `elemes:compile_and_run` API Bridge**
  - Mengkoneksikan trigger kompilasi sehingga UI utama Elemes juga bisa mem-bypass eksekusi ke dalam iFrame (saat ini *placeholder* `compile_and_run` bridge belum sepenuhnya utuh ter-wire dengan UI submit).

## ⚪ Opsional
- [x] ~~**Locust Load Testing Plan**~~ → Sudah diimplementasi di `load-test/`
- [x] **Locust Hasil Analisis** — Evaluasi skenario 50 user (5 worker) selesai. *Finding*: Rata-rata respons LMS stabil di 200ms (50th percentile). Namun, kompilasi Arduino (`/velxio/api/compile/`) terdeteksi sebagai *CPU bottleneck* yang menyebabkan waktu tunggu mencapai 30 detik (95th percentile) di bawah tekanan serbuan *request* berskala ekstrem. Server/LMS dinilai layak dan responsif secara keseluruhan.

## 🚨 Security Review & Vulnerability Fixes (Prioritas Kritis)

Berdasarkan hasil code review terbaru yang difokuskan pada keamanan sistem dan *exposed routes* API, ditemukan beberapa celah kerentanan kritis yang perlu segera diperbaiki. Berikut adalah detail temuan dan *task* perbaikannya:

### 1. Remote Code Execution (RCE) via Endpoint `/compile`
- **Penjelasan**: Endpoint `/compile` di `elemes/routes/compile.py` menerima dan mengeksekusi kode C dan Python yang di-*submit* oleh pengguna secara langsung (via `subprocess.run`). Eksekusi ini berjalan di dalam kontainer `elemes` tanpa adanya batasan hak akses atau *sandbox* tambahan. Pengguna anonim/jahat dapat mengeksekusi *shell script* atau perintah OS (seperti `os.system("rm -rf /")`) untuk menghapus, memodifikasi, atau membaca file sensitif. Terlebih lagi, *volume* `content`, `tokens_siswa.csv`, dan `assets` di-mount dengan akses *read-write* pada konfigurasi podman/docker, sehingga token akses seluruh siswa rentan diretas atau data materi bisa terhapus.
- **Task Perbaikan**:
  - [x] **Gunakan Sandbox gVisor (Compiler Worker)**: Pisahkan fungsi kompilasi ke dalam kontainer terpisah (`compiler-worker`) yang dijalankan menggunakan *runtime* `runsc` (gVisor). Backend utama akan mengirimkan kode via HTTP internal.
  - [x] **Read-Only Mounts**: Ubah konfigurasi *bind mount* di `podman-compose.yml` pada direktori sensitif (`tokens_siswa.csv`, `content`, `assets`) menjadi *read-only* dengan menambahkan parameter `:ro` pada kontainer backend utama.
  - [x] **Otentikasi / Wajib Login**: Lindungi *route* `/compile` dengan menambahkan pengecekan token mahasiswa agar tidak bisa diakses oleh *user* anonim di luar sistem.
  - [x] **Resource Limiting**: Terapkan limit komputasi RAM dan CPU pada kontainer worker guna menghindari celah *Denial of Service* (DoS).

### 2. Information Disclosure via Endpoint `/progress-report.json`
- **Penjelasan**: Rute `/progress-report.json` dan `/progress-report/export-csv` di `elemes/routes/progress.py` dapat diakses oleh siapa saja karena tidak menerapkan validasi token atau *role checks*. Data kemajuan belajar dan nama semua siswa di dalam file CSV akan terekspos tanpa otentikasi.
- **Task Perbaikan**:
  - [x] **Otentikasi Token**: Tambahkan validasi token (via `validate_token`) sebelum memberikan *response* dari kedua *route* tersebut.

### 3. Miskonfigurasi CORS Longgar (Overly Permissive)
- **Penjelasan**: Deklarasi `CORS(app)` di `elemes/app.py` mengizinkan seluruh asal domain (*all origins*) secara *default* (`*`). Mengingat sistem sudah menggunakan sesi berbasis *Cookie* (`samesite='Lax'`), ada potensi ancaman pengiriman *requests* lintas *website* dari penyerang.
- **Task Perbaikan**:
  - [x] **Batasi Konfigurasi CORS**: Gunakan *environment variable* `ORIGIN` untuk menentukan domain eksplisit yang diizinkan (misal: `http://localhost:3000`).

### 4. Penyimpanan Token Teks Terbuka (Plaintext Credentials)
- **Penjelasan**: Data di `tokens_siswa.csv` menyimpan token dalam format *plaintext*. Meskipun hanya file CSV lokal, bocornya satu file tersebut akan mengkompromikan semua token akses dalam sistem (terutama karena kerentanan RCE di poin 1).
- **Task Perbaikan**:
  - [x] **Proteksi Token CSV**: Prioritas utama adalah menambal *vulnerability* utama (RCE via gVisor & Read-Only Mounts) agar peretas tidak bisa mengekstrak isinya.
  - [ ] *(Opsional)* **Hashed Tokens**: Gunakan fungsi *hashing* saat membaca/memverifikasi token.

### 5. Tidak Ada Sanitasi Input pada Parameter Path (Defense in Depth)
- **Penjelasan**: Fungsi *route* `/lesson/<filename>.json` di `elemes/routes/lessons.py` mengandalkan `<filename>` yang langsung disambungkan via `os.path.join()`. Meskipun Flask memblokir `../` (Directory Traversal konvensional), tetap berisiko jika pengguna memanipulasi *request* API secara lebih *advanced*.
- **Task Perbaikan**:
  - [x] **Terapkan `secure_filename`**: Gunakan `werkzeug.utils.secure_filename(filename)` sebelum argumen `<filename>` disambung ke direktori *content*.
