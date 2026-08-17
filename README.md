# Elemes - Panduan Guru

**Elemes** adalah Learning Management System (LMS) untuk mengajar pemrograman atau elektronika.
Guru cukup menyiapkan file konfigurasi dan konten materi dalam format Markdown,
lalu menjalankan container untuk deploy.

Fitur utama:
- **Playground Interaktif** — tab Velxio (Arduino simulator), Flowchart, Circuit, dan Code dengan run sesi PTY, stdinQueue, dan FileTree collapsible
- **Embed Konten** — sisipkan iframe Canva, YouTube, Google Docs, Figma langsung dari markdown
- **Kuis Interaktif** — Flashcard & Pilihan Ganda dengan randomisasi, skor, dan pembahasan
- **Slide** — carousel presentasi interaktif dari markdown dengan fullscreen mode
- **Flowchart** — editor flowchart interaktif dengan evaluasi frontend
- **Velxio BLE/USB Deployer** — flashing firmware Arduino via BLE (Chrome Android) atau USB (Web Serial API), dengan serial monitor inline

## Struktur Folder

Setelah setup, struktur folder utama (parent folder) akan terlihat seperti ini:

```
project/
├── .env                  # Konfigurasi environment
├── content/              # Folder materi pelajaran (file .md)
│   ├── home.md           # Halaman utama & daftar pelajaran
│   ├── hello_world.md    # Contoh materi
│   └── ...
├── assets/               # Gambar untuk materi (opsional)
│   └── gambar.png
├── backups/              # Hasil ./elemes.sh dbbackup (dump PostgreSQL)
├── state/                # State Tailscale (auto-generated)
└── elemes/               # Folder engine LMS (JANGAN DIUBAH)
    ├── elemes.sh          # Script untuk menjalankan LMS
    └── ...
```

## Quick Start

```bash
cd elemes
./elemes.sh init      # Generate .env, content/, assets/, dan state/ dari contoh
```

Output:

```
=== Elemes Quick Start ===

[buat] .env  (edit sesuai kebutuhan, termasuk TEACHER_NAME / TEACHER_TOKEN)
[buat] content/  (4 materi)
[buat] assets/  (untuk gambar/media)
[buat] state/  (untuk Tailscale)

Selesai! Langkah selanjutnya:
  1. Edit ../.env sesuai kebutuhan
  2. Edit ../content/home.md untuk daftar materi
  3. Jalankan ./elemes.sh teacher untuk membuat akun guru
  4. Jalankan:  ./elemes.sh runbuild
```

Perintah `init` aman dijalankan ulang — file yang sudah ada tidak akan ditimpa.

### 1. Edit `.env`

Sesuaikan `.env` di parent folder:

```env
# Identitas LMS (tampil di frontend)
APP_BAR_TITLE=Pemrograman C - SMK Nusantara
COPYRIGHT_TEXT=SMK Nusantara @ 2025
PAGE_TITLE_SUFFIX=SMK Nusantara

# Lokasi konten (dipakai di dalam container)
CONTENT_DIR=content

# Akun guru (bootstrap canonical)
TEACHER_NAME=Guru LMS    # Nama default guru (dipakai ./elemes.sh teacher & first-run)
TEACHER_TOKEN=           # Token guru untuk first-run non-interaktif (opsional);
                         # kosongkan untuk prompt manual via ./elemes.sh teacher

# Tailscale (opsional, untuk akses remote)
ELEMES_HOST=lms-smk-nusantara
TS_AUTHKEY=tskey-auth-xxxx
```

### 2. Edit Konten

### 3. Buat `home.md` (Halaman Utama)

File `content/home.md` adalah halaman utama LMS. Di sinilah guru mendefinisikan
judul sambutan dan **daftar pelajaran yang tersedia**.

Contoh `content/home.md`:

```markdown
## Selamat Datang di Kelas Pemrograman C

Situs LMS ini untuk belajar dasar-dasar pemrograman C.

## Topik yang Akan Dipelajari

1. [Hello, World!](lesson/hello_world.md)
2. [Variables](lesson/variables.md)
3. [Conditions](lesson/conditions.md)

----Available_Lessons----

1. [Hello, World!](lesson/hello_world.md)
2. [Variables](lesson/variables.md)
3. [Conditions](lesson/conditions.md)
```

> **Penting:** Bagian setelah `----Available_Lessons----` adalah daftar pelajaran
> yang dikenali sistem. Pastikan setiap materi yang ada di folder `content/`
> terdaftar di sini.

### 3b. Sub Bab (Opsional): `sub-home.md` dalam Folder

Untuk mengelompokkan materi ke dalam bab, buat folder satu level di dalam
`content/` (misal `content/bab1/`) dan beri file `sub-home.md` di dalamnya:

```markdown
# Judul Bab

Intro bab (opsional).

----Available_Lessons----
1. [Materi A](lesson/materi_a.md)
2. [Materi B](lesson/materi_b.md)
```

Folder yang memiliki `sub-home.md` otomatis punya halaman bab di
`/bab/<folder>`, dan sidebar/navigasi materi di dalam folder tersebut memakai
daftar dari `sub-home.md` (bukan daftar global).

> **Catatan fallback:** Folder **tanpa** `sub-home.md` tetap memakai daftar
global dari `home.md` — perilaku lama tidak berubah. `sub-home.md` tidak
> dihitung sebagai materi.

Panduan lengkap: `docs/13-content-sub-home.md`.

### 4. Buat Materi Pelajaran

Setiap file `.md` di folder `content/` adalah satu materi pelajaran.
Format dasar materi:

```markdown
---LESSON_INFO---
**Learning Objectives:**
- Tujuan pembelajaran 1
- Tujuan pembelajaran 2

**Prerequisites:**
- Materi prasyarat (atau "Tidak ada")
---END_LESSON_INFO---

# Judul Materi

Penjelasan materi di sini. Gunakan format Markdown biasa.

Contoh kode bisa ditulis dalam code block:

` ` `c
#include <stdio.h>

int main() {
    printf("Hello, World!\n");
    return 0;
}
` ` `

---EXERCISE---
### Latihan
Buat program yang mencetak "Hello, World!"
---

---INITIAL_CODE---
#include <stdio.h>

int main() {
    // Tulis kode kamu di sini

    return 0;
}
---END_INITIAL_CODE---

---EXPECTED_OUTPUT---
Hello, World!
---END_EXPECTED_OUTPUT---

---KEY_TEXT---
printf
---END_KEY_TEXT---
```

#### Penjelasan Blok-Blok Khusus

| Blok | Fungsi |
|------|--------|
| `---LESSON_INFO---` | Info pelajaran: tujuan & prasyarat |
| `---EXERCISE---` | Deskripsi latihan soal |
| `---INITIAL_CODE---` | Kode awal C yang muncul di editor siswa |
| `---INITIAL_PYTHON---` | Kode awal Python yang muncul di editor siswa |
| `---INITIAL_CIRCUIT---` | Rangkaian awal Falstad CircuitJS |
| `---INITIAL_QUIZ---` | Data quiz (format JSON) |
| `---QUIZ_FLASHCARD---` | Kuis format Markdown (Flashcard & Pilihan Ganda) |
| `---slide-start---` | Blok slide presentasi interaktif |
| `---EXPECTED_OUTPUT---` | Output yang diharapkan untuk C (stdout) |
| `---EXPECTED_OUTPUT_PYTHON---` | Output yang diharapkan untuk Python (stdout) |
| `---KEY_TEXT---` | Kata kunci yang harus ada di kode siswa |

#### Fitur Tombol "Coba" (Code Try-out)

LMS menyediakan fitur tombol **"Coba ▶"** pada blok kode di dalam materi pelajaran.

- Tombol **hanya muncul** jika instruktur memberikan label bahasa pada *code fence* (contoh: ` ```c `, ` ```python `, ` ```arduino `).
- Klik tombol akan menyalin kode ke editor dan beralih ke tab yang relevan.

#### Blok Khusus Circuit (Opsional)

Untuk materi yang melibatkan simulator rangkaian elektronika Falstad:

| Blok | Fungsi |
|------|--------|
| `` ```circuit `` | Rangkaian yang ditampilkan di materi (embed) |
| `---INITIAL_CIRCUIT---` | Rangkaian awal untuk latihan |
| `---EXPECTED_CIRCUIT_OUTPUT---` | Validasi rangkaian (format JSON: node voltage) |
| `---KEY_TEXT_CIRCUIT---` | Kata kunci rangkaian |

#### Blok Khusus Arduino/Velxio

Untuk materi yang menggunakan simulator Arduino (Velxio):

| Blok | Fungsi |
|------|--------|
| `---INITIAL_CODE_ARDUINO---` | Kode Arduino awal di editor Velxio |
| `---VELXIO_CIRCUIT---` | Rangkaian komponen (JSON: board, components, wires) |
| `---EXPECTED_SERIAL_OUTPUT---` | Output serial yang diharapkan (subsequence match) |
| `---EXPECTED_WIRING---` | Wiring yang harus dibuat siswa (JSON, lenient) |
| `---KEY_TEXT---` | Kata kunci yang harus ada di kode siswa |
| `---EVALUATION_CONFIG---` | Konfigurasi tambahan evaluasi Arduino (JSON: e.g. `timeout_ms` dalam milidetik) |

Contoh materi Arduino:

```markdown
---INITIAL_CODE_ARDUINO---
void setup() {
  pinMode(13, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  digitalWrite(13, HIGH);
  Serial.println("LED ON");
  delay(1000);
  digitalWrite(13, LOW);
  Serial.println("LED OFF");
  delay(1000);
}
---END_INITIAL_CODE_ARDUINO---

---VELXIO_CIRCUIT---
{
  "board": "arduino:avr:uno",
  "components": [
    { "type": "wokwi-led", "id": "led-1", "x": 400, "y": -200, "props": { "color": "red", "pin": 13 } }
  ],
  "wires": []
}
---END_VELXIO_CIRCUIT---

---EXPECTED_SERIAL_OUTPUT---
LED ON
LED OFF
---END_EXPECTED_SERIAL_OUTPUT---

---EXPECTED_WIRING---
{
  "wires": [
    { "start": { "componentId": "arduino-uno", "pinName": "13" }, "end": { "componentId": "led-1", "pinName": "A" } },
    { "start": { "componentId": "led-1", "pinName": "C" }, "end": { "componentId": "arduino-uno", "pinName": "GND" } }
  ]
}
---END_EXPECTED_WIRING---

---KEY_TEXT---
pinMode
digitalWrite
---END_KEY_TEXT---

---EVALUATION_CONFIG---
{
  "timeout_ms": 8000
}
---END_EVALUATION_CONFIG---
```

##### Referensi Nama Pin Komponen Velxio

| Komponen | Tipe Wokwi | Pin Names |
|----------|------------|----------|
| Arduino Uno | `wokwi-arduino-uno` | `0`-`13`, `A0`-`A5`, `GND`, `5V`, `3.3V` |
| LED | `wokwi-led` | `A` (Anode), `C` (Cathode) |
| Push Button | `wokwi-pushbutton` | `1.l`, `2.l`, `1.r`, `2.r` |
| Resistor | `wokwi-resistor` | `1`, `2` |
| RGB LED | `wokwi-rgb-led` | `R`, `G`, `B`, `COM` |

> **Penting:** Nama pin harus **persis** seperti tabel di atas.
> `componentId` untuk Arduino Uno selalu `arduino-uno` (huruf kecil, dengan strip).

##### Evaluasi Arduino

Sistem mengevaluasi 3 aspek (semua harus lulus):

1. **Key Text** — kata kunci wajib ada di source code siswa
2. **Serial Output** — baris yang diharapkan harus muncul dalam urutan (subsequence match)
3. **Wiring** — koneksi yang diharapkan harus ada (lenient: extra wires OK, GND.1/GND.2 dinormalisasi)

#### Blok Khusus Flowchart (Opsional)

Untuk materi logika pemrograman menggunakan flowchart:

| Blok | Fungsi |
|------|--------|
| `` ```flowchart `` | Flowchart yang ditampilkan di materi (embed) |
| `---INITIAL_FLOWCHART---` | Struktur flowchart awal untuk latihan |
| `---EXPECTED_FLOWCHART---` | Validasi struktur flowchart (JSON) |

#### Blok Khusus Quiz (Opsional)

LMS mendukung pembuatan kuis interaktif (Flashcard dan Pilihan Ganda) dalam dua format:

| Blok | Fungsi |
|------|--------|
| `---QUIZ_FLASHCARD---` | Kuis format Markdown (Flashcard & Pilihan Ganda) |
| `---INITIAL_QUIZ---` | Kuis format JSON |

##### Format Markdown (`QUIZ_FLASHCARD`)

Format ini sangat mudah digunakan untuk membuat kuis cepat.

```markdown
---QUIZ_FLASHCARD---
### Pertanyaan Flashcard
Ini adalah jawaban yang akan muncul di balik kartu.
> Penjelasan: Muncul setelah kartu dibalik.

### Apa output dari printf("%d", 10 + 5)?
- [] 105
- [x] 15
- [] 10
> Penjelasan: Operasi aritmatika dikerjakan dulu sebelum dicetak.
---END_QUIZ_FLASHCARD---
```

**Aturan Penulisan:**
1. Pertanyaan harus diawali dengan `###`.
2. Untuk **Pilihan Ganda**, gunakan `- []` untuk pilihan salah dan `- [x]` untuk pilihan benar.
3. Untuk **Flashcard**, cukup tulis jawaban langsung di bawah pertanyaan (tanpa `- []`).
4. Penjelasan opsional bisa ditambahkan di akhir pertanyaan dengan awalan `>`.

### 5. Keamanan & Akses Anonim

Sistem dilengkapi fitur keamanan untuk menjaga stabilitas:

- **Akses Anonim**: Siswa tanpa token tetap bisa mencoba materi, namun dibatasi **1 kali kompilasi setiap 2 menit**.
- **Login Token**: Siswa yang login dengan token **bebas** dari batasan rate limit kompilasi.
- **Proteksi Login**: Percobaan login salah akan ditahan (**tarpitting**) selama 1.5 detik untuk mencegah brute-force.
- **Anti Copy-Paste**: Mencegah siswa menyalin konten materi atau menempel kode dari luar (bisa dikonfigurasi).

### 6. Kelola Akun Guru

Aplikasi memakai **satu akun guru** (canonical) untuk mengakses dashboard
Laporan Progress (`/progress`). Buat atau update akun guru dengan:

```bash
cd elemes
./elemes.sh teacher
```

Perintah ini akan:
- Meminta **nama guru** — tekan Enter untuk memakai default dari
  `TEACHER_NAME` di `.env` (default: `Guru LMS`).
- Meminta **token guru** secara tersembunyi (via stdin — tidak muncul di
  layar, process list, maupun shell history).
- **Upsert** satu akun canonical di PostgreSQL: belum ada guru → dibuat;
  sudah ada → nama diperbarui **dan token dirotasi** (token lama langsung
  tidak berlaku); token sama dengan yang aktif → hanya nama yang diperbarui
  (idempotent).

> **Catatan:**
> - Token guru disimpan sebagai **HMAC-SHA256 digest** — tidak pernah dalam
>   bentuk plaintext dan tidak bisa dilihat kembali. Jangan bagikan token
>   guru ke siswa.
> - Akun siswa dikelola lewat halaman Laporan Progress (export → edit →
>   import CSV) — lihat bagian 9 — atau langsung di PostgreSQL.

#### First-Run Otomatis

`./elemes.sh runbuild`, `run`, dan `runclearbuild` otomatis menjalankan
migrasi schema database (`alembic upgrade head`) saat start. Bila
`TEACHER_TOKEN` di `.env` terisi, akun guru juga di-bootstrap otomatis
(non-interaktif). Bila `TEACHER_TOKEN` kosong, aplikasi tetap start tanpa
akun guru — operator tinggal menjalankan `./elemes.sh teacher` kapan saja.

### 7. (Opsional) Tambahkan Gambar

Letakkan gambar di folder `assets/` di parent folder.
Referensi di materi menggunakan:

```markdown
![deskripsi](assets/nama_gambar.png)
```

### 8. Jalankan LMS

```bash
cd elemes

# Build dan jalankan (pertama kali atau setelah update)
./elemes.sh runbuild

# Jalankan tanpa build ulang
./elemes.sh run

# Stop
./elemes.sh stop
```

LMS akan berjalan dan bisa diakses melalui Tailscale (jika dikonfigurasi)
atau langsung di `http://localhost:3000`.

### 9. Kelola Siswa via Round-Trip CSV (Export → Edit → Import)

Halaman **Laporan Progress** (`/progress`) menyediakan workflow bulat untuk
menambah atau memulihkan siswa tanpa menyentuh database secara manual:

1. **Export CSV** — unduh siswa terpilih (atau seluruh siswa bila tidak ada
   yang dipilih) beserta progress. Kolom `token` **selalu kosong** — token
   tidak pernah diekspor.
2. **Edit CSV** — ubah nama/progress siswa yang sudah ada, atau tambahkan
   baris siswa baru (dengan `student_id` kosong + token).
3. **Import CSV** — preview lalu konfirmasi. Import **all-or-nothing**: satu
   saja baris bermasalah membuat seluruh file ditolak tanpa perubahan.

Format CSV round-trip:

```csv
student_id;token;nama_siswa;hello_world;variabel
7eab651c-5eb1-4eb8-8fd2-17fd77aec6df;;Nama Siswa 1;completed;3/4
;TOKEN_87654321;Siswa Baru;not_started;completed
```

- Baris dengan `student_id` terisi (hasil export): token **boleh kosong** —
  siswa yang sudah ada **dipulihkan/di-update** (nama & progress diperbarui)
  dan **token lama dipertahankan**. Jangan mengisi token baru pada baris
  seperti ini — import ditolak.
- Baris dengan `student_id` kosong = **siswa baru**: token **wajib diisi**
  (8–128 karakter); server membuat UUID baru.
- `student_id` yang terisi tapi tidak dikenal di database ditolak (tidak ada
  pembuatan user dengan UUID sembarangan); teacher tidak pernah bisa diubah
  lewat import siswa.
- Status progress: kosong/`not_started` = belum mulai, `completed` = selesai,
  `<earned>/<total>` = skor.
- Kolom lesson lain wajib merupakan lesson yang masih aktif; kolom lesson yang
  tidak dikenal/duplikat membuat file ditolak.

#### Delimiter CSV

- **Export** dari aplikasi selalu memakai delimiter **titik koma (`;`)** dan
  encoding UTF-8 dengan BOM — contoh di atas adalah format canonical.
- **Import** menerima dua delimiter: **titik koma (`;`)** maupun
  **koma (`,`)**, agar file yang disimpan dari Excel/LibreOffice/Google
  Sheets (yang umumnya memakai koma) bisa langsung dipreview dan diimpor.
  Deteksi delimiter dilakukan dari header (kolom wajib `student_id`, `token`,
  `nama_siswa` harus muncul sebagai kolom terpisah), bukan dari isi file.
- Delimiter lain (mis. tab) atau header campuran yang tidak bisa dipetakan ke
  schema ditolak dengan pesan yang jelas — jangan mengganti delimiter secara
  manual dengan find-and-replace, karena itu merusak nilai ber-quote yang
  mengandung koma/titik koma.

## Perintah `elemes.sh`

| Perintah | Fungsi |
|----------|--------|
| `./elemes.sh init` | Setup awal: generate `.env`, `content/`, `assets/`, `state/` dari contoh |
| `./elemes.sh run` | Jalankan container (termasuk migrasi schema & bootstrap guru otomatis) |
| `./elemes.sh runbuild` | Build ulang & jalankan container |
| `./elemes.sh stop` | Hentikan container |
| `./elemes.sh teacher` | Buat/update akun guru (upsert; prompt nama & token tersembunyi) |
| `./elemes.sh dbupgrade` | Jalankan migrasi schema (alembic upgrade head) |
| `./elemes.sh dbstatus` | Cek versi schema database |
|| `./elemes.sh dbbackup` | Backup database → `backups/elemes_<ts>.sql` |
|| `./elemes.sh dbrestore` | Restore backup terbaru dari `backups/` |
|| `./elemes.sh test` | Full test suite (alias ke `test-all`) |
|| `./elemes.sh test-unit` | Unit test saja (cepat, no DB) |
|| `./elemes.sh test-integration` | Integration test (butuh PostgreSQL `elemes_test`) |
|| `./elemes.sh test-all` | Full test suite (CI gate) |
|| `./elemes.sh test-smoke` | Smoke test post-deploy (unit + sub-home subset) |
|| `./elemes.sh docs-validate` | Validasi frontmatter & broken link di `docs/*.md` |

## Dokumentasi & Referensi API

- **Docs Viewer**: Buka `http://localhost:3000/docs` untuk panduan teknis lengkap (arsitektur, backend, frontend, kuis, velxio, embed, dll) yang merender file `docs/*.md` secara dinamis.
- **API Reference**: `http://localhost:3000/docs/api-reference` menampilkan daftar semua endpoint Flask dengan docstring, metode, path, dan requirement auth.
- **Troubleshooting**: Buka `http://localhost:3000/help` untuk tutorial siswa; tautan ke Docs Viewer ada di sana.

## Database & Penyimpanan (PostgreSQL)

Sejak migrasi Agustus 2026, progress siswa & data token disimpan di **PostgreSQL**
— satu-satunya backend — melalui SQLAlchemy + Alembic (migrasi schema). Backend
CSV (`tokens_siswa.csv`, `STORAGE_BACKEND=csv`) sudah **dicabut**: file CSV token
tidak lagi dibuat, dibaca, maupun menjadi *source of truth*.

- Akun siswa & guru tersimpan di PostgreSQL (container `postgres`); akun guru
  dikelola via `./elemes.sh teacher` atau bootstrap otomatis `TEACHER_TOKEN`.
- Token hanya disimpan sebagai **HMAC-SHA256 digest** (pepper: `TOKEN_PEPPER`
  di `.env` — jangan hilangkan, semua token bergantung padanya).
- Daftar lesson disinkronkan **otomatis** dari `content/home.md` ke database
  setiap kali aplikasi start (tidak ada perintah sinkronisasi manual).
- **Backup rutin wajib**: `./elemes.sh dbbackup` (dump ke `backups/`);
  restore via `./elemes.sh dbrestore`.
- Panduan lengkap (arsitektur, riwayat migrasi): `docs/11-database-migration.md`.

## Contoh Siap Pakai

Folder `examples/` berisi contoh lengkap yang digunakan oleh `./elemes.sh init`:

```
examples/
├── content/
│   ├── home.md                    # Halaman utama (7 materi)
│   ├── dasar/                     # Sub bab: materi pemrograman dasar
│   │   ├── sub-home.md            # Halaman bab dasar
│   │   ├── hello_world.md         # Materi dasar: Hello World
│   │   ├── variabel.md            # Materi dasar: Variabel
│   │   └── ...
│   ├── arduino/                   # Sub bab: materi Arduino (Velxio)
│   │   ├── sub-home.md            # Halaman bab arduino
│   │   ├── led_blink_arduino.md   # Arduino: LED Blink + wiring
│   │   └── ...
│   └── rangkaian_dasar.md         # Materi hybrid: C + Circuit
```

### Jenis Materi

| Tipe | Contoh | Evaluasi |
|------|--------|----------|
| **C/Python** | `hello_world.md`, `variabel.md` | Output stdout |
| **Hybrid** | `rangkaian_dasar.md` | C output + node voltage |
| **Arduino (Velxio)** | `led_blink_arduino.md` | Key text + serial + wiring |
| **Arduino (tanpa wiring)** | `hello_serial_arduino.md` | Key text + serial |

## FAQ

**Q: Bagaimana menambah materi baru?**
Buat file `.md` baru di `content/`, lalu tambahkan link-nya di `content/home.md`
(di bagian daftar topik DAN bagian `----Available_Lessons----`).
Daftar lesson disinkronkan otomatis ke database saat aplikasi start — tidak
perlu perintah manual.

**Q: Bagaimana mengelompokkan materi ke dalam bab?**
Buat folder satu level di dalam `content/` (misal `content/bab1/`), letakkan
file `sub-home.md` di folder itu, dan daftarkan materi bab di bagian
`----Available_Lessons----` file tersebut. Folder punya halaman sendiri di
`/bab/<folder>` dan sidebar/navigasi materinya otomatis scoped ke bab itu.
Detail: `docs/13-content-sub-home.md`.

**Q: Bagaimana menambah siswa baru?**
Buka halaman **Laporan Progress** (`/progress`), Export CSV, tambahkan baris
baru (`student_id` kosong + token unik + nama siswa), lalu Import. Detail
format ada di bagian 9.

**Q: Siswa lupa token-nya?**
Token tidak bisa dilihat kembali — hanya digest HMAC yang tersimpan. Buatkan
siswa baru dengan token baru via halaman `/progress` (Import CSV, baris dengan
`student_id` kosong), lalu hapus akun lama lewat bulk delete.

**Q: Bagaimana melihat progress siswa?**
Login menggunakan token guru (kelola via `./elemes.sh teacher`). Dashboard progress
akan otomatis muncul. Data dibaca dari PostgreSQL.

**Q: Bagaimana backup/restore database?**
Jalankan `./elemes.sh dbbackup` — dump PostgreSQL tersimpan di
`backups/elemes_<timestamp>.sql`. Restore: `./elemes.sh dbrestore`
(memakai backup terbaru). Untuk mengubah data siswa, gunakan halaman
`/progress` (export → edit → import CSV).

**Q: Apakah harus pakai Tailscale?**
Tidak. Tailscale opsional untuk akses remote. Tanpa Tailscale, LMS
bisa diakses di jaringan lokal via `http://localhost:3000`.

**Q: Bagaimana membuat materi Arduino baru?**
Buat file `.md` baru di `content/` dengan blok `---INITIAL_CODE_ARDUINO---`
dan `---VELXIO_CIRCUIT---`. Lihat contoh di `led_blink_arduino.md`
atau `button_input_arduino.md`. Pastikan `componentId` dan `pinName`
di `EXPECTED_WIRING` sesuai dengan tabel referensi pin di atas.

**Q: Materi Arduino bisa tanpa wiring?**
Ya. Jika hanya evaluasi kode + serial output, cukup sertakan
`VELXIO_CIRCUIT` dengan `components: []` kosong dan hilangkan blok
`EXPECTED_WIRING`. Contoh: `hello_serial_arduino.md`.

**Q: Apakah wiring harus persis sama?**
Tidak harus. Evaluasi bersifat *lenient*: koneksi yang diharapkan harus ada,
tapi siswa boleh menambahkan kabel ekstra. Pin GND juga dinormalisasi
(GND.1 = GND.2 = GND).

**Q: Bagaimana cara membuat slide presentasi?**
Gunakan blok `---slide-start---` dan `---slide-end---` di materi markdown.
Setiap slide bisa berisi teks, gambar, code fence, dan embed (Canva/YouTube/Figma).
Contoh: `rangkaian_dasar.md`.

**Q: Bagaimana membuat flowchart interaktif?**
Gunakan blok `` ```flowchart `` di materi markdown. Flowchart mendukung
node, edge, obstacle-aware routing, dan evaluasi frontend.
Contoh: `flowchart.md`.

**Q: Bagaimana cara embed konten (Canva, YouTube, Google Docs, Figma)?**
Gunakan fence ```embed dengan raw HTML embed code dari platform:

````markdown
```embed
<div style="position: relative; width: 100%; padding-top: 56.25%;">
  <iframe loading="lazy" src="https://www.canva.com/design/.../view?embed" allowfullscreen></iframe>
</div>
```
````

Canva wajib URL dengan `?embed`. Lihat `docs/06-embed-content.md` untuk detail.

**Q: Bagaimana membuat kuis?**
Gunakan blok `---QUIZ_FLASHCARD---` dengan format Flashcard atau Pilihan Ganda.
Lihat `docs/07-quiz-authoring.md` untuk panduan lengkap.

**Q: Bagaimana kebijakan anti-cheat kuis bekerja?**
Strict focus-loss: berpindah tab, minimize, atau pindah app saat kuis aktif
langsung mengakhiri kuis dengan penalti, mencatat pelanggaran untuk laporan guru,
dan menyembunyikan pembahasan soal. Lihat `docs/12-quiz-integrity.md` untuk detail.

**Q: Apakah ada playground interaktif untuk mencoba kode?**
Ya. Route `/playground` menyediakan tab Velxio (Arduino simulator), Flowchart,
Circuit, dan Code. Fitur run sesi PTY mendukung Python `input()` dan C `scanf()`.
FileTree collapsible mendukung filter per bahasa (C/Python).

**Q: Bagaimana cara deploy firmware via USB (bukan BLE)?**
Gunakan browser Chrome desktop. DeployTab mendukung auto-detect:
Chrome desktop → USB (Web Serial API), mobile → BLE (Web Bluetooth).
Pilih tab Deploy, klik "Deploy" — firmware akan di-flash via kabel USB.

## Persyaratan Sistem

- [Podman](https://podman.io/) dan `podman-compose`
- Koneksi internet (saat build pertama kali untuk download image)
