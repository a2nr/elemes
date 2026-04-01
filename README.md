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
| `---INITIAL_CODE---` | Kode awal yang muncul di editor siswa |
| `---EXPECTED_OUTPUT---` | Output yang diharapkan untuk validasi jawaban |
| `---KEY_TEXT---` | Kata kunci yang harus ada di kode siswa |

#### Blok Khusus Circuit (Opsional)

Untuk materi yang melibatkan simulator rangkaian elektronika:

| Blok | Fungsi |
|------|--------|
| `` ```circuit `` | Rangkaian yang ditampilkan di materi |
| `---INITIAL_CIRCUIT---` | Rangkaian awal untuk latihan |
| `---EXPECTED_CIRCUIT_OUTPUT---` | Validasi rangkaian (format JSON) |
| `---KEY_TEXT_CIRCUIT---` | Kata kunci rangkaian |

### 5. Generate Token Siswa

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

### 6. (Opsional) Tambahkan Gambar

Letakkan gambar di folder `assets/` di parent folder.
Referensi di materi menggunakan:

```markdown
![deskripsi](assets/nama_gambar.png)
```

### 7. Jalankan LMS

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
│   ├── home.md              # Halaman utama (3 materi)
│   ├── hello_world.md       # Materi dasar: Hello World
│   ├── variabel.md          # Materi dasar: Variabel
│   └── rangkaian_dasar.md   # Materi hybrid: C + Circuit
└── tokens_siswa.csv         # Data siswa contoh (1 guru + 3 siswa)
```

File `rangkaian_dasar.md` adalah contoh **materi hybrid** yang menggabungkan
latihan pemrograman C dan simulator rangkaian elektronika dalam satu lesson.

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

## Persyaratan Sistem

- [Podman](https://podman.io/) dan `podman-compose`
- Python 3 (untuk `generatetoken`)
- Koneksi internet (saat build pertama kali untuk download image)
