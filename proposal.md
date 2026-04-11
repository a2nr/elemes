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
- [ ] **Testing End-to-End (E2E)**
  - Script Locust sudah siap, tinggal jalankan:
    ```
    cd elemes/load-test && python content_parser.py && locust -f locustfile.py
    ```
  - Build ulang container dan test via Locust web UI
  - Tes khusus: lesson tanpa wiring (`hello_serial_arduino.md`) harus bisa pass hanya dengan kode + serial.
- [ ] **Push ke Remote**
  - `git push` untuk repo elemes dan velxio (keduanya ahead of origin).
- [ ] **Hapus file test lama** di root `elemes/`:
  - `rm elemes/content_parser.py elemes/locustfile.py elemes/requirements-test.txt`

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
- [ ] **Locust Hasil Analisis** — Setelah test jalan, analisis bottleneck compilation rate dan response time.
