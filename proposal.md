# Proposal: Studi Kelayakan dan Perencanaan Implementasi CircuitJS1 di Elemes LMS

## Pendahuluan
Dokumen ini merupakan proposal dan studi kelayakan untuk mengintegrasikan **[CircuitJS1](https://github.com/pfalstad/circuitjs1)** (sebuah simulator rangkaian elektronik berbasis web) ke dalam ekosistem Elemes LMS. Tujuannya adalah untuk mentransisikan atau menambahkan kapabilitas LMS yang saat ini fokus pada pemrograman (Code Editor) menjadi platform pembelajaran rangkaian elektronik yang interaktif.

---

## 1. Cara Implementasi dengan Sistem Elemes yang Sekarang

Sistem Elemes saat ini terdiri dari Backend (Flask) dan Frontend (SvelteKit). Implementasi CircuitJS1 dapat dilakukan dengan mulus karena CircuitJS1 berjalan sepenuhnya di sisi klien (browser).

### a. Integrasi Frontend (SvelteKit)
- **Komponen Baru (`CircuitEditor.svelte`):** Komponen `CodeEditor.svelte` (berbasis CodeMirror) akan diganti atau didampingi dengan komponen baru yang memuat CircuitJS1.
- **Metode Embed:** CircuitJS1 dapat diintegrasikan menggunakan elemen `<iframe>` (dengan file HTML bawaan CircuitJS) yang disematkan di dalam halaman `/lesson/[slug]`. Alternatif lainnya adalah me-load file JavaScript CircuitJS secara langsung ke dalam DOM container SvelteKit.
- **Manajemen State (Auto-save):** CircuitJS1 memiliki fitur *Export/Import as Text*. Teks representasi rangkaian ini akan diperlakukan sama seperti "kode sumber" pada sistem saat ini. Teks tersebut dapat disimpan ke dalam `sessionStorage` (untuk auto-save) dan di-load kembali saat halaman di-refresh.

### b. Peran Backend (Flask)
- Karena kompilasi dan simulasi berjalan di browser (menggunakan JavaScript/HTML5), fungsi kompilasi di backend (`/api/compile` dan *compiler factory*) tidak lagi diperlukan untuk pelajaran elektronik.
- Backend hanya perlu fokus pada *API proxy*, autentikasi token (`/api/login`), penyajian konten pelajaran, dan pencatatan progres (`/api/track-progress`).

---

## 2. Cara Sistem Melakukan Evaluasi Terhadap Rangkaian Siswa

Pada sistem pemrograman C/Python, evaluasi dilakukan dengan menangkap `stdout` (Output) dari eksekusi kode di backend. Untuk rangkaian listrik, evaluasi dipindah ke **sisi klien (Frontend)** dengan dua pendekatan yang bisa digabungkan:

### a. Pendekatan Statis (Pencocokan Teks/Komponen)
CircuitJS merepresentasikan rangkaian dalam bentuk string teks baris per baris.
- Saat pengguna menekan tombol **"Submit" / "Cek Rangkaian"**, SvelteKit akan meminta teks representasi rangkaian dari iframe CircuitJS.
- Sistem akan mengecek ketersediaan komponen-komponen wajib menggunakan fitur yang mengadopsi mekanisme `---KEY_TEXT---` saat ini. Misalnya, memastikan ada resistor (`r`), sumber tegangan (`v`), atau LED dalam teks rangkaian siswa.

### b. Pendekatan Dinamis (Pencocokan Nilai Simulasi)
Karena CircuitJS disajikan secara *Same-Origin* (satu *domain/port* dengan SvelteKit), Elemes dapat mengakses langsung API global dari simulator tersebut tanpa batasan CORS.

Dengan pendekatan ini, data yang dimasukkan instruktur pada tag `---EXPECTED_STATE---` adalah berformat **JSON** yang mendefinisikan kriteria kelulusan simulasi.

**Contoh Format JSON `---EXPECTED_STATE---` di Markdown**:
```json
{
  "nodes": {
    "TestPoint_A": { "voltage": 5.0, "tolerance": 0.5 }
  },
  "elements": {
    "Resistor_1": { "voltage_drop": 2.5 }
  }
}
```

Sistem SvelteKit (melalui JavaScript) secara periodik akan mengekstrak state aktual komponen dengan merujuk pada **[Dokumentasi jsinterface CircuitJS1 (GitHub)](https://github.com/pfalstad/circuitjs1/blob/master/war/jsinterface.html)** atau melalui **[Live Example Interaktifnya](https://www.falstad.com/circuit/jsinterface.html)**:
1. Menarik API Simulator: `var sim = iframe.contentWindow.CircuitJS1;`
2. **`sim.getNodeVoltage(String n)`**: Mengambil nilai tegangan spesifik pada node observasi (misal node berlabel `TestPoint_A`).
3. **`sim.getElements()`**: Mengambil sekumpulan *array* objek komponen yang aktif di *canvas*. Frontend kemudian akan memanipulasinya (contoh pencarian berdasarkan indeks/teks properti) lalu memanggil properti internal seperti `.getVoltage(0)` atau *current*-nya.

- SvelteKit mencocokkan kondisi aktual simulator vs ekspektasi JSON. (*Contoh: Apakah tegangan di TestPoint_A masuk dalam range 4.5V s.d. 5.5V?*)
- Jika seluruh evaluasi menyatakan **LULUS**, maka SvelteKit mengirimkan HTTP request `POST /api/track-progress` ke Flask Backend untuk mencatat kelulusan siswa, lalu memunculkan *CelebrationOverlay* (kembang api).

---

## 3. Mengikuti Pola Pembuatan Konten yang Sekarang (Markdown)

Salah satu keunggulan arsitektur Elemes saat ini adalah kemudahan membuat konten hanya dengan file Markdown (`.md`) dan pemisah teks (delimiter). **Pola ini dapat dipertahankan 100% tanpa mengubah struktur parser backend secara masif.**

Pembuat konten (guru) cukup membuat rangkaian di CircuitJS versi publik, melakukan *Export as Text*, lalu memasukkannya ke dalam format Markdown Elemes.

**Pemetaan Delimiter Markdown Baru:**

| Tipe C/C++ (Default) | Tipe Python (Baru) | Tipe Electronics | Tipe Kuis (Tambahan) | Keterangan / Fungsi pada Modul |
|---|---|---|---|---|
| `---LESSON_INFO---` | `---LESSON_INFO---` | `---LESSON_INFO---` | `---LESSON_INFO---` | Sama. Berisi tujuan pembelajaran. |
| `---EXERCISE---` | `---EXERCISE---` | `---EXERCISE---` | `---EXERCISE---` | Sama. Soal instruksi untuk siswa. |
| `---INITIAL_CODE---` | `---INITIAL_PYTHON---` | `---INITIAL_CIRCUIT---` | `---INITIAL_QUIZ---` | Initial blok kode, simulator, atau *payload* kuis (JSON) saat dibuka. |
| `---SOLUTION_CODE---` | `---SOLUTION_PYTHON---` | `---SOLUTION_CIRCUIT---` | `---SOLUTION_QUIZ---` | Solusi akhir yang benar (kunci jawaban). |
| `---KEY_TEXT---` | `---KEY_TEXT---` | `---KEY_TEXT---` | `---KEY_TEXT---` | Komponen wajib atau validasi teks statis. |
| `---EXPECTED_OUTPUT---`| `---EXPECTED_OUTPUT---`| `---EXPECTED_STATE---` | `---EXPECTED_JSON---` | Output/Rules/Format evaluasi untuk hit *Track Progress*. |

### Konfigurasi Multi-Tab Workspace (Mode Hybrid)
Agar sistem Elemes tahu antarmuka mana yang perlu dimuat, kita akan menggunakan **Pendekatan Implisit Kolektif**. 

Alih-alih memaksa satu modul *hanya* menjadi "pelajaran C" atau "pelajaran Elektronika", parser SvelteKit dan Backend akan bersikap asimilatif. Jika seorang instruktur (misalnya untuk modul *Embedded System* berbekal AVR8js) memasukkan semua tag sekaligus ke dalam satu materi, sistem akan merender **Sistem Multi-Tab di Workspace**.

Cara kerjanya (Pendeteksian Paralel):
- Apakah `---INITIAL_CODE---` ada? -> Aktifkan Tab **CodeEditor (C/C++)**.
- Apakah `---INITIAL_PYTHON---` ada? -> Aktifkan Tab **CodeEditor (Python)**.
- Apakah `---INITIAL_CIRCUIT---` ada? -> Aktifkan Tab **CircuitEditor**.
- Apakah `---INITIAL_QUIZ---` ada? -> Aktifkan Tab **QuizPanel**.

Visi ini sangat **Backward Compatible** dan sangat visioner secara infrastruktur. Ratusan materi lama Anda yang secara konvensional hanya memiliki tag `_CODE` murni akan tetap tampil sebagai satu layar editor penuh C/C++. Sedangkan materi yang kompleks di masa depan bisa memadukan keempat fungsi (*C, Python, Simulator, Quiz*) dalam sistem tab yang elegan.

**Workflow Pembuatan Konten oleh Guru:**
1. Buka CircuitJS di browser.
2. Gambar rangkaian "awal" (sebagian belum lengkap). Klik *File -> Export as Text*, salin ke dalam tag `---INITIAL_CIRCUIT---`.
3. Selesaikan rangkaiannya. Klik *Export as Text*, salin ke dalam tag `---SOLUTION_CIRCUIT---`.
4. Definisikan komponen yang diwajibkan di `---KEY_TEXT---`.
5. Siswa membuka Elemes LMS, SvelteKit mem-parsing string `INITIAL_CIRCUIT` dan menampilkannya sebagai rangkaian hidup di dalam CircuitJS.

## 4. Analisa Source Code & Refactoring Backend
Sistem `elemes/services/lesson_service.py` saat ini (`render_markdown_content`) memiliki parser *hardcoded* yang mengembalikan `7 item tuple` yang sangat restriktif. Menambahkan data elektronika ke *tuple* ini secara mentah akan menghasilkan rantai kembalian panjang (12+ item) yang rawan eror.

Oleh karena itu, bagian teknis dari proposal ini menyertakan perbaikan (*refactoring*) pada *blueprint* backend:

### a. Modifikasi `elemes/services/lesson_service.py`
- Mengubah titik temu fungsi `render_markdown_content` menjadi tipe data **Dictionary** (*key-value*) bernama `parsed_data`.
- Menerapkan pola deteksi Kolektif: Fungsi *extract* akan memverifikasi ekstensi tag dan mengumpulkannya ke dalam *array* metadata, misal `active_tabs`.
  - Jika `---INITIAL_CODE---` ada -> `active_tabs.append("c")`
  - Jika `---INITIAL_PYTHON---` ada -> `active_tabs.append("python")`
  - Jika `---INITIAL_CIRCUIT---` ada -> `active_tabs.append("circuit")`
  - Jika `---INITIAL_QUIZ---` ada -> `active_tabs.append("quiz")`

### b. Modifikasi Router `elemes/routes/lessons.py`
- Menyesuaikan API endpoint `/lesson/[slug].json` agar memproses keluaran `active_tabs` ini dengan format JSON yang valid ke Frontend.

### c. Modifikasi Frontend SvelteKit (`elemes/frontend/src/routes/lesson/[slug]/+page.svelte`)
- Berdasarkan **analisa *source code* UI saat ini**, komponen *Workspace* Elemes sudah memiliki infrastruktur `<div class="panel-tabs">` dan skema *state* bawaan.
- *State type* bawaan `activeTab` yang semula hanya menampung tipe statis (`'info'|'exercise'|'editor'|'output'`) akan diperlebar menjadi dinamis (`'editor_c' | 'editor_python' | 'circuit' | 'quiz'`).
- SvelteKit cukup melacak *array* `active_tabs` rakitan backend untuk membangun komponen *tab/button* secara kondisional. Jika *array* lebih dari 1, *tab* aktif bergantian (*Embedded Systems Mode*). Jika *array* hanya 1 (pada file lama), antarmuka langsung kembali ke 100% *full-editor* seperti kondisi *legacy*.

---

## Kesimpulan
Perubahan dari LMS pemrograman ke LMS simulasi rangkaian menggunakan CircuitJS1 **sangat feasible (layak)** dan **hemat sumber daya** karena:
1. Tidak membutuhkan komputasi simulasi berat di server (semua dilimpahkan ke client secara penuh).
2. Mempertahankan gaya pembuatan konten berbasis Markdown yang *author-friendly*; menggunakan pendekatan pendeteksian tag *Implisit* (redundansi pengetikan nol, 100% backward-compatible dengan skenario C/Python lama).
3. Proses migrasinya sangat terpusat: hanya butuh merapikan *parser tuple-to-dictionary* di backend dan membuat *komponen UI tunggal iframe CircuitJS1* yang diletakkan pada SvelteKit frontend.