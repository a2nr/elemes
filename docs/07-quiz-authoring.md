---
title: Quiz Authoring
order: 7
category: quiz
---
# 07. Quiz Authoring (Format Soal Kuis)

Kuis ditulis sebagai Markdown di dalam marker `---QUIZ_FLASHCARD---` sampai `---END_QUIZ_FLASHCARD---`. Setiap blok diawali `###` (heading level 3). Opsi pilihan ganda ditulis sebagai list item dengan tanda kurung: `- [x]` = jawaban benar, `- []` = salah. **Wajib tepat satu `[x]` per soal** — parser menolak soal tanpa jawaban benar atau dengan lebih dari satu.

```
---QUIZ_FLASHCARD---
### Pertanyaan pertama?
- [] Opsi A
- [x] Opsi B (benar)

### Pertanyaan kedua?
...
---END_QUIZ_FLASHCARD---
```

## Dua tipe soal

### 1. Pilihan Ganda (MCQ) — format flat (kompatibel)

Heading langsung diikuti daftar opsi:

```markdown
### Apa output dari `printf("%d", 5 + 5);`?
- [] 55
- [x] 10
- [] 5 + 5
- [] Error
> Penjelasan: Operasi `5 + 5` dihitung terlebih dahulu menjadi `10`.
```

### 2. Pilihan Ganda (MCQ) — format kaya (baru)

Blok Markdown apa pun boleh mendahului daftar opsi: paragraf, code fence, tabel, math (`$...$` / `$$...$$`), bahkan embed (Canva/YouTube/Figma). Seluruh blok tersebut dirender sebagai **lembar soal** di area materi; opsi muncul di **lembar jawaban** (tab kuis). Kode tidak boleh berisi baris yang diawali `- [` (akan terbaca sebagai opsi) — gunakan code fence.

```markdown
### Perhatikan program berikut:
```c
int x = 2;
printf("%d", x * 3);
```
Berapakah keluaran program di atas?
- [] 5
- [] 8
- [x] 6
- [] Error
> Pembahasan: `x * 3` menghasilkan `6`.
```

```markdown
### Berdasarkan tabel berikut, tipe data mana yang tepat untuk menyimpan `3.14`?
| Tipe   | Ukuran | Rentang        |
|--------|--------|----------------|
| int    | 4 byte | -2^31 s/d 2^31-1 |
| double | 8 byte | ~1e-308 s/d ~1e308 |
- [x] double
- [] int
```

```markdown
### Berapakah nilai dari $\int_0^1 2x \, dx$?
- [x] 1
- [] 2
- [] 0.5
```

### 3. Flashcard

Heading diikuti langsung jawaban (tanpa daftar opsi):

```markdown
### Apa fungsi dari `return 0;` di dalam fungsi `main()`?
Menandakan bahwa program telah selesai berjalan dengan sukses tanpa ada error.
```

Selama mengerjakan, murid hanya melihat sisi depan (heading). Sisi belakang ditampilkan di pembahasan setelah kuis selesai.

## Gambar soal

| Cara | Contoh | Hasil |
|------|--------|-------|
| Directive `image:` (baris apa pun di blok soal) | `image: https://.../c.png` atau `image: gambar.png` (relatif → `/assets/`) | Field `image` soal; baris directive dibuang dari prompt |
| Markdown image di body, sebelum opsi (format kaya) | `![C Logo](https://.../c.svg)` | Field `image` soal; markup dihapus dari prompt agar tidak ganda |
| Markdown image di dalam opsi | `- [x] ![C Logo](https://.../c.svg)` | Gambar dirender sebagai bagian teks opsi |

Gambar di heading (`### ... ![alt](url)`) juga diekstrak ke field `image` selama URL-nya http(s) atau `/assets/`.

## Penjelasan / pembahasan

Blockquote `>` di bagian akhir soal (setelah opsi) menjadi field `explanation` dan hanya ditampilkan di pembahasan setelah kuis selesai — murid tidak melihatnya saat mengerjakan.

## Perilaku (wajib dipahami)

- **ID stabil**: soal diberi id `q-0`, `q-1`, ...; opsi `q-0-o-0`, ... sesuai urutan penulisan di file. ID tidak pernah berubah karena urutan tampil diacak.
- **Randomisasi**: saat murid menekan "Mulai Kuis", urutan soal dan urutan opsi diacak **sekali**, lalu dibekukan sampai kuis selesai. Pindah soal / kembali tidak mengacak ulang.
- **Skor**: `benar/total-MCQ` (flashcard tidak masuk penyebut). Soal MCQ yang tidak dijawab saat keluar = salah. Ambang lulus 75%.
- **Submit**: tombol "Selesai Kuis" aktif hanya jika semua soal dijawab/ditandai. Keluar, pindah halaman, atau reload = submit final (penalti).
- **Satu kesempatan**: token `---QUIZ_TOKEN---` menandai kuis sekali jalan; hanya guru yang bisa reset.
- **Feedback**: benar/salah + pembahasan hanya muncul di ringkasan setelah kuis tersimpan. Tidak ada indikator benar/salah selama mengerjakan (jawaban boleh diganti).

## Contoh lengkap

Lihat `content/dasar/quiz_test.md` (atau `examples/content/dasar/quiz_test.md`).

## Integritas kuis (anti-cheat)

Kuis berjalan dengan kebijakan strict focus-loss: berpindah tab/kehilangan fokus
saat kuis aktif mengakhiri kuis secara otomatis dengan penalti dan mencatat
pelanggaran untuk laporan guru. Lihat
[12. Quiz Integrity](./12-quiz-integrity.md) untuk detail policy, event yang
terdeteksi, dan cara membaca badge pelanggaran di laporan guru.
