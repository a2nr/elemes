---LESSON_INFO---
**Learning Objectives:**
- Memahami berbagai tipe data dalam bahasa C
- Mengenal tipe data karakter, angka bulat, dan angka desimal
- Belajar menggunakan operator sizeof() untuk mengetahui ukuran tipe data
- Memahami penggunaan tipe data dalam konteks nyata
- Mengenal tipe data extended (lebih lanjut)

**Prerequisites:**
- Dasar-dasar pemrograman
- Pemahaman tentang program Halo Dunia
- Pemahaman tentang variabel

---END_LESSON_INFO---
# Tipe Data dalam C

**Tipe data dalam bahasa C** menentukan jenis nilai yang bisa disimpan dalam variabel, serta ukuran dan rentang nilai yang bisa ditampung. Setiap variabel dalam C harus memiliki tipe data yang dideklarasikan.

## Mengapa Tipe Data Penting?

**Tipe data** penting karena:
- Menentukan **jumlah memori** yang dialokasikan untuk variabel
- Menentukan **jenis nilai** yang bisa disimpan (angka, karakter, dll.)
- Menentukan **operasi** yang bisa dilakukan pada variabel tersebut

## Tipe Data Karakter

**Tipe data `char`** digunakan untuk menyimpan **satu karakter**. Karakter harus ditempatkan di dalam tanda petik tunggal `' '`.

```c
char myGrade = 'A';
char letter = 'x';
char symbol = '@';
```

**Format specifier** untuk `char` adalah `%c`:
```c
char myGrade = 'A';
printf("My grade is: %c\n", myGrade);  // Output: My grade is: A
```

## Tipe Data Angka Bulat

**Tipe data `int`** digunakan untuk menyimpan **bilangan bulat** (angka tanpa desimal).

```c
int myNum = 5;               // Bilangan positif
int myNegativeNum = -5;      // Bilangan negatif
int zero = 0;                // Nol
```

**Format specifier** untuk `int` adalah `%d` atau `%i`:
```c
int myNum = 5;
printf("My number is: %d\n", myNum);  // Output: My number is: 5
```

### Tipe Data Integer Lainnya

C juga menyediakan tipe data integer lainnya:
- `short` - versi pendek dari int (biasanya 2 byte)
- `long` - versi panjang dari int (biasanya 8 byte)
- `unsigned int` - versi int tanpa tanda (hanya nilai positif dan nol)

## Tipe Data Desimal

**Tipe data `float`** digunakan untuk menyimpan **bilangan desimal** dengan presisi tunggal.

```c
float myFloat = 9.99;
float scientific = 3e5;      // 300000
float negative = -3.99;
```

**Format specifier** untuk `float` adalah `%f`:
```c
float myFloat = 9.99;
printf("My float is: %f\n", myFloat);  // Output: My float is: 9.990000
```

**Tipe data `double`** digunakan untuk menyimpan **bilangan desimal** dengan presisi ganda (lebih akurat dari float).

```c
double myDouble = 19.99;
double precise = 3.141592653589793;
```

**Format specifier** untuk `double` adalah `%lf`:
```c
double myDouble = 19.99;
printf("My double is: %lf\n", myDouble);  // Output: My double is: 19.990000
```

## Mengetahui Ukuran Tipe Data

Anda bisa menggunakan **operator `sizeof()`** untuk mengetahui ukuran tipe data dalam byte:

```c
#include <stdio.h>

int main() {
    printf("Size of char: %zu byte(s)\n", sizeof(char));
    printf("Size of int: %zu byte(s)\n", sizeof(int));
    printf("Size of float: %zu byte(s)\n", sizeof(float));
    printf("Size of double: %zu byte(s)\n", sizeof(double));
    
    return 0;
}
```

**Output (dapat bervariasi tergantung sistem):**
```
Size of char: 1 byte(s)
Size of int: 4 byte(s)
Size of float: 4 byte(s)
Size of double: 8 byte(s)
```

## Tipe Data Extended

C juga menyediakan tipe data extended untuk kebutuhan spesifik:

### Tipe Data Unsigned
- `unsigned char` - karakter tanpa tanda (0 hingga 255)
- `unsigned int` - integer tanpa tanda (0 hingga 4,294,967,295)
- `unsigned short` - short integer tanpa tanda
- `unsigned long` - long integer tanpa tanda

### Tipe Data Signed
- `signed char` - karakter dengan tanda (-128 hingga 127)
- `signed int` - integer dengan tanda (sama seperti int biasa)

## Contoh Nyata Penggunaan Tipe Data

Berikut adalah contoh penggunaan berbagai tipe data dalam situasi nyata:

```c
#include <stdio.h>

int main() {
    // Tipe data karakter
    char initial = 'J';
    
    // Tipe data angka bulat
    int age = 25;
    unsigned int population = 1000000;
    
    // Tipe data desimal
    float temperature = 36.6;
    double preciseValue = 3.141592653589793238;
    
    // Menampilkan informasi
    printf("Initial: %c\n", initial);
    printf("Age: %d years old\n", age);
    printf("Population: %u people\n", population);
    printf("Temperature: %.1f°C\n", temperature);
    printf("Pi: %.10lf\n", preciseValue);
    
    // Menampilkan ukuran tipe data
    printf("\nSize of age variable: %zu bytes\n", sizeof(age));
    printf("Size of temperature variable: %zu bytes\n", sizeof(temperature));
    
    return 0;
}
```

**Output:**
```
Initial: J
Age: 25 years old
Population: 1000000 people
Temperature: 36.6°C
Pi: 3.1415926535

Size of age variable: 4 bytes
Size of temperature variable: 4 bytes
```

## Konstanta dalam C

**Konstanta** dalam bahasa C adalah nilai tetap yang tidak dapat diubah selama eksekusi program. Konstanta juga dikenal sebagai **literal** karena nilainya langsung ditulis dalam kode program.

### Jenis-Jenis Konstanta

Ada beberapa jenis konstanta dalam bahasa C:

#### 1. Konstanta Integer
Nilai bilangan bulat yang tidak memiliki bagian desimal:
```c
const int MAX_STUDENTS = 100;
int count = 50;
```

#### 2. Konstanta Floating-Point
Nilai bilangan desimal:
```c
const double PI = 3.14159;
float tax_rate = 0.08;
```

#### 3. Konstanta Karakter
Satu karakter yang diapit oleh tanda petik tunggal:
```c
const char NEWLINE = '\n';
char grade = 'A';
```

#### 4. Konstanta String
Rangkaian karakter yang diapit oleh tanda petik ganda:
```c
const char *GREETING = "Hello, World!";
char message[] = "Welcome to C programming";
```

### Keyword `const`

Anda bisa membuat variabel menjadi konstan dengan menggunakan **keyword `const`**. Setelah dideklarasikan sebagai konstan, nilai variabel tersebut tidak bisa diubah:

```c
const int AGE = 25;
// AGE = 30;  // Ini akan menyebabkan error karena AGE adalah konstan
```

### Preprocessor `#define`

Alternatif lain untuk membuat konstanta adalah dengan menggunakan **preprocessor directive `#define`**:

```c
#define PI 3.14159
#define MAX_SIZE 100
#define NAME "John Doe"

int main() {
    double area = PI * 5 * 5;  // Menghitung luas lingkaran dengan jari-jari 5
    printf("Area of circle: %.2f\n", area);
    return 0;
}
```

**Tips:**
- Gunakan tipe data yang **tepat** untuk kebutuhan Anda
- Perhatikan **rentang nilai** yang bisa ditampung oleh masing-masing tipe data
- Gunakan `unsigned` jika Anda yakin nilai tidak akan negatif
- Gunakan `double` jika Anda membutuhkan presisi tinggi

**Referensi:**
- [https://www.w3schools.com/c/c_data_types.php](https://www.w3schools.com/c/c_data_types.php)
- [https://www.w3schools.com/c/c_data_types_characters.php](https://www.w3schools.com/c/c_data_types_characters.php)
- [https://www.w3schools.com/c/c_data_types_numbers.php](https://www.w3schools.com/c/data_types_numbers.php)
- [https://www.w3schools.com/c/c_data_types_dec.php](https://www.w3schools.com/c/c_data_types_dec.php)
- [https://www.w3schools.com/c/c_data_types_sizeof.php](https://www.w3schools.com/c/c_data_types_sizeof.php)
- [https://www.w3schools.com/c/c_data_types_reallife.php](https://www.w3schools.com/c/c_data_types_reallife.php)
- [https://www.w3schools.com/c/c_data_types_extended.php](https://www.w3schools.com/c/c_data_types_extended.php)
- [Hello, World!](lesson/hello_world.md)
- [Variables in C](lesson/variables.md)

---EXERCISE---

# Latihan: Menggunakan Tipe Data

Dalam latihan ini, Anda akan membuat program sederhana yang menggunakan berbagai tipe data untuk menyimpan informasi buku dan menampilkannya.

**Requirements:**
- Buat variabel `title` untuk menyimpan judul buku (gunakan tipe data char array)
- Buat variabel `pages` untuk menyimpan jumlah halaman (gunakan tipe data int)
- Buat variabel `price` untuk menyimpan harga buku (gunakan tipe data float)
- Buat variabel `rating` untuk menyimpan rating buku (gunakan tipe data double)
- Tampilkan informasi buku menggunakan printf dengan format specifier yang sesuai
- Tampilkan ukuran dari variabel pages menggunakan sizeof()

**Expected Output:**
```
Book Title: The Art of Programming
Pages: 450
Price: $49.99
Rating: 4.75
Size of pages variable: 4 byte(s)
```

Try writing your solution in the code editor below!

---EXPECTED_OUTPUT---
Book Title: The Art of Programming
Pages: 450
Price: $49.99
Rating: 4.75
Size of pages variable: 4 byte(s)
---END_EXPECTED_OUTPUT---

---INITIAL_CODE---
#include <stdio.h>

int main() {
    // Deklarasi variabel di sini
    
    // Tampilkan informasi buku di sini
    printf("Book Title: \n");
    printf("Pages: \n");
    printf("Price: $\n");
    printf("Rating: \n");
    printf("Size of pages variable:  byte(s)\n");
    
    return 0;
}
---END_INITIAL_CODE---

---SOLUTION_CODE---
#include <stdio.h>

int main() {
    // Deklarasi variabel
    char title[] = "The Art of Programming";
    int pages = 450;
    float price = 49.99;
    double rating = 4.75;
    
    // Tampilkan informasi buku
    printf("Book Title: %s\n", title);
    printf("Pages: %d\n", pages);
    printf("Price: $%.2f\n", price);
    printf("Rating: %.2lf\n", rating);
    printf("Size of pages variable: %zu byte(s)\n", sizeof(pages));
    
    return 0;
}
---END_SOLUTION_CODE---