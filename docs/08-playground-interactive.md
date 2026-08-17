---
title: Playground Interaktif
order: 8
category: playground
---
# 08. Playground Interaktif

Route `/playground` menyediakan lingkungan coding interaktif untuk mencoba kode langsung di browser.

## Fitur Utama

- **Multi-tab** — tab Velxio (Arduino simulator), Flowchart, Circuit, dan Code
- **Run Session PTY** — klik "Run" → sesi worker (POST `/compile/sessions`) → prompt muncul → input dikirim ke sesi (PTY write_input + `\n`)
- **stdinQueue** — enqueue/consume/clear atomik untuk Python `input()` dan C `scanf()`
- **FileTree collapsible** — tree file per bahasa (C/Python), `.h` valid di C
- **Auto-save** — kode otomatis disimpan saat edit

## Alur Interaktif

```
1. Buka /playground
2. Pilih tab (Velxio / Flowchart / Circuit / Code)
3. Tulis kode di editor
4. Klik "Run" → sesi worker dimulai
5. Prompt input muncul (untuk Python input() / C scanf())
6. Kirim input → sesi PTY write_input
7. Output muncul di Console
8. FileTree collapsible untuk navigasi file
```

## Endpoint

| Endpoint | Fungsi |
|----------|--------|
| `POST /compile/sessions` | Buat sesi worker baru |
| `POST /compile/sessions/{id}/prompt` | Kirim prompt ke sesi |
| `POST /compile/sessions/{id}/input` | Kirim input ke sesi PTY |
| `GET /compile/sessions/{id}/status` | Cek status run |
| `GET /compile/sessions/{id}/output` | Baca output (cursor-based) |

## Store State

| Key | Fungsi |
|-----|--------|
| `runStatus` | Status sesi (idle/running/done/error) |
| `runSessionId` | ID sesi worker |
| `outputCursor` | Cursor untuk baca output incrementally |

## FileTree

- Collapsible tree untuk navigasi file
- Filter per bahasa: C dan Python dipisah
- `.h` file valid di C
- Mendukung file `.c`, `.h`, `.py`

## Verifikasi

- `pytest services/tests -q` — test sesi interaktif + parser konten rekursif + e2e smoke check
- `npm run build` — sukses tanpa error