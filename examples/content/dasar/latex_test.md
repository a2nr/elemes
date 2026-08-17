---LESSON_INFO---
**Learning Objectives:**
- Memahami cara penulisan LaTeX di LMS.
- Verifikasi perenderan rumus matematika.

**Prerequisites:**
- [Uji Coba Kuis](lesson/quiz_test.md) min: 75%
---END_LESSON_INFO---

# Uji Coba LaTeX

Selamat datang di modul uji coba LaTeX. LMS ini sekarang mendukung penulisan rumus matematika menggunakan KaTeX.

## Rumus Inline
Rumus inline dapat ditulis dengan menggunakan satu simbol dollar, contohnya: $E = mc^2$. 
Anda juga bisa menuliskan rumus yang lebih kompleks seperti akar kuadrat: $\sqrt{x^2 + y^2} = r$.

## Rumus Block
Rumus block ditulis dengan menggunakan double dollar:
$$\int_{a}^{b} x^2 dx = \frac{1}{3}(b^3 - a^3)$$

### Persamaan Multi-baris (Aligned)
Gunakan environment `aligned` untuk menjabarkan langkah-langkah perhitungan agar simbol sama dengan (`=`) sejajar:
$$
\begin{aligned}
(a+b)^2 &= (a+b)(a+b) \\
&= a^2 + ab + ba + b^2 \\
&= a^2 + 2ab + b^2
\end{aligned}
$$

### Fungsi Piecewise (Cases)
Contoh penulisan fungsi dengan beberapa kondisi:
$$
f(n) =
\begin{cases} 
n/2 & \text{jika } n \text{ genap} \\
3n+1 & \text{jika } n \text{ ganjil}
\end{cases}
$$

### Matriks dan Vektor
$$
A = \begin{pmatrix}
a_{11} & a_{12} \\
a_{21} & a_{22}
\end{pmatrix}, \quad
\mathbf{v} = \begin{bmatrix}
x \\
y
\end{bmatrix}
$$

## Penggunaan dalam Latihan
Anda juga bisa melihat rumus di bagian latihan di samping.

---EXERCISE---

Selesaikan masalah berikut:
Jika diketahui $f(x) = 2x + 3$, hitunglah nilai dari $\int_{0}^{1} f(x) dx$.

---INITIAL_CODE---
#include <stdio.h>

int main() {
    printf("4\n");
    return 0;
}
---END_INITIAL_CODE---

---EXPECTED_OUTPUT---
4
---END_EXPECTED_OUTPUT---
