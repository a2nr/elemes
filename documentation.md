# Elemes LMS — Dokumentasi Teknis

**Project:** LMS-C (Learning Management System untuk Pemrograman C)
**Terakhir diupdate:** 25 Maret 2026

---

## Arsitektur

```
Internet (HTTPS :443)
    │
    ▼
Tailscale Funnel (elemes-ts)
    │
    ▼
SvelteKit Frontend (elemes-frontend :3000)
  ├── SSR pages (lesson content embedded in HTML)
  ├── CodeMirror 6 editor (lazy-loaded)
  ├── API proxy: /api/* → Flask
  └── PWA manifest
    │
    ▼  /api/*
Flask API Backend (elemes :5000)
  ├── Code compilation (gcc / python)
  ├── Token authentication (CSV)
  ├── Progress tracking
  └── Lesson content parsing (markdown)
```

### Container Setup

| Container | Image | IP (static) | Port | Fungsi |
|-----------|-------|-------------|------|--------|
| `elemes` | Python 3.11 + gcc | 10.89.100.10 | 5000 | Flask API |
| `elemes-frontend` | Node 20 | 10.89.100.11 | 3000 | SvelteKit SSR |
| `elemes-ts` | Tailscale | 10.89.100.12 | 443 | HTTPS Funnel |

Static IPs karena aardvark-dns (podman DNS) tidak resolve hostname antar container.

---

## Struktur Direktori

```
lms-c/
├── content/                     # 25 lesson markdown
├── assets/                      # Gambar untuk lesson
├── tokens_siswa.csv             # Data siswa & progress
├── config/sinau-c-tail.json     # Tailscale serve config
├── state/                       # Tailscale runtime state
├── .env                         # Environment variables
│
└── elemes/                      # Semua kode aplikasi
    ├── app.py                   # Flask create_app() factory
    ├── config.py                # Environment config
    ├── Dockerfile               # Flask container
    ├── gunicorn.conf.py         # Production WSGI
    ├── requirements.txt         # Python deps
    ├── podman-compose.yml       # 3 services
    ├── generate_tokens.py       # Utility: generate CSV tokens
    │
    ├── compiler/                # Code compilation
    │   ├── __init__.py          # CompilerFactory
    │   ├── base_compiler.py     # Abstract base
    │   ├── c_compiler.py        # gcc wrapper
    │   └── python_compiler.py   # python wrapper
    │
    ├── routes/                  # Flask Blueprints
    │   ├── auth.py              # /login, /logout, /validate-token
    │   ├── compile.py           # /compile
    │   ├── lessons.py           # /lessons, /lesson/<slug>.json
    │   └── progress.py          # /track-progress, /progress-report.json
    │
    ├── services/                # Business logic
    │   ├── token_service.py     # CSV token CRUD
    │   └── lesson_service.py    # Markdown parsing
    │
    └── frontend/                # SvelteKit PWA
        ├── package.json
        ├── svelte.config.js     # adapter-node + path aliases
        ├── vite.config.ts       # API proxy (dev only)
        ├── Dockerfile           # Multi-stage build
        └── src/
            ├── hooks.server.ts  # API proxy (production)
            ├── app.html
            ├── app.css
            ├── lib/
            │   ├── components/
            │   │   ├── CodeEditor.svelte   # CodeMirror 6 (lazy-loaded)
            │   │   ├── Navbar.svelte
            │   │   ├── LessonCard.svelte
            │   │   ├── OutputPanel.svelte
            │   │   ├── ProgressBadge.svelte
            │   │   └── Footer.svelte
            │   ├── stores/
            │   │   ├── auth.ts             # Svelte writable stores
            │   │   └── theme.ts            # Dark/light toggle
            │   ├── services/
            │   │   └── api.ts              # Flask API client
            │   └── types/
            │       ├── lesson.ts
            │       ├── auth.ts
            │       └── compiler.ts
            ├── routes/
            │   ├── +layout.svelte
            │   ├── +page.svelte            # Home (lesson grid)
            │   ├── +page.ts                # SSR data loader
            │   ├── lesson/[slug]/
            │   │   ├── +page.svelte        # Lesson viewer + editor
            │   │   └── +page.ts            # SSR data loader
            │   └── progress/
            │       └── +page.svelte        # Teacher dashboard
            └── static/
                └── manifest.json           # PWA manifest
```

---

## Keputusan Teknis

### Kenapa SvelteKit, bukan Flutter?
- CodeMirror 6 (code editor production-grade) — tidak ada equivalent di Flutter
- Bundle ~250KB vs Flutter Web 2-4MB
- SSR untuk konten markdown (instant first paint)
- PWA installable tanpa app store

### Kenapa Svelte writable stores, bukan runes ($state)?
Svelte 5 runes (`$state`, `$derived`) hanya bekerja di dalam file `.svelte`. File `.ts` biasa tidak diproses oleh Svelte compiler, sehingga `$state()` menjadi `ReferenceError` saat runtime di server. Solusi: gunakan `writable()` dari `svelte/store` di file `.ts`, dan `$storeName` auto-subscription di `.svelte`.

### Kenapa static IP, bukan DNS?
Podman's aardvark-dns tidak berfungsi di environment ini (getaddrinfo EAI_AGAIN). Workaround: assign static IP per container via IPAM config di podman-compose.yml.

### Kenapa hooks.server.ts untuk API proxy?
Vite `server.proxy` hanya bekerja di dev mode (`vite dev`). Di production (adapter-node), SvelteKit tidak punya proxy. `hooks.server.ts` mem-forward `/api/*` ke Flask backend saat runtime.

### Kenapa lazy-load CodeMirror?
CodeMirror 6 bundle ~475KB. Dengan dynamic `import()`, lesson content (text) muncul langsung via SSR, editor menyusul setelah JS bundle selesai download. Perceived load time jauh lebih cepat.

---

## Cara Menjalankan

```bash
cd elemes/
podman-compose --env-file ../.env up --build -d
```

- **Frontend:** http://localhost:3000
- **Tailscale:** https://{ELEMES_HOST}.{tailnet}.ts.net

### Rebuild setelah perubahan kode

```bash
podman-compose --env-file ../.env down
podman-compose --env-file ../.env up --build -d
```

### Logs

```bash
podman logs elemes           # Flask API
podman logs elemes-frontend  # SvelteKit
podman logs elemes-ts        # Tailscale
```

---

## API Endpoints

Semua endpoint Flask diakses via SvelteKit proxy (`/api/*` → Flask `:5000`):

| Method | Path | Fungsi |
|--------|------|--------|
| POST | `/api/login` | Login dengan token |
| POST | `/api/logout` | Logout |
| POST | `/api/validate-token` | Validasi token |
| GET | `/api/lessons` | Daftar lesson + home content |
| GET | `/api/lesson/<slug>.json` | Data lesson lengkap |
| GET | `/api/get-key-text/<slug>` | Key text untuk lesson |
| POST | `/api/compile` | Compile & run kode |
| POST | `/api/track-progress` | Track progress siswa |
| GET | `/api/progress-report.json` | Data progress semua siswa |
| GET | `/api/progress-report/export-csv` | Export CSV |

---

## Anti Copy-Paste System

Sistem berlapis untuk mencegah siswa meng-copy konten pelajaran dan mem-paste kode dari sumber eksternal ke editor.

### Selection & Copy Prevention (Halaman Lesson)

**File:** `frontend/src/routes/lesson/[slug]/+page.svelte`

Mencegah siswa men-select dan meng-copy teks dari konten pelajaran (termasuk code blocks).

| Layer | Mekanisme | Target |
|-------|-----------|--------|
| CSS | `user-select: none`, `-webkit-touch-callout: none` | `.lesson-content`, `.lesson-info` |
| Events | `onselectstart`, `oncopy`, `oncut`, `oncontextmenu` → `preventDefault()` | `.lesson-content`, `.lesson-info` |
| JS | `selectionchange` + `mouseup` + `touchend` → `getSelection().removeAllRanges()` | Fallback aktif — clear selection jika terjadi di area konten (scoped, tidak mengganggu editor) |

### Paste Prevention (CodeEditor)

**File:** `frontend/src/lib/components/CodeEditor.svelte`

Mencegah siswa mem-paste kode dari sumber eksternal ke code editor. Diaktifkan via prop `noPaste={true}`.

| Layer | Mekanisme | Menangani |
|-------|-----------|-----------|
| 1 | `EditorView.domEventHandlers` — `paste`, `drop`, `beforeinput` → `preventDefault()` | Desktop paste, iOS paste |
| A | `EditorState.transactionFilter` — block `input.paste` + heuristik ukuran (>2 baris atau >20 chars untuk 2 baris) | Standard paste + **GBoard clipboard panel** (paste via IME yang menyamar sebagai `input.type.compose`) |
| C | `EditorView.clipboardInputFilter` — replace clipboard text → `''` (runtime check) | Standard paste (jika API tersedia) |
| D | `EditorView.inputHandler` — block multi-line insertion >20 chars | GBoard clipboard via DOM mutations |
| 2 | DOM capture-phase listeners — `paste`, `copy`, `cut`, `contextmenu`, `drop` → `preventDefault()` | Backup DOM-level |
| B | `input` event listener — `CM.undo()` jika `insertFromPaste` | Fallback post-hoc revert |

**Limitasi:** GBoard clipboard panel menyuntikkan teks lewat IME composition system (bukan clipboard API), sehingga tidak bisa dibedakan 100% dari ketikan biasa. Heuristik ukuran teks digunakan untuk mendeteksi dan memblokir mayoritas kasus paste, namun paste 1 baris pendek (<20 chars) masih bisa lolos.

---

## Status Implementasi

- [x] **Phase 0:** Backend decomposition (monolith → Blueprints + services)
- [x] **Phase 1:** SvelteKit scaffolding (adapter-node, TypeScript, path aliases)
- [x] **Phase 2:** Core components (CodeEditor, Navbar, auth/theme stores, API client)
- [x] **Phase 3:** Pages (Home, Lesson, Progress) + SSR data loading
- [x] **Phase 5:** Containerization (3-container setup, static IPs, API proxy)
- [ ] **Phase 4:** PWA (service worker, offline caching, icons)
- [ ] **Phase 6:** Polish (Tailscale config update, testing)
