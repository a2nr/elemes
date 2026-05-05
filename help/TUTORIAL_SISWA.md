# Panduan Penggunaan LMS Elemes (Sinau-C)

Selamat datang di LMS Elemes! Panduan ini akan membantu kamu memahami cara menggunakan platform ini untuk belajar pemrograman C, elektronika, dan Arduino secara interaktif.

---

## 1. Memasukkan Token
Untuk mulai belajar, kamu perlu masuk menggunakan token yang diberikan oleh gurumu.
- Buka halaman utama LMS
- Klik tombol **"Masuk"** di pojok kanan atas.
- Masukkan token kamu (contoh: `dummy_token_12345`) dan klik **"Masuk"**.

![Memasukkan Token](/api/help/asset/tutorial_2_token.png)

---

## 2. Navigasi ke Kursus
Setelah berhasil masuk, nama kamu akan muncul di pojok kanan atas. Kamu bisa melihat daftar materi yang tersedia di halaman Home.
- Klik pada **Kartu Materi** (misalnya: "Hello, World!") untuk masuk ke halaman pelajaran.

![Dashboard Siswa](/api/help/asset/tutorial_9_progress.png)

---

## 3. Pengoperasian Halaman Lesson (Mode Desktop)
Halaman pelajaran terbagi menjadi dua bagian utama: **Materi** di sisi kiri dan **Workspace** di sisi kanan.

### Tab Workspace
Workspace memiliki beberapa tab sesuai dengan materi yang sedang dipelajari:
- **Info**: Menampilkan tujuan pembelajaran dan prasyarat.
- **Exercise**: Instruksi tugas yang harus diselesaikan.
- **C / Python**: Editor kode untuk menulis program.
- **Circuit / Arduino**: Simulator rangkaian atau mikrokontroler.
- **Output**: Hasil eksekusi program kamu.

![Halaman Pelajaran](/api/help/asset/tutorial_4_lesson_desktop.png)

### Floating & Docked Mode
Kamu bisa merubah tampilan Workspace agar lebih fleksibel:
- **Floating Mode**: Klik ikon kotak bertumpuk (**⊞**) di pojok kanan atas Workspace untuk menjadikannya jendela melayang.
- **Docker Workspace**: Klik ikon panah bawah (**▽**) untuk meminimalkan Workspace, atau klik ikon kotak (**⊡**) untuk mengembalikannya ke posisi semula (docked).
- **Resize**: Tarik ikon di pojok kiri atas jendela melayang (**◳**) untuk mengubah ukuran Workspace.

![Workspace Floating](/api/help/asset/tutorial_5_floating_workspace.png)

---

## 4. Pemrograman C dan Python
Di tab **C** atau **Python**, kamu bisa langsung menulis kode.
- Klik tombol **"▶ Run"** untuk menjalankan kodemu.
- Hasilnya akan muncul di tab **Output**.
- Gunakan tombol **"Reset"** jika ingin mengulang kode ke kondisi awal.

![Workspace C](/api/help/asset/tutorial_6_c_workspace.png)

---

## 5. Fitur "Coba ▶" (Code Try-out)
Di dalam materi pelajaran, kamu mungkin melihat blok kode dengan tombol **"Coba ▶"** di pojok kanan atasnya.
- Klik tombol tersebut untuk menyalin kode contoh langsung ke editor Workspace.
- Kamu bisa langsung meninjau kode tersebut dan menekan **"Run"** untuk melihat hasilnya tanpa harus mengetik ulang.

![Fitur Coba Kode](/api/help/asset/tutorial_5_coba.png)

---

## 6. Simulasi CircuitJS
Untuk materi elektronika, kamu bisa menggunakan simulator **CircuitJS**.
- Pilih tab **"Circuit"**.
- Kamu bisa melihat simulasi aliran arus secara *real-time*.
- Kamu bisa berinteraksi dengan komponen (seperti saklar) langsung di dalam simulator.

![Simulator CircuitJS](/api/help/asset/tutorial_7_circuitjs_workspace.png)

---

## 7. Simulasi Velxio (Arduino)
Untuk materi Arduino, platform ini menyediakan simulator **Velxio**.
- Pilih tab **"Arduino"**.
- Tulis kode `.ino` kamu di sisi kiri editor.
- Klik tombol **"Run"** (ikon petir/play) untuk mengunggah kode ke Arduino virtual.
- Perhatikan komponen di sisi kanan (seperti LED) yang akan bereaksi sesuai kodemu.

### Undo & Redo Wiring
Jika kamu melakukan kesalahan saat memasang kabel (wiring):
- Gunakan tombol **Panah Melengkung Ke Kiri** (Undo) untuk membatalkan langkah terakhir.
- Gunakan tombol **Panah Melengkung Ke Kanan** (Redo) untuk mengembalikan langkah yang dibatalkan.
- Kamu juga bisa menggunakan shortcut keyboard `Ctrl+Z` (Undo) dan `Ctrl+Shift+Z` (Redo).

![Simulator Velxio](/api/help/asset/tutorial_8_velxio_workspace.png)

---

## 8. Memantau Keberhasilan Exercise
Platform ini akan otomatis mendeteksi jika kamu telah berhasil menyelesaikan tugas.
- Jika tugas selesai, akan muncul tanda centang hijau (**✓ Selesai**) di samping judul materi.
- Kamu juga bisa melihat status penyelesaian di halaman Home (Dashboard) pada setiap kartu materi.

![Status Selesai](/api/help/asset/tutorial_9_progress.png)

---

## 9. Penting: Gunakan Token Kamu
Jika kamu belum masuk menggunakan token (akses anonim):
- Kamu hanya bisa menjalankan kode (**Run**) sekali setiap **2 menit**.
- Jika kamu masuk menggunakan token, kamu bisa menjalankan kode sepuasnya tanpa batasan waktu.

---
*Selamat belajar dan selamat bereksperimen!*
