---LESSON_INFO---
**Learning Objectives:**
- Memahami alur logika sistem otomatis berbasis sensor.
- Mengimplementasikan percabangan (IF-ELSE) dalam flowchart.
- Membuat siklus perulangan (LOOP) untuk pemantauan berkelanjutan.

**Prerequisites:**
- [Variabel](lesson/variabel.md)

**Challenge:**
Buatlah flowchart untuk **Sistem Penyiraman Tanaman Otomatis**.
1. Mulai sistem.
2. Inisialisasi sensor kelembapan tanah.
3. Baca nilai kelembapan secara terus-menerus.
4. JIKA tanah **Kering**, maka **Nyalakan Pompa Air**.
5. JIKA tanah **Basah**, maka **Matikan Pompa Air**.
6. Setelah tindakan (nyala/mati), kembali baca sensor.

---END_LESSON_INFO---

# Tantangan: Penyiram Tanaman Otomatis
Gunakan elemen di sebelah kiri untuk menyusun logika sistem penyiraman otomatis Anda.

Berikut adalah contoh visualisasi alur logika dasar:

```flowchart,100%,300px
start[roundrect] "Mulai"
setup[rect] "Setup LED"
loop[circle] "Loop"
on[parallelogram] "LED ON"
off[parallelogram] "LED OFF"

start --> setup
setup --> loop
loop --> on
on --> off
off --> loop
```

---INITIAL_FLOWCHART---
start[roundrect] "Mulai Sistem"
init[rect] "Inisialisasi Sensor"
read[rect] "Baca Kelembapan Tanah"
check[diamond] "Apakah Tanah Kering?"
on[parallelogram] "Nyalakan Pompa Air"
off[parallelogram] "Matikan Pompa Air"

start --> init
init --> read
read --> check
check --> on "Ya"
check --> off "Tidak"
on --> read
off --> read
---END_INITIAL_FLOWCHART---

---EXPECTED_FLOWCHART---
start[roundrect] "mulai"
init[rect] "inisialisasi"
read[rect] "baca"
check[diamond] "kering"
on[parallelogram] "nyalakan"
off[parallelogram] "matikan"

start --> init
init --> read
read --> check
check --> on
check --> off
on --> read
off --> read
---END_EXPECTED_FLOWCHART---