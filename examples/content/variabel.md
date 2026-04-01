---LESSON_INFO---
**Learning Objectives:**
- Memahami konsep variabel di bahasa C
- Belajar mendeklarasikan dan menginisialisasi variabel
- Mengenal tipe data dasar: int, float, char

**Prerequisites:**
- Hello, World!
---END_LESSON_INFO---

# Variabel dalam C

**Variabel** adalah tempat untuk menyimpan data di memori komputer.
Setiap variabel memiliki **nama** dan **tipe data**.

## Tipe Data Dasar

| Tipe | Deskripsi | Contoh |
|------|-----------|--------|
| `int` | Bilangan bulat | `42`, `-7` |
| `float` | Bilangan desimal | `3.14`, `-0.5` |
| `char` | Satu karakter | `'A'`, `'z'` |

## Deklarasi dan Inisialisasi

```c
#include <stdio.h>

int main() {
    int umur = 17;
    float tinggi = 165.5;
    char huruf = 'A';

    printf("Umur: %d tahun\n", umur);
    printf("Tinggi: %.1f cm\n", tinggi);
    printf("Huruf: %c\n", huruf);

    return 0;
}
```

Format specifier untuk `printf()`:
- `%d` — integer
- `%f` — float (gunakan `%.1f` untuk 1 desimal)
- `%c` — character

## Versi Python

Python tidak perlu mendeklarasikan tipe data secara eksplisit:

```python
umur = 17
tinggi = 165.5
huruf = 'A'

print(f"Umur: {umur} tahun")
print(f"Tinggi: {tinggi:.1f} cm")
print(f"Huruf: {huruf}")
```

Perbedaan utama:
- Tidak perlu menuliskan tipe (`int`, `float`, `char`) — Python mengenali otomatis
- Gunakan **f-string** (`f"..."`) untuk menyisipkan variabel ke dalam teks
- `{tinggi:.1f}` sama fungsinya dengan `%.1f` di C

---EXERCISE---
### Latihan
Buat program yang mendeklarasikan variabel `nama_panjang` bertipe `int` dengan nilai `10`,
lalu cetak hasilnya.

Output yang diharapkan:
```
Panjang nama: 10
```
---

---INITIAL_CODE---
#include <stdio.h>

int main() {
    // Deklarasikan variabel nama_panjang bertipe int
    // Cetak hasilnya menggunakan printf

    return 0;
}
---END_INITIAL_CODE---

---EXPECTED_OUTPUT---
Panjang nama: 10
---END_EXPECTED_OUTPUT---

---INITIAL_PYTHON---
# Deklarasikan variabel nama_panjang
# Cetak hasilnya menggunakan print

---END_INITIAL_PYTHON---

---KEY_TEXT---
int
printf
---END_KEY_TEXT---
