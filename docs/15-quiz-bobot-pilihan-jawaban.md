---
title: Quiz Bobot Opsi Jawaban (Weighted MCQ)
order: 15
category: quiz
---
# 15. Quiz Pilihan Ganda dengan Bobot Nilai per Opsi (TERIMPLEMENTASI)

Fitur: soal pilihan ganda (MCQ) di mana **setiap pilihan jawaban memiliki bobot
nilai yang berbeda**. Contoh: opsi paling tepat bernilai 10, opsi "kurang tepat"
bernilai 7, opsi salah 0 — partial credit, bukan hanya benar/salah.

> **Catatan desain:** versi awal rencana fitur ini memakai sintaks
> `[x:10]` di dalam key legacy. Implementasi final memakai **taksonomi key
> quiz** — jenis soal ditentukan key blok, bukan anotasi per opsi. Rencana
> awal tidak lagi akurat; dokumen ini menjelaskan desain yang benar-benar
> diimplementasikan. Panduan penulis konten: [07. Quiz Authoring](./07-quiz-authoring.md).

## Desain final: key per jenis + bobot `[N]`

Key `---QUIZ_WEIGHTED---` (end: `---END_QUIZ_WEIGHTED---`) menandai soal
berbobot. Bobot ditulis langsung di tanda kurung:

```markdown
---QUIZ_WEIGHTED---
### Berapakah hasil dari 2 * 3?
- [10] 6
- [7] 5
- [ ] 7
> Pembahasan: 2 * 3 = 6.
---END_QUIZ_WEIGHTED---
```

Aturan validasi parser (pelanggaran → error jelas dengan nomor soal):

1. **Larang `[x]`** di `QUIZ_WEIGHTED` — benar/salah digantikan bobot.
2. **Bobot integer ≥ 1** — `- [0]` ditolak; opsi salah ditulis `- [ ]` (tanpa angka, bernilai 0).
3. **Minimal satu `[ ]`** per soal sebagai jawaban salah.
4. **Bobot tertinggi harus unik** — opsi bobot terbesar = kunci soal (`is_correct`).

Sebaliknya, `QUIZ_MCQ` **melarang** bobot angka supaya penulisan keliru
terdeteksi dini (pesan error mengarahkan ke key yang tepat).

## Keputusan desain penting

| Keputusan | Alasan |
|---|---|
| Key baru `---QUIZ_MCQ---`, `---QUIZ_WEIGHTED---`, `---FLASHCARD---`; legacy `---QUIZ_FLASHCARD---` / `---INITIAL_QUIZ---` tetap dibaca | Nol regresi untuk konten lama; authoring baru eksplisit per jenis |
| `::diagnostic` tetap kategori **di dalam** `QUIZ_MCQ` dan tetap masuk skor resmi | Sumbu kategori (eval/diag) ortogonal terhadap sumbu jenis |
| Regex opsi legacy TIDAK berubah (`[ xX]?` saja) | Baris `- [10]` di konten legacy tetap BUKAN opsi — zero regression |
| Regex key baru mengenali `[ xX]?[0-9]*` | Satu regex untuk MCQ + weighted; validasi per kind |
| `weight` & `quiz_type` selalu di-emit (legacy: benar=1/salah=0) | Konsumen tidak perlu menebak model evaluasi |
| `is_correct` weighted = opsi bobot tertinggi | Kunci soal tetap tunggal untuk review & integritas |
| Skor akhir = `Math.round(rata-rata persentase per jenis yang ada)` | Jenis dinilai setara; flashcard netral; pembulatan sekali di akhir |
| Skor resmi `"X/Y"` bila hanya MCQ/legacy; `"P/100"` bila ada weighted; `"completed"` bila hanya flashcard | Kompatibel mundur dengan parsing `attempt_score` yang ada |
| Lulus = skor akhir ≥ 75 (angka yang tampil = angka yang diputuskan) | Ambang lulus tidak ambigu antar format skor |
| Satu sesi/attempt untuk semua jenis, soal flat urut dokumen | Taksonomi key tidak memecah sesi kuis |
| Ekstraksi blok mendukung **beberapa blok per key**, urut dokumen, id `q-N` deterministik | Paritas backend↔frontend; id stabil untuk jawaban tersimpan |
| Payload attempt baru: `quiz_type`, `earned_points`, `question_max_points` (opsional → payload klien lama tetap diterima) | Laporan & resume tanpa mem-break klien lama |
| Poin di-recompute dari konten saat resume/review | Guard bila konten soal berubah antara attempt dan resume |

## Implementasi per lapisan

| Lapisan | File | Perubahan |
|---|---|---|
| Parser backend | `services/lesson_service.py` | `_WEIGHTED_OPTION_LINE_RE`, `_iter_option_lines(kind)`, `_validate_quiz_options(kind)`, `_parse_flashcards(text, kind, id_offset)`, `_extract_quiz_sections` (multi-blok urut dokumen), `QUIZ_TAB_MARKERS` + dedupe tab |
| Parser frontend | `frontend/src/lib/services/markdown/parseFlashcards.ts`, `index.ts`, `detectActiveTabs.ts`, `extractSections.ts` | Mirror byte-perilaku backend; ekstraksi multi-key urut dokumen |
| Tipe | `frontend/src/lib/types/quiz.ts` | `weight`, `quiz_type`, `earnedPoints`, `questionMaxPoints` |
| Sesi & skor | `frontend/src/lib/services/quiz-session.ts` | `questionMaxPoints`, `typeScores` per jenis, `percent`, `hasWeighted`, aturan `statusString`, recompute poin saat restore |
| Submit | `frontend/src/lib/services/api.ts`, `lesson.svelte.ts`, `routes/lesson_progress.py` | Payload + validasi `quiz_type`/poin (opsional, earned ≤ max) |
| UI siswa | `QuizTab.svelte` | Skor via `statusString`, alert lulus berbasis `percent`, badge `✓ 10` / `🟡 7/10` / `✗ 0`, CSS `partial` |
| Preview guru | `QuizPreviewReadonly.svelte` | Badge bobot opsi + label "Berbobot (total N)" |
| Laporan guru | `postgres_backend.py`, `teacher/progress/+page.svelte`, `routes/progress.py` | Kolom `<slug>_quiz_mcq`, `<slug>_quiz_weighted`; badge + tooltip; CSV 2 kolom baru per lesson |
| Skor CSV | `lesson_service.py::get_lesson_quiz_total` | 100 bila ada soal weighted → format skor `"P/100"` konsisten round-trip |
| Migrasi | `scripts/convert_quiz_keys.py` | Konversi legacy → key baru per run jenis; idempoten; verifikasi parse identik |

## Pengujian

- Backend: `services/tests/test_lesson_service_quiz.py` (validasi ketat per key, urutan dokumen, multi-blok, zero regression legacy, field selalu di-emit, `get_lesson_quiz_total`).
- Frontend: `markdown.test.ts` (validasi + pesan error), `quiz-session.test.ts` (model skor rata-rata), `parity.test.ts` (fixture backend↔frontend).
- Paritas fixture diregenerasi via `scripts/dump_markdown_fixtures.py`.
