---LESSON_INFO---
**Learning Objectives:**
- Memahami konsep variabel dalam bahasa C
- Belajar mendeklarasikan dan menginisialisasi variabel
- Mengenal aturan penamaan variabel dalam C
- Memahami cara mengubah nilai variabel
- Mengenal format specifier untuk berbagai tipe data
- Belajar mendeklarasikan beberapa variabel sekaligus
- Memahami penggunaan variabel dalam konteks nyata

**Prerequisites:**
- Dasar-dasar pemrograman
- Pemahaman tentang program Halo Dunia

---END_LESSON_INFO---
# Variabel dalam C

**Variabel dalam bahasa C** adalah bagian memori bernama yang digunakan untuk menyimpan data dan mengaksesnya kapan saja diperlukan. Variabel memungkinkan kita menggunakan memori tanpa harus mengingat alamat memori yang tepat.

## Apa itu Variabel?

**Variabel** dalam bahasa C adalah **wadah (kontainer)** untuk menyimpan nilai data. Seperti halnya kotak yang bisa kita beri label dan isi dengan nilai tertentu. Setiap variabel memiliki **nama** (identifier) dan **nilai**.

## Deklarasi dan Inisialisasi Variabel

Untuk membuat variabel dalam C, kita harus menentukan **tipe data** dan **nama** yang akan disimpan. Setiap variabel harus dideklarasikan sebelum digunakan.

### Deklarasi Variabel
**Deklarasi variabel** adalah proses membuat variabel dengan menentukan tipe data dan nama:

```c
int myNum;
```

### Inisialisasi Variabel
**Inisialisasi variabel** adalah proses memberikan nilai awal ke variabel:

```c
int myNum = 15;
```

Contoh lengkap deklarasi dan inisialisasi:
```c
// Deklarasi dan inisialisasi sekaligus
int age = 20;
float price = 19.99;
char grade = 'A';

// Deklarasi terlebih dahulu, kemudian inisialisasi
int score;
score = 100;
```

## Format Specifier untuk Variabel

**Format specifier** digunakan dalam fungsi `printf()` untuk menentukan tipe data yang akan dicetak:

- `%d` atau `%i` untuk bilangan bulat (integer)
- `%f` untuk bilangan desimal (float/double)
- `%c` untuk karakter
- `%s` untuk string

Contoh:
```c
int myNum = 5;
float myFloatNum = 5.99;
char myLetter = 'D';

printf("Number: %d\n", myNum);
printf("Float: %f\n", myFloatNum);
printf("Letter: %c\n", myLetter);
```

## Mengubah Nilai Variabel

Setelah variabel dideklarasikan, kita bisa **mengubah nilainya** kapan saja dengan menggunakan operator penugasan (`=`):

```c
int myNum = 15;
printf("Original value: %d\n", myNum);  // Output: 15

myNum = 20;
printf("New value: %d\n", myNum);       // Output: 20
```

**Catatan penting:** Anda tidak bisa mengganti tipe data dari variabel yang sudah dideklarasikan. Jika sebuah variabel dideklarasikan sebagai `int`, Anda hanya bisa menyimpan bilangan bulat di dalamnya.

## Deklarasi Beberapa Variabel

Anda bisa **mendeklarasikan beberapa variabel sekaligus** dengan tipe data yang sama menggunakan koma:

```c
int x, y, z;
x = y = z = 50;
```

Atau deklarasi dan inisialisasi sekaligus:
```c
int x = 10, y = 20, z = 30;
```

## Aturan Penamaan Variabel

**Aturan untuk memberi nama variabel dalam C:**
1. Nama variabel hanya boleh mengandung **huruf**, **angka**, dan **garis bawah**
2. Harus **dimulai dengan huruf atau garis bawah**, tidak bisa dimulai dengan angka
3. **Tidak diperbolehkan spasi** dalam nama variabel
4. Nama **tidak boleh merupakan kata kunci** atau reserved word
5. Nama harus **unik dalam program**
6. Bahasa C bersifat **case-sensitive** (huruf besar dan kecil berbeda)

Contoh nama variabel yang **valid**: `myVar`, `_count`, `totalAmount`, `student_id`
Contoh nama variabel yang **tidak valid**: `2count`, `first name`, `int`

## Contoh Nyata Penggunaan Variabel

Berikut adalah contoh penggunaan variabel dalam situasi nyata:

```c
#include <stdio.h>

int main() {
    // Informasi pelanggan
    char firstName[] = "John";
    char lastName[] = "Doe";
    int age = 30;
    float salary = 2500.50;
    
    // Menampilkan informasi
    printf("Name: %s %s\n", firstName, lastName);
    printf("Age: %d years old\n", age);
    printf("Salary: $%.2f\n", salary);
    
    return 0;
}
```

**Output:**
```
Name: John Doe
Age: 30 years old
Salary: $2500.50
```

**Tips:**
- Gunakan nama variabel yang **deskriptif** agar kode lebih mudah dipahami
- Gunakan **camelCase** atau **snake_case** untuk nama variabel yang terdiri dari beberapa kata
- Hindari nama variabel yang terlalu singkat kecuali untuk variabel loop (seperti `i`, `j`, `k`)

**Referensi:**
- [https://www.w3schools.com/c/c_variables.php](https://www.w3schools.com/c/c_variables.php)
- [https://www.w3schools.com/c/c_variables_format.php](https://www.w3schools.com/c/c_variables_format.php)
- [https://www.w3schools.com/c/c_variables_change.php](https://www.w3schools.com/c/c_variables_change.php)
- [https://www.w3schools.com/c/c_variables_multiple.php](https://www.w3schools.com/c/c_variables_multiple.php)
- [https://www.w3schools.com/c/c_variables_names.php](https://www.w3schools.com/c/c_variables_names.php)
- [https://www.w3schools.com/c/c_variables_reallife.php](https://www.w3schools.com/c/c_variables_reallife.php)
- [Hello, World!](lesson/hello_world.md)
- [Data Types in C](lesson/data_types.md)

---EXERCISE---

# Latihan: Menggunakan Variabel

Dalam latihan ini, Anda akan membuat program sederhana yang menggunakan beberapa variabel untuk menyimpan informasi produk dan menampilkannya.

**Requirements:**
- Buat variabel `productName` untuk menyimpan nama produk (gunakan tipe data char array)
- Buat variabel `quantity` untuk menyimpan jumlah produk (gunakan tipe data int)
- Buat variabel `price` untuk menyimpan harga produk (gunakan tipe data float)
- Tampilkan informasi produk menggunakan printf dengan format specifier yang sesuai

**Expected Output:**
```
Product: Laptop
Quantity: 5
Price: $1200.00
```

Try writing your solution in the code editor below!

---EXPECTED_OUTPUT---
Product: Laptop
Quantity: 5
Price: $1200.00
---END_EXPECTED_OUTPUT---

---INITIAL_CODE---
#include <stdio.h>

int main() {
    // Deklarasi variabel di sini
    
    // Tampilkan informasi produk di sini
    printf("Product: \n");
    printf("Quantity: \n");
    printf("Price: $\n");
    
    return 0;
}
---END_INITIAL_CODE---

---SOLUTION_CODE---
#include <stdio.h>

int main() {
    // Deklarasi variabel
    char productName[] = "Laptop";
    int quantity = 5;
    float price = 1200.00;
    
    // Tampilkan informasi produk
    printf("Product: %s\n", productName);
    printf("Quantity: %d\n", quantity);
    printf("Price: $%.2f\n", price);
    
    return 0;
}
---END_SOLUTION_CODE---