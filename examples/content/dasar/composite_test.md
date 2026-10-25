---LESSON_INFO---
**Learning Objectives:**
- Memahami konsep materi komposit di Elemes (latihan koding + kuis)
- Menyelesaikan latihan program C/Python dan kuis evaluasi pemahaman
**Prerequisites:**
- variabel
---END_LESSON_INFO---

# Uji Coba Komposit (Latihan dan Kuis)

Pelajaran ini merupakan contoh materi **komposit**, yaitu materi pembelajaran yang menggabungkan:
1. **Latihan Pemrograman (Exercise):** Menulis kode program langsung di editor dan memverifikasi keluarannya.
2. **Kuis Evaluasi (Quiz):** Menjawab pertanyaan pilihan ganda terkait materi.

### Perhitungan Nilai Komposit
Nilai akhir siswa dihitung dari kombinasi kedua komponen:
- Bobot Latihan: 70%
- Bobot Kuis: 30%
- Ambang Tuntas (*Done*): $\ge$ 75%

---EXERCISE---
### Latihan: Pengecekan Angka Positif
Buatlah program yang memeriksa nilai variabel `angka`. Jika `angka > 0`, cetak:
```
Positif
```

---INITIAL_CODE---
#include <stdio.h>

int main() {
    int angka = 10;
    // Tulis logika percabangan if di bawah ini:
    if (angka > 0) {
        printf("Positif\n");
    }
    return 0;
}
---END_INITIAL_CODE---

---EXPECTED_OUTPUT---
Positif
---END_EXPECTED_OUTPUT---

---INITIAL_PYTHON---
angka = 10
# Tulis logika percabangan if di bawah ini:
if angka > 0:
    print("Positif")
---END_INITIAL_PYTHON---

---EXPECTED_OUTPUT_PYTHON---
Positif
---END_EXPECTED_OUTPUT_PYTHON---

---SOLUTION_CODE---
#include <stdio.h>

int main() {
    int angka = 10;
    if (angka > 0) {
        printf("Positif\n");
    }
    return 0;
}
---END_SOLUTION_CODE---

---SOLUTION_PYTHON---
angka = 10
if angka > 0:
    print("Positif")
---END_SOLUTION_PYTHON---

---KEY_TEXT---
if
printf
print
---END_KEY_TEXT---



---QUIZ_MCQ---
### Manakah sintaks penulisan kondisi `if` yang benar dalam bahasa C?
- [x] `if (kondisi) { ... }`
- [] `if kondisi then { ... }`
- [] `if [kondisi] { ... }`
- [] `if {kondisi} then { ... }`
> Penjelasan: Dalam bahasa C, ekspresi logika kondisi pada `if` wajib berada di dalam tanda kurung biasa `( )`.

### Apa keluaran dari kode berikut jika `x = 5`?
```c
if (x > 10) {
    printf("Besar\n");
} else {
    printf("Kecil\n");
}
```
- [] Besar
- [x] Kecil
- [] Error sintaks
- [] Tidak ada keluaran
> Penjelasan: Karena `5 > 10` bernilai salah (false), maka blok `else` yang akan dieksekusi, menghasilkan output "Kecil".

### Berapa bobot penilaian komponen latihan koding dalam penentuan nilai komposit standar Elemes?
- [] 30%
- [] 50%
- [x] 70%
- [] 100%
> Penjelasan: Secara default pada konfigurasi Elemes, komponen latihan koding memiliki bobot 70% dan kuis memiliki bobot 30%.
---END_QUIZ_MCQ---


