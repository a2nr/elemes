---LESSON_INFO---
**Learning Objectives:**
- Memahami struktur dasar program C
- Mengenal fungsi main() sebagai titik awal eksekusi program
- Belajar menggunakan perintah printf untuk menampilkan output
- Memahami konsep header file dan direktif include

**Prerequisites:**
- Tidak ada persyaratan khusus
- Cocok untuk pemula dalam pemrograman C

---END_LESSON_INFO---
# Program Pertama C: Halo, Dunia!

**Bahasa pemrograman C** adalah bahasa pemrograman umum yang berhubungan erat dengan cara mesin bekerja. **Memahami cara kerja memori komputer** adalah aspek penting dari bahasa pemrograman C. Meskipun C bisa dianggap sebagai "sulit dipelajari", sebenarnya C adalah bahasa yang sangat sederhana, dengan kemampuan yang sangat kuat.

C adalah **bahasa yang sangat umum**, dan merupakan bahasa dari banyak aplikasi seperti Windows, interpreter Python, Git, dan banyak lagi.

**C adalah bahasa yang dikompilasi** - yang berarti bahwa untuk menjalankannya, **kompiler** (misalnya, GCC atau Visual Studio) harus mengambil kode yang kita tulis, memprosesnya, lalu membuat file yang dapat dieksekusi. File ini kemudian dapat dijalankan, dan akan melakukan apa yang kita maksudkan agar program tersebut lakukan.

## Program pertama kita
Setiap program C menggunakan **pustaka**, yang memberikan kemampuan untuk mengeksekusi fungsi-fungsi yang diperlukan. Sebagai contoh, fungsi paling dasar yang disebut `printf`, yang mencetak ke layar, didefinisikan dalam **file header `stdio.h`**.

Untuk menambahkan kemampuan menjalankan perintah `printf` ke program kita, kita harus menambahkan **direktif include** berikut ke baris pertama kode kita:

```c
#include <stdio.h>
```

Bagian kedua dari kode adalah kode aktual yang akan kita tulis. **Kode pertama yang akan dijalankan selalu berada di fungsi `main`**.

```c
int main() {
    ... kode kita ada di sini
}
```

**Kata kunci `int`** menunjukkan bahwa fungsi `main` akan mengembalikan bilangan bulat - angka sederhana. Angka yang akan dikembalikan oleh fungsi menunjukkan apakah program yang kita tulis berjalan dengan benar. Jika kita ingin mengatakan bahwa kode kita berjalan dengan sukses, kita akan mengembalikan angka 0. Angka lebih besar dari 0 akan berarti bahwa program yang kita tulis gagal. Untuk tutorial ini, kita akan mengembalikan 0 untuk menunjukkan bahwa program kita berhasil:

```c
return 0;
```

**Perhatikan bahwa setiap pernyataan dalam C harus diakhiri dengan titik koma**, sehingga kompiler tahu bahwa pernyataan baru telah dimulai.

Terakhir tetapi tidak kalah pentingnya, kita perlu memanggil fungsi `printf` untuk mencetak kalimat kita.

## Sintaks Dasar dalam C

**Sintaks dalam bahasa C** merujuk pada aturan dan struktur yang menentukan bagaimana program ditulis. Berikut adalah beberapa konsep penting dalam sintaks C:

### Struktur Program C
**Program C memiliki struktur tertentu** yang harus diikuti:
- **Header files** (menggunakan `#include`)
- **Fungsi `main()` sebagai titik awal eksekusi**
- **Deklarasi variabel** (jika ada)
- **Pernyataan-pernyataan program**
- **Pengembalian nilai dari fungsi `main()`**

### Case Sensitivity
**Bahasa C bersifat *case-sensitive***, artinya huruf besar dan kecil dibedakan. Misalnya, `variable`, `Variable`, dan `VARIABLE` adalah tiga nama yang berbeda.

### Titik Koma (;)
**Setiap pernyataan dalam C harus diakhiri dengan titik koma**. Ini memberi tahu kompiler bahwa pernyataan tersebut telah selesai.

### Blok Kode
**Blok kode dalam C didefinisikan dengan kurung kurawal `{` dan `}`**. Semua kode yang berada di antara kurung kurawal ini dianggap sebagai satu unit.

## Pernyataan dalam C

**Pernyataan dalam bahasa C adalah instruksi** yang memberi tahu komputer untuk melakukan tindakan tertentu. Ada beberapa jenis pernyataan dalam C:

### Pernyataan Ekspresi
Pernyataan yang terdiri dari ekspresi dan diakhiri dengan titik koma:
```c
x = 5;
y = x + 3;
hasil = a * b + c;
```

### Pernyataan Kompoun (Blok)
Sejumlah pernyataan yang dikelompokkan bersama dalam kurung kurawal:
```c
{
    int a = 10;
    int b = 20;
    int sum = a + b;
}
```

## Output dalam C

**Output dalam bahasa C biasanya dilakukan menggunakan fungsi `printf()`** dari pustaka `stdio.h`. Fungsi ini memungkinkan kita untuk menampilkan teks dan nilai variabel ke layar.

### Format Specifier
**Fungsi `printf()` menggunakan format specifier** untuk menentukan tipe data yang akan dicetak:
- **`%d` atau `%i` untuk bilangan bulat (integer)**
- **`%f` untuk bilangan desimal (float/double)**
- **`%c` untuk karakter**
- **`%s` untuk string**

Contoh:
```c
int usia = 25;
float tinggi = 175.5;
char inisial = 'J';
printf("Usia saya %d tahun\n", usia);
printf("Tinggi saya %.1f cm\n", tinggi);
printf("Inisial saya %c\n", inisial);
```

## Baris Baru dalam C

**Untuk membuat baris baru dalam output C, kita menggunakan karakter escape `\n`**. Karakter ini memberi tahu kompiler untuk pindah ke baris berikutnya.

Contoh:
```c
printf("Baris pertama\nBaris kedua\nBaris ketiga");
```

Output:
```
Baris pertama
Baris kedua
Baris ketiga
```

**Selain `\n`, ada beberapa karakter escape lain dalam C**:
- **`\t` untuk tab**
- **`\\` untuk backslash**
- **`\"` untuk tanda kutip ganda**

## Komentar dalam C

**Komentar adalah teks yang ditulis dalam kode program tetapi tidak akan dieksekusi**. Komentar digunakan untuk menjelaskan kode dan membuatnya lebih mudah dipahami.

### Komentar Satu Baris
**Komentar satu baris dimulai dengan `//`**:
```c
// Ini adalah komentar satu baris
int x = 5; // komentar setelah pernyataan
```

### Komentar Lebih dari Satu Baris
**Komentar yang lebih dari satu baris dimulai dengan `/*` dan diakhiri dengan `*/`**:
```c
/*
Ini adalah komentar
yang mencakup lebih dari
satu baris
*/
int y = 10;
```

**Komentar sangat penting untuk dokumentasi kode** dan membantu programmer lain (atau diri sendiri di masa depan) memahami maksud dari kode yang ditulis.

---

## Tabel Fungsi Dasar dalam stdio.h

| Fungsi | Deskripsi | Contoh |
|--------|-----------|--------|
| printf() | Mencetak output ke layar | `printf("Halo Dunia\\n");` |
| scanf() | Membaca input dari pengguna | `scanf("%d", &angka);` |
| getchar() | Membaca satu karakter | `char c = getchar();` |
| putchar() | Mencetak satu karakter | `putchar('A');` |

**Referensi:**
- [https://www.w3schools.com/c/c_syntax.php](https://www.w3schools.com/c/c_syntax.php)
- [https://www.w3schools.com/c/c_statements.php](https://www.w3schools.com/c/c_statements.php)
- [https://www.w3schools.com/c/c_output.php](https://www.w3schools.com/c/c_output.php)
- [https://www.w3schools.com/c/c_newline.php](https://www.w3schools.com/c/c_newline.php)
- [https://www.w3schools.com/c/c_comments.php](https://www.w3schools.com/c/c_comments.php)
- [Variables in C](lesson/variables.md)
- [Data Types in C](lesson/data_types.md)

---EXERCISE---

# Latihan: Program Halo, Dunia! dan Penggunaan Dasar C

Latih pemahamanmu tentang sintaks dasar C dengan menyelesaikan program berikut. Tambahkan komentar, gunakan format specifier, dan karakter escape sesuai permintaan.

**Requirements:**
- Ganti teks "Goodbye, World!" menjadi "Hello, World!"
- Tambahkan komentar satu baris sebelum fungsi main() menjelaskan tujuan program
- Tambahkan komentar lebih dari satu baris di dalam fungsi main() untuk menjelaskan apa yang dilakukan oleh printf
- Gunakan format specifier untuk mencetak usia kamu (sebagai integer) setelah "Hello, World!"
- Tambahkan karakter escape untuk membuat baris baru sebelum mencetak usia
- Pastikan program berjalan tanpa error

**Expected Output:**
```
Hello, World!
Saya berusia 20 tahun
```

Try writing your solution in the code editor below!

---EXPECTED_OUTPUT---
Hello, World!
Saya berusia 20 tahun
---END_EXPECTED_OUTPUT---

---KEY_TEXT---
Hello,
\n
---END_KEY_TEXT---

---INITIAL_CODE---
#include <stdio.h>

int main() {
    printf("Goodbye, World!");
    return 0;
}
---END_INITIAL_CODE---


---SOLUTION_CODE---
#include <stdio.h>

// Program ini mencetak pesan sambutan dan usia
int main() {
    /*
     * Fungsi printf digunakan untuk mencetak output ke layar
     * Dalam contoh ini, kita mencetak Hello, World! dan usia
     */
    printf("Hello, World!\nSaya berusia 20 tahun");
    return 0;
}
---END_SOLUTION_CODE---
