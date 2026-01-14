---LESSON_INFO---
**Learning Objectives:**
- Memahami berbagai tipe data dalam bahasa C
- Belajar mendeklarasikan dan menginisialisasi variabel
- Mengenal batas-batas masing-masing tipe data
- Memahami perbedaan antara tipe data signed dan unsigned

**Prerequisites:**
- Dasar-dasar pemrograman
- Pemahaman tentang program Halo Dunia

---END_LESSON_INFO---
# Tipe Data dan Variabel dalam C

C memiliki beberapa jenis variabel, tetapi ada beberapa tipe dasar:

* Bilangan Bulat - bilangan bulat yang bisa positif atau negatif. Didefinisikan menggunakan `char`, `int`, `short`, `long` atau `long long`.
* Bilangan Bulat Tak Bertanda - bilangan bulat yang hanya bisa positif. Didefinisikan menggunakan `unsigned char`, `unsigned int`, `unsigned short`, `unsigned long` atau `unsigned long long`.
* Bilangan Pecahan - bilangan real (bilangan dengan pecahan). Didefinisikan menggunakan `float` dan `double`.
* Struktur - akan dijelaskan nanti, di bagian Struktur.

## Tipe Data dalam C

Jenis-jenis variabel yang berbeda menentukan batas-batasnya. Sebuah `char` bisa dari -128 hingga 127, sedangkan sebuah `long` bisa dari -2,147,483,648 hingga 2,147,483,647 (`long` dan tipe data numerik lainnya mungkin memiliki rentang lain di komputer yang berbeda, misalnya - dari –9,223,372,036,854,775,808 hingga 9,223,372,036,854,775,807 di komputer 64-bit).

Perhatikan bahwa C _tidak_ memiliki tipe boolean. Biasanya, itu didefinisikan menggunakan notasi berikut:

```c
#define BOOL char
#define FALSE 0
#define TRUE 1
```

C menggunakan array karakter untuk mendefinisikan string, dan akan dijelaskan di bagian String.

## Mendefinisikan variabel
Untuk angka, kita biasanya akan menggunakan tipe `int`. Di kebanyakan komputer saat ini, itu adalah bilangan 32-bit, yang berarti angkanya bisa dari -2,147,483,648 hingga 2,147,483,647.

Untuk mendefinisikan variabel `foo` dan `bar`, kita perlu menggunakan sintaks berikut:

```c
int foo;
int bar = 1;
```

Variabel `foo` bisa digunakan, tetapi karena kita tidak menginisialisasinya, kita tidak tahu apa yang ada di dalamnya. Variabel `bar` berisi angka 1.

Sekarang, kita bisa melakukan beberapa operasi matematika. Dengan mengasumsikan `a`, `b`, `c`, `d`, dan `e` adalah variabel, kita bisa menggunakan operator penjumlahan, pengurangan dan perkalian dalam notasi berikut, dan memberikan nilai baru ke `a`:

```c
int a = 0, b = 1, c = 2, d = 3, e = 4;
a = b - c + d * e;
printf("%d", a); /* akan mencetak 1-2+3*4 = 11 */
```

---

## Tabel Tipe Data dalam C

| Tipe | Ukuran (bit) | Rentang Nilai | Contoh |
|------|--------------|---------------|--------|
| char | 8 | -128 hingga 127 | `char grade = 'A';` |
| int | 32 | -2,147,483,648 hingga 2,147,483,647 | `int age = 25;` |
| short | 16 | -32,768 hingga 32,767 | `short year = 2023;` |
| long | 64 | -9,223,372,036,854,775,808 hingga 9,223,372,036,854,775,807 | `long population = 1000000L;` |
| float | 32 | ~7 digit desimal | `float price = 19.99f;` |
| double | 64 | ~15 digit desimal | `double pi = 3.14159;` |
| unsigned char | 8 | 0 hingga 255 | `unsigned char count = 100;` |

---EXERCISE---

# Latihan: Menjumlahkan Variabel

Di latihan berikutnya, Anda perlu membuat program yang mencetak jumlah dari angka `a`, `b`, dan `c`.

**Requirements:**
- Hitung jumlah dari variabel a, b, dan c
- Simpan hasilnya dalam variabel sum
- Pastikan tipe data yang digunakan sesuai

**Expected Output:**
```
The sum of a, b, and c is 12.750000.
```

Try writing your solution in the code editor below!

---EXPECTED_OUTPUT---
The sum of a, b, and c is 12.750000.
---END_EXPECTED_OUTPUT---

---INITIAL_CODE---
#include <stdio.h>

int main() {
    int a = 3;
    float b = 4.5;
    double c = 5.25;
    float sum;

    /* Kode Anda di sini */

    printf("The sum of a, b, and c is %f.", sum);
    return 0;
}
---END_INITIAL_CODE---

---SOLUTION_CODE---
#include <stdio.h>

int main() {
    int a = 3;
    float b = 4.5;
    double c = 5.25;
    float sum;

    sum = a + b + c;
    printf("The sum of a, b, and c is %f.", sum);
    return 0;
}
---END_SOLUTION_CODE---