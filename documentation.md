# Elemes LMS — Dokumentasi Teknis

**Project:** LMS-C (Learning Management System untuk Pemrograman C)
**Terakhir diupdate:** 30 Maret 2026

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
  ├── CircuitJS simulator (iframe, GWT-compiled)
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
            │   │   ├── CircuitEditor.svelte  # CircuitJS iframe wrapper
            │   │   ├── CrosshairOverlay.svelte # Touch precision overlay (fat finger fix)
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
            │       ├── compiler.ts
            │       └── circuitjs.ts         # CircuitJSApi interface
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
                ├── manifest.json           # PWA manifest
                └── circuitjs1/             # CircuitJS simulator (GWT-compiled)
                    ├── circuitjs.html      # GWT entry point (loaded in iframe)
                    ├── lz-string.min.js    # LZ compression (circuit export)
                    └── circuitjs1/         # GWT compiled output
                        ├── *.cache.js      # Compiled permutations
                        ├── circuitjs1.nocache.js  # Bootstrap loader
                        └── circuits/       # Bundled example circuits
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

### Kenapa transparent overlay untuk touch, bukan inject ke iframe?
CircuitJS adalah GWT-compiled app — tidak bisa modify source code-nya. Alternatif lain:
- **Inject script via `contentDocument`**: Fragile, GWT overwrite DOM handlers.
- **PostMessage**: Tidak bisa dispatch native MouseEvent dari luar.
- **Transparent overlay**: Intercept PointerEvent di parent, konversi ke MouseEvent, dispatch ke iframe via `contentDocument.elementFromPoint()`. Paling reliable karena tidak bergantung pada internal CircuitJS.

Overlay dinonaktifkan (`pointer-events: none`) di desktop sehingga mouse events langsung tembus ke iframe tanpa overhead.

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

## CircuitJS Integration

Integrasi Falstad CircuitJS1 sebagai simulator rangkaian interaktif di dalam tab "Circuit" pada halaman lesson. CircuitJS adalah aplikasi GWT (Java → JavaScript) yang di-embed via iframe same-origin.

### Arsitektur

```
content/z_test_circuit.md
  │  ---INITIAL_CIRCUIT--- ... ---END_INITIAL_CIRCUIT---
  │
  ▼  lesson_service.py: _extract_section()
Flask API (/api/lesson/<slug>.json)
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

### File-file Utama

| File | Fungsi |
|------|--------|
| `frontend/static/circuitjs1/circuitjs.html` | GWT entry point, di-load dalam iframe |
| `frontend/static/circuitjs1/circuitjs1/circuitjs1.nocache.js` | GWT bootstrap — memilih permutation `.cache.js` berdasarkan browser |
| `frontend/static/circuitjs1/lz-string.min.js` | Kompresi LZ untuk circuit text export |
| `frontend/src/lib/components/CircuitEditor.svelte` | Wrapper iframe + API bridge |
| `frontend/src/lib/components/CrosshairOverlay.svelte` | Touch precision overlay |
| `services/lesson_service.py` | Parsing markdown, ekstraksi `---INITIAL_CIRCUIT---` |
| `routes/lessons.py` | API endpoint, serve `initial_circuit` ke frontend |
| `frontend/src/routes/lesson/[slug]/+page.svelte` | Evaluasi rangkaian (`evaluateCircuit()`) |

### CircuitJS API (via `iframe.contentWindow.CircuitJS1`)

API object didapatkan melalui callback `window.oncircuitjsloaded` yang dipanggil oleh GWT setelah inisialisasi, dengan fallback 3 detik via `window.CircuitJS1`.

| Method | Fungsi |
|--------|--------|
| `importCircuit(text, showMessage)` | Load circuit dari text |
| `exportCircuit()` | Ekspor circuit saat ini sebagai text |
| `getNodeVoltage(nodeName)` | Query tegangan di named node |
| `setSimRunning(bool)` | Jalankan/hentikan simulasi |
| `updateCircuit()` | Redraw setelah perubahan |
| `elements()` | Jumlah elemen di circuit (belum dipakai) |
| `getElm(index)` | Ambil elemen berdasarkan index (belum dipakai) |

### Circuit Text Format

CircuitJS menggunakan format XML-like custom. Contoh dari `content/z_test_circuit.md`:

```xml
<cir f="1" ts="0.000005" ic="10.20027730826997" cb="50" pb="50" vr="5" mts="5e-11">
  <v x="80 200 80 112" f="0" wf="0" maxv="5"/>    <!-- Voltage source 5V -->
  <r x="80 112 176 112" f="0" r="1000"/>           <!-- Resistor 1kΩ -->
  <r x="176 112 176 200" f="0" r="1000"/>          <!-- Resistor 1kΩ -->
  <w x="176 200 80 200" f="0"/>                     <!-- Wire -->
  <ln x="176 112 208 32" f="0" te="TestPoint_A"/>  <!-- Named node (label) -->
</cir>
```

### Evaluasi Rangkaian

Saat siswa klik "Cek Rangkaian", fungsi `evaluateCircuit()` di `+page.svelte` menjalankan validasi:

| Langkah | Mekanisme | Sumber Data |
|---------|-----------|-------------|
| 1. Parse kriteria | `JSON.parse(data.expected_output)` | Markdown `---EXPECTED_OUTPUT---` |
| 2. Cek tegangan node | `simApi.getNodeVoltage(nodeName)` vs expected ± tolerance | `expected_output.nodes` |
| 3. Cek komponen wajib | `circuitEditor.getCircuitText()` → `checkKeyText()` (string contains) | Markdown `---KEY_TEXT---` |
| 4. Track progress | `POST /api/track-progress` (jika semua passed) | Auth token |

**Expected Output JSON Format:**

```json
{
  "nodes": {
    "TestPoint_A": { "voltage": 2.5, "tolerance": 0.2 }
  },
  "elements": {}
}
```

### Lesson Markdown Format (Circuit)

Section-section yang dikenali oleh `lesson_service.py` untuk lesson circuit:

| Section | Fungsi |
|---------|--------|
| `---INITIAL_CIRCUIT---` ... `---END_INITIAL_CIRCUIT---` | Circuit text awal yang dimuat ke simulator |
| `---SOLUTION_CIRCUIT---` ... `---END_SOLUTION_CIRCUIT---` | Solusi (ditampilkan setelah lesson selesai) |
| `---EXPECTED_OUTPUT---` ... `---END_EXPECTED_OUTPUT---` | JSON kriteria evaluasi (node voltages) |
| `---KEY_TEXT---` ... `---END_KEY_TEXT---` | Teks/komponen wajib (string matching pada circuit text) |
| `---EXERCISE---` | Instruksi untuk siswa (di bawah separator ini) |

Keberadaan `---INITIAL_CIRCUIT---` secara otomatis menambahkan `'circuit'` ke `active_tabs[]`, yang menampilkan tab Circuit di halaman lesson.

### Auto-save

`CircuitEditor` mendukung auto-save ke `sessionStorage` (polling setiap 5 detik):

- **Key:** `elemes_circuit_{slug}` (hanya saat user login & bukan mode solusi)
- **Restore:** Saat load, cek sessionStorage dulu, fallback ke `initialCircuit` prop
- **Export:** `simApi.exportCircuit()` → bandingkan dengan saved → simpan jika berbeda

### Catatan Teknis

- **GWT tidak butuh build step**: File `.cache.js` sudah ter-compile. Copy as-is ke `frontend/static/`.
- **Same-origin wajib**: `contentDocument` access membutuhkan iframe same-origin. CircuitJS di-serve dari `/circuitjs1/` path di SvelteKit static.
- **Callback discovery**: GWT memanggil `window.oncircuitjsloaded(api)` setelah inisialisasi. Ini lebih reliable daripada polling `window.CircuitJS1` yang mungkin belum tersedia.
- **TypeScript interface**: `CircuitJSApi` di `types/circuitjs.ts` mengetik semua method yang digunakan. `simApi` bertipe `CircuitJSApi | null`, bukan `any`.
- **Auto-save cleanup**: `setInterval` untuk auto-save di-cleanup via `$effect` return saat komponen destroy, mencegah memory leak.

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

## Touch Crosshair System (Fat Finger Fix)

Sistem overlay untuk memberikan presisi interaksi di iframe CircuitJS pada perangkat sentuh. Aktif hanya pada touch device (deteksi via CSS media query `hover: none` + `pointer: coarse`), tidak mengganggu interaksi mouse di desktop.

**File:** `frontend/src/lib/components/CrosshairOverlay.svelte`
**Dimount di:** `frontend/src/lib/components/CircuitEditor.svelte`

### Gesture Mapping

| Gesture | Action | Keterangan |
|---------|--------|------------|
| Single tap | `click` | Delay 300ms (menunggu double/triple). Termasuk toolbar CircuitJS |
| Double tap | `dblclick` | Edit komponen (buka dialog edit di CircuitJS) |
| Triple tap | Right-click (`contextmenu`) | Fallback untuk right-click satu jari |
| Two-finger tap | Right-click (`contextmenu`) | Gesture natural untuk right-click |
| Long tap (400ms) | Crosshair aiming mode | 4-phase state machine untuk presisi drag |

### State Machine (Crosshair Aiming)

```
idle → [long tap] → aiming_start (crosshair muncul, belum click)
                         │
                    [release] → holding (mousedown dispatch di posisi crosshair)
                                    │                          │
                              [long tap] → aiming_end    [5s timeout]
                                    │          │               │
                                    │     [release]            ▼
                                    │          │          mouseup + idle
                                    │          ▼
                                    │        idle (mouseup dispatch)
                                    │
                              [short tap] → mouseup + idle
```

### Cara Kerja Event Forwarding

| Layer | Mekanisme | Tujuan |
|-------|-----------|--------|
| Overlay | `<div>` transparan dengan `pointer-events: auto` (touch only) | Intercept semua touch event sebelum iframe |
| Koordinat | `getBoundingClientRect()` → konversi viewport ke iframe-local | Akurasi posisi di dalam iframe |
| Target | `iframe.contentDocument.elementFromPoint(x, y)` | Temukan elemen yang tepat (canvas, toolbar, dialog) |
| Dispatch | `new MouseEvent()` dengan `view: iframe.contentWindow` | GWT CircuitJS menerima event seolah native |
| Focus | `focusIfEditable()` → `.focus()` pada input/textarea | Virtual keyboard muncul saat tap text field |

### Konfigurasi

| Variable | Default | Lokasi | Fungsi |
|----------|---------|--------|--------|
| `PUBLIC_CURSOR_OFFSET_Y` | `50` | `podman-compose.yml` | Offset Y crosshair dari posisi jari (pixel). Semakin besar, crosshair semakin jauh di atas jari |

### Konstanta Internal

| Nama | Nilai | Fungsi |
|------|-------|--------|
| `LONG_PRESS_MS` | 400ms | Durasi tahan untuk aktifkan crosshair |
| `DOUBLE_TAP_MS` | 300ms | Window waktu antara tap untuk deteksi double/triple |
| `HOLDING_TIMEOUT_MS` | 5000ms | Safety net — auto-mouseup jika terjebak di holding state |

### Limitasi

- **Single tap delay 300ms**: Trade-off untuk membedakan single/double/triple tap. Tidak bisa dihindari tanpa mengorbankan multi-tap detection.
- **Synthetic focus**: Virtual keyboard mungkin tidak muncul di semua browser karena `.focus()` pada elemen di dalam iframe tidak selalu dianggap "user gesture" oleh browser.
- **Same-origin only**: `contentDocument` access membutuhkan iframe same-origin. CircuitJS di-serve dari path yang sama (`/circuitjs1/`), jadi ini bukan masalah.

---

## Status Implementasi

- [x] **Phase 0:** Backend decomposition (monolith → Blueprints + services)
- [x] **Phase 1:** SvelteKit scaffolding (adapter-node, TypeScript, path aliases)
- [x] **Phase 2:** Core components (CodeEditor, Navbar, auth/theme stores, API client)
- [x] **Phase 3:** Pages (Home, Lesson, Progress) + SSR data loading
- [x] **Phase 5:** Containerization (3-container setup, static IPs, API proxy)
- [ ] **Phase 4:** PWA (service worker, offline caching, icons)
- [ ] **Phase 6:** Polish (Tailscale config update, testing)
