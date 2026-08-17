---
title: Quiz Integrity — Anti-Cheat
order: 12
category: quiz
---
# 12. Quiz Integrity — Strict Focus-Loss Anti-Cheat

Kuis diakhiri secara otomatis saat browser mendeteksi siswa meninggalkan halaman
kuis. Kebijakan ini **strict**: kehilangan fokus pertama ketika kuis aktif
langsung mengakhiri kuis dengan penalti (soal belum dijawab dianggap salah),
menyimpan alasan pelanggaran di PostgreSQL, dan tidak ada kesempatan melanjutkan
setelah kembali fokus.

Baca juga: [07. Quiz Authoring](./07-quiz-authoring.md) untuk format soal.

## Policy

| Kejadian | Dampak |
|---|---|
| Selesai kuis normal (semua soal dijawab) | 1 attempt `submitted`, tanpa pelanggaran |
| Tombol "Keluar Kuis" | 1 attempt `terminated/user_exit`, skor penalti |
| Navigasi SPA (pindah halaman) | 1 attempt `terminated/spa_navigation`, skor penalti |
| Switch tab / minimize / switch app (visibility `hidden`) | 1 attempt `terminated/focus_lost` — **pelanggaran** |
| Window desktop kehilangan fokus (`blur`) | 1 attempt `terminated/focus_lost` — **pelanggaran** |
| Reload / tutup tab | 1 attempt `terminated/page_unload` via `sendBeacon` |
| Kembali fokus setelah terminated | Tidak ada efek — kuis tidak kembali aktif |

Event yang memicu termination hanya dipasang **saat kuis aktif** dan dibersihkan
saat kuis selesai/unmount. Event ganda (mis. `visibilitychange` lalu `blur`,
atau `blur` lalu `beforeunload`) hanya memfinalisasi **satu** attempt karena
seluruh exit path memakai `attempt_id` yang sama dan finalisasi idempotent.

Kuis yang berakhir karena `focus_lost` **tidak menampilkan pembahasan** soal
pada ringkasan (skor tetap tampil; lihat `shouldShowQuizReview` di
`frontend/src/lib/services/quiz-integrity.ts`). Alasan lain
(`user_exit`, `spa_navigation`, `page_unload`, `completed`) tetap
menampilkan pembahasan.

## Arsitektur

- `LessonManager` (`frontend/src/routes/lesson/[slug]/lesson.svelte.ts`) adalah
  single source of truth: saat `startQuiz()`, dibuat `attempt_id`
  (`crypto.randomUUID()`); seluruh exit path memanggil `terminateQuiz(reason)`
  yang idempotent dan menyusun payload attempt secara synchronous.
- Event `visibilitychange` + `blur` dipasang di `+page.svelte` lewat satu
  `$effect` yang hanya aktif ketika `isQuizMode`.
- Exit path yang bisa membuat browser suspend (`focus_lost`, `page_unload`)
  memakai `navigator.sendBeacon` terlebih dahulu — tidak ada `await` dari event
  lifecycle. Exit biasa (`user_exit`, `spa_navigation`, `completed`) memakai
  `fetch` agar response dapat ditangani; fallback legacy `track-progress` hanya
  dipakai bila endpoint attempt tidak dapat dijangkau (tanpa attempt kedua).
- Backend `POST /api/quiz-attempts/submit` (lihat `routes/quiz_attempts.py`)
  memvalidasi payload, menyimpan audit attempt di tabel `quiz_attempts`, dan
  meng-update `student_progress` **dalam satu transaksi**. Retry dengan
  `attempt_id` sama → respons idempotent tanpa menggandakan row; record pertama
  tidak pernah ditimpa. One-attempt policy dijaga unique `(user_id, lesson_id)`.

### Data contract (payload klien)

```json
{
  "attempt_id": "uuid-canonical",
  "token": "student-token",
  "lesson_name": "quiz_test",
  "status": "terminated",
  "termination_reason": "focus_lost",
  "score": "2/4",
  "occurred_at": "2026-08-09T14:04:44.000Z",
  "started_at": "2026-08-09T14:03:00.000Z",
  "visibility_event_count": 1
}
```

Aturan status: `completed` → `submitted` + `termination_reason: null`;
`focus_lost` wajib `terminated`. Nilai reason diizinkan: `focus_lost`,
`spa_navigation`, `page_unload`, `user_exit`, `completed` (reserved).

## Apa yang bisa dan tidak bisa dideteksi browser

| Sinyal | Status |
|---|---|
| Switch tab (desktop) | Terdeteksi (`visibilitychange` → `hidden`) |
| Alt-Tab / minimize (desktop) | Terdeteksi (`blur` / `visibilitychange`) |
| Switch app (Chrome Android) | Terdeteksi bila browser menerbitkan `visibilitychange` `hidden` |
| iOS Safari switch app / tab | Tidak selalu terdeteksi — kebijakan tampil tapi tidak menjanjikan deteksi penuh |
| Blur karena browser chrome / permission prompt / dialog OS | **False positive** — kebijakan strict menerima trade-off ini; uji di device target |
| Interaksi dengan iframe embed di dalam soal kuis (mis. Canva/YouTube/simulator) | **False positive** — fokus pindah ke iframe memicu `blur` window → termination; hindari embed interaktif di soal bila hal ini tidak diterima |
| Siswa mematikan JavaScript / memakai browser automation | Tidak terdeteksi — ini lapisan deterrence & audit, bukan proctoring kriptografis |

Browser tidak menyediakan API yang membuktikan aplikasi mana yang dibuka siswa.
`user_agent` disimpan hanya untuk diagnosis device/browser — bukan dasar hukuman
tambahan, dan tidak ada isi layar atau daftar aplikasi yang direkam.

## Laporan guru

Laporan progress (`/progress-report.json`) menambahkan field terpisah per lesson
tanpa mengubah kontrak status lama:

```json
{
  "quiz_test": "2/4",
  "quiz_test_attempt_status": "terminated",
  "quiz_test_termination_reason": "focus_lost",
  "quiz_test_has_violation": true,
  "quiz_test_attempt_finished_at": "2026-08-09T14:04:44+00:00"
}
```

- Badge **⚠ Pelanggaran** muncul di cell kuis; tooltip memuat reason dan waktu
  termination (bukan token).
- Tombol reset guru menghapus progress **dan** attempt (one-attempt) sehingga
  siswa dapat mengulang setelah reset.
- Export CSV laporan ikut menyertakan kolom audit di atas.

## Fallback & kegagalan

- `sendBeacon` gagal → best-effort `fetch` keepalive hanya saat document masih
  visible; tidak ada blokir UI. Kegagalan di luar itu terdokumentasi sebagai
  kehilangan audit (progress tetap aman karena endpoint atomic).
- Endpoint attempt tidak terjangkau (server down) saat exit biasa → fallback
  `track-progress` agar skor tetap tersimpan; attempt tidak dibuat dua kali.

## Privacy

- Token mentah tidak pernah di-log, disimpan, atau dipantulkan ke response —
  backend hanya menyimpan HMAC digest dan id anonim.
- Metadata attempt tidak berisi jawaban soal maupun isi layar.

## Deployment

Migration baru: `migrations/versions/0002_quiz_attempts.py` (tabel
`quiz_attempts` + constraint reason/status + index). Existing `student_progress`
tetap kompatibel; siswa yang sudah menyelesaikan kuis sebelum fitur ini tidak
memiliki row attempt, dan gate one-attempt tetap memakai `lesson_progress_status`
sehingga mereka tidak bisa mengulang tanpa reset guru.

## Hardening lanjutan (fase terpisah)

Untuk ujian high-stakes, jangan percaya skor client: simpan question
IDs/order & jawaban di server, atau gunakan attempt token/session yang
dikeluarkan server. Berbeda scope dari event focus-loss dan sengaja tidak
termasuk dalam implementasi ini.
