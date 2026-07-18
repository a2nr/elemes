---LESSON_INFO---
Pelajaran Arduino: Komunikasi Serial Monitor dan debugging.

**Learning Objectives:**
- Memahami fungsi `Serial.begin()` dan baud rate
- Menggunakan `Serial.println()` dan `Serial.print()` untuk mengirim data
- Membedakan `println` (dengan newline) dan `print` (tanpa newline)
- Menggunakan `millis()` untuk tracking waktu

**Prerequisites:**
- [Hello, World!](lesson/hello_world.md)
---END_LESSON_INFO---
# Hello Serial — Komunikasi Serial Arduino

Serial Monitor adalah **alat debugging utama** saat bekerja dengan Arduino.
Dengan Serial Monitor, kamu bisa mengirim teks dari Arduino ke komputer
untuk memantau apa yang sedang terjadi dalam program.

## Apa itu Komunikasi Serial?

Arduino berkomunikasi dengan komputer melalui **port serial** (USB).
Data dikirim bit-per-bit dengan kecepatan tertentu yang disebut **baud rate**.

```
Arduino  ──USB──►  Komputer (Serial Monitor)
         TX/RX
```

## Fungsi Serial Dasar

### 1. `Serial.begin(baud_rate)`
Memulai komunikasi serial. Harus dipanggil di `setup()`:

```
Serial.begin(9600);    // Baud rate 9600 (paling umum)
```

### 2. `Serial.println(data)`
Mengirim data + **newline** (`\n`) di akhir:

```
Serial.println("Hello");   // output: Hello↵
Serial.println("World");   // output: World↵
```

### 3. `Serial.print(data)`
Mengirim data **tanpa newline**:

```
Serial.print("Suhu: ");    // output: Suhu: 
Serial.println("25 C");    // output: 25 C↵
```

Hasil gabungan: `Suhu: 25 C`

### 4. `millis()`
Mengembalikan jumlah milidetik sejak Arduino dinyalakan:

```
unsigned long waktu = millis();
Serial.print("Waktu: ");
Serial.print(waktu / 1000);
Serial.println(" detik");
```

## Contoh Program

```
void setup() {
  Serial.begin(9600);
  Serial.println("Arduino Ready!");
  Serial.println("Serial Monitor aktif");
}

void loop() {
  Serial.print("Uptime: ");
  Serial.print(millis() / 1000);
  Serial.println(" detik");
  delay(2000);
}
```

---EXERCISE---
### Tantangan

**Tulis program Arduino** yang melakukan hal berikut saat dinyalakan (`setup`):

1. Mulai komunikasi serial dengan baud rate `9600`
2. Cetak teks `Hello Arduino` (dengan newline)
3. Cetak teks `Serial Ready` (dengan newline)

Kemudian di `loop()`:
4. Cetak `Tick` setiap 1 detik

Setelah selesai menulis kode, tekan **Compile & Run** dan tunggu beberapa detik agar Serial output muncul.

> **Tips:** Lesson ini tidak memerlukan wiring — cukup tulis kode saja!
---

---INITIAL_CODE_ARDUINO---
// Hello Serial - Belajar Serial Monitor
// Kirim pesan ke Serial Monitor

void setup() {
  // 1. Mulai serial dengan baud rate 9600

  // 2. Cetak "Hello Arduino"

  // 3. Cetak "Serial Ready"

}

void loop() {
  // 4. Cetak "Tick" setiap 1 detik

}
---END_INITIAL_CODE_ARDUINO---

---VELXIO_CIRCUIT---
{
  "board": "arduino:avr:uno",
  "components": [],
  "wires": []
}
---END_VELXIO_CIRCUIT---

---EXPECTED_SERIAL_OUTPUT---
Hello Arduino
Serial Ready
Tick
---END_EXPECTED_SERIAL_OUTPUT---

---KEY_TEXT---
Serial.begin
Serial.println
delay
---END_KEY_TEXT---
