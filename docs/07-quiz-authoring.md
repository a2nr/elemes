---
title: Quiz Authoring
order: 7
category: quiz
---
# 07. Quiz Authoring (Format Soal Kuis)

Kuis ditulis sebagai Markdown di dalam blok key quiz. **Setiap jenis soal punya key sendiri** — supaya model penilaiannya eksplisit dan tidak ditebak dari isi konten:

| Key | Jenis soal | Model penilaian |
|-----|------------|-----------------|
| `---QUIZ_MCQ---` | Pilihan ganda biner | Benar/salah per soal (tepat satu `[x]`) |
| `---QUIZ_WEIGHTED---` | Pilihan ganda berbobot | Poin parsial sesuai bobot opsi `[N]` |
| `---FLASHCARD---` | Kartu hafalan | Tidak dinilai (netral terhadap skor) |
| `---QUIZ_FLASHCARD---` | *(Legacy)* campuran | Model lama: inspeksi konten per soal |

Semua key mengaktifkan tab kuis yang sama. Bisa dipakai lebih dari satu blok per key, dan beberapa blok boleh berselang-seling — seluruh soal tetap digabung jadi **satu sesi kuis** dengan urutan sesuai posisi di dokumen.

Setiap soal diawali `###` (heading level 3). Parser menolak soal yang tidak valid dengan pesan error yang jelas (nama key + nomor soal), dan preview editor guru menampilkan error itu sebelum konten disimpan.

## 1. `QUIZ_MCQ` — pilihan ganda biner

`- [x]` = jawaban benar, `- []` = salah. **Wajib tepat satu `[x]` per soal** — parser menolak soal tanpa jawaban benar atau dengan lebih dari satu. Bobot angka `[N]` **tidak diperbolehkan** di key ini (itu tugas `QUIZ_WEIGHTED`).

```
---QUIZ_MCQ---
### Apa output dari `printf("%d", 5 + 5);`?
- [] 55
- [x] 10
- [] 5 + 5
- [] Error
> Penjelasan: Operasi `5 + 5` dihitung terlebih dahulu menjadi `10`.
---END_QUIZ_MCQ---
```

### Format kaya (lembar soal + lembar jawaban)

Blok Markdown apa pun boleh mendahului daftar opsi: paragraf, code fence, tabel, math (`$...$` / `$$...$$`), bahkan embed (Canva/YouTube/Figma). Seluruh blok tersebut dirender sebagai **lembar soal** di area materi; opsi muncul di **lembar jawaban** (tab kuis). Kode tidak boleh berisi baris yang diawali `- [` (akan terbaca sebagai opsi) — gunakan code fence.

````markdown
---QUIZ_MCQ---
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
---END_QUIZ_MCQ---
````

### Soal diagnostik (`::diagnostic`)

Tulis `::diagnostic` pada baris sendiri di dalam blok soal (di key apa pun yang berupa pilihan ganda) untuk menandai soal **diagnostik**. Soal diagnostik tetap **masuk skor resmi**; kategorinya hanya memisahkan breakdown laporan guru (Eval/Diag) dan daftar topik yang belum dikuasai.

```
---QUIZ_MCQ---
### Soal diagnostik: apa output program ini?
::diagnostic
- [x] 10
- [] 55
---END_QUIZ_MCQ---
```

## 2. `QUIZ_WEIGHTED` — pilihan ganda berbobot

Opsi diberi bobot `- [N]` (N bilangan bulat ≥ 1); opsi salah ditulis `- [ ]` (tanpa angka). Aturan ketat (parser menolak pelanggarannya):

1. **Larang `[x]`** — penanda benar/salah digantikan bobot.
2. **Bobot ≥ 1** — `- [0]` ditolak (opsi kosong `[ ]` sudah mewakili 0 poin).
3. **Minimal satu `[ ]`** — setiap soal wajib punya opsi bernilai 0 sebagai jawaban salah.
4. **Bobot tertinggi unik** — opsi dengan bobot terbesar adalah kunci soal; bila dua opsi sama-sama tertinggi, parser menolak soal itu.

```
---QUIZ_WEIGHTED---
### Seberapa lengkah jawaban ini tentang scanf?
- [10] `scanf("%d", &x);` — membaca integer ke variabel x
- [7] `scanf("%d", x);` — tanpa alamat, tapi maksudnya benar
- [ ] `scanf` tidak bisa membaca integer
> Pembahasan: `scanf` butuh alamat variabel (`&x`).
---END_QUIZ_WEIGHTED---
```

**Penilaian:** siswa yang memilih opsi `[7]` mendapat 7 poin dari 10 (**poin parsial**); opsi `[ ]` bernilai 0. Poin maksimum soal = bobot tertinggi. `is_correct` hanya true untuk opsi bobot tertinggi.

## 3. `FLASHCARD` — kartu hafalan

Heading diikuti langsung jawaban (tanpa daftar opsi — opsi di key ini ditolak parser):

```
---FLASHCARD---
### Apa fungsi dari `return 0;` di dalam fungsi `main()`?
Menandakan bahwa program telah selesai berjalan dengan sukses tanpa ada error.
---END_FLASHCARD---
```

Selama mengerjakan, murid hanya melihat sisi depan (heading). Sisi belakang ditampilkan di pembahasan setelah kuis selesai. Flashcard **tidak memengaruhi skor** — murid menandai "mengerti / belum" per kartu, dan semua kartu wajib ditandai agar kuis bisa diselesaikan.

## Model skor resmi

Skor kuis = **rata-rata persentase per jenis quiz yang ada di kuis**, dibulatkan (`Math.round`):

```
persen_jenis  = poin_diperoleh / poin_maksimum × 100   (per jenis dinilai)
skor_akhir    = round( rata-rata persen_jenis )
```

- **Kuis hanya `QUIZ_MCQ`** (atau legacy) → format skor lama `X/Y` dipertahankan (kompatibel mundur, nilai = proporsi benar).
- **Ada `QUIZ_WEIGHTED`** → format skor `P/100` (persen).
- **Hanya `FLASHCARD`** → skor `completed`; menyelesaikan kuis = lulus.
- **Lulus** bila skor akhir ≥ **75**.

Contoh: kuis berisi 4 soal MCQ (benar 2 → 50%) dan 2 soal weighted (17/20 → 85%) → skor akhir = round((50+85)/2) = **68** → `68/100`, belum lulus.

Laporan guru menampilkan badge breakdown per jenis (`MCQ: 2/4`, `Bobot: 17/20`) di samping skor kuis; CSV ekspor progres punya kolom `<slug>_quiz_mcq` dan `<slug>_quiz_weighted`.

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

- **ID stabil**: soal diberi id `q-0`, `q-1`, ... mengikuti urutan blok di dokumen; opsi `q-0-o-0`, ... sesuai urutan penulisan di file. ID tidak pernah berubah karena urutan tampil diacak. Menyisipkan soal baru di tengah menggeser id soal sesudahnya — jawaban tersimpan pada attempt lama tidak lagi cocok (satu attempt = satu snapshot konten).
- **Randomisasi**: saat murid menekan "Mulai Kuis", urutan soal dan urutan opsi diacak **sekali**, lalu dibekukan sampai kuis selesai. Pindah soal / kembali tidak mengacak ulang.
- **Skor**: rata-rata persentase per jenis (lihat di atas). Soal MCQ/weighted yang tidak dijawab saat keluar = 0 poin. Ambang lulus 75.
- **Submit**: tombol "Selesai Kuis" aktif hanya jika semua soal dijawab/ditandai. Keluar, pindah halaman, atau reload = submit final (penalti).
- **Satu kesempatan**: satu sesi/attempt per kuis (semua jenis digabung); hanya guru yang bisa reset.
- **Feedback**: benar/salah + pembahasan hanya muncul di ringkasan setelah kuis tersimpan. Soal weighted menampilkan badge poin (`✓ 10`, `🟡 7/10`, `✗ 0`) di pembahasan; tidak ada indikator benar/salah selama mengerjakan (jawaban boleh diganti).

## Migrasi dari key legacy

Konten lama dengan `---QUIZ_FLASHCARD---` **tetap dibaca** tanpa perubahan perilaku (jenis soal ditebak dari konten: ada opsi → MCQ, tanpa opsi → flashcard). Untuk memakai model penilaian baru, konversikan dengan:

```bash
python scripts/convert_quiz_keys.py            # default: examples/content
python scripts/convert_quiz_keys.py --dry-run  # lihat rencana konversi saja
```

Script memecah blok legacy menjadi run `QUIZ_MCQ` / `FLASHCARD` per jenis sambil menjaga urutan soal (id tidak bergeser), lalu memverifikasi hasil parse sebelum vs sesudah konversi identik. Konversi idempoten — dijalankan kedua kali tidak mengubah apa pun.

## Contoh lengkap

Lihat `examples/content/dasar/quiz_test.md` (MCQ + weighted + flashcard bercampur) dan `examples/content/dasar/composite_test.md`.

## Integritas kuis (anti-cheat)

Kuis berjalan dengan kebijakan strict focus-loss: berpindah tab/kehilangan fokus
saat kuis aktif mengakhiri kuis secara otomatis dengan penalti dan mencatat
pelanggaran untuk laporan guru. Guru dapat **me-reset** (siswa mengulang dari
nol) atau memberi izin **resume** (siswa melanjutkan dari jawaban tersimpan)
saat ada kendala tak terduga. Lihat
[12. Quiz Integrity](./12-quiz-integrity.md) untuk detail policy, event yang
terdeteksi, cara membaca badge pelanggaran, dan alur resume di laporan guru.
