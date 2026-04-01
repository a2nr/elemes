---LESSON_INFO---
**Learning Objectives:**
- Memahami struktur dasar program C
- Belajar menggunakan printf untuk menampilkan output

**Prerequisites:**
- Tidak ada persyaratan khusus
---END_LESSON_INFO---

# Hello, World!

Program C paling sederhana terdiri dari fungsi `main()` dan perintah `printf()`.

## Struktur Dasar

```c
#include <stdio.h>

int main() {
    printf("Hello, World!\n");
    return 0;
}
```

Penjelasan:
- `#include <stdio.h>` — memasukkan pustaka input/output standar
- `int main()` — fungsi utama, titik awal program
- `printf()` — mencetak teks ke layar
- `\n` — membuat baris baru
- `return 0` — menandakan program selesai tanpa error

---EXERCISE---
### Latihan
Buat program yang mencetak teks berikut:

```
Halo Dunia
```
---

---INITIAL_CODE---
#include <stdio.h>

int main() {
    // Tulis kode kamu di sini

    return 0;
}
---END_INITIAL_CODE---

---EXPECTED_OUTPUT---
Halo Dunia
---END_EXPECTED_OUTPUT---

---KEY_TEXT---
printf
---END_KEY_TEXT---
