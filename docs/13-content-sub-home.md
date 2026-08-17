---
title: Sub Bab (`sub-home.md`)
order: 13
category: content
---
# Sub Bab (`sub-home.md`) — Mengelompokkan Materi dalam Folder

**Tanggal:** 2026-08-13
**Status:** Aktif
**Lokasi kode:** Backend `services/lesson_service.py` + `routes/lessons.py`

---

## 1. Latar Belakang

Konten LMS biasa ditulis sebagai file `.md` langsung di `content/` dan didaftarkan
satu per satu di `content/home.md`. Ketika materi bertambah banyak, daftar global
menjadi panjang dan susah dirawat.

Fitur **sub-home** memungkinkan penulis menaruh sekelompok materi di dalam folder
satu level di `content/` (misal `content/bab1/`), lengkap dengan halaman bab
sendiri (`/bab/<folder>`) dan daftar materi yang akurat untuk folder itu.

## 2. Cara Kerja

### Struktur Folder

```
content/
├── home.md              # Halaman utama + daftar global (fallback)
├── hello_world.md       # Materi di root (tanpa sub bab)
└── bab1/                # Satu folder = satu sub bab (level satu)
    ├── sub-home.md      # "Halaman bab" — judul, intro, daftar materi
    ├── materi_a.md
    ├── materi_b.md
    └── materi_c.md
```

### Format `sub-home.md`

```markdown
# Judul Bab

Intro / deskripsi bab (opsional).

----Available_Lessons----
1. [Materi A](lesson/materi_a.md)
2. [Materi B](lesson/materi_b.md)
3. [Materi C](lesson/materi_c.md)
```

Aturan:

1. **Baris pertama `# Judul`** menjadi judul bab (ditampilkan di halaman `/bab/<folder>`).
2. **Teks sebelum `----Available_Lessons----`** menjadi intro bab (dirender markdown).
3. **Bagian setelah `----Available_Lessons----`** adalah daftar materi folder —
   format sama dengan `home.md` (`[Judul](path.md)`, boleh dengan awalan `lesson/`).
4. **`sub-home.md` tidak dihitung sebagai materi** — di-skip oleh `find_lesson_file()`
   dan `_parse_lesson_links()`, jadi tidak muncul di daftar lesson global maupun
   sinkronisasi lesson registry.

### Fallback

- Folder **tanpa** `sub-home.md` tidak memiliki halaman bab — materinya tetap
  diambil dari daftar global `home.md` (perilaku lama, tidak berubah).
- Lesson di dalam folder yang **memiliki** `sub-home.md` mendapat `ordered_lessons`
  (sidebar) dan navigasi prev/next **scoped ke folder itu**. Bila lesson belum
  dicantumkan di `sub-home.md`, fallback ke daftar global `home.md`.

## 3. API

### `GET /bab/<folder>` (via proxy frontend: `/api/bab/<folder>`)

Mengembalikan JSON isi `sub-home.md`:

```json
{
  "title": "Judul Bab",
  "intro_html": "<p>Intro bab...</p>",
  "lessons": [
    { "filename": "materi_a.md", "title": "Materi A", "description": "...", "path": "...", "prerequisite_titles": [] },
    { "filename": "materi_b.md", "title": "Materi B", "description": "...", "path": "...", "prerequisite_titles": [] }
  ],
  "folder": "bab1",
  "url": "/bab/bab1"
}
```

Respons `404` bila folder tidak ada atau tidak memiliki `sub-home.md`.

### `GET /lesson/<slug>.json`

Bila lesson berada di folder yang memiliki `sub-home.md`, field `ordered_lessons`
diisi daftar materi dari `sub-home.md` folder itu (bukan dari `home.md` global),
dan field `sub_home` berisi metadata folder:

```json
{
  "ordered_lessons": [ { "filename": "materi_a.md", "title": "Materi A" }, "..."],
  "sub_home": { "folder": "bab1", "url": "/bab/bab1", "title": "Judul Bab" }
}
```

Bila tidak ada `sub-home.md`, `ordered_lessons` memakai daftar global `home.md`
dan `sub_home` bernilai `null`.

## 4. Cache

Parsing `sub-home.md` di-cache berbasis **mtime**: setiap kali file diubah,
hasil parsing otomatis segar tanpa restart aplikasi (tidak memakai `lru_cache`
yang bisa mengembalikan data basi). Perubahan pada `sub-home.md` juga
meng-invalidate cache `find_lesson_file()` agar materi yang baru ditambahkan
langsung terdeteksi.

## 5. Contoh Siap Pakai

Contoh lengkap ada di `examples/content/`:

- `examples/content/dasar/sub-home.md`
- `examples/content/arduino/sub-home.md`

## 6. FAQ

**Q: Apakah sub bab bisa bersarang (folder di dalam folder)?**
Tidak. Fitur ini dirancang untuk folder **satu level** di dalam `content/`.
Sub bab bertingkat di luar lingkup.

**Q: Apakah materi di dalam folder harus didaftarkan juga di `home.md`?**
Tidak wajib. Materi folder cukup didaftarkan di `sub-home.md` folder tersebut.
Lesson yang tidak ada di `home.md` tidak akan disinkronkan ke lesson registry
(progress per-lesson di halaman guru mengikuti daftar `home.md` global).
