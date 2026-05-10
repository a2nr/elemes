# Elemes - Panduan Guru

**Elemes** adalah Learning Management System (LMS) untuk mengajar pemrograman atau elektronika.
Guru cukup menyiapkan file konfigurasi dan konten materi dalam format Markdown,
lalu menjalankan container untuk deploy.

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
├── tokens_siswa.csv      # Data token siswa (auto-generated)
├── state/                # State Tailscale (auto-generated)
└── elemes/               # Folder engine LMS (JANGAN DIUBAH)
    ├── elemes.sh          # Script untuk menjalankan LMS
    └── ...
```

## Quick Start

```bash
cd elemes
./elemes.sh init      # Generate .env, content/, dan tokens dari contoh
```

Output:

```
=== Elemes Quick Start ===

[buat] .env  (edit sesuai kebutuhan)
[buat] content/  (4 materi)
[buat] tokens_siswa.csv  (edit untuk tambah siswa)

Selesai! Langkah selanjutnya:
  1. Edit ../.env sesuai kebutuhan
  2. Edit ../content/home.md untuk daftar materi
  3. Edit ../tokens_siswa.csv untuk data siswa
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

# Lokasi file
CONTENT_DIR=content
TOKENS_FILE=tokens.csv

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

### 6. Generate Token Siswa

Setelah materi siap, generate file `tokens_siswa.csv`:

```bash
cd elemes
./elemes.sh generatetoken
```

File `tokens_siswa.csv` akan dibuat di parent folder. Edit file ini untuk
menambahkan siswa:

```csv
token;nama_siswa;hello_world;variables;conditions
TOKEN_GURU_001;Pak Guru;not_started;not_started;not_started
TOKEN_SISWA_001;Budi Santoso;not_started;not_started;not_started
TOKEN_SISWA_002;Siti Aminah;not_started;not_started;not_started
```

> **Catatan:**
> - Kolom dipisahkan dengan **titik koma** (`;`), bukan koma.
> - Baris **pertama data** (setelah header) dianggap sebagai **token guru**.
> - Token bisa berupa string apa saja yang unik per siswa.
> - File ini bisa diedit menggunakan spreadsheet (LibreOffice Calc, Excel).
>   Saat membuka di Excel/Calc, pilih delimiter **titik koma**.

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

## Perintah `elemes.sh`

| Perintah | Fungsi |
|----------|--------|
| `./elemes.sh init` | Setup awal: generate `.env`, `content/`, `tokens_siswa.csv` dari contoh |
| `./elemes.sh run` | Jalankan container |
| `./elemes.sh runbuild` | Build ulang & jalankan container |
| `./elemes.sh stop` | Hentikan container |
| `./elemes.sh generatetoken` | Generate/update `tokens_siswa.csv` |

## Contoh Siap Pakai

Folder `examples/` berisi contoh lengkap yang digunakan oleh `./elemes.sh init`:

```
examples/
├── content/
│   ├── home.md                    # Halaman utama (7 materi)
│   ├── hello_world.md             # Materi dasar: Hello World
│   ├── variabel.md                # Materi dasar: Variabel
│   ├── rangkaian_dasar.md         # Materi hybrid: C + Circuit
│   ├── led_blink_arduino.md       # Arduino: LED Blink + wiring
│   ├── hello_serial_arduino.md    # Arduino: Serial Monitor (tanpa wiring)
│   ├── button_input_arduino.md    # Arduino: Button + LED input/output
│   └── traffic_light_arduino.md   # Arduino: Lampu lalu lintas 3 LED
└── tokens_siswa.csv               # Data siswa contoh (1 guru + 3 siswa)
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
Jalankan `./elemes.sh generatetoken` untuk update kolom di CSV.

**Q: Bagaimana menambah siswa baru?**
Edit `tokens_siswa.csv`, tambahkan baris baru dengan token unik dan nama siswa.
Kolom pelajaran diisi `not_started`.

**Q: Siswa lupa token-nya?**
Buka file `tokens_siswa.csv` dan cari nama siswa untuk melihat token-nya.

**Q: Bagaimana melihat progress siswa?**
Login menggunakan token guru (baris pertama di CSV). Dashboard progress
akan otomatis muncul.

**Q: Apakah harus pakai Tailscale?**
Tidak. Tailscale opsional untuk akses remote. Tanpa Tailscale, LMS
bisa diakses di jaringan lokal via `http://localhost:3000`.

**Q: Bagaimana membuat materi Arduino baru?**
Buat file `.md` baru di `content/` dengan blok `---INITIAL_CODE_ARDUINO---`
dan `---VELXIO_CIRCUIT---`. Lihat contoh di `led_blink_arduino.md`
atau `button_input_arduino.md`. Pastikan `componentId` dan `pinName`
di `EXPECTED_WIRING` sesuai dengan tabel referensi pin di atas.

**Q: Materi Arduino bisa tanpa wiring?**
Ya. Jika hanya ingin evaluasi kode + serial output, cukup sertakan
`VELXIO_CIRCUIT` dengan `components: []` kosong dan hilangkan blok
`EXPECTED_WIRING`. Contoh: `hello_serial_arduino.md`.

**Q: Apakah wiring harus persis sama?**
Tidak harus. Evaluasi bersifat *lenient*: koneksi yang diharapkan harus ada,
tapi siswa boleh menambahkan kabel ekstra. Pin GND juga dinormalisasi
(GND.1 = GND.2 = GND).

## Persyaratan Sistem

- [Podman](https://podman.io/) dan `podman-compose`
- Python 3 (untuk `generatetoken`)
- Koneksi internet (saat build pertama kali untuk download image)
