# Proposal: Integrasi AVR8js (Simulator Mikrokontroler AVR) ke Elemes LMS

## Pendahuluan

Dokumen ini merupakan proposal untuk mengintegrasikan **[avr8js](https://github.com/wokwi/avr8js)** — sebuah simulator mikrokontroler AVR 8-bit berbasis JavaScript — ke dalam ekosistem Elemes LMS. Referensi implementasi diambil dari **[Falstad Circuit Simulator + AVR8js](https://www.falstad.com/circuit/avr8js/index.html)**.

Tujuannya: siswa dapat menulis kode C/Arduino, meng-compile, dan mensimulasikan eksekusi pada mikrokontroler virtual — lengkap dengan koneksi ke simulator rangkaian CircuitJS1 yang sudah ada.

---

## 1. Apakah Memerlukan Compile Custom?

**Ya, memerlukan kompilasi khusus.**

AVR8js adalah *execution engine* saja — ia menjalankan machine code AVR yang sudah dikompilasi (format Intel HEX). Library ini **tidak menyertakan compiler**. Oleh karena itu:

| Aspek | Penjelasan |
|-------|-----------|
| **Compiler yang dibutuhkan** | `avr-gcc` (toolchain AVR), bukan `gcc` biasa |
| **Solusi yang dipilih** | **PlatformIO** — mengelola `avr-gcc` + Arduino core secara otomatis |
| **Lokasi kompilasi** | Backend (Flask) — sama seperti alur compile C yang sudah ada |
| **Output kompilasi** | Intel HEX string, dikirim ke frontend via JSON response |
| **Eksekusi** | Frontend (browser) — avr8js menjalankan HEX di browser |

### Alur Kerja

```
┌──────────────┐     POST /api/compile      ┌──────────────────┐
│  Code Editor │ ──── {code, language} ────→ │  Flask Backend   │
│  (SvelteKit) │                             │  + PlatformIO    │
└──────────────┘                             └────────┬─────────┘
       ↑                                              │
       │          {success, hex: "..."}               │
       └──────────────────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────────────────┐
│  Browser: avr8js                                     │
│  ┌─────────┐  USART  ┌───────────────┐              │
│  │   CPU   │ ──────→ │ Output Panel  │ (Serial)     │
│  │ Timer   │         │ (Console)     │              │
│  │ GPIO    │ ──────→ │ CircuitJS1    │ (LED, dll)   │
│  └─────────┘         └───────────────┘              │
└──────────────────────────────────────────────────────┘
```

---

## 2. Dua Mode Bahasa: C Standar (avr-libc) & Arduino C++

Sistem mendukung dua mode pemrograman, ditentukan per-lesson melalui `active_tabs`:

### a. Mode AVR-C (avr-libc)
- Tag: `active_tabs` mengandung `'avr'`
- Sintaks: `#include <avr/io.h>`, manipulasi register langsung (`PORTB`, `DDRB`, dll.)
- PlatformIO framework: `none` (bare-metal avr-libc)
- Cocok untuk: pelajaran arsitektur mikrokontroler, register-level programming

```c
#include <avr/io.h>
#include <util/delay.h>

int main(void) {
    DDRB |= (1 << PB5);  // Pin 13 sebagai output
    while (1) {
        PORTB ^= (1 << PB5);  // Toggle LED
        _delay_ms(500);
    }
}
```

### b. Mode Arduino C++
- Tag: `active_tabs` mengandung `'arduino'`
- Sintaks: `setup()`, `loop()`, `digitalWrite()`, `Serial.println()`, dll.
- PlatformIO framework: `arduino` (include Arduino core library)
- Cocok untuk: pelajaran pemula, rapid prototyping

```cpp
void setup() {
    pinMode(13, OUTPUT);
    Serial.begin(9600);
}

void loop() {
    digitalWrite(13, HIGH);
    Serial.println("LED ON");
    delay(500);
    digitalWrite(13, LOW);
    Serial.println("LED OFF");
    delay(500);
}
```

---

## 3. Implementasi dengan Sistem Tab yang Sudah Ada

Sistem tab Elemes saat ini (`info | exercise | editor | circuit | output`) dimanfaatkan sepenuhnya:

| Tab | Fungsi untuk AVR |
|-----|------------------|
| **Editor** | Menulis kode AVR-C atau Arduino C++. CodeMirror 6 sudah support `lang-cpp`. |
| **Circuit** | CircuitJS1 iframe — rangkaian terhubung ke pin AVR via bridge. |
| **Output** | Serial console — menampilkan output USART dari avr8js (seperti `Serial.println()`). |

### Integrasi Tab di `active_tabs`

Lesson markdown menentukan mode via tag konten:
- `---INITIAL_CODE_AVR---` → aktifkan tab editor mode AVR-C
- `---INITIAL_CODE_ARDUINO---` → aktifkan tab editor mode Arduino
- `---INITIAL_CIRCUIT---` → aktifkan tab circuit (sudah ada)
- Keduanya bisa hadir bersamaan (hybrid lesson)

### Flow Tombol "Run" untuk Mode AVR/Arduino

1. Ambil kode dari CodeEditor
2. POST ke `/api/compile` dengan `language: 'avr'` atau `'arduino'`
3. Backend compile via PlatformIO → return Intel HEX
4. Frontend parse HEX → load ke avr8js CPU memory
5. Jalankan simulation loop (60fps via requestAnimationFrame)
6. USART output → tampilkan di Output Panel sebagai serial console
7. GPIO changes → update CircuitJS1 via bridge

### Tombol Kontrol Tambahan

- **Run**: Compile + Start simulation
- **Stop**: Hentikan simulation loop
- **Reset**: Stop + reset CPU state + clear serial output

---

## 4. Backend: PlatformIO sebagai Compiler Universal

### Arsitektur Compiler Baru

File: `elemes/compiler/avr_compiler.py`

```
BaseCompiler (base_compiler.py)
├── CCompiler (c_compiler.py)        ← sudah ada
├── PythonCompiler (python_compiler.py) ← sudah ada
└── AVRCompiler (avr_compiler.py)    ← BARU
    ├── mode 'avr'     → PlatformIO framework=none
    └── mode 'arduino' → PlatformIO framework=arduino
```

### Cara Kerja AVRCompiler

1. Buat temporary PlatformIO project directory
2. Generate `platformio.ini`:
   ```ini
   [env:uno]
   platform = atmelavr
   board = uno
   framework = arduino   ; atau kosong untuk avr-libc
   ```
3. Tulis source code ke `src/main.cpp` (Arduino) atau `src/main.c` (AVR-C)
4. Jalankan `pio run` → compile
5. Baca output `.hex` dari `.pio/build/uno/firmware.hex`
6. Return HEX string sebagai bagian dari JSON response:
   ```json
   {
     "success": true,
     "hex": ":100000000C9462000C947E00...",
     "output": "Compilation successful"
   }
   ```
7. Cleanup temporary directory

### Response Format Baru

```typescript
interface CompileResponse {
    success: boolean;
    output: string;    // stdout/stderr dari compiler
    error: string;     // error message jika gagal
    hex?: string;      // Intel HEX (hanya untuk avr/arduino)
}
```

### Perubahan Docker

```dockerfile
# Tambahan di elemes/Dockerfile
RUN pip install platformio
# Pre-cache PlatformIO packages (agar first compile cepat)
RUN mkdir -p /tmp/pio-warmup/src && \
    echo '[env:uno]\nplatform = atmelavr\nboard = uno\nframework = arduino' \
    > /tmp/pio-warmup/platformio.ini && \
    echo 'void setup(){} void loop(){}' > /tmp/pio-warmup/src/main.cpp && \
    cd /tmp/pio-warmup && pio run && \
    rm -rf /tmp/pio-warmup
```

---

## 5. Frontend: AVR8js Simulation Engine

### Komponen Baru: `avr-simulator.ts`

File: `elemes/frontend/src/lib/services/avr-simulator.ts`

**Tanggung jawab:**
- Parse Intel HEX → `Uint16Array` (program memory 32KB)
- Inisialisasi avr8js CPU, Timer, USART
- Simulation loop via `requestAnimationFrame`
- Callback: `onSerialOutput(char)` — untuk serial console
- Callback: `onPortWrite(port, value)` — untuk GPIO bridge

**Intel HEX Parser:**
Format Intel HEX per baris: `:LLAAAATT[DD...]CC`
- `LL` = byte count
- `AAAA` = address
- `TT` = type (00=data, 01=EOF)
- `DD` = data bytes
- `CC` = checksum

**Simulation Loop:**
```
requestAnimationFrame → 
  run N instructions (16MHz / 60fps ≈ 266,666 cycles per frame) →
  tick timers →
  check USART output →
  repeat
```

**Pertimbangan performa:**
- 266K cycles per frame cukup untuk real-time simulation
- Jika perlu, bisa dipindah ke Web Worker untuk non-blocking UI
- `delay()` di Arduino code berjalan secara natural karena timer simulation

---

## 6. Bridge: AVR8js ↔ CircuitJS1

### Mekanisme Koneksi

File: `elemes/frontend/src/lib/services/avr-circuit-bridge.ts`

Bridge menghubungkan pin AVR dengan elemen CircuitJS1 menggunakan API yang sudah tersedia:

| Arah | Mekanisme |
|------|-----------|
| **AVR → CircuitJS** | `cpu.writeHooks[PORTB]` mendeteksi GPIO write → `circuitApi.setExtVoltage(name, voltage)` |
| **CircuitJS → AVR** | `circuitApi.ontimestep` callback → `circuitApi.getNodeVoltage(name)` → set AVR PIN register |

### Konfigurasi Pin Map (per lesson)

Setiap lesson AVR+Circuit menyertakan JSON pin mapping di markdown:

```
---AVR_PIN_MAP---
{
    "outputs": {
        "PB5": { "extVoltageName": "arduino_d13", "type": "digital" }
    },
    "inputs": {
        "PC0": { "circuitNode": "sensor_out", "type": "analog" }
    }
}
---END_AVR_PIN_MAP---
```

**Cara kerja:**
- **Output (AVR → Circuit):** Saat AVR menulis ke PORTB bit 5, bridge memanggil `setExtVoltage("arduino_d13", 5.0)` atau `setExtVoltage("arduino_d13", 0.0)`.
- **Input (Circuit → AVR):** Setiap CircuitJS timestep, bridge membaca `getNodeVoltage("sensor_out")` dan set bit di register PIN AVR.

### Prasyarat untuk Lesson Author

Rangkaian CircuitJS harus menyertakan elemen **External Voltage** (ExtVoltageElm) dengan nama yang sesuai pin map. Contoh: elemen bernama `arduino_d13` mewakili output digital pin 13 Arduino.

---

## 7. Format Lesson Markdown — Marker Baru

### Marker Baru untuk AVR

| Marker | Fungsi |
|--------|--------|
| `---INITIAL_CODE_AVR---` | Kode awal mode AVR-C (avr-libc) |
| `---INITIAL_CODE_ARDUINO---` | Kode awal mode Arduino C++ |
| `---AVR_PIN_MAP---` | JSON konfigurasi pin mapping AVR ↔ CircuitJS |
| `---EXPECTED_SERIAL_OUTPUT---` | Expected serial output untuk auto-grading |

### Deteksi `active_tabs` (Backward Compatible)

Parser mendeteksi tag secara implisit (sama seperti sistem saat ini):
- `---INITIAL_CODE_AVR---` ada → `active_tabs.append('avr')`
- `---INITIAL_CODE_ARDUINO---` ada → `active_tabs.append('arduino')`
- Tag lama (`---INITIAL_CODE---`, `---INITIAL_CIRCUIT---`, dll.) tetap berfungsi tanpa perubahan.

### Contoh Lesson: Blink LED (Arduino)

```markdown
---LESSON_INFO---
Pelajaran Arduino: LED Blink dengan Simulator AVR.
- Memahami fungsi setup() dan loop()
- Mengontrol LED menggunakan pin digital
---END_LESSON_INFO---

# Blink LED

Program klasik Arduino: menyalakan dan mematikan LED bergantian.

---EXERCISE---
Buat program Arduino yang menyalakan LED selama 500ms dan mematikan selama 500ms.
Serial monitor harus menampilkan "ON" dan "OFF".
---

---INITIAL_CODE_ARDUINO---
void setup() {
    // Inisialisasi pin 13 sebagai output
    // Inisialisasi Serial
}

void loop() {
    // Nyalakan LED, print "ON", delay 500ms
    // Matikan LED, print "OFF", delay 500ms
}
---END_INITIAL_CODE_ARDUINO---

---INITIAL_CIRCUIT---
$ 1 0.000005 ...
v arduino_d13 ... 
r 220 ...
162 ...
---END_INITIAL_CIRCUIT---

---EXPECTED_SERIAL_OUTPUT---
ON
OFF
---END_EXPECTED_SERIAL_OUTPUT---

---AVR_PIN_MAP---
{
    "outputs": {
        "PB5": { "extVoltageName": "arduino_d13", "type": "digital" }
    },
    "inputs": {}
}
---END_AVR_PIN_MAP---

---KEY_TEXT---
Serial.println
digitalWrite
---END_KEY_TEXT---

---SOLUTION_CODE---
void setup() {
    pinMode(13, OUTPUT);
    Serial.begin(9600);
}

void loop() {
    digitalWrite(13, HIGH);
    Serial.println("ON");
    delay(500);
    digitalWrite(13, LOW);
    Serial.println("OFF");
    delay(500);
}
---END_SOLUTION_CODE---
```

---

## 8. Evaluasi & Auto-Grading

Evaluasi lesson AVR menggunakan kombinasi metode yang sudah ada:

| Kriteria | Mekanisme | Existing? |
|----------|-----------|-----------|
| **Serial output** | Bandingkan USART output vs `expected_serial_output` | Adaptasi dari `expected_output` |
| **Node voltages** | `getNodeVoltage()` vs `expected_circuit_output` JSON | Sudah ada |
| **Key text** | Cek keyword wajib di source code | Sudah ada |
| **Hybrid AND** | Semua kriteria harus lulus | Sudah ada |

---

## 9. Perubahan File — Ringkasan

### File Baru
| File | Deskripsi |
|------|-----------|
| `elemes/compiler/avr_compiler.py` | PlatformIO compiler class |
| `frontend/src/lib/services/avr-simulator.ts` | AVR8js simulation engine + HEX parser |
| `frontend/src/lib/services/avr-circuit-bridge.ts` | Bridge GPIO ↔ CircuitJS1 |
| `content/blink_led.md` | Contoh lesson Arduino |

### File yang Dimodifikasi
| File | Perubahan |
|------|-----------|
| `elemes/compiler/__init__.py` | Register AVRCompiler |
| `elemes/services/lesson_service.py` | Parse marker AVR baru |
| `elemes/routes/lessons.py` | Tambah field AVR ke JSON response |
| `elemes/Dockerfile` | Install PlatformIO + warmup cache |
| `frontend/package.json` | Tambah dependency `avr8js` |
| `frontend/src/lib/types/lesson.ts` | Tambah field AVR |
| `frontend/src/lib/types/compiler.ts` | Tambah field `hex` |
| `frontend/src/lib/types/circuitjs.ts` | Tambah `setExtVoltage`, `ontimestep`, dll |
| `frontend/src/lib/components/WorkspaceHeader.svelte` | Tab AVR/Arduino |
| `frontend/src/routes/lesson/[slug]/+page.svelte` | Wire compile→simulate→output→bridge |
| `frontend/src/lib/components/OutputPanel.svelte` | Section serial console |

---

## 10. Potensi Tantangan & Mitigasi

| Tantangan | Mitigasi |
|-----------|---------|
| PlatformIO cold start lambat di Docker | Pre-cache packages saat `docker build` (warmup step) |
| avr8js tidak support semua peripheral | Untuk edukasi (LED, serial, digital I/O) sudah cukup. Dokumentasikan limitasi. |
| Sinkronisasi timing AVR ↔ CircuitJS | Keduanya berjalan real-time di browser event loop — natural sync |
| HEX file besar | Arduino sketch tipikal 5-50KB — cukup kecil untuk JSON response |
| CircuitJS `setExtVoltage` butuh elemen ExtVoltage | Lesson author wajib menyertakan elemen ini di initial circuit. Buat template. |

---

## Kesimpulan

Integrasi AVR8js ke Elemes LMS **sangat layak** karena:

1. **Infrastruktur sudah siap** — Tab system, CircuitJS1 iframe, output panel, dan compiler factory sudah ada. AVR8js hanya menambah layer baru di atas fondasi yang kokoh.
2. **PlatformIO menyederhanakan toolchain** — Tidak perlu install avr-gcc manual; PlatformIO mengelola semua dependency secara otomatis dan support dua mode (avr-libc dan Arduino).
3. **Backward compatible** — Semua lesson C/Python yang sudah ada tidak terpengaruh. Deteksi tag implisit memastikan kompatibilitas penuh.
4. **Simulasi penuh di browser** — Setelah compile di backend, eksekusi sepenuhnya di client. Tidak membebani server.
5. **Bridge CircuitJS1 sudah feasible** — API `setExtVoltage` dan `getNodeVoltage` yang sudah ada di CircuitJS1 memungkinkan koneksi dua arah antara kode AVR dan simulasi rangkaian.
