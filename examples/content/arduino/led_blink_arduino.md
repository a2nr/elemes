---LESSON_INFO---
Pelajaran Arduino: Mengedipkan LED menggunakan simulator Velxio.

**Learning Objectives:**
- Memahami fungsi `pinMode()`, `digitalWrite()`, dan `delay()`
- Menghubungkan LED dan resistor ke Arduino Uno
- Menggunakan `Serial.print()` untuk debugging

**Prerequisites:**
- [Hello, World!](lesson/hello_world.md)
---END_LESSON_INFO---
# LED Blink dengan Arduino

Proyek pertama setiap programmer Arduino: **mengedipkan LED!**

## Konsep Dasar

### Digital Output

Arduino Uno memiliki 14 pin digital (0–13). Setiap pin bisa menjadi **OUTPUT** atau **INPUT**:

```
pinMode(13, OUTPUT);     // Set pin 13 sebagai output
digitalWrite(13, HIGH);  // Nyalakan (5V)
digitalWrite(13, LOW);   // Matikan (0V)
```

### Rangkaian LED

LED membutuhkan **resistor pembatas arus** agar tidak rusak:

```
Pin 13 → Resistor 220Ω → LED (Anode) → LED (Cathode) → GND
```

Tanpa resistor, arus terlalu besar dan LED bisa terbakar!

### Serial Monitor

`Serial.println()` mengirim teks ke Serial Monitor — sangat berguna untuk debugging:

```
Serial.begin(9600);           // Mulai komunikasi serial
Serial.println("LED ON");     // Cetak teks + newline
```

---EXERCISE---
### Tantangan

**Kode Arduino:**
Tulis program yang mengedipkan LED di **pin 13** dengan interval 1 detik.
Program harus mencetak `LED ON` saat LED menyala dan `LED OFF` saat LED mati ke Serial Monitor.

**Rangkaian:**
Hubungkan komponen-komponen berikut:
- Pin 13 Arduino → Resistor (pin 1)
- Resistor (pin 2) → LED Anode (A)
- LED Cathode (C) → GND Arduino

Setelah selesai, tekan **Compile & Run** untuk menjalankan program dan tunggu beberapa detik agar Serial output muncul.
---

---INITIAL_CODE_ARDUINO---
// LED Blink - Tugas Pertama Arduino
// Mengedipkan LED di pin 13 dengan resistor pembatas arus

void setup() {
  pinMode(13, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  digitalWrite(13, HIGH);
  Serial.println("LED ON");

  delay(1000);

  digitalWrite(13, LOW);
  Serial.println("LED OFF");

  delay(1000);
}
---END_INITIAL_CODE_ARDUINO---

---VELXIO_CIRCUIT---
{
  "board": "arduino:avr:uno",
  "components": [
    {
      "type": "led",
      "id": "led-builtin",
      "x": 394,
      "y": -208,
      "rotation": 0,
      "props": {
        "color": "red",
        "pin": 13,
        "state": true,
        "value": true
      }
    },
    {
      "type": "resistor",
      "id": "resistor-1775728124959-5rknpronw",
      "x": 292,
      "y": -159,
      "rotation": 0,
      "props": {
        "value": true,
        "state": true
      }
    }
  ],
  "wires": []
}
---END_VELXIO_CIRCUIT---

---EXPECTED_SERIAL_OUTPUT---
LED ON
LED OFF
---END_EXPECTED_SERIAL_OUTPUT---

---EXPECTED_WIRING---
{
  "wires": [
    {
      "start": { "componentId": "arduino-uno", "pinName": "13" },
      "end": { "componentId": "resistor-1775728124959-5rknpronw", "pinName": "1" }
    },
    {
      "start": { "componentId": "resistor-1775728124959-5rknpronw", "pinName": "2" },
      "end": { "componentId": "led-builtin", "pinName": "A" }
    },
    {
      "start": { "componentId": "arduino-uno", "pinName": "GND" },
      "end": { "componentId": "led-builtin", "pinName": "C" }
    }
  ]
}
---END_EXPECTED_WIRING---

---KEY_TEXT---
pinMode
digitalWrite
Serial
---END_KEY_TEXT---
