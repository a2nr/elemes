# 05. Velxio BLE Deployer — Dokumentasi Implementasi

**Versi:** 3.2
**Tanggal:** 19 Juli 2026
**Status:** ✅ **SELESAI + USB DEPLOYER FIX (v3.2)** — Re-deploy fix, serial terminal, baud dropdown, LED patterns, event-based Arduino detection, get_sync timing & fail-fast reliability

---

## 1. Ringkasan

Integrasi fitur **BLE Deployer** ke LMS untuk memungkinkan siswa melakukan flashing firmware Arduino langsung dari browser Chrome Android via Web Bluetooth API, menggunakan ESP32-S3 sebagai bridge BLE-to-USB.

Arsitektur:

```
Webapp (Chrome Android)
  |  Web Bluetooth API (GATT)
  v
ESP32-S3 N16R8 (BLE Peripheral + USB Host)
  |  STK500v1 over USB CDC (115200 baud)
  v
Arduino Uno/Nano (Target)
  |
  |  USB CDC read (9600 baud — match Serial.begin(9600))
  v
ESP32-S3 (Serial Bridge via BLE Notify)
  |
  v
Webapp Serial Monitor
```

---

## 2. Status Implementasi Aktual

| Area | Status | Keterangan |
|------|--------|------------|
| **Frontend SvelteKit** | ✅ Selesai | `DeployTab.svelte`, `ble-deployer.ts`, `deployer.ts` — UUID branded, chunks 240, MTU 255 |
| **Backend Flask** | ✅ Selesai | `/velxio-compile` return `hex_content` (tidak berubah) |
| **Firmware BLE + Parser** | ✅ Selesai | Advertising OK, UUID branded, MTU 255, protocol ACK benar |
| **Firmware USB Host** | ✅ Selesai | CherryUSB 1.6.1 host CDC, RX claim/unclaim, dual baud rate |
| **Firmware STK500v1** | ✅ Selesai | Flash Arduino via STK500v1 (get_sync, signature, prog_page, dll) |
| **Firmware Serial Bridge** | ✅ Selesai | USB CDC ↔ BLE Notify, throttle 20 pkt/s, flush 500ms |
| **Serial Monitor (data flow)** | ✅ **SELESAI** | Data "LED ON"/"LED OFF" dari Arduino tampil di webapp |
| **Integrasi Webapp** | ✅ Selesai | `DeployTab` ter-render saat `active_tabs` include `velxio` |
| **Debug tools** | ✅ Selesai | `debug-capture.sh` — capture CDP + firmware log simultan |
| **Re-deploy fix** (v3.1) | ✅ **FIXED** | Stuck di INIT setelah deploy pertama — root cause: ACK sent before serial_bridge_stop + CCCD left at 0 |
| **Serial terminal inline** (v3.1) | ✅ **DONE** | Serial terminal tampil saat paired (bukan gated di deploy success) + baud dropdown (9600/19200/38400) |
| **LED blink patterns** (v3.1) | ✅ **DONE** | IDLE slow blink (1s), RECEIVING medium (200ms), FLASHING fast (100ms) |
|| **Arduino event-based** (v3.1) | ✅ **DONE** | Hybrid event+1s poll via CherryUSB `usbh_event_handler_t` — disconnect ~200ms |
|| **USB Deployer (get_sync fix)** (v3.2) | ✅ **SELESAI** | DTR 50ms+100ms, CDC drain, fail-fast, STK_SYNC_RETRIES 20 |

---

## 3. Keputusan Desain Final

| Keputusan | Pilihan | Alasan |
|-----------|---------|--------|
| UUID BLE | Branded hex `56454C58-494F-0000-...` | UUID lama `0000VELX-IO00` invalid |
| ESP-IDF | v6.0 | v5.1 tidak support ESP32-S3 USB Host dengan benar |
| USB Host | CherryUSB 1.6.1 | TinyUSB tidak stabil di S3 |
| USB Native | GPIO19/20 = Host ke Arduino | Debug log via UART0 |
| Chunk size | 240 byte | Field Len 1-byte (max 255), MTU 255 |
| MTU | 255 | `requestMTU(255)` di frontend |
| ACK timing END | Setelah STK500v1 flash sukses | Bukan sebelum flash |
| Adv name | "Velxio" (shortened) | Max 31 byte adv data |
| **Baud STK500** | **115200** | Arduino bootloader sync (get_sync) |
| **Baud Serial Bridge** | **9600** | Match `Serial.begin(9600)` di sketch siswa |

---

## 4. UUID BLE (Final)

```
Service UUID:        56454c58-494f-0000-0000-000000000001
Flashing Char UUID:  56454c58-494f-0000-0000-000000000002
Serial Char UUID:    56454c58-494f-0000-0000-000000000003
```

Firmware (C, little-endian NimBLE `BLE_UUID128_INIT`):
```c
// 56454C58-494F-0000-0000-000000000001
static const ble_uuid128_t service_uuid = BLE_UUID128_INIT(
    0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x4F, 0x49, 0x58, 0x4C, 0x45, 0x56
);
```

Frontend (TypeScript):
```typescript
export const BLE_SERVICE_UUID = '56454c58-494f-0000-0000-000000000001';
```

---

## 5. Protokol BLE

```
Payload: [CMD:1][Index:2 LE][Len:1][Data:N][CRC32:4 LE]

CMD_INIT (0x01) — mulai transfer, data = total CRC (4 byte)
CMD_DATA (0x02) — chunk binary, data = raw hex bytes
CMD_END  (0x03) — selesai transfer, data = total CRC (4 byte)
CMD_ACK  (0x04) — respon sukses dari firmware
CMD_ERR  (0x05) — respon error dari firmware
```

### Alur ACK (Final)

```
Webapp → INIT → ESP32 kirim ACK segera
Webapp → DATA chunk 0 → ESP32 kirim ACK
Webapp → DATA chunk 1 → ESP32 kirim ACK
...
Webapp → DATA chunk N → ESP32 kirim ACK
Webapp → END → ESP32 TIDAK kirim ACK langsung
              ESP32 verifikasi CRC buffer
              ESP32 flash via STK500v1
              Jika sukses → kirim ACK
              Jika gagal → kirim ERR
```

---

## 6. Firmware ESP32-S3

Lokasi: `elemes/velxio-deployer-firmware/`

### 6.1 Persyaratan

- ESP-IDF v6.0 (`/home/a2nr/Downloads/lms-c/esp-idf-v6`)
- Target: `esp32s3`
- CherryUSB 1.6.1 (managed component)

### 6.2 Build & Flash

```bash
source /home/a2nr/Downloads/lms-c/esp-idf-v6/export.sh
cd elemes/velxio-deployer-firmware
idf.py build
idf.py -p /dev/ttyACM0 flash
```

### 6.3 Konfigurasi (sdkconfig.defaults)

| Key | Value | Keterangan |
|-----|-------|------------|
| `CONFIG_IDF_TARGET` | `esp32s3` | Target chip |
| `CONFIG_BT_NIMBLE_SVC_GAP_DEVICE_NAME` | `Velxio-Deployer` | Nama BLE |
| `CONFIG_BT_NIMBLE_ATT_PREFERRED_MTU` | `255` | MTU |
| `CONFIG_SPIRAM` | `y` | PSRAM enabled |
| `CONFIG_SPIRAM_MODE_OCT` | `y` | Octal mode (N16R8) |
| `CONFIG_ESPTOOLPY_FLASHSIZE_16MB` | `y` | Flash 16MB |
| `CONFIG_CHERRYUSB_HOST_CDC_ACM` | `y` | USB Host CDC |
| `CONFIG_ESP_CONSOLE_UART_DEFAULT` | `y` | Debug via UART0 |

### 6.4 Dual Baud Rate Strategy (Kunci Fix Serial Monitor)

Dua baud rate berbeda untuk dua mode operasi:

| Mode | Baud | Fungsi | File |
|------|------|--------|------|
| **STK500 flashing** | **115200** | Arduino bootloader sync | `usb_host.c:make_stk500_termios()` |
| **Serial bridge** | **9600** | Match `Serial.begin(9600)` sketch | `usb_host.c:make_termios()` |

Switch terjadi otomatis via `usb_host_rx_claim()` / `usb_host_rx_release()`:
- Saat flashing: `rx_claim()` set 115200 → STK500 sync sukses
- Setelah flash: `rx_release()` set 9600 → serial bridge cocok dengan baud sketch Arduino

### 6.5 USB Deployer Timing & Reliability (v3.2 fix)

Bug fix: `get_sync failed after 10 attempts` saat deploy USB via BLE → ESP32 → Arduino.

Root cause: DTR pulse 1ms terlalu pendek untuk RC reset circuit klon Arduino,
CDC ringbuffer berisi byte stale dari sesi serial bridge sebelumnya, dan
`read_exact` tidak fail-fast saat device disconnect.

Fix:
1. `usb_host_reset_arduino`: DTR/RTS low 50ms → high → settle 100ms (align avrdude + frontend TS)
2. `usb_host_drain_cdc`: explicit drain 256 bytes / 50ms sebelum `cmd_get_sync` pertama
3. `stk500v1_flash_buffer`: guard `usb_host_arduino_connected()` di awal
4. `read_exact`: break early jika device disconnect mid-read
5. `STK_SYNC_RETRIES`: 10 → 20 dengan backoff 20-150ms (total ≤9s, masih dalam optiboot 8s window)
6. Logging: per-attempt DEBUG, OK/fail INFO

Verification: 5× berturut-turut deploy (cold + re-deploy) sukses, rata-rata get_sync OK ≤ 3 attempts.

### 6.6 File Firmware

| File | Fungsi |
|------|--------|
| `main.c` | Entry point, BLE command router |
| `ble_service.c` | BLE GATT server, advertising, 2 karakteristik |
| `binary_parser.c` | Parse INIT/DATA/END, CRC32 verification |
| `state_machine.c` | IDLE → RECEIVING → VERIFYING → FLASHING → SERIAL_BRIDGE → ERROR |
| `stk500v1.c` | STK500v1 protocol (get_sync, prog_page, dll) |
| `usb_host.c` | CherryUSB host CDC, RX claim/release, DTR pulse, dual baud |
| `serial_bridge.c` | USB CDC ↔ BLE Notify bridge, throttle 20 pkt/s |
| `led_button.c` | LED RGB + tombol Retry |

### 6.7 Debug

- Serial log: UART0 (CH343 USB-to-UART devkit) via `/dev/ttyACM0`
- Tag logging: `BLE_SVC`, `BIN_PARSER`, `SM`, `USB`, `STK500`, `SERIAL_BRIDGE`
- CDP remote debug Chrome Android via ADB + `debug-capture.sh`

---

## 7. Frontend SvelteKit

### 7.1 File Terkait

| File | Fungsi |
|------|--------|
| `src/lib/types/deployer.ts` | UUID, constants, types |
| `src/lib/services/ble-deployer.ts` | `BLEHardwareDeployer` class |
| `src/routes/lesson/[slug]/DeployTab.svelte` | UI tab Deploy + Serial Monitor |
| `src/lib/components/WorkspaceHeader.svelte` | Tab button "Deploy" |
| `src/lib/components/Footer.svelte` | Version badge |

### 7.2 Konstanta

```typescript
export const BLE_SERVICE_UUID = '56454c58-494f-0000-0000-000000000001';
export const BLE_CHAR_FLASHING_UUID = '56454c58-494f-0000-0000-000000000002';
export const BLE_CHAR_SERIAL_UUID = '56454c58-494f-0000-0000-000000000003';
export const CHUNK_SIZE = 240;
export const BLE_TIMEOUT_MS = 5000;
export const MAX_RETRIES = 3;
```

### 7.3 Fitur Serial Monitor

- Subscribe karakteristik serial (CCCD notify)
- `TextDecoder().decode()` untuk BLE notify → terminal UI
- Auto-scroll ke bawah
- Input form untuk kirim data ke Arduino (Write Without Response)
- Throttle BLE notify dari firmware (max 20 pkt/s)
- Stop serial monitor via unsubscribe

### 7.4 Build & Deploy

```bash
cd elemes/frontend
npm run build
cd elemes
# via container:
./elemes.sh runbuild
```

---

## 8. Debug & Testing Tools

### 8.1 debug-capture.sh

Lokasi: `elemes/debug-capture.sh`

Script multifungsi untuk capture log simultan:

| Command | Fungsi |
|---------|--------|
| `setup` | Auto-detect ADB + CDP WebSocket URL |
| `cdp` | Stream console.log Chrome Android via CDP |
| `firmware` | Source IDF + `idf.py monitor` pada `/dev/ttyACM0` |
| `all` | CDP + firmware simultan |
| `sw-clear` | Unregister SW + clear caches + reload page |
| `eval '<js>'` | Evaluate JS expression di device |
| `status` | Cek ADB, CDP, ACM0, IDF, Node |

### 8.2 Remote Debug Chrome Android

```bash
# Setup koneksi ADB via Tailscale
adb forward tcp:9222 localabstract:chrome_devtools_remote

# Capture log
./debug-capture.sh setup
./debug-capture.sh all

# On-demand inspect
./debug-capture.sh eval 'document.querySelector(".serial-line")?.textContent'
```

---

## 9. Bug Fix yang Sudah Dilakukan

### Firmware

| # | File | Bug | Fix | Sesi |
|---|------|-----|-----|------|
| B1 | `ble_service.c` | UUID invalid (encode "LEXV") | Branded hex little-endian | 22/6 |
| B2 | `main.c` | CMD_INIT tidak kirim ACK | `binary_parser_process_packet` kirim ACK | 22/6 |
| B3 | `binary_parser.c` | END ACK dikirim sebelum flash | Hapus ACK dari parser, kirim setelah flash | 23/6 |
| B4 | `stk500v1.c` | `expect_resp()` cuma delay | Rewrite `send_and_expect` baca response | 23/6 |
| B5 | `usb_host.c` | RX serial bridge vs STK500 bentrok | RX claim/unclaim mechanism | 23/6 |
| B6 | `ble_service.c` | `conn_handle` tidak disimpan | Simpan dari `BLE_GAP_EVENT_CONNECT` | 22/6 |
| B7 | `ble_service.c` | MTU tidak dinegosiasi | `ble_att_set_preferred_mtu(255)` | 22/6 |
| B8 | `ble_service.c` | `serial_char_access_cb` kosong | Forward ke `serial_bridge_on_ble_write()` | 22/6 |
| B9 | `ble_service.c` | Adv tanpa nama | Build explicit adv data | 22/6 |
| B10 | `usb_host.c` | TIOCMSET deref alamat 0x6 crash | Pointer ke `uint32_t` flags | 23/6 |
| B11 | `main.c` | CMD_END skip parser → `buffer_size=0` | Panggil `binary_parser_process_packet` | 23/6 |
| B12 | `binary_parser.c` | CRC check duplikat → ERR ganda | Hapus CRC check di parser | 23/6 |
| **B13** | **`usb_host.c`** | **Baud rate 115200 → null bytes di serial** | **Dual baud: 115200 STK500 + 9600 serial bridge** | **4/7** |

### Frontend

| # | File | Bug | Fix | Sesi |
|---|------|-----|-----|------|
| F1 | `deployer.ts` | UUID invalid | Branded hex | 22/6 |
| F2 | `ble-deployer.ts` | `CHUNK_SIZE=512` tanpa `requestMTU()` | 240 + `requestMTU(255)` | 22/6 |
| F3 | `ble-deployer.ts` | `payload[3]=data.length` overflow | Aman karena chunk ≤ 240 | 22/6 |
| F4 | `ble-deployer.ts` | `pair()` tidak panggil `requestMTU` | Tambah `requestMTU(255)` | 22/6 |
| F5 | `ble-deployer.ts` | Race condition ACK | ackResolver BEFORE write | 23/6 |
| F6 | `ble-deployer.ts` | DataView byteOffset bug | `new Uint8Array(buffer, byteOffset, byteLength)` | 23/6 |
| F7 | `ble-deployer.ts` | END timeout 5s terlalu pendek | 30s + write fallback | 23/6 |
| F8 | `DeployTab.svelte` | Svelte 5 reactivity `isConnected` | `$state isPaired` flag | 22/6 |
| F9 | `sw.js` | Service Worker cache stale | Bump cache version | 22/6 |
| F10 | `Dockerfile` | Tidak copy `package-lock.json` | `npm ci` + copy lock | 22/6 |
| F11 | `ble-deployer.ts` | CCCD subscription hilang saat idle | Refresh `stop+startNotifications` sebelum END | 30/6 |
| F12 | `ble-deployer.ts` | Poll loop resolve di deadline | Hapus `resolve()` — biarkan ackPromise yg tentukan | 30/6 |

---

## 10. Enhancement v3.1 (4 Juli 2026)

### 10.1 Fix Re-Deploy Stuck di INIT

**Root cause:** Dua faktor:
1. **Firmware** — `main.c:29-30`: ACK INIT dikirim oleh `binary_parser_process_packet()` (`binary_parser.c:70`) SEBELUM `serial_bridge_stop()` dipanggil. Saat re-deploy dari SERIAL_BRIDGE, serial bridge masih aktif dan NimBLE mbuf pool (12 blocks) bisa habis → ACK silent drop di `ble_service.c:277-278`.
2. **Webapp** — `ble-deployer.ts:278-284`: END flow melakukan `stopNotifications()` (CCCD=0) lalu `startNotifications()` fire-and-forget yang race dengan `readValue()` poll → bisa gagal → CCCD tertinggal 0 → ACK INIT notification tidak di-deliver.

**Fix:**
- `main.c`: `serial_bridge_stop()` SEBELUM `binary_parser_process_packet()`
- `ble_service.c`: Retry mbuf alloc 3x + error log jika gagal
- `sdkconfig.defaults`: `CONFIG_BT_NIMBLE_MSYS_1_BLOCK_COUNT=24`
- `serial_bridge.c`: `vTaskDelay(1)` yield di large-packet loop
- `binary_parser.c`: Hapus `memset(hex_buffer, 0, MAX_HEX_SIZE)` — block BLE thread ~25ms tidak perlu
- `ble-deployer.ts`: `deployHex()` stop serial monitor + `await startNotifications()` ensure CCCD=1 sebelum INIT
- `ble-deployer.ts`: Hapus `stopNotifications()` dari END flow (penyebab CCCD=0)
- `DeployTab.svelte`: `serialActive = false` di handleDeploy

### 10.2 Serial Terminal Always Visible + Baud Dropdown

- Serial terminal render saat `isPaired` (bukan `deployState === 'success'`)
- Toggle "Mulai"/"Tutup" di serial header
- Auto-start serial setelah deploy success
- Dropdown baud: 9600 / 19200 / 38400 (hanya rate yang aman untuk BLE throughput ~4800 B/s)
- `CMD_SET_BAUD (0x06)` — dikirim via serialChar (writeWithoutResponse)
- Firmware `ble_service.c` intercept CMD_SET_BAUD → `usb_host_set_baud_rate(baud)`
- `usb_host.c`: configurable baud via `serial_baud` static variable

### 10.3 LED Blink Pattern Per-State

| State | Pattern | Interval |
|-------|---------|----------|
| IDLE (advertising) | LED_BLUE_BLINK_SLOW | 1000ms |
| RECEIVING chunks | LED_BLUE_BLINK | 200ms |
| VERIFYING CRC | LED_BLUE solid | — |
| FLASHING STK500 | LED_BLUE_BLINK_FAST | 100ms |
| SERIAL_BRIDGE | LED_GREEN solid | — |
| ERROR_CHECKSUM | LED_RED_BLINK | 100ms |
| ERROR_TARGET | LED_RED solid | — |

### 10.4 Arduino Connect/Disconnect Event-Based

- CherryUSB `usbh_event_handler_t` callback di `usbh_initialize(0, ESP_USB_FS0_BASE, usb_event_handler)`
- Listen `USBH_EVENT_INTERFACE_START` (connect) + `USBH_EVENT_DEVICE_DISCONNECTED`
- Forward via `xTaskNotifyGive` ke `usb_monitor_task`
- `vTaskDelay(1000)` → `xTaskNotifyWait(0, 0, NULL, pdMS_TO_TICKS(1000))` — event OR 1s poll fallback
- Constraint: handler jalan di hub thread, hanya boleh notify, tidak boleh `usbh_serial_*`

---

## 11. Sisa Pekerjaan (Improvement, Bukan Blocker)

| Task | Prioritas | Keterangan |
|------|-----------|------------|
| OTA firmware update | Rencana V2 | Update firmware ESP32 via webapp |
| Multi-board support | Rencana V2 | Target MCU selain ATmega328P |
| Baud rate auto-detect | Rencana V2 | Deteksi baud dari kode siswa |

---

## 12. Alur Data End-to-End (Final)

```
Webapp                          ESP32-S3                        Arduino
  |                                |                              |
  |-- BLE INIT (total CRC) ------->|                              |
  |<-- BLE ACK --------------------|                              |
  |-- BLE DATA (chunk 0..N) ------>|                              |
  |<-- BLE ACK (per chunk) --------|                              |
  |-- BLE END -------------------->|                              |
  |                                |-- STK500 (115200) --------->|
  |                                |  get_sync → signature →      |
  |                                |  enter_prog → load_addr →    |
  |                                |  prog_page → leave_prog     |
  |                                |<-- flash OK -----------------|
  |<-- BLE ACK END (flash OK) -----|                              |
  |                                |-- switch to 9600 baud        |
  |                                |                              |
  |== Serial Monitor mode ==       |                              |
  |<-- BLE serial Notify ----------|<-- Serial.print (9600) ------|
  |-- BLE serial Write ----------->|-- USB CDC write ------------>|
```

### Verifikasi End-to-End (4 Juli 2026)

Dari capture simultan firmware + CDP:

```
FW: SERIAL_BRIDGE: USB->BLE: 8 bytes, buf=0/240
FW: NimBLE: att_handle=19
CDP: [BLE-SERIAL] RX: 8B "LED ON"
FW: SERIAL_BRIDGE: USB->BLE: 9 bytes, buf=0/240
FW: NimBLE: att_handle=19
CDP: [BLE-SERIAL] RX: 9B "LED OFF"
```

Data "LED ON" / "LED OFF" dari Arduino muncul di webapp setiap ~1 detik.

---

## 13. Catatan Teknis

- Advertising data max 31 byte. Nama "Velxio-Deployer" (15 char) + UUID128 (18 byte) + flags (3 byte) = 38 byte → overflow. Solusi: shorten ke "Velxio" (6 char) → total ~21 byte.
- Frontend scan pakai `namePrefix: 'Velxio'` → tetap match.
- Web Bluetooth types (`BluetoothRemoteGATTServer`, dll) tidak ada di TypeScript default — perlu `@types/web-bluetooth` atau ignore. Error ini pre-existing.
- Lesson terkunci (prerequisite belum selesai) → backend kosongkan `initial_code_arduino`, tapi `active_tabs` tetap di-return. Tab Deploy tetap muncul.
- `idf.py monitor` membutuhkan TTY — tidak bisa dijalankan di bash tool non-interaktif. Alternatif: Python serial raw (`python3 -c "import serial; ..."`).
- Debug-capture.sh menggunakan Node.js inline (WebSocket native) untuk CDP — tidak perlu dependency eksternal.
