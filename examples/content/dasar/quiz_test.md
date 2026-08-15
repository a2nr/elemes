# Uji Coba Kuis Komprehensif

Pelajaran ini berisi berbagai tipe kuis untuk menguji fitur Pilihan Ganda, Flashcard, dan sistem penguncian pembatalan.

---QUIZ_FLASHCARD---
### Bahasa C adalah bahasa pemrograman tingkat rendah.
image: https://upload.wikimedia.org/wikipedia/commons/1/18/C_Programming_Language.svg
- [] Benar
- [x] Salah
> Penjelasan: Bahasa C sebenarnya dikategorikan sebagai bahasa tingkat menengah (*middle-level language*) karena memiliki fitur bahasa tingkat rendah (seperti manipulasi memori) sekaligus fitur bahasa tingkat tinggi (seperti struktur kontrol yang manusiawi).

### Apa output dari `printf("%d", 5 + 5);`?
::diagnostic
- [] 55
- [x] 10
- [] 5 + 5
- [] Error
> Penjelasan: Operasi `5 + 5` dihitung terlebih dahulu menjadi `10`, lalu dicetak sebagai integer menggunakan format specifier `%d`.

### Perhatikan program berikut:
```c
int x = 2;
printf("%d", x * 3);
```
Berapakah keluaran program di atas?
- [] 5
- [] 8
- [x] 6
- [] Error
> Pembahasan: `x * 3` menghasilkan `6` karena nilai `x` adalah `2`.

### Berdasarkan tabel berikut, tipe data mana yang tepat untuk menyimpan `3.14`?
::diagnostic
|| Tipe   | Ukuran | Rentang            ||
|--------|--------|--------------------|
| int    | 4 byte | -2^31 s/d 2^31-1   |
| float  | 4 byte | ~1e-38 s/d ~1e38   |
| double | 8 byte | ~1e-308 s/d ~1e308 |
- [x] double
- [] int
- [] char
> Pembahasan: `double` punya presisi lebih tinggi dan rentang lebih luas untuk bilangan pecahan.

### Berapakah nilai dari $\int_0^1 2x \, dx$?
::diagnostic
- [x] 1
- [] 2
- [] 0.5
- [] Tidak terdefinisi
> Pembahasan: Hasil integralnya adalah $[x^2]_0^1 = 1$.

### Pilih gambar yang melambangkan bahasa C:
![C Logo](https://upload.wikimedia.org/wikipedia/commons/1/18/C_Programming_Language.svg)
- [x] Logo C
- [] Logo Python
- [] Logo Java

### Bagaimana cara menulis komentar satu baris di bahasa C?
Cukup gunakan dua garis miring di awal baris, contoh: `// ini komentar`.
> Penjelasan: Komentar berguna untuk mendokumentasikan kode agar mudah dibaca oleh manusia, dan akan diabaikan oleh compiler.

### Apa fungsi dari `return 0;` di dalam fungsi `main()`?
Menandakan bahwa program telah selesai berjalan dengan sukses tanpa ada error.

### Apa warna langit pada siang hari?
image: demo_quiz.png
- [x] Biru
- [] Hijau
- [] Merah
- [] Kuning
> Penjelasan: Langit terlihat biru karena hamburan Rayleigh — cahaya matahari dihamburkan oleh atmosfer bumi.

---END_QUIZ_FLASHCARD---