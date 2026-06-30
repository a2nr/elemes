# Velxio BLE Deployer — Firmware ESP32-S3

Firmware untuk ESP32-S3 N16R8 yang bertindak sebagai **BLE-to-USB bridge** untuk flashing Arduino Uno/Nano via Web Bluetooth.

## Persyaratan

- [ESP-IDF v6.0](https://docs.espressif.com/projects/esp-idf/en/v6.0/esp32s3/get-started/index.html)
- ESP32-S3 dev board (N16R8 — 16MB Flash + 8MB PSRAM)
- Kabel USB-C (data) untuk menghubungkan ke Arduino (USB OTG GPIO19/20)
- Debug log via UART0 (USB-to-UART bridge devkit)

## Setup

```bash
# Export ESP-IDF environment
source /home/a2nr/Downloads/lms-c/esp-idf-v6/export.sh

# Build
idf.py build

# Flash (ganti /dev/ttyACM0 sesuai port)
idf.py -p /dev/ttyACM0 flash monitor
```

## Konfigurasi

Variabel utama di `sdkconfig.defaults`:

| Konfigurasi | Nilai | Keterangan |
|------------|-------|------------|
| `CONFIG_IDF_TARGET` | `esp32s3` | Target chip (WAJIB, bukan esp32) |
| `CONFIG_BT_NIMBLE_SVC_GAP_DEVICE_NAME` | `Velxio-Deployer` | Nama BLE yang tampil di browser |
| `CONFIG_BT_NIMBLE_ATT_PREFERRED_MTU` | `255` | Ukuran MTU BLE |
| `CONFIG_SPIRAM` | `y` | PSRAM enabled |
| `CONFIG_SPIRAM_MODE_OCT` | `y` | Octal mode (N16R8) |
| `CONFIG_ESPTOOLPY_FLASHSIZE_16MB` | `y` | Flash 16MB |
| `CONFIG_CHERRYUSB_HOST_CDC_ACM` | `y` | USB Host CDC (CherryUSB) |
| `CONFIG_ESP_CONSOLE_UART_DEFAULT` | `y` | Debug via UART0 (bukan USB-JTAG) |

## Partisi Flash

| Partisi | Ukuran | Fungsi |
|---------|--------|--------|
| ota_0 | 3 MB | Firmware utama |
| ota_1 | 3 MB | OTA update |
| storage | ~10 MB | SPIFFS untuk log/filesystem |

## Arsitektur Komponen

```
main.c
├── ble_service.c      # NimBLE peripheral (2 karakteristik)
├── binary_parser.c    # Parser payload binary (INIT/DATA/END)
├── checksum.c         # CRC32
├── usb_host.c         # CherryUSB Host (CDC) — belum lengkap
├── stk500v1.c         # STK500v1 flashing protocol — belum lengkap
├── state_machine.c    # Finite state machine
├── serial_bridge.c    # USB CDC ↔ BLE Notify bridge
└── led_button.c       # LED RGB + Retry button
```

## Protokol BLE

```
Service:     56454c58-494f-0000-0000-000000000001
Flashing:    56454c58-494f-0000-0000-000000000002  (Write+Resp + Notify)
Serial:      56454c58-494f-0000-0000-000000000003  (WriteWO+Resp + Notify)
```

Payload format: `[CMD:1][Index:2 LE][Len:1][Data:N ≤240][CRC32:4 LE]`

### Catatan UUID (PENTING)

UUID di firmware menggunakan `BLE_UUID128_INIT` dengan byte order **little-endian**:
```c
// 56454C58-494F-0000-0000-000000000001
BLE_UUID128_INIT(
    0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x4F, 0x49, 0x58, 0x4C, 0x45, 0x56
)
```

## Testing (tanpa Web Bluetooth)

Gunakan `nRF Connect` Android untuk test BLE:
1. Scan → pilih "Velxio-Deployer" (nama pendek "Velxio" di adv data)
2. Connect → MTU otomatis ter-negosiasi ke 255
3. Subscribe ke karakteristik Flashing (Notify)
4. Kirim payload INIT: `01 00 00 04 [CRC-total(4)] [CRC-packet(4)]`
5. Kirim payload DATA: `02 [idx(2)] [len] [data...] [CRC(4)]`
6. Kirim payload END: `03 00 00 04 [CRC-total(4)] [CRC-packet(4)]`

## Status Development

| Fase | Status | Keterangan |
|------|--------|------------|
| F0 Environment | Selesai | ESP-IDF v6.0 terinstall |
| F1 Project config | Selesai | Target esp32s3, PSRAM, CherryUSB |
| F2 BLE service | Selesai | UUID branded hex, adv data, MTU 255 |
| F3 Protocol/ACK | Selesai | END ACK setelah flash, parse error fix |
| F4 STK500v1 | Belum | Implementasi lengkap |
| F5 USB Host | Belum | CherryUSB RX claim/unclaim |
| F6 Serial bridge | Belum | Throttle + LED polish |
| F7 Frontend | Selesai | UUID, chunk 240, requestMTU |
| F8 Dokumen | Selesai | Dokumen ini |
| F9 Testing | Belum | Progressive integration test |
