# Proposal Refactoring: LMS Belajar Pemrograman C

**Tanggal:** 24 Maret 2026
**Project:** LMS-C (Learning Management System untuk Pemrograman C)
**Workspace:** `elemes/`

---

## 1. Ringkasan Eksekutif

Proposal ini mengusulkan refactoring LMS-C dari arsitektur **Flask monolith + Jinja2 templates** menjadi arsitektur **Flask API + SvelteKit PWA**. Tujuannya adalah memberikan pengalaman belajar yang optimal di **desktop dan mobile** dengan code editor yang proper, performa cepat, dan kemampuan instalasi sebagai aplikasi (PWA).

---

## 2. Kondisi Saat Ini

### Arsitektur
- **Backend:** Flask monolith (`app.py`, 982 baris) — semua logic dalam satu file
- **Frontend:** Jinja2 templates + vanilla JavaScript + Bootstrap 5
- **Code Editor:** Plain textarea dengan line numbers manual (bukan code editor sesungguhnya)
- **Compiler:** Factory pattern — CCompiler (gcc) dan PythonCompiler
- **Auth:** Token-based via CSV file (`tokens_siswa.csv`)
- **Deploy:** Podman container + Tailscale sidecar untuk HTTPS
- **Flutter app:** 0% — hanya folder kosong, tidak ada kode sama sekali

### Masalah Utama
1. **Monolith 982 baris** — sulit di-maintain dan di-test
2. **Bukan code editor** — textarea biasa, tidak ada syntax highlighting saat mengetik, bracket matching, atau auto-indent
3. **Tidak mobile-friendly** — code editor tidak bisa dipakai di mobile
4. **Tidak bisa offline** — tidak ada caching mekanisme
5. **Vanilla JS** — duplikasi kode di setiap template (login logic di-copy paste)
6. **Tidak installable** — harus buka browser setiap kali

---

## 3. Evaluasi Framework

### 3.1 Flutter Web + Mobile

| Aspek | Evaluasi |
|-------|----------|
| **Rendering** | CanvasKit — render ke HTML canvas, BUKAN native DOM |
| **Code Editor** | Tidak ada widget setara CodeMirror/Monaco. `code_text_field` sangat terbatas |
| **Bundle Size** | 2-4 MB initial download (CanvasKit engine) |
| **Mobile** | Excellent untuk native app, tapi web version bermasalah |
| **Accessibility** | Buruk — canvas rendering, tidak bisa "Find in Page", screen reader tidak jalan |
| **SEO** | Tidak ada — semua di-render di canvas |
| **Markdown** | Ecosystem terbatas untuk rendering markdown |

**Verdict:** ❌ Tidak cocok untuk LMS yang content-heavy dengan code editor sebagai fitur utama.

**Alasan utama penolakan:** Flutter Web me-render SELURUH UI ke HTML `<canvas>`. Ini berarti:
- Siswa tidak bisa copy-paste text dari lesson content secara natural
- Browser "Find in Page" (Ctrl+F) tidak berfungsi
- Code editor di Flutter tidak bisa match fitur CodeMirror 6 (syntax highlighting, bracket matching, multiple cursors, mobile keyboard support)
- Bundle 2-4 MB sangat berat untuk siswa dengan koneksi mobile

### 3.2 Next.js (React) PWA

| Aspek | Evaluasi |
|-------|----------|
| **Rendering** | Native DOM + SSR/SSG |
| **Code Editor** | Monaco Editor (VS Code engine) — sangat powerful tapi 5MB+ |
| **Bundle Size** | 200-400 KB base, 5MB+ dengan Monaco |
| **Mobile** | Baik, tapi Monaco Editor tidak optimal di mobile |
| **Ecosystem** | Sangat besar, banyak library |
| **Complexity** | Lebih kompleks dari Svelte (virtual DOM, hooks, etc.) |

**Verdict:** ⚠️ Bisa dipakai, tapi overkill dan Monaco terlalu berat.

### 3.3 SvelteKit PWA (REKOMENDASI)

| Aspek | Evaluasi |
|-------|----------|
| **Rendering** | Native DOM + SSR, compile-time (no virtual DOM) |
| **Code Editor** | CodeMirror 6 — production-grade, mobile-friendly, 150KB |
| **Bundle Size** | 50-100 KB base + 150KB CodeMirror = ~250KB total |
| **Mobile** | Excellent — native HTML/CSS responsive, CodeMirror 6 support touch |
| **PWA** | Built-in via `@vite-pwa/sveltekit` |
| **SSR** | Built-in — fast first paint untuk konten markdown |
| **Learning Curve** | Minimal — Svelte lebih sederhana dari React |
| **TypeScript** | Native support |

**Verdict:** ✅ Pilihan terbaik untuk project ini.

### 3.4 Flask + HTMX/Alpine.js

| Aspek | Evaluasi |
|-------|----------|
| **Perubahan** | Minimal dari arsitektur sekarang |
| **Code Editor** | Bisa pakai CodeMirror, tapi integrasi manual |
| **Mobile** | Terbatas — tetap server-rendered, tidak ada PWA |
| **Offline** | Tidak ada |

**Verdict:** ⚠️ Perbaikan inkremental, bukan refactor sebenarnya.

### Tabel Perbandingan

| Kriteria | Flutter Web | Next.js | **SvelteKit** | Flask+HTMX |
|----------|:-----------:|:-------:|:-------------:|:----------:|
| Code editor quality | 2/10 | 9/10 | **9/10** | 5/10 |
| Bundle size | 2/10 | 5/10 | **9/10** | 10/10 |
| Mobile experience | 4/10 | 7/10 | **9/10** | 4/10 |
| PWA support | 3/10 | 7/10 | **9/10** | 2/10 |
| SSR / first paint | 2/10 | 9/10 | **9/10** | 8/10 |
| Complexity | 6/10 | 5/10 | **8/10** | 9/10 |
| Markdown rendering | 4/10 | 8/10 | **9/10** | 8/10 |
| **Total** | **23/70** | **50/70** | **62/70** | **46/70** |

---

## 4. Arsitektur yang Diusulkan

### 4.1 Overview

```
                    ┌─────────────────────────────┐
                    │       Internet (HTTPS)       │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │    Tailscale Funnel (:443)   │
                    │    (elemes-ts container)     │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │   SvelteKit Frontend (:3000) │
                    │   - SSR pages                │
                    │   - CodeMirror 6 editor      │
                    │   - PWA + Service Worker     │
                    │   - Responsive UI            │
                    └──────────────┬──────────────┘
                                   │ /api/*
                    ┌──────────────▼──────────────┐
                    │    Flask API Backend (:5000)  │
                    │   - Code compilation (gcc)    │
                    │   - Token authentication      │
                    │   - Progress tracking (CSV)   │
                    │   - Lesson content parsing    │
                    └─────────────────────────────┘
```

### 4.2 Tiga Container

| Container | Base Image | Port | Fungsi |
|-----------|-----------|------|--------|
| `elemes-frontend` | Node 20 slim | 3000 | SvelteKit SSR, static assets, PWA |
| `elemes-api` | Python 3.11 slim + gcc | 5000 | Flask JSON API, compilation, auth |
| `elemes-ts` | Tailscale | 443 | HTTPS termination, Funnel |

### 4.3 Alur Data

```
Siswa buka browser
  → GET /lesson/hello_world
  → SvelteKit SSR: fetch /api/lesson/hello_world dari Flask
  → Flask: parse markdown, return JSON {lesson_html, initial_code, ...}
  → SvelteKit: render HTML + hydrate CodeMirror editor
  → Siswa tulis kode C di CodeMirror
  → Klik "Run"
  → POST /api/compile {code: "..."}
  → Flask: write temp file → gcc compile → run → return output
  → SvelteKit: tampilkan output di OutputPanel
  → Jika benar → POST /api/track-progress
  → Flask: update CSV file
```

---

## 5. Struktur Direktori

```
lms-c/                              # Root — konten saja
├── content/                         # 25 lesson markdown
│   ├── home.md
│   ├── hello_world.md
│   ├── variables.md
│   └── ... (25 file)
├── assets/                          # Gambar untuk lesson
├── tokens_siswa.csv                 # Data siswa & progress
├── config/
│   └── sinau-c-tail.json           # Tailscale config
├── state/                           # Runtime state (certs, logs)
└── .env                             # Environment variables

elemes/                              # Semua kode aplikasi
├── documentation.md                 # Dokumen ini
│
├── api/                             # ── Flask API Backend ──
│   ├── app.py                       # create_app() factory
│   ├── config.py                    # Environment config
│   ├── requirements.txt             # Python dependencies
│   ├── Dockerfile
│   ├── gunicorn.conf.py
│   ├── compiler/                    # Compiler module (tidak berubah)
│   │   ├── __init__.py              # CompilerFactory
│   │   ├── base_compiler.py         # Abstract base
│   │   ├── c_compiler.py            # gcc wrapper
│   │   └── python_compiler.py       # python wrapper
│   ├── routes/                      # Flask Blueprints (JSON only)
│   │   ├── auth.py                  # /api/login, logout, validate-token
│   │   ├── compile.py               # /api/compile
│   │   ├── lessons.py               # /api/lessons, /api/lesson/<slug>
│   │   └── progress.py              # /api/track-progress, progress-report
│   ├── services/                    # Business logic
│   │   ├── token_service.py         # CSV token operations
│   │   └── lesson_service.py        # Markdown parsing
│   └── tests/                       # pytest
│       ├── test_auth.py
│       ├── test_compile.py
│       ├── test_lessons.py
│       └── test_progress.py
│
├── frontend/                        # ── SvelteKit PWA Frontend ──
│   ├── package.json
│   ├── svelte.config.js             # adapter-node
│   ├── vite.config.ts               # PWA plugin + API proxy
│   ├── Dockerfile
│   └── src/
│       ├── app.html                 # Root HTML shell
│       ├── app.css                  # Global styles
│       ├── lib/
│       │   ├── components/
│       │   │   ├── CodeEditor.svelte     # CodeMirror 6 (KRITIS)
│       │   │   ├── Navbar.svelte         # Navigation + auth
│       │   │   ├── LessonCard.svelte     # Card lesson
│       │   │   ├── OutputPanel.svelte    # Output kompilasi
│       │   │   ├── ProgressBadge.svelte  # Badge status
│       │   │   └── Footer.svelte
│       │   ├── stores/
│       │   │   ├── auth.ts               # Token state
│       │   │   └── theme.ts              # Dark/light
│       │   ├── services/
│       │   │   └── api.ts                # Flask API client
│       │   └── types/
│       │       ├── lesson.ts
│       │       ├── auth.ts
│       │       └── compiler.ts
│       ├── routes/
│       │   ├── +layout.svelte            # Navbar + Footer
│       │   ├── +page.svelte              # Home (lesson grid)
│       │   ├── lesson/[slug]/
│       │   │   └── +page.svelte          # Lesson viewer
│       │   └── progress/
│       │       └── +page.svelte          # Teacher dashboard
│       └── static/
│           ├── manifest.json             # PWA manifest
│           └── icons/                    # App icons
│
└── podman-compose.yml               # 3 services
```

---

## 6. Komponen Kritis: Code Editor

CodeMirror 6 adalah code editor web paling mature yang support mobile. Berikut fitur yang akan diimplementasi:

### Fitur Editor
- **Syntax highlighting** — C language mode (`@codemirror/lang-cpp`)
- **Line numbers** — gutter di sisi kiri
- **Bracket matching** — highlight bracket pasangan
- **Auto-close brackets** — otomatis tutup `{`, `(`, `[`
- **Dark/Light theme** — toggle dengan `@codemirror/theme-one-dark`
- **Undo/Redo** — Ctrl+Z / Ctrl+Shift+Z
- **Tab handling** — insert 4 spasi (bukan tab karakter)
- **Ctrl+Enter** — shortcut untuk Run
- **Copy-paste prevention** — bisa diaktifkan per-lesson (configurable)
- **Mobile keyboard support** — CodeMirror 6 handle virtual keyboard natively

### Perbandingan dengan Editor Saat Ini

| Fitur | Saat Ini (textarea) | SvelteKit (CodeMirror 6) |
|-------|:-------------------:|:------------------------:|
| Syntax highlighting saat mengetik | ❌ | ✅ |
| Auto-indent | ❌ | ✅ |
| Bracket matching | ❌ | ✅ |
| Auto-close brackets | ❌ | ✅ |
| Undo/Redo | Basic browser | ✅ Full history |
| Mobile keyboard | Problematic | ✅ Native support |
| Dark/Light theme | Partial | ✅ Full themes |
| Find & Replace | ❌ | ✅ Ctrl+F |
| Multiple cursors | ❌ | ✅ |

---

## 7. Mobile Strategy: PWA

### Apa itu PWA?
Progressive Web App memungkinkan web app di-install seperti native app di mobile dan desktop, tanpa harus publish ke App Store / Play Store.

### Fitur PWA yang diimplementasi
1. **Add to Home Screen** — siswa bisa install dari browser
2. **Standalone mode** — berjalan tanpa browser chrome (address bar hilang)
3. **Splash screen** — branding saat app loading
4. **Offline reading** — lesson content di-cache oleh service worker
5. **Auto-update** — service worker update otomatis saat ada versi baru

### Responsive Design

| Viewport | Layout |
|----------|--------|
| Desktop (>1024px) | 2 kolom: lesson content (8/12) + sidebar (4/12) |
| Tablet (768-1023px) | 2 kolom: lesson content (7/12) + sidebar (5/12) |
| Mobile (<768px) | 1 kolom, sidebar jadi accordion expandable |

### Code Editor di Mobile
- Default height 200px dengan tombol expand
- CodeMirror 6 handle virtual keyboard secara native
- Touch-friendly buttons (target area lebih besar)
- Auto-scroll ke cursor saat virtual keyboard muncul

---

## 8. Tailscale Integration

### Arsitektur Deployment
```
                    Tailscale Network
                         │
        ┌────────────────▼────────────────┐
        │  elemes-ts (Tailscale container) │
        │  hostname: sinau-c-dev           │
        │  HTTPS :443 (Funnel)             │
        │         │                        │
        │         ▼ proxy                  │
        │  elemes-frontend :3000           │
        │  (SvelteKit)                     │
        │         │                        │
        │         ▼ /api/*                 │
        │  elemes-api :5000                │
        │  (Flask + gcc)                   │
        └─────────────────────────────────┘
```

### Akses Development
- **Internal:** `http://localhost:3000` (langsung ke SvelteKit)
- **External via Tailscale:** `https://sinau-c-dev.<tailnet>.ts.net`
- **Funnel (public):** Bisa diaktifkan untuk akses tanpa Tailscale client

### Perubahan dari Setup Saat Ini
- Tailscale proxy target berubah dari Flask (:5000) ke SvelteKit (:3000)
- SvelteKit yang meng-handle semua request client, lalu proxy `/api/*` ke Flask internal

---

## 9. Fase Implementasi

### Phase 0: Backend Decomposition
**Tujuan:** Pecah Flask monolith menjadi modular API

- Buat struktur `elemes/api/`
- Extract services: `lesson_service.py`, `token_service.py`
- Extract routes ke Blueprints: `auth.py`, `compile.py`, `lessons.py`, `progress.py`
- Rewrite `app.py` sebagai factory function
- Tambah `flask-cors`
- Write unit tests

**Output:** Flask API yang return JSON, siap dikonsumsi frontend

### Phase 1: SvelteKit Scaffolding
**Tujuan:** Setup project SvelteKit dengan dependencies

- Initialize project dengan TypeScript
- Install CodeMirror 6, PWA plugin, marked
- Configure adapter-node dan API proxy

### Phase 2: Core Components
**Tujuan:** Build komponen reusable

- Auth store + API service
- CodeEditor (CodeMirror 6)
- Navbar, Footer, LessonCard, OutputPanel

### Phase 3: Pages
**Tujuan:** Build semua halaman

- Home page (lesson grid + SSR)
- Lesson page (content + editor + output)
- Progress report (teacher dashboard)

### Phase 4: Mobile + PWA
**Tujuan:** Optimasi mobile dan installability

- Responsive CSS
- PWA manifest + service worker
- Offline lesson caching
- Mobile-optimized editor

### Phase 5: Containerization + Tailscale
**Tujuan:** Deploy ke containers

- Frontend Dockerfile (Node 20)
- API Dockerfile (Python 3.11 + gcc)
- Update podman-compose.yml (3 services)
- Update Tailscale config

### Phase 6: Cleanup
**Tujuan:** Hapus kode lama

- Remove Jinja2 templates
- Remove vanilla JS
- Remove flutter_app/ placeholder
- Remove flask-talisman (CSP di SvelteKit)

---

## 10. Stack Teknologi

### Backend (Flask API)
| Teknologi | Versi | Fungsi |
|-----------|-------|--------|
| Python | 3.11 | Runtime |
| Flask | 2.3+ | Web framework (API only) |
| Flask-CORS | latest | Cross-origin untuk SvelteKit |
| Gunicorn | 21.2 | Production WSGI server |
| gcc | system | C compiler |
| python-markdown | 3.5 | Markdown → HTML |

### Frontend (SvelteKit)
| Teknologi | Versi | Fungsi |
|-----------|-------|--------|
| Node.js | 20 LTS | Runtime |
| SvelteKit | 2.x | Full-stack framework |
| Svelte | 5.x | UI framework |
| TypeScript | 5.x | Type safety |
| CodeMirror 6 | 6.x | Code editor |
| @vite-pwa/sveltekit | latest | PWA support |
| marked | latest | Client-side markdown (jika perlu) |
| highlight.js | 11.x | Syntax highlighting di konten |

### Infrastructure
| Teknologi | Fungsi |
|-----------|--------|
| Podman | Container runtime |
| Podman Compose | Container orchestration |
| Tailscale | VPN + HTTPS (Funnel) |

---

## 11. API Endpoints

Semua endpoint Flask akan di-prefix dengan `/api/`:

### Authentication
| Method | Endpoint | Request | Response |
|--------|----------|---------|----------|
| POST | `/api/login` | `{token}` | `{success, student_name}` |
| POST | `/api/logout` | — | `{success}` |
| POST | `/api/validate-token` | `{token}` | `{success, student_name}` |

### Lessons
| Method | Endpoint | Response |
|--------|----------|----------|
| GET | `/api/lessons` | `[{title, filename, description, completed}]` |
| GET | `/api/lesson/<slug>` | `{lesson_html, exercise_html, initial_code, solution_code, expected_output, key_text, title, prev, next}` |
| GET | `/api/key-text/<slug>` | `{key_text}` |

### Compilation
| Method | Endpoint | Request | Response |
|--------|----------|---------|----------|
| POST | `/api/compile` | `{code, language?}` | `{success, output, error}` |

### Progress
| Method | Endpoint | Request/Params | Response |
|--------|----------|----------------|----------|
| POST | `/api/track-progress` | `{token, lesson_name}` | `{success}` |
| GET | `/api/progress-report` | `?token=xxx` | `{students: [{name, progress: {}}]}` |
| GET | `/api/export-csv` | `?token=xxx` | CSV file download |

---

## 12. Verifikasi

### Testing Strategy
1. **Backend:** pytest di dalam container (`podman exec elemes-api pytest -v`)
2. **Frontend unit:** Vitest (`npm run test`)
3. **Frontend E2E:** Playwright (`npm run test:e2e`)
4. **Manual:** Cek di desktop dan mobile viewport

### Checklist Verifikasi
- [ ] Home page menampilkan 25 lesson cards
- [ ] Login dengan token berhasil
- [ ] Lesson page menampilkan konten markdown
- [ ] Code editor berfungsi (syntax highlighting, line numbers)
- [ ] Run code → output ditampilkan
- [ ] Kode benar → progress ter-track
- [ ] Progress report menampilkan data siswa
- [ ] Export CSV berfungsi
- [ ] Responsive di mobile (375x667)
- [ ] PWA installable
- [ ] Tailscale Funnel accessible

---

## 13. Risiko dan Mitigasi

| Risiko | Dampak | Mitigasi |
|--------|--------|----------|
| CodeMirror 6 bundle size di mobile | Slow initial load | Lazy-load CodeMirror hanya di lesson page |
| Flask API downtime saat refactor | Siswa tidak bisa belajar | Parallel running: old templates tetap jalan |
| Markdown parsing perbedaan Python vs JS | Rendering berbeda | Flask tetap parse markdown (single source of truth) |
| Tailscale config berubah | Akses terputus | Backup config lama, rollback plan ready |

---

*Dokumen ini adalah proposal. Implementasi dimulai setelah disetujui.*
