# Elemes LMS — Dokumentasi Teknis

**Project:** LMS-C (Learning Management System untuk Pemrograman C & Arduino)
**Terakhir diupdate:** 10 Mei 2026

---

## Arsitektur

```
Internet (HTTPS :443)
    │
    ▼
Tailscale Funnel (elemes-ts)
    │
    ├── /                   → SvelteKit Frontend (elemes-frontend :3000)
    ├── /assets/            → Flask Backend (elemes :5000)
    ├── /velxio/api/compile → Flask Backend (Rate-limited Proxy :5000)
    ├── /velxio/            → Velxio Arduino Simulator (velxio :80)
    │
    ▼
SvelteKit Frontend (elemes-frontend :3000)
  ├── SSR pages (lesson content embedded in HTML)
  ├── CodeMirror 6 editor (lazy-loaded)
  ├── CircuitJS simulator (iframe, GWT-compiled) — mode "circuit"
  ├── Velxio Arduino simulator (iframe, React) — mode "velxio"
  ├── API proxy: /api/* → Flask
  └── PWA manifest
    │
    ▼  /api/*
Flask API Backend (elemes :5000)
  ├── Code compilation (Proxied to Compiler Worker)
  ├── Arduino Proxy (/velxio-compile → Velxio :80)
  ├── Token authentication (CSV)
  ├── Progress tracking
  └── Lesson content parsing (markdown)
    │
    ▼  HTTP
Compiler Worker (compiler-worker :8080)
  ├── gVisor Sandbox (runsc runtime)
  ├── Gunicorn (4 workers)
  └── Isolation: gcc / python3 execution
    │
Velxio Arduino Simulator (velxio :80)
  ├── React + Vite frontend (editor + simulator canvas)
  ├── FastAPI backend (arduino-cli compile)
  ├── AVR8 / RP2040 CPU emulation (browser)
  └── PostMessage bridge ↔ Elemes (EmbedBridge.ts)
```

### Container Setup

| Container | Image | Port | Fungsi |
|-----------|-------|------|--------|
| `elemes` | Python 3.11 | 5000 | Flask API (auth, lessons, progress, compile-proxy) |
| `compiler-worker` | Python 3.11 + gcc | 8080 | **Sandboxed** execution engine (gVisor) |
| `elemes-frontend` | Node 20 | 3000 | SvelteKit SSR |
| `velxio` | Node + Python + arduino-cli | 80 | Simulator Arduino (React + FastAPI) |
| `elemes-ts` | Tailscale | 443 | HTTPS Funnel + reverse proxy |

Container berkomunikasi via hostname Podman (compose service name). Proxy rules di `config/sinau-c-tail.json`.

---

## Struktur Direktori

```
lms-c/
├── content/                     # Lesson markdown files
│   ├── home.md                  # Daftar lesson + landing page
│   ├── hello_world.md           # Lesson C
│   ├── variabel.md              # Lesson C
│   ├── rangkaian_dasar.md       # Lesson Circuit
│   └── led_blink_arduino.md     # Lesson Arduino/Velxio
├── assets/                      # Gambar untuk lesson
├── tokens_siswa.csv             # Data siswa & progress
├── state/                       # Tailscale runtime state
├── .env                         # Environment variables
│
└── elemes/                      # Semua kode aplikasi
    ├── app.py                   # Flask create_app() factory
    ├── config.py                # CONTENT_DIR, TOKENS_FILE
    ├── Dockerfile               # Flask container
    ├── gunicorn.conf.py         # Production WSGI
    ├── requirements.txt         # Python deps
    ├── podman-compose.yml       # 4 services (elemes, frontend, velxio, ts)
    ├── elemes.sh                # CLI: init, run, runbuild, stop, generatetoken
    ├── generate_tokens.py       # Utility: generate CSV tokens
    ├── proposal.md              # Proposal integrasi Velxio (referensi arsitektur)
    │
    ├── config/
    │   └── sinau-c-tail.json    # Tailscale Serve proxy rules
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
    │   ├── lessons.py           # /lessons, /lesson/<slug>.json, /get-key-text/<slug>
    │   └── progress.py          # /track-progress, /progress-report.json, export-csv
    │
    ├── services/                # Business logic
    │   ├── token_service.py     # CSV token CRUD
    │   └── lesson_service.py    # Markdown parsing + rendering
    │
    ├── frontend/                # SvelteKit (Svelte 5)
    │   ├── package.json
    │   ├── svelte.config.js     # adapter-node + path aliases
    │   ├── vite.config.ts
    │   ├── Dockerfile           # Multi-stage build
    │   └── src/
    │       ├── hooks.server.ts  # API proxy: /api/* → Flask, /assets/* → Flask
    │       ├── app.html
    │       ├── app.css
    │       ├── lib/
    │       │   ├── components/
    │       │   │   ├── CodeEditor.svelte       # CodeMirror 6 (lazy-loaded, anti-paste)
    │       │   │   ├── CircuitEditor.svelte    # CircuitJS iframe wrapper
    │       │   │   ├── CrosshairOverlay.svelte # Touch precision overlay (CircuitJS)
    │       │   │   ├── OutputPanel.svelte      # Multi-section output (C, Python, Circuit, Arduino)
    │       │   │   ├── CelebrationOverlay.svelte # Lesson completion animation
    │       │   │   ├── WorkspaceHeader.svelte  # Tab switcher + floating/mobile controls
    │       │   │   ├── LessonFooterNav.svelte  # Prev/next lesson navigation
    │       │   │   ├── Navbar.svelte
    │       │   │   ├── LessonCard.svelte
    │       │   │   ├── LessonList.svelte
    │       │   │   ├── ProgressBadge.svelte
    │       │   │   └── Footer.svelte
    │       │   ├── stores/
    │       │   │   ├── auth.ts             # Svelte writable stores (login, token)
    │       │   │   ├── lessonContext.ts     # Current lesson nav context
    │       │   │   └── theme.ts            # Dark/light toggle
    │       │   ├── services/
    │       │   │   ├── api.ts              # Flask API client
    │       │   │   ├── exercise.ts         # checkKeyText(), validateNodes()
    │       │   │   └── velxio-bridge.ts    # PostMessage bridge ke Velxio iframe
    │       │   ├── actions/
    │       │   │   ├── floatingPanel.svelte.ts  # Draggable/resizable editor panel
    │       │   │   ├── highlightCode.ts         # Syntax highlighting post-render
    │       │   │   ├── noSelect.ts              # Anti-select directive
    │       │   │   └── renderCircuitEmbeds.ts   # Inline circuit embed renderer
    │       │   └── types/
    │       │       ├── lesson.ts           # LessonContent interface
    │       │       ├── auth.ts
    │       │       ├── compiler.ts
    │       │       └── circuitjs.ts        # CircuitJSApi interface
    │       ├── routes/
    │       │   ├── +layout.svelte          # App shell (Navbar, theme sinkronisasi)
    │       │   ├── +page.svelte            # Home (lesson grid)
    │       │   ├── +page.ts                # SSR data loader
    │       │   ├── lesson/[slug]/
    │       │   │   ├── +page.svelte        # Lesson viewer (Layout utama & inisialisasi)
    │       │   │   └── +page.ts            # SSR data loader
    │       │   └── progress/
    │       │       └── +page.svelte        # Teacher dashboard
    │       └── static/
    │           ├── manifest.json           # PWA manifest
    │           └── circuitjs1/             # CircuitJS simulator (GWT-compiled)
    │
    └── velxio/                  # Velxio fork (Git submodule)
        ├── frontend/            # React + Vite + TypeScript
        │   └── src/
        │       ├── services/EmbedBridge.ts       # PostMessage listener (Velxio side)
        │       ├── pages/EditorPage.tsx           # Editor + embed mode
        │       ├── components/editor/EditorToolbar.tsx
        │       ├── components/simulator/SimulatorCanvas.tsx  # Canvas + touch/pinch + undo/redo toolbar
        │       ├── components/simulator/SimulatorCanvas.css # Canvas styling (undo-controls class)
        │       ├── components/simulator/WireInProgressRenderer.tsx  # Wire preview + crosshair
        │       ├── components/simulator/WireLayer.tsx      # Wire SVG rendering + segment handles
        │       ├── components/simulator/PinOverlay.tsx
        │       ├── store/useEditorStore.ts        # Multi-file workspace
        │       └── store/useSimulatorStore.ts     # Simulation state, wires, undo/redo stacks
        ├── backend/             # FastAPI + arduino-cli
        ├── Dockerfile.standalone
        └── CLAUDE.md            # Dokumentasi teknis lengkap Velxio
```

---

## Keputusan Teknis

### Refactoring Halaman Lesson (Modularitas)
Halaman lesson (`+page.svelte`) sebelumnya bertindak sebagai "God Component" (>1.300 baris) yang menangani state, integrasi iframe, logika kompilasi, dan UI rendering. Untuk skalabilitas, halaman ini telah direfaktor menjadi arsitektur modular:
1. **`lessonState.svelte.ts`**: Menggunakan Svelte 5 Runes (`$state`, `$derived`) untuk mengelola seluruh state pelajaran secara reaktif di luar komponen UI.
2. **`LessonWorkspace.svelte`**: Komponen presentasional yang membungkus seluruh area interaktif (Editor, Output, Tab).
3. **`VelxioIframe.svelte`**: Mengisolasi logika inisialisasi bridge, `postMessage`, dan *auto-save* khusus untuk simulator Arduino.
4. **`highlightCode.ts` (Svelte Action)**: Syntax highlighting menggunakan eksekusi level DOM (via `use:highlightAction`) yang dipicu ulang setiap kali string HTML materi berubah, menggantikan efek reaktif (`$effect`) yang rentan *race-condition*.

### Kenapa SvelteKit, bukan Flutter?
- CodeMirror 6 (code editor production-grade) — tidak ada equivalent di Flutter
- Bundle ~250KB vs Flutter Web 2-4MB
- SSR untuk konten markdown (instant first paint)
- PWA installable tanpa app store

### Svelte 5 Runes vs Writable Stores
Proyek ini menggunakan **Svelte 5** dengan dua pola state management:
- **Runes (`$state`, `$derived`, `$effect`)** — digunakan di file `.svelte` (contoh: `lesson/[slug]/+page.svelte` menggunakan `$state` untuk semua UI state, `$derived` untuk computed values, `$effect` untuk side effects)
- **Writable stores (`writable()`)** — digunakan di file `.ts` biasa karena runes tidak diproses oleh Svelte compiler di luar file `.svelte`. Contoh: `auth.ts`, `lessonContext.ts`, `theme.ts`

### Kenapa hooks.server.ts untuk API proxy?
Vite `server.proxy` hanya bekerja di dev mode (`vite dev`). Di production (adapter-node), SvelteKit tidak punya proxy. `hooks.server.ts` mem-forward `/api/*` dan `/assets/*` ke Flask backend saat runtime. Prefix `/api/` di-strip sebelum forward (Flask routes tidak pakai `/api/` prefix).

### Kenapa transparent overlay untuk touch CircuitJS?
CircuitJS adalah GWT-compiled app — tidak bisa modify source code-nya. Transparent overlay mengintercept PointerEvent di parent, konversi ke MouseEvent, dispatch ke iframe via `contentDocument.elementFromPoint()`. Overlay dinonaktifkan (`pointer-events: none`) di desktop sehingga mouse events langsung tembus ke iframe.

### Kenapa lazy-load CodeMirror?
CodeMirror 6 bundle ~475KB. Dengan dynamic `import()`, lesson content (text) muncul langsung via SSR, editor menyusul setelah JS bundle selesai download.

### Kenapa Velxio di-embed via iframe, bukan komponen?
Velxio adalah aplikasi React lengkap (editor + simulator + serial monitor + wire system). Mengekstrak komponen-komponennya ke SvelteKit tidak praktis. Iframe + PostMessage bridge memungkinkan kedua sistem dikembangkan secara independen. Same-origin via Tailscale Serve proxy (`/velxio/`), jadi tidak perlu CORS/CSP khusus.

---

## Cara Menjalankan

```bash
# Setup awal (sekali)
cd elemes/
./elemes.sh init

# Edit ../.env sesuai kebutuhan (ELEMES_HOST, TS_AUTHKEY, branding)

# Build & run semua container
./elemes.sh runbuild

# Atau: run tanpa rebuild
./elemes.sh run

# Stop
./elemes.sh stop

# Rebuild tanpa cache
./elemes.sh runclearbuild

# Generate token siswa dari content
./elemes.sh generatetoken
```

- **Frontend:** http://localhost:3000 (dev)
- **Tailscale:** https://{ELEMES_HOST}.{tailnet}.ts.net

### Logs

```bash
podman logs elemes           # Flask API
podman logs elemes-frontend  # SvelteKit
podman logs velxio           # Velxio simulator
podman logs elemes-ts        # Tailscale
```

---

## API Endpoints

Semua endpoint Flask diakses via SvelteKit proxy (`/api/*` → Flask `:5000`, prefix `/api/` di-strip):

| Method | Frontend Path | Flask Path | Fungsi |
|--------|--------------|------------|--------|
| POST | `/api/login` | `/login` | Login dengan token |
| POST | `/api/logout` | `/logout` | Logout |
| POST | `/api/validate-token` | `/validate-token` | Validasi token |
| GET | `/api/lessons` | `/lessons` | Daftar lesson + home content |
| GET | `/api/lesson/<slug>.json` | `/lesson/<slug>.json` | Data lesson lengkap |
| GET | `/api/get-key-text/<slug>` | `/get-key-text/<slug>` | Key text untuk lesson |
| POST | `/api/compile` | `/compile` | Compile & run kode (C/Python) via worker |
| POST | `/velxio/api/compile` | `/velxio-compile` | **Rate-limited** Arduino compile proxy |
| POST | `/api/track-progress` | `/track-progress` | Track progress siswa |
| GET | `/api/progress-report.json` | `/progress-report.json` | Data progress semua siswa |
| GET | `/api/progress-report/export-csv` | `/progress-report/export-csv` | Export CSV |
| GET | `/assets/<path>` | `/assets/<path>` | Static assets (proxy langsung, tanpa strip) |

---

## Mode Lesson

Elemes mendukung beberapa mode lesson melalui **marker** di file markdown. Mode ditentukan otomatis dari marker yang ada:

| Mode | Marker | Tab yang muncul | Evaluasi |
|------|--------|-----------------|----------|
| **C** | `---INITIAL_CODE---` | Editor (C) + Output | stdout matching + key_text |
| **Python** | `---INITIAL_PYTHON---` | Editor (Python) + Output | stdout matching + key_text |
| **Circuit** | `---INITIAL_CIRCUIT---` | Circuit + Output | node voltage + key_text |
| **Arduino/Velxio** | `---INITIAL_CODE_ARDUINO---` | Velxio (iframe) + Output | serial + wiring + key_text |
| **Velxio circuit-only** | `---VELXIO_CIRCUIT---` (tanpa code) | Velxio (no editor) + Output | wiring + key_text |
| **Quiz** | `---QUIZ_FLASHCARD---` atau `---INITIAL_QUIZ---` | Quiz | Completion status |
| **Slide** | `---slide-start---` | — | Tampilan Carousel (Presentasi) |
| **Hybrid** | C/Python + Circuit | Editor + Circuit + Output | AND-logic: kedua harus pass |

### Markdown Sections yang Dikenali

| Section | Fungsi |
|---------|--------|
| `---LESSON_INFO---` / `---END_LESSON_INFO---` | Info tab (learning objectives) |
| `---EXERCISE---` | Instruksi latihan (separator) |
| `---slide-start---` / `---slide-end---` | Konten slide presentasi (dipisah dengan `---`) |
| `---INITIAL_CODE---` / `---END_INITIAL_CODE---` | Kode awal C |
| `---INITIAL_PYTHON---` / `---END_INITIAL_PYTHON---` | Kode awal Python |
| `---INITIAL_CIRCUIT---` / `---END_INITIAL_CIRCUIT---` | Circuit text awal (CircuitJS format) |
| `---INITIAL_QUIZ---` / `---END_INITIAL_QUIZ---` | Quiz data (JSON) |
| `---QUIZ_FLASHCARD---` / `---END_QUIZ_FLASHCARD---` | Quiz data (Markdown/Flashcard format) |
| `---INITIAL_CODE_ARDUINO---` / `---END_INITIAL_CODE_ARDUINO---` | Kode awal Arduino |
| `---VELXIO_CIRCUIT---` / `---END_VELXIO_CIRCUIT---` | Circuit JSON untuk Velxio (komponen + wires) |
| `---EXPECTED_OUTPUT---` / `---END_EXPECTED_OUTPUT---` | Expected stdout (C/Python) atau node voltage JSON (Circuit) |
| `---EXPECTED_CIRCUIT_OUTPUT---` / `---END_EXPECTED_CIRCUIT_OUTPUT---` | Expected circuit output (hybrid mode) |
| `---EXPECTED_SERIAL_OUTPUT---` / `---END_EXPECTED_SERIAL_OUTPUT---` | Expected serial output (Arduino) |
| `---EXPECTED_WIRING---` / `---END_EXPECTED_WIRING---` | Expected wiring JSON (Arduino) |
| `---KEY_TEXT---` / `---END_KEY_TEXT---` | Keyword wajib di source code / circuit |
| `---KEY_TEXT_CIRCUIT---` / `---END_KEY_TEXT_CIRCUIT---` | Keyword wajib di circuit (hybrid) |
| `---SOLUTION_CODE---` / `---END_SOLUTION_CODE---` | Solusi kode (ditampilkan setelah selesai) |
| `---SOLUTION_CIRCUIT---` / `---END_SOLUTION_CIRCUIT---` | Solusi circuit |

### Fitur Tombol "Coba" (Code Try-out)

LMS menyediakan fitur tombol **"Coba ▶"** pada blok kode di dalam materi pelajaran.

**Penentuan Kemunculan Tombol:**
- Tombol **hanya muncul** jika instruktur secara eksplisit memberikan label bahasa pada *code fence* di file Markdown (contoh: ` ```c `, ` ```python `, ` ```arduino ` atau ` ```cpp `).
- Jika blok kode bersifat generik atau tidak memiliki label (hanya ` ``` `), tombol **tidak akan muncul**. Ini memberikan kendali untuk membedakan mana cuplikan kode yang bisa dicoba dan mana yang sekadar teks penjelasan/diagram.

**Perilaku Tombol:**
1. **Load & Switch Tab:** Mengklik tombol akan menyalin teks kode ke editor dan mengalihkan fokus LMS ke tab yang relevan (C, Python, atau Arduino/Velxio).
2. **Review Sebelum Eksekusi:** Kode **tidak langsung dieksekusi** (No Auto-Run). Siswa berkesempatan untuk meninjau atau memodifikasi kode sebelum menekan tombol "Run".
3. **Mobile UX (Layar < 768px):**
   - Tombol "Coba ▶" selalu terlihat (karena ketiadaan fitur *hover* pada layar sentuh).
   - Saat diklik, panel *workspace* di bawah akan otomatis membuka setengah layar (`half-sheet`) dan browser akan melakukan *smooth scroll* agar editor langsung terfokus.

---

## Velxio Integration (Arduino Simulator)

### PostMessage Bridge Protocol

Komunikasi antara Elemes dan Velxio iframe via `window.postMessage`:

**Elemes → Velxio (Commands):**
| Message Type | Payload | Fungsi |
|---|---|---|
| `elemes:load_code` | `{ files: [{name, content}] }` | Load source code ke editor |
| `elemes:load_circuit` | `{ board, components, wires }` | Load rangkaian ke simulator |
| `elemes:set_embed_mode` | `{ hideAuth, hideComponentPicker }` | Configure embed UI |
| `elemes:get_source_code` | — | Request source code |
| `elemes:get_serial_log` | — | Request serial output |
| `elemes:get_wires` | — | Request wire topology |
| `elemes:stop` | — | Stop simulation |
| `elemes:ping` | — | Re-trigger ready signal |

**Velxio → Elemes (Events):**
| Message Type | Payload | Fungsi |
|---|---|---|
| `velxio:ready` | `{ version }` | Iframe siap (broadcast tiap 300ms sampai parent acknowledge) |
| `velxio:compile_result` | `{ success }` | Kompilasi selesai |
| `velxio:source_code` | `{ files }` | Response ke get_source_code |
| `velxio:serial_log` | `{ log }` | Response ke get_serial_log |
| `velxio:wires` | `{ wires }` | Response ke get_wires |

### Flow Lesson Arduino

```
1. User buka lesson → frontend fetch /api/lesson/<slug>.json
2. Backend parse markdown → extract INITIAL_CODE_ARDUINO, VELXIO_CIRCUIT, dll
3. Frontend detect active_tabs=['velxio'] → render iframe src="/velxio/editor?embed=true"
4. Iframe load → Velxio EmbedBridge broadcast velxio:ready (tiap 300ms)
5. Frontend initVelxioBridge() → create VelxioBridge → acknowledge → stop broadcast
6. Bridge send: set_embed_mode, load_circuit, load_code
7. Siswa edit kode + wiring di Velxio → klik Compile & Run
8. Velxio notify: velxio:compile_result { success: true }
9. Auto-evaluate setelah 3 detik (tunggu serial output)
10. Evaluate: get_source_code → key_text, get_serial_log → serial match, get_wires → wiring match
11. Jika semua pass → completeLesson() → celebration + track progress
```

### Evaluasi Arduino (3 jenis, semua harus pass)

| Evaluasi | Mekanisme | Sumber Data |
|----------|-----------|-------------|
| **Key Text** | Keyword wajib ada di source code | `---KEY_TEXT---` di markdown |
| **Serial Output** | Subsequence matching (expected lines muncul dalam urutan di actual) | `---EXPECTED_SERIAL_OUTPUT---` |
| **Wiring** | Lenient graph comparison (expected edges harus ada, extra OK) | `---EXPECTED_WIRING---` (JSON array of pairs) |

### File-file Kunci

| Sisi | File | Fungsi |
|------|------|--------|
| Elemes | `frontend/src/lib/services/velxio-bridge.ts` | VelxioBridge class (send commands, evaluate) |
| Elemes | `frontend/src/routes/lesson/[slug]/+page.svelte` | initVelxioBridge(), handleVelxioSubmit() |
| Velxio | `frontend/src/services/EmbedBridge.ts` | PostMessage listener (handle commands) |
| Velxio | `frontend/src/pages/EditorPage.tsx` | Embed mode UI control |
| Velxio | `frontend/src/components/editor/EditorToolbar.tsx` | Embed-aware toolbar |

---

## CircuitJS Integration

Integrasi Falstad CircuitJS1 sebagai simulator rangkaian interaktif di tab "Circuit". CircuitJS adalah aplikasi GWT (Java → JavaScript) yang di-embed via iframe same-origin.

### Arsitektur

```
content/rangkaian_dasar.md
  │  ---INITIAL_CIRCUIT--- ... ---END_INITIAL_CIRCUIT---
  │
  ▼  lesson_service.py: _extract_section()
Flask API (/lesson/<slug>.json)
  │  { initial_circuit, expected_output, key_text, active_tabs: ["circuit"] }
  │
  ▼  +page.ts SSR loader
lesson/[slug]/+page.svelte
  │  <CircuitEditor initialCircuit={data.initial_circuit} />
  │
  ▼  iframe onload → oncircuitjsloaded callback
CircuitEditor.svelte
  │  simApi.importCircuit(text, false)
  │
  ▼
circuitjs1/circuitjs.html (GWT app in iframe)
  │  Canvas rendering, simulasi real-time
  │
  ▼  CrosshairOverlay.svelte (touch devices only)
Touch event forwarding → synthetic MouseEvent dispatch
```

### CircuitJS API (via `iframe.contentWindow.CircuitJS1`)

API object didapatkan melalui callback `window.oncircuitjsloaded`, dengan fallback 3 detik via `window.CircuitJS1`.

| Method | Fungsi |
|--------|--------|
| `importCircuit(text, showMessage)` | Load circuit dari text |
| `exportCircuit()` | Ekspor circuit saat ini sebagai text |
| `getNodeVoltage(nodeName)` | Query tegangan di named node |
| `setSimRunning(bool)` | Jalankan/hentikan simulasi |
| `updateCircuit()` | Redraw setelah perubahan |

### Evaluasi Rangkaian

Saat siswa klik "Cek Rangkaian", fungsi `evaluateCircuit()` menjalankan:

1. Parse kriteria dari `expected_output` (JSON)
2. Cek tegangan node via `simApi.getNodeVoltage()` ± tolerance
3. Cek komponen wajib via `checkKeyText()` (string contains pada circuit text)
4. Track progress jika semua passed

**Expected Output JSON Format:**
```json
{
  "nodes": {
    "TestPoint_A": { "voltage": 2.5, "tolerance": 0.2 }
  }
}
```

### Auto-save

`CircuitEditor` mendukung auto-save ke `sessionStorage` (polling setiap 5 detik):
- **Key:** `elemes_circuit_{slug}` (hanya saat user login & bukan mode solusi)
- **Restore:** Cek sessionStorage dulu, fallback ke `initialCircuit` prop

---

## Quiz Integration

Elemes mendukung kuis interaktif yang terintegrasi langsung dengan sistem progres. Kuis dapat berupa Flashcard (Tanya-Jawab) atau Pilihan Ganda (MCQ).

### Arsitektur Parsing (`QUIZ_FLASHCARD`)

Untuk memudahkan pengajar, Elemes menyediakan parser Markdown khusus di `lesson_service.py` (`_parse_flashcards`):

1. **Detection**: Mencari blok `---QUIZ_FLASHCARD---`.
2. **Splitting**: Membagi konten berdasarkan heading `###`.
3. **MCQ vs Flashcard**:
   - Jika ditemukan pola `- []` atau `- [x]`, elemen diparse sebagai `type: 'mcq'`.
   - Jika tidak, diparse sebagai `type: 'flashcard'`.
4. **Explanation**: Menangkap blok kutipan `>` sebagai penjelasan yang muncul setelah kuis dijawab.
5. **Images**: Mendukung penambahan gambar melalui:
   - Keyword `image: URL` tepat di bawah heading pertanyaan (akan tampil sebagai gambar utama).
   - Syntax Markdown standar `![alt](url)` di dalam teks pertanyaan, opsi, atau penjelasan.
6. **Rendering**: Pertanyaan dan jawaban di-render menggunakan filter Markdown standar (mendukung formatting, code snippets, dll).

### Quiz State Management

**File:** `frontend/src/lib/components/QuizTab.svelte`

1. **Shuffle**: Pertanyaan diacak setiap kali kuis dimulai (opsional).
2. **Tracking**: Menggunakan state lokal untuk melacak jawaban benar/salah.
3. **Completion**: Setelah semua pertanyaan dijawab, memicu `completeLesson('completed')` yang mengirimkan progres ke backend.

---

## Anti Copy-Paste System

Sistem berlapis untuk mencegah siswa meng-copy konten pelajaran dan mem-paste kode dari sumber eksternal.

### Selection & Copy Prevention (Konten Lesson)

**File:** `lesson/[slug]/+page.svelte`

| Layer | Mekanisme | Target |
|-------|-----------|--------|
| CSS | `user-select: none`, `-webkit-touch-callout: none` | `.lesson-content`, info/exercise tabs |
| Events | `onselectstart`, `oncopy`, `oncut`, `oncontextmenu` → `preventDefault()` | Konten lesson |
| Directive | `use:noSelect` | Reusable action |

### Paste Prevention (CodeEditor)

**File:** `CodeEditor.svelte`

Diaktifkan via prop `noPaste={true}`.

| Layer | Mekanisme | Menangani |
|-------|-----------|-----------|
| DOM handlers | `paste`, `drop`, `beforeinput` → `preventDefault()` | Desktop paste, iOS paste |
| Transaction filter | Block `input.paste` + heuristik ukuran (>2 baris atau >20 chars) | Standard paste + GBoard clipboard panel |
| Clipboard filter | Replace clipboard text → `''` | Standard paste (jika API tersedia) |
| Input handler | Block multi-line insertion >20 chars | GBoard clipboard via DOM mutations |

**Limitasi:** GBoard clipboard panel menggunakan IME composition, tidak bisa dibedakan 100% dari ketikan biasa. Paste 1 baris pendek (<20 chars) masih bisa lolos.

---

## Keamanan & Autentikasi (Security)

Sistem pengamanan untuk melindungi data siswa dan mencegah penyalahgunaan API.

### 1. Eksekusi Terisolasi (gVisor Sandbox)
Seluruh kode yang dikirim oleh siswa (C dan Python) tidak dieksekusi di dalam container utama, melainkan diteruskan ke **Compiler Worker** yang berjalan menggunakan **runtime gVisor (`runsc`)**. Ini mencegah serangan *Remote Code Execution* (RCE) yang menargetkan kernel sistem operasi host.

### 2. Anonymous Access & Rate Limiting
Sistem mengizinkan pengguna tanpa token (anonim) untuk mencoba pembelajaran dengan batasan ketat:
- **Rate Limit**: Pengguna anonim dibatasi **1 kali kompilasi setiap 2 menit** per IP.
- **Global Queue**: Maksimal **20 slot** antrean kompilasi anonim secara global untuk menjaga stabilitas server.
- **Bypass**: Pengguna yang telah login (memiliki token/cookie valid) **bebas** dari batasan rate limit ini.
- **Velxio Protection**: Kompilasi Arduino diproteksi melalui proxy backend Flask untuk mencegah *hijacking* API dari sisi klien.

### 3. Cookie Security (Dynamic Secure Flag)
LMS menggunakan cookie `student_token` untuk mengelola sesi. Keamanannya diatur secara dinamis melalui environment variable.
- **`httponly: true`**: Mencegah akses cookie via JavaScript (proteksi XSS).
- **`secure: COOKIE_SECURE`**: Jika `true`, cookie hanya dikirim via HTTPS. Sangat penting saat dideploy via Tailscale Funnel.
- **`samesite: 'Lax'`**: Proteksi dasar terhadap CSRF.

### 2. Proteksi Brute-Force & Anti-Spam
Untuk mencegah penebakan token secara massal, terutama pada jaringan WiFi sekolah yang menggunakan satu IP publik (NAT):
- **Rate Limiting**: Endpoint `/api/login` dibatasi maksimal **50 request per menit per IP**. Angka ini diatur untuk mengakomodasi satu kelas (50 siswa) yang login bersamaan tanpa saling memblokir.
- **Tarpitting (Login Delay)**: Setiap percobaan login yang **gagal** akan ditahan selama **1.5 detik** sebelum server memberikan respons. Ini melumpuhkan efektivitas alat brute-force otomatis tanpa mengganggu pengalaman siswa asli yang hanya sesekali salah ketik.

---

## Touch Crosshair System (CircuitJS)

Overlay untuk presisi interaksi di iframe CircuitJS pada perangkat sentuh. Aktif hanya pada touch device (CSS media query `hover: none` + `pointer: coarse`).

**File:** `CrosshairOverlay.svelte` (dimount di `CircuitEditor.svelte`)

### Gesture Mapping

| Gesture | Action |
|---------|--------|
| Single tap | `click` (delay 300ms) |
| Double tap | `dblclick` (edit komponen) |
| Triple tap | Right-click (`contextmenu`) |
| Two-finger tap | Right-click |
| Long tap (400ms) | Crosshair aiming mode (4-phase state machine) |

### Cara Kerja

Overlay transparan mengintercept touch events → konversi koordinat ke iframe-local → `elementFromPoint()` untuk target → dispatch synthetic `MouseEvent` ke iframe.

### Konfigurasi

| Variable | Default | Fungsi |
|----------|---------|--------|
| `PUBLIC_CURSOR_OFFSET_Y` | `50` | Offset Y crosshair dari jari (pixel) |

---

## Velxio Mobile Wiring Crosshair

Berbeda dari CircuitJS crosshair (yang menggunakan overlay), Velxio crosshair ada di dalam simulator canvas sendiri (SVG).

**File:** `velxio/frontend/src/components/simulator/WireInProgressRenderer.tsx`

Saat user sedang menarik wire, garis bantu horizontal + vertikal muncul di posisi cursor:
- Style: dashed `rgba(255,255,255,0.25)`, `strokeWidth=0.5`, `strokeDasharray="8,6"`
- Panjang: 8000px ke setiap arah (cukup untuk semua zoom level)
- Terinspirasi CircuitJS — membantu alignment karena jari menutupi pin target

### Pinch-Zoom Preserve Wire

**File:** `velxio/frontend/src/components/simulator/SimulatorCanvas.tsx`

Sebelumnya, pinch-to-zoom (2 jari) otomatis cancel wire yang sedang ditarik. Sekarang wire-in-progress tetap aktif selama zoom. Preview freeze (hanya update saat 1 jari), lalu resume setelah zoom selesai.

---

## Wire Undo/Redo

Snapshot-based undo/redo untuk operasi wire di Velxio simulator. Memungkinkan user membatalkan kesalahan wiring tanpa harus memilih dan menghapus wire secara manual.

### Arsitektur

```
User action (add/remove/update/finish wire)
    │
    ├── Push current state.wires → wireUndoStack (max 50)
    ├── Clear wireRedoStack
    └── Mutate state.wires
    
Undo (Ctrl+Z / toolbar button)
    │
    ├── Pop wireUndoStack → restore as state.wires
    ├── Push current state.wires → wireRedoStack
    └── Reset selectedWireId = null

Redo (Ctrl+Shift+Z / toolbar button)
    │
    ├── Pop wireRedoStack → restore as state.wires
    ├── Push current state.wires → wireUndoStack
    └── Reset selectedWireId = null
```

### File yang Terlibat

| File | Perubahan |
|------|-----------|
| `velxio/frontend/src/store/useSimulatorStore.ts` | State: `wireUndoStack`, `wireRedoStack`. Actions: `undoWire()`, `redoWire()`. Snapshot push di `addWire`, `removeWire`, `updateWire`, `finishWireCreation`. |
| `velxio/frontend/src/components/simulator/SimulatorCanvas.tsx` | Keyboard handler (`Ctrl+Z`/`Ctrl+Shift+Z`), toolbar buttons (undo/redo icons), store selectors (`canUndoWire`, `canRedoWire`). |
| `velxio/frontend/src/components/simulator/SimulatorCanvas.css` | Class `.undo-controls` — styling identik dengan `.zoom-controls` tapi **tidak di-hide** di mobile media query. |

### Keputusan Desain

1. **Snapshot-based vs action-based** — Dipilih snapshot (simpan seluruh `wires[]` per step) karena lebih sederhana dan reliable. Trade-off: memory lebih besar, tapi dengan limit 50 entries dan array wire yang kecil, tidak masalah.
2. **Separate CSS class** — `.undo-controls` terpisah dari `.zoom-controls` karena zoom di-hide di mobile (`display: none` — pakai pinch-to-zoom), tapi undo/redo harus tetap visible.
3. **`setWires()` tidak push snapshot** — `setWires()` digunakan oleh `EmbedBridge` saat load circuit dari LMS. Ini bukan user action, jadi tidak masuk undo history.
4. **`selectedWireId: null` saat undo/redo** — Mencegah bug dimana UI mencoba menampilkan info wire yang sudah tidak ada setelah undo.

---

## Status Implementasi

- [x] Backend decomposition (monolith → Blueprints + services)
- [x] SvelteKit scaffolding (adapter-node, Svelte 5, path aliases)
- [x] Core components (CodeEditor, Navbar, auth/theme stores, API client)
- [x] Pages (Home, Lesson, Progress) + SSR data loading
- [x] Containerization (4-container setup, API proxy)
- [x] CircuitJS integration (iframe, evaluasi node voltage, touch overlay)
- [x] Floating/mobile editor panel (draggable, resizable, bottom sheet)
- [x] Anti copy-paste system (lesson content + code editor)
- [x] Velxio fork + EmbedBridge (PostMessage protocol)
- [x] Velxio integration di Elemes (bridge, parsing, UI, evaluasi)
- [x] Mobile wiring UX (pinch-zoom preserve wire, crosshair alignment)
- [x] Wire undo/redo (snapshot-based, Ctrl+Z/Ctrl+Shift+Z, toolbar button, mobile-friendly)
- [x] Security Review & Hardening (Cookie security, Rate limiting, Tarpitting)
- [x] Examples of Arduino lessons (LED Blink)
- [x] Flowchart integration (parsing & embedding)
- [x] Quiz support (parsing INITIAL_QUIZ)
- [ ] PWA (service worker, offline caching)
- [ ] More Arduino lesson examples (2-3 more)
- [ ] Velxio enhancements (lock components, solution overlay, multi-board)
