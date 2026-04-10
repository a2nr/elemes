# Proposal: Integrasi Velxio sebagai Simulator Mikrokontroler di Elemes LMS

## Daftar Isi

1. [Latar Belakang](#1-latar-belakang)
2. [Keputusan Arsitektur](#2-keputusan-arsitektur)
3. [Arsitektur Integrasi](#3-arsitektur-integrasi)
4. [Format Lesson Markdown](#4-format-lesson-markdown)
5. [PostMessage Bridge Protocol](#5-postmessage-bridge-protocol)
6. [Sistem Evaluasi](#6-sistem-evaluasi)
7. [Modifikasi Velxio (Fork)](#7-modifikasi-velxio-fork)
8. [Modifikasi Elemes](#8-modifikasi-elemes)
9. [Workflow Guru](#9-workflow-guru)
10. [Deployment](#10-deployment)
11. [Lisensi](#11-lisensi)
12. [Roadmap](#12-roadmap)
13. [Pertanyaan Terbuka](#13-pertanyaan-terbuka)

---

## 1. Latar Belakang

### 1.1 Elemes Saat Ini

Elemes adalah LMS untuk mengajar pemrograman dan elektronika. Saat ini mendukung:

- **Mode C** — editor + gcc backend + evaluasi stdout
- **Mode Python** — editor + python exec + evaluasi stdout
- **Mode Circuit** — CircuitJS1 iframe + evaluasi node voltage

Setiap mode menggunakan tab system (info | exercise | editor | circuit | output) dan evaluasi berbasis:
- `expected_output` — stdout matching
- `expected_circuit_output` — node voltage JSON
- `key_text` — keyword wajib di source code

### 1.2 Kebutuhan Baru

Materi Arduino/mikrokontroler membutuhkan kemampuan:
- Menulis dan compile kode Arduino C++
- Simulasi CPU (AVR8) di browser
- Komponen visual interaktif (LED, LCD, sensor, dll)
- Serial Monitor
- Wiring interaktif (siswa merangkai sendiri)

### 1.3 Mengapa Velxio

[Velxio](https://github.com/davidmonterocrespo24/velxio) adalah simulator Arduino open-source yang sudah menyediakan semua kebutuhan di atas:

- 19 board (Arduino Uno/Mega/Nano, ESP32, Pico, dll)
- 48+ komponen visual (wokwi-elements)
- CPU emulation nyata (avr8js, rp2040js)
- Wire system dengan drag-and-drop
- Serial Monitor
- Compile via arduino-cli
- Self-hosted via Docker

Membangun semua ini dari nol membutuhkan ~2-3 minggu. Integrasi Velxio via iframe + postMessage bridge membutuhkan ~3-5 hari.

---

## 2. Keputusan Arsitektur

### 2.1 Velxio Mengambil Alih Workspace (Exclusive Mode)

Ketika lesson mengandung `---INITIAL_CODE_ARDUINO---`, Velxio di-embed sebagai iframe dan **menggantikan** seluruh workspace Elemes. Marker `---INITIAL_CODE---` (C), `---INITIAL_CODE_PYTHON---`, dan tab system yang lama **diabaikan** untuk lesson tersebut.

**Alasan:** Velxio sudah bundle editor + simulator + serial monitor + wire system. Memecahnya ke tab Elemes akan merusak UX dan mempersulit integrasi.

```
Lesson C/Python (existing):
┌────────┬──────────┬──────────┐
│  Info  │  Editor  │  Output  │
│        │ (Elemes) │ (stdout) │
└────────┴──────────┴──────────┘

Lesson Arduino (baru):
┌────────┬───────────────────────────────┐
│  Info  │           Velxio              │
│        │  (editor+sim+serial+wiring)   │
│Exercise│                               │
│        │         [iframe]              │
└────────┴───────────────────────────────┘
```

### 2.2 Initial Circuit via Markdown JSON

Guru mendesain rangkaian di Velxio standalone, export sebagai JSON, lalu paste ke blok `---VELXIO_CIRCUIT---` di lesson markdown. Saat lesson dimuat, Elemes mengirim JSON ini ke Velxio iframe via postMessage.

**Alasan:** Velxio menyimpan project ke database (karena pakai akun), tapi Elemes tidak perlu database — cukup JSON di markdown yang di-serve saat lesson load.

### 2.3 Evaluasi: Serial Output + Key Text + Wiring

Tiga jenis evaluasi yang disepakati:

| Tipe Evaluasi | Objek | Metode |
|---------------|-------|--------|
| **Program** | Serial output (USART) | String matching: actual vs `expected_serial_output` |
| **Program** | Source code | Keyword check: `key_text` ada di source code |
| **Circuit** | Wiring topology | Graph comparison: student wires vs `expected_wiring` |

**Keputusan penting:** IO state (pin HIGH/LOW) **tidak** dievaluasi secara otomatis. LED nyala, servo berputar, dll adalah **feedback visual** bagi siswa — bukan objek evaluasi. Alasannya:

- IO state berubah terhadap waktu (non-deterministic snapshot)
- Evaluasi time-based memerlukan recording + timing CPU cycle (effort tinggi)
- Timing avr8js ≠ wall clock (simulasi bisa lebih cepat dari real-time)
- Guru harus paham timing mikrokontroler untuk menulis expected IO pattern
- Serial output sudah cukup membuktikan program berjalan benar untuk konteks edukasi

### 2.4 Component ID Fixed dari Initial Circuit

Saat guru menyediakan `VELXIO_CIRCUIT`, component ID sudah ditetapkan (`led1`, `r1`, dll). Siswa tidak perlu drag komponen baru — komponen sudah ada di canvas, siswa hanya perlu wiring.

**Alasan:** Evaluasi wiring bergantung pada component ID. Kalau siswa drag komponen sendiri, ID-nya auto-generated dan tidak cocok dengan expected wiring. Dengan ID fixed, evaluasi wiring menjadi deterministik.

---

## 3. Arsitektur Integrasi

### 3.1 Overview

```
┌─────────────────── Browser ───────────────────────┐
│                                                    │
│  ┌─── Elemes (host page) ────────────────────┐    │
│  │                                            │    │
│  │  Lesson Info + Exercise                    │    │
│  │  VelxioBridge.js ◄──── postMessage ──────┐│    │
│  │  Evaluate button                          ││    │
│  │                                           ││    │
│  │  ┌─── Velxio (iframe) ─────────────────┐ ││    │
│  │  │                                     │ ││    │
│  │  │  EmbedBridge.ts ───── postMessage ──┘│ │    │
│  │  │  Monaco Editor (source code)         │ │    │
│  │  │  Simulator Canvas (komponen+wiring)  │ │    │
│  │  │  Serial Monitor (USART output)       │ │    │
│  │  │  Toolbar (Compile/Run/Stop)          │ │    │
│  │  │                                     │  │    │
│  │  └─────────────────────────────────────┘  │    │
│  └────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────┘

┌─────────────────── Docker ────────────────────────┐
│  Elemes container (Flask, port 3000)               │
│  Velxio container (FastAPI + arduino-cli, port 3080│
└────────────────────────────────────────────────────┘
```

### 3.2 Data Flow

```
LESSON LOAD:
  Elemes parse markdown
    → extract INITIAL_CODE_ARDUINO
    → extract VELXIO_CIRCUIT JSON
    → render iframe src="velxio:3080/editor?embed=true"
    → on velxio:ready → send elemes:load_code + elemes:load_circuit

SISWA BEKERJA:
  Siswa edit code di Velxio editor
  Siswa wiring komponen di Velxio canvas
  Siswa klik Run → Velxio compile + simulate internally
  Serial output tampil di Velxio Serial Monitor
  LED nyala, LCD tampil → feedback visual

EVALUASI (klik Submit di Elemes):
  Elemes send elemes:get_source_code → Velxio respond velxio:source_code
  Elemes send elemes:get_serial_log → Velxio respond velxio:serial_log
  Elemes send elemes:get_wires → Velxio respond velxio:wires
  Elemes evaluate:
    1. serial_log vs expected_serial_output
    2. source_code vs key_text
    3. wires vs expected_wiring
  → pass/fail
```

---

## 4. Format Lesson Markdown

### 4.1 Lesson Arduino Murni (Code Only)

```markdown
---LESSON_INFO---
**Learning Objectives:**
- Memahami fungsi setup() dan loop()
- Menggunakan Serial.println()

**Prerequisites:**
- Dasar pemrograman C
---END_LESSON_INFO---

# Serial Hello World

Program pertama Arduino: mencetak teks ke Serial Monitor.

---EXERCISE---
Buat program Arduino yang mencetak "Hello, World!" ke Serial Monitor.
---

---INITIAL_CODE_ARDUINO---
void setup() {
    // Inisialisasi Serial dengan baud rate 9600

}

void loop() {
    // Cetak "Hello, World!" lalu delay 1 detik

}
---END_INITIAL_CODE_ARDUINO---

---EXPECTED_SERIAL_OUTPUT---
Hello, World!
---END_EXPECTED_SERIAL_OUTPUT---

---KEY_TEXT---
Serial.begin
Serial.println
---END_KEY_TEXT---
```

### 4.2 Lesson Arduino + Circuit (Hybrid)

```markdown
---LESSON_INFO---
**Learning Objectives:**
- Mengontrol LED dengan digitalWrite
- Merangkai LED + resistor ke Arduino

**Prerequisites:**
- Serial Hello World
---END_LESSON_INFO---

# Blink LED

Menyalakan dan mematikan LED di pin 13 setiap 500ms.

---EXERCISE---
### Bagian 1: Wiring
Hubungkan komponen sesuai skema:
- Pin 13 → Resistor 220Ω → LED (Anoda) → GND

### Bagian 2: Kode
Buat program yang toggle LED dan cetak status ke Serial Monitor.
---

---INITIAL_CODE_ARDUINO---
void setup() {
    // Inisialisasi pin 13 sebagai OUTPUT
    // Inisialisasi Serial
}

void loop() {
    // Nyalakan LED, cetak "ON", delay 500ms
    // Matikan LED, cetak "OFF", delay 500ms
}
---END_INITIAL_CODE_ARDUINO---

---VELXIO_CIRCUIT---
{
  "board": "arduino:avr:uno",
  "components": [
    {
      "type": "wokwi-led",
      "id": "led1",
      "x": 350, "y": 180,
      "rotation": 0,
      "props": { "color": "red" }
    },
    {
      "type": "wokwi-resistor",
      "id": "r1",
      "x": 280, "y": 180,
      "rotation": 0,
      "props": { "value": "220" }
    }
  ],
  "wires": []
}
---END_VELXIO_CIRCUIT---

---EXPECTED_SERIAL_OUTPUT---
ON
OFF
ON
OFF
---END_EXPECTED_SERIAL_OUTPUT---

---EXPECTED_WIRING---
[
  ["board:13", "r1:1"],
  ["r1:2", "led1:A"],
  ["led1:C", "board:GND"]
]
---END_EXPECTED_WIRING---

---KEY_TEXT---
digitalWrite
delay
Serial.println
pinMode
---END_KEY_TEXT---
```

### 4.3 Lesson Circuit Only (Wiring Tanpa Kode)

```markdown
---LESSON_INFO---
**Learning Objectives:**
- Memahami rangkaian seri LED + resistor
- Memahami fungsi resistor sebagai pembatas arus
---END_LESSON_INFO---

# Rangkaian Dasar LED

Pelajari cara merangkai LED dengan resistor pembatas arus.

---EXERCISE---
Hubungkan rangkaian berikut:
- 5V → Resistor 220Ω → LED → GND
---

---VELXIO_CIRCUIT---
{
  "board": "arduino:avr:uno",
  "components": [
    {
      "type": "wokwi-led",
      "id": "led1",
      "x": 350, "y": 180,
      "props": { "color": "green" }
    },
    {
      "type": "wokwi-resistor",
      "id": "r1",
      "x": 280, "y": 180,
      "props": { "value": "220" }
    }
  ],
  "wires": []
}
---END_VELXIO_CIRCUIT---

---EXPECTED_WIRING---
[
  ["board:5V", "r1:1"],
  ["r1:2", "led1:A"],
  ["led1:C", "board:GND"]
]
---END_EXPECTED_WIRING---
```

Catatan: tidak ada `INITIAL_CODE_ARDUINO` → Velxio di-embed dengan `hideEditor=true`, hanya menampilkan canvas simulator.

### 4.4 Deteksi Mode (Backward Compatible)

```python
# Prioritas mode detection:
# 1. INITIAL_CODE_ARDUINO ada → mode velxio (abaikan INITIAL_CODE, INITIAL_CODE_PYTHON)
# 2. INITIAL_CODE_PYTHON ada  → mode python (existing)
# 3. INITIAL_CODE ada         → mode c (existing)
# 4. INITIAL_CIRCUIT saja     → mode circuit (CircuitJS, existing)
#
# VELXIO_CIRCUIT hanya di-parse jika mode = velxio
# INITIAL_CIRCUIT (CircuitJS format) diabaikan jika mode = velxio
```

### 4.5 Ringkasan Semua Marker

| Marker | Mode | Status |
|--------|------|--------|
| `---INITIAL_CODE---` | C | Existing |
| `---INITIAL_CODE_PYTHON---` | Python | Existing |
| `---INITIAL_CIRCUIT---` | Circuit (CircuitJS) | Existing |
| `---INITIAL_CODE_ARDUINO---` | **Velxio (baru)** | Baru |
| `---VELXIO_CIRCUIT---` | **Velxio (baru)** | Baru |
| `---EXPECTED_OUTPUT---` | C/Python | Existing |
| `---EXPECTED_SERIAL_OUTPUT---` | **Velxio (baru)** | Baru |
| `---EXPECTED_WIRING---` | **Velxio (baru)** | Baru |
| `---EXPECTED_CIRCUIT_OUTPUT---` | Circuit (CircuitJS) | Existing |
| `---KEY_TEXT---` | Semua mode | Existing |
| `---LESSON_INFO---` | Semua mode | Existing |
| `---EXERCISE---` | Semua mode | Existing |

---

## 5. PostMessage Bridge Protocol

### 5.1 Elemes → Velxio (Commands)

| Message Type | Payload | Kapan Dikirim |
|-------------|---------|---------------|
| `elemes:load_code` | `{ files: [{ name, content }] }` | Saat lesson load |
| `elemes:load_circuit` | `{ board, components, wires }` | Saat lesson load |
| `elemes:compile_and_run` | `{}` | Opsional: trigger dari Elemes |
| `elemes:stop` | `{}` | Opsional: stop dari Elemes |
| `elemes:reset` | `{}` | Opsional: reset simulation |
| `elemes:get_source_code` | `{}` | Saat evaluasi (submit) |
| `elemes:get_serial_log` | `{}` | Saat evaluasi (submit) |
| `elemes:get_wires` | `{}` | Saat evaluasi (submit) |
| `elemes:set_embed_mode` | `{ hideEditor?, hideAuth?, hideToolbar? }` | Saat iframe load |

### 5.2 Velxio → Elemes (Events/Responses)

| Message Type | Payload | Kapan Dikirim |
|-------------|---------|---------------|
| `velxio:ready` | `{ version }` | Saat Velxio iframe selesai load |
| `velxio:source_code` | `{ files: [{ name, content }] }` | Response ke `get_source_code` |
| `velxio:serial_log` | `{ log: string }` | Response ke `get_serial_log` |
| `velxio:wires` | `{ wires: [{ start, end, signalType }] }` | Response ke `get_wires` |
| `velxio:compile_result` | `{ success, errors? }` | Setelah compile selesai |
| `velxio:sim_start` | `{}` | Saat simulation mulai |
| `velxio:sim_stop` | `{}` | Saat simulation berhenti |

### 5.3 Sequence Diagram: Load Lesson

```
Elemes                          Velxio (iframe)
  │                                  │
  │  render iframe                   │
  │  src="velxio/editor?embed=true"  │
  │ ────────────────────────────────>│
  │                                  │
  │         velxio:ready             │
  │ <────────────────────────────────│
  │                                  │
  │  elemes:set_embed_mode           │
  │  {hideAuth:true}                 │
  │ ────────────────────────────────>│
  │                                  │
  │  elemes:load_circuit             │
  │  {board, components, wires:[]}   │
  │ ────────────────────────────────>│  → inject ke useSimulatorStore
  │                                  │
  │  elemes:load_code                │
  │  {files:[{name:"sketch.ino",     │
  │    content:"void setup()..."}]}  │
  │ ────────────────────────────────>│  → inject ke useEditorStore
  │                                  │
  │  (siswa bekerja...)              │
```

### 5.4 Sequence Diagram: Evaluasi

```
Elemes                          Velxio (iframe)
  │                                  │
  │ [Siswa klik Submit]              │
  │                                  │
  │  elemes:get_source_code          │
  │ ────────────────────────────────>│
  │         velxio:source_code       │
  │ <────────────────────────────────│
  │                                  │
  │  elemes:get_serial_log           │
  │ ────────────────────────────────>│
  │         velxio:serial_log        │
  │ <────────────────────────────────│
  │                                  │
  │  elemes:get_wires                │
  │ ────────────────────────────────>│
  │         velxio:wires             │
  │ <────────────────────────────────│
  │                                  │
  │  [Elemes evaluasi lokal]         │
  │  ✓ serial_log vs expected        │
  │  ✓ source_code vs key_text       │
  │  ✓ wires vs expected_wiring      │
  │  → PASS / FAIL                   │
```

---

## 6. Sistem Evaluasi

### 6.1 Serial Output Matching

Membandingkan akumulasi output USART selama simulasi berjalan dengan `expected_serial_output`.

```python
# Pseudocode evaluasi
def evaluate_serial(actual_log: str, expected: str) -> bool:
    actual_lines = actual_log.strip().splitlines()
    expected_lines = expected.strip().splitlines()

    # Cek: expected lines harus muncul di actual (in order)
    # Actual boleh lebih panjang (program terus loop)
    j = 0
    for line in actual_lines:
        if j < len(expected_lines) and line.strip() == expected_lines[j].strip():
            j += 1
        if j == len(expected_lines):
            return True
    return j == len(expected_lines)
```

**Catatan:** Evaluasi subsequence, bukan exact match — karena program Arduino biasanya loop terus, serial output bisa lebih panjang dari expected.

### 6.2 Key Text Check

Sama dengan sistem yang sudah ada di Elemes — cek apakah keyword wajib ada di source code.

```python
def evaluate_key_text(source_code: str, keywords: list[str]) -> bool:
    return all(kw in source_code for kw in keywords)
```

### 6.3 Wiring Topology Check

Membandingkan koneksi wire siswa vs expected wiring sebagai **undirected graph edges**.

```javascript
function evaluateWiring(studentWires, expectedConnections) {
  // Normalize setiap wire menjadi sorted pair string
  const normalize = (a, b) => [a, b].sort().join('↔');

  const studentEdges = new Set(
    studentWires.map(w => normalize(
      `${w.start.componentId}:${w.start.pinName}`,
      `${w.end.componentId}:${w.end.pinName}`
    ))
  );

  const expectedEdges = expectedConnections.map(
    ([a, b]) => normalize(a, b)
  );

  // Semua expected edge harus ada di student wiring
  const allPresent = expectedEdges.every(e => studentEdges.has(e));

  // Opsional: tidak boleh ada wire berlebih (strict mode)
  // const noExtra = studentEdges.size === expectedEdges.length;

  return allPresent;
}
```

**Keputusan:** Evaluasi hanya cek expected edges **ada** di student wiring. Wire berlebih (misalnya siswa tambah wire extra) **tidak** menyebabkan fail. Ini lebih forgiving untuk konteks edukasi.

### 6.4 Kombinasi Evaluasi Per Tipe Lesson

| Tipe Lesson | Serial | Key Text | Wiring | Lulus jika |
|-------------|--------|----------|--------|-----------|
| Code only | ✓ | ✓ | — | Serial + Key Text pass |
| Circuit only | — | — | ✓ | Wiring pass |
| Hybrid | ✓ | ✓ | ✓ | Semua pass |

---

## 7. Modifikasi Velxio (Fork)

### 7.1 File Baru

| File | Deskripsi | LOC estimasi |
|------|-----------|-------------|
| `frontend/src/services/EmbedBridge.ts` | PostMessage bridge terpusat: kirim event, terima command, dispatch ke store | ~150 |

### 7.2 File yang Dimodifikasi

| # | File | Modifikasi | LOC estimasi |
|---|------|-----------|-------------|
| 1 | `frontend/src/simulation/AVRSimulator.ts` | Akumulasi serial output ke buffer, expose `getSerialLog()` | ~15 |
| 2 | `frontend/src/store/useSimulatorStore.ts` | (a) Tambah action `loadCircuit(data)` untuk inject components+wires dari JSON. (b) Tambah action `getWires()` return current wires. (c) Init EmbedBridge saat store create. | ~40 |
| 3 | `frontend/src/store/useEditorStore.ts` | Tambah action `loadFiles(files)` untuk inject code dari parent (sudah ada `loadFiles` — tinggal expose ke bridge) | ~10 |
| 4 | `frontend/src/pages/EditorPage.tsx` | Parse query param `?embed=true`, hide AppHeader, hide auth UI, hide save/login modal, opsional hide editor/sidebar | ~30 |
| 5 | `frontend/src/components/editor/EditorToolbar.tsx` | Tambah tombol "Export Circuit JSON" (copy to clipboard). Hanya tampil di non-embed mode (untuk workflow guru). | ~15 |
| 6 | `frontend/vite.config.ts` | Opsional: konfigurasi CSP header untuk iframe embedding | ~5 |

**Total modifikasi: ~265 LOC**

### 7.3 Detail: EmbedBridge.ts

```typescript
// frontend/src/services/EmbedBridge.ts

import { useSimulatorStore } from '../store/useSimulatorStore';
import { useEditorStore } from '../store/useEditorStore';

class EmbedBridge {
  private isEmbedded: boolean;

  constructor() {
    this.isEmbedded = window.parent !== window;
    if (this.isEmbedded) {
      window.addEventListener('message', this.onMessage.bind(this));
    }
  }

  // Dipanggil setelah Velxio fully loaded
  notifyReady() {
    this.send('velxio:ready', { version: '1.0' });
  }

  private send(type: string, payload: any = {}) {
    if (!this.isEmbedded) return;
    window.parent.postMessage({ type, ...payload }, '*');
  }

  private onMessage(event: MessageEvent) {
    const { type } = event.data || {};
    if (!type?.startsWith('elemes:')) return;

    switch (type) {
      case 'elemes:load_code':
        useEditorStore.getState().loadFiles(
          event.data.files.map((f: any) => ({
            id: f.name,
            name: f.name,
            content: f.content,
            modified: false
          }))
        );
        break;

      case 'elemes:load_circuit':
        useSimulatorStore.getState().loadCircuit(event.data);
        break;

      case 'elemes:get_source_code':
        const files = useEditorStore.getState().files;
        this.send('velxio:source_code', {
          files: files.map(f => ({ name: f.name, content: f.content }))
        });
        break;

      case 'elemes:get_serial_log':
        const log = useSimulatorStore.getState().getSerialLog();
        this.send('velxio:serial_log', { log });
        break;

      case 'elemes:get_wires':
        const wires = useSimulatorStore.getState().wires;
        this.send('velxio:wires', { wires });
        break;

      case 'elemes:set_embed_mode':
        // Dispatch ke EditorPage via global state atau event
        window.dispatchEvent(
          new CustomEvent('velxio-embed-mode', { detail: event.data })
        );
        break;

      case 'elemes:compile_and_run':
        // Trigger compile + run programmatically
        break;

      case 'elemes:stop':
        useSimulatorStore.getState().stopSimulation();
        break;
    }
  }
}

export const embedBridge = new EmbedBridge();
```

### 7.4 Detail: Export Circuit JSON (Workflow Guru)

```typescript
// Tambah di EditorToolbar.tsx

function exportCircuitJSON() {
  const { components, wires } = useSimulatorStore.getState();
  const board = /* current selected board FQBN */;

  const circuitData = {
    board,
    components: components.map(c => ({
      type: c.type,
      id: c.id,
      x: c.x,
      y: c.y,
      rotation: c.rotation || 0,
      props: c.props || {}
    })),
    wires: wires.map(w => ({
      start: { componentId: w.start.componentId, pinName: w.start.pinName },
      end: { componentId: w.end.componentId, pinName: w.end.pinName },
      signalType: w.signalType
    }))
  };

  const json = JSON.stringify(circuitData, null, 2);
  navigator.clipboard.writeText(json);
  alert('Circuit JSON copied to clipboard!');
}
```

Guru juga bisa export expected wiring:

```typescript
function exportExpectedWiring() {
  const { wires } = useSimulatorStore.getState();
  const wiringArray = wires.map(w => [
    `${w.start.componentId}:${w.start.pinName}`,
    `${w.end.componentId}:${w.end.pinName}`
  ]);
  const json = JSON.stringify(wiringArray, null, 2);
  navigator.clipboard.writeText(json);
  alert('Expected wiring JSON copied to clipboard!');
}
```

---

## 8. Modifikasi Elemes

### 8.1 File Baru

| File | Deskripsi |
|------|-----------|
| `frontend/src/lib/services/velxio-bridge.js` | PostMessage bridge sisi Elemes: kirim command, terima response, evaluasi |

### 8.2 File yang Dimodifikasi

| # | File | Modifikasi |
|---|------|-----------|
| 1 | `services/lesson_service.py` | Parse marker baru: `INITIAL_CODE_ARDUINO`, `VELXIO_CIRCUIT`, `EXPECTED_SERIAL_OUTPUT`, `EXPECTED_WIRING` |
| 2 | `routes/lessons.py` | Serve field Arduino/Velxio ke frontend JSON response |
| 3 | `frontend/src/routes/lesson/[slug]/+page.svelte` | Conditional render: jika mode=velxio → render iframe + VelxioBridge, else → existing UI |
| 4 | `podman-compose.yml` | Tambah Velxio service |

### 8.3 Detail: VelxioBridge.js

```javascript
// frontend/src/lib/services/velxio-bridge.js

export class VelxioBridge {
  constructor(iframe) {
    this.iframe = iframe;
    this.pending = {};  // pending request-response
    this.serialLog = '';
    this._onReady = null;

    window.addEventListener('message', this._onMessage.bind(this));
  }

  // === Lifecycle ===

  onReady(callback) { this._onReady = callback; }

  destroy() {
    window.removeEventListener('message', this._onMessage.bind(this));
  }

  // === Commands ===

  loadCode(files) {
    this._send('elemes:load_code', { files });
  }

  loadCircuit(circuitData) {
    this._send('elemes:load_circuit', circuitData);
  }

  setEmbedMode(options) {
    this._send('elemes:set_embed_mode', options);
  }

  // === Evaluation ===

  async evaluate(expected) {
    const results = {};

    // 1. Source code → key text
    if (expected.key_text) {
      const { files } = await this._request('elemes:get_source_code', 'velxio:source_code');
      const allCode = files.map(f => f.content).join('\n');
      results.key_text = expected.key_text.every(kw => allCode.includes(kw));
    }

    // 2. Serial output
    if (expected.serial_output) {
      const { log } = await this._request('elemes:get_serial_log', 'velxio:serial_log');
      results.serial = this._matchSerial(log, expected.serial_output);
    }

    // 3. Wiring
    if (expected.wiring) {
      const { wires } = await this._request('elemes:get_wires', 'velxio:wires');
      results.wiring = this._matchWiring(wires, expected.wiring);
    }

    results.pass = Object.values(results)
      .filter(v => typeof v === 'boolean')
      .every(Boolean);

    return results;
  }

  // === Internal ===

  _send(type, payload = {}) {
    this.iframe.contentWindow.postMessage({ type, ...payload }, '*');
  }

  _request(sendType, expectType) {
    return new Promise((resolve) => {
      this.pending[expectType] = resolve;
      this._send(sendType);
      // Timeout safety
      setTimeout(() => {
        if (this.pending[expectType]) {
          delete this.pending[expectType];
          resolve(null);
        }
      }, 3000);
    });
  }

  _onMessage(event) {
    const { type } = event.data || {};
    if (!type?.startsWith('velxio:')) return;

    if (type === 'velxio:ready' && this._onReady) {
      this._onReady();
    }

    if (this.pending[type]) {
      this.pending[type](event.data);
      delete this.pending[type];
    }
  }

  _matchSerial(actual, expected) {
    const actualLines = actual.trim().split('\n').map(l => l.trim());
    const expectedLines = expected.trim().split('\n').map(l => l.trim());
    let j = 0;
    for (const line of actualLines) {
      if (j < expectedLines.length && line === expectedLines[j]) j++;
      if (j === expectedLines.length) return true;
    }
    return j === expectedLines.length;
  }

  _matchWiring(studentWires, expectedPairs) {
    const norm = (a, b) => [a, b].sort().join('↔');
    const studentEdges = new Set(
      studentWires.map(w =>
        norm(
          `${w.start.componentId}:${w.start.pinName}`,
          `${w.end.componentId}:${w.end.pinName}`
        )
      )
    );
    return expectedPairs.every(([a, b]) => studentEdges.has(norm(a, b)));
  }
}
```

---

## 9. Workflow Guru

### 9.1 Membuat Lesson Arduino + Circuit

```
1. Buka Velxio standalone (http://localhost:3080)

2. Pilih board (Arduino Uno)

3. Tambah komponen dari Component Picker
   - Drag LED ke canvas
   - Drag Resistor ke canvas
   - Atur posisi

4. Wiring rangkaian (sebagai contoh jawaban)
   - Pin 13 → Resistor → LED → GND

5. Klik "Export Circuit JSON" (tombol baru di fork)
   → JSON component+wires ter-copy ke clipboard
   → Ini jadi isi blok ---VELXIO_CIRCUIT---

6. Klik "Export Expected Wiring" (tombol baru di fork)
   → JSON edges ter-copy ke clipboard
   → Ini jadi isi blok ---EXPECTED_WIRING---

7. Hapus semua wires (biarkan komponen saja)

8. Klik "Export Circuit JSON" lagi
   → JSON tanpa wires ter-copy ke clipboard
   → Ini jadi isi blok ---VELXIO_CIRCUIT--- yang sebenarnya
     (komponen ada, wires kosong — siswa yang harus wiring)

9. Buka file lesson.md
   - Paste VELXIO_CIRCUIT (tanpa wires)
   - Paste EXPECTED_WIRING (dari langkah 6)
   - Tulis INITIAL_CODE_ARDUINO
   - Tulis EXPECTED_SERIAL_OUTPUT
   - Tulis KEY_TEXT

10. Jalankan ./elemes.sh generatetoken → update CSV

11. Test lesson sebagai siswa
```

### 9.2 Membuat Lesson Code Only (Tanpa Wiring)

```
1. Buka file lesson.md
2. Tulis INITIAL_CODE_ARDUINO (tanpa VELXIO_CIRCUIT)
3. Tulis EXPECTED_SERIAL_OUTPUT
4. Tulis KEY_TEXT
5. Selesai — Velxio akan embed tanpa circuit canvas
```

---

## 10. Deployment

### 10.1 Docker Compose

```yaml
# podman-compose.yml
version: '3.8'

services:
  elemes:
    build: ./elemes
    ports:
      - "3000:3000"
    volumes:
      - ../content:/app/content:ro
      - ../assets:/app/assets:ro
      - ../tokens_siswa.csv:/app/tokens.csv
    environment:
      - VELXIO_URL=http://localhost:3080

  velxio:
    image: ghcr.io/a2nr/velxio-elemes:latest
    # atau: build dari fork
    # build: ./velxio-fork
    ports:
      - "3080:80"
    environment:
      - SECRET_KEY=embed-only-no-auth-needed
```

### 10.2 Nginx/Caddy Reverse Proxy (Opsional)

Jika mau serve kedua service di satu domain:

```
https://lms.sekolah.id/        → Elemes
https://lms.sekolah.id/velxio/ → Velxio (iframe src)
```

### 10.3 Image Size

| Container | Estimasi Size |
|-----------|---------------|
| Elemes | ~200MB (Python + gcc) |
| Velxio | ~1.5GB (Node + Python + arduino-cli + avr core) |
| Total | ~1.7GB |

Velxio image besar karena arduino-cli + platform cores. Ini satu kali download, compile berjalan lokal.

---

## 11. Lisensi

### 11.1 Velxio: AGPLv3

Velxio menggunakan dual licensing:
- AGPLv3 untuk personal/educational/open-source
- Commercial license untuk proprietary/SaaS

**Implikasi untuk Elemes:**

Elemes di-deploy secara self-hosted (Podman + Tailscale) untuk lingkungan sekolah, bukan sebagai SaaS publik. Dalam konteks ini:

- AGPLv3 mengharuskan: jika Velxio dimodifikasi dan di-deploy sebagai network service, source code modifikasi harus tersedia.
- Solusi: **Fork publik** di Gitea/GitHub. Semua modifikasi EmbedBridge sudah open source.

### 11.2 Library Inti: MIT

| Library | Lisensi | Dipakai oleh |
|---------|---------|-------------|
| avr8js | MIT | Velxio (internal) |
| wokwi-elements | MIT | Velxio (internal) |
| rp2040js | MIT | Velxio (internal) |

Tidak ada masalah lisensi tambahan dari library inti.

---

## 12. Roadmap

### Fase 1: Velxio Fork + Embed Mode (3 hari)

- [ ] Fork Velxio repository
- [ ] Implementasi `EmbedBridge.ts`
- [ ] Modifikasi `EditorPage.tsx` — embed mode (hide auth/header)
- [ ] Modifikasi `useSimulatorStore.ts` — `loadCircuit()` action
- [ ] Akumulasi serial log di `AVRSimulator.ts`
- [ ] Tombol "Export Circuit JSON" + "Export Expected Wiring" di toolbar
- [ ] Build Docker image fork
- [ ] Test: load circuit via postMessage, ambil serial log, ambil wires

### Fase 2: Elemes Integration (2 hari)

- [ ] `VelxioBridge.js` — bridge sisi Elemes
- [ ] `lesson_service.py` — parse marker baru
- [ ] `routes/lessons.py` — serve field Arduino
- [ ] `lesson/[slug]/+page.svelte` — conditional render iframe
- [ ] Evaluasi: serial + key_text + wiring
- [ ] Update `podman-compose.yml`
- [ ] Test end-to-end: lesson load → siswa wiring + coding → submit → evaluate

### Fase 3: Content + Polish (2 hari)

- [ ] Buat 3 contoh lesson Arduino (Hello Serial, Blink LED, Button Input)
- [ ] Buat 2 contoh lesson circuit-only (LED circuit, Voltage divider)
- [ ] Update `examples/` folder
- [ ] Update `elemes.sh init` untuk include contoh Arduino
- [ ] Update README guru
- [ ] Test sebagai "guru" dan "siswa"

### Fase 4: Enhancement (Opsional, Nanti)

- [ ] Velxio embed: preselect board dari URL param
- [ ] Velxio embed: lock komponen (siswa tidak bisa drag/delete)
- [ ] Velxio embed: disable component picker (siswa tidak bisa tambah komponen baru)
- [ ] Lesson review mode: tampilkan solution wiring overlay
- [ ] Multiple board support per lesson
- [ ] Library management dari Elemes (install Arduino library)

---

## 13. Keputusan (Resolved)

### 13.1 Pin Naming Convention

**Keputusan:** Ditentukan setelah Velxio fork berjalan. Buat rangkaian test, wiring manual, inspect `wire.start.pinName` / `wire.end.pinName` di console, lalu tulis konvensi berdasarkan observasi.

### 13.2 Strict vs Lenient Wiring Evaluation

**Keputusan: Lenient.** Expected wires harus ada di student wiring, wire berlebih OK. Tanpa `FORBIDDEN_WIRING` untuk tahap awal — bisa ditambah di Fase 4 jika dibutuhkan.

### 13.3 Embed URL: Same Origin via Tailscale Serve

**Keputusan: Same-origin.** Velxio di-proxy lewat Tailscale Serve di path `/velxio/`, sehingga satu domain dengan Elemes. Tidak perlu origin validation atau konfigurasi CSP.

Tambah handler di `config/sinau-c-tail.json`:
```json
"/velxio/": {
  "Proxy": "http://velxio:3080/"
}
```

Iframe src di Elemes: `<iframe src="/velxio/editor?embed=true" />`

### 13.4 Board Selection

**Keputusan: Force board dari `VELXIO_CIRCUIT` JSON.** Hide board selector di embed mode. Board di-set otomatis via `elemes:load_circuit`.

### 13.5 Velxio Compile Dependency

**Keputusan: Compile tetap di Velxio backend.** Tidak duplikasi ke Elemes. Siswa klik Run di Velxio → compile + simulate semuanya internal di Velxio.

### 13.6 Apakah Siswa Boleh Menambah Komponen Sendiri?

**Keputusan: Disable component picker di embed mode.** Komponen sudah pre-loaded dari `VELXIO_CIRCUIT`, siswa hanya bisa wiring. Menjaga evaluasi deterministik (fixed component IDs). Mode open sandbox bisa ditambah di Fase 4.

### 13.7 Bagaimana Kalau Velxio Container Down?

**Keputusan: Tampilkan fallback message.** Timeout 10 detik menunggu `velxio:ready`. Jika tidak ada response, tampilkan pesan: "Simulator Arduino sedang tidak tersedia. Hubungi guru jika masalah berlanjut." Lesson C/Python tetap berfungsi normal.

### 13.8 Serial Output: Kapan Mulai Record?

**Keputusan: Reset setiap kali Run.** Evaluasi berdasarkan serial log dari run terakhir. Konsisten dengan behavior Elemes saat ini (output panel di-clear setiap Run).

