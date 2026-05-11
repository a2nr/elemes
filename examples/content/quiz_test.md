# Uji Coba Kuis Komprehensif

Pelajaran ini berisi berbagai tipe kuis untuk menguji fitur Pilihan Ganda, Flashcard, dan sistem penguncian pembatalan.

---QUIZ_FLASHCARD---
### Bahasa C adalah bahasa pemrograman tingkat rendah.
image: https://upload.wikimedia.org/wikipedia/commons/1/18/C_Programming_Language.svg
- [] Benar
- [x] Salah
> Penjelasan: Bahasa C sebenarnya dikategorikan sebagai bahasa tingkat menengah (*middle-level language*) karena memiliki fitur bahasa tingkat rendah (seperti manipulasi memori) sekaligus fitur bahasa tingkat tinggi (seperti struktur kontrol yang manusiawi).

### Apa output dari `printf("%d", 5 + 5);`?
- [] 55
- [x] 10
- [] 5 + 5
- [] Error
> Penjelasan: Operasi `5 + 5` dihitung terlebih dahulu menjadi `10`, lalu dicetak sebagai integer menggunakan format specifier `%d`.

### Bagaimana cara menulis komentar satu baris di bahasa C?
Cukup gunakan dua garis miring di awal baris, contoh: `// ini komentar`.
> Penjelasan: Komentar berguna untuk mendokumentasikan kode agar mudah dibaca oleh manusia, dan akan diabaikan oleh compiler.

### Apa fungsi dari `return 0;` di dalam fungsi `main()`?
Menandakan bahwa program telah selesai berjalan dengan sukses tanpa ada error.

### Pilih gambar yang melambangkan bahasa C:
- [x] ![C Logo](https://upload.wikimedia.org/wikipedia/commons/1/18/C_Programming_Language.svg)
- [] ![Wrong Logo](https://upload.wikimedia.org/wikipedia/commons/c/c3/Python-logo-notext.svg)
---END_QUIZ_FLASHCARD---

---EXERCISE---
Cobalah untuk menyelesaikan kuis di tab sebelah kanan. Ingat, kamu tidak bisa melihat materi ini jika kuis sedang berjalan!
---

---INITIAL_CODE---
#include <stdio.h>

int main() {
    printf("Selesaikan kuisnya dulu ya!\n");
    return 0;
}
---END_INITIAL_CODE---
