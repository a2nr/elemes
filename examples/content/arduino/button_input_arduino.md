---LESSON_INFO---
Pelajaran Arduino: Membaca input tombol dan mengontrol LED.

**Learning Objectives:**
- Memahami fungsi `digitalRead()` untuk membaca input digital
- Menggunakan `INPUT_PULLUP` untuk push button
- Menerapkan logika kondisional (`if-else`) berdasarkan input
- Menghubungkan push button dan LED ke Arduino

**Prerequisites:**
- Hello, World!
- LED Blink
- Hello Serial
---END_LESSON_INFO---

# Button Input — Membaca Tombol

Setelah belajar **output** (menyalakan LED) dan **serial** (mengirim teks),
sekarang kita belajar **input** — membaca tombol yang ditekan oleh pengguna.

## Konsep Digital Input

Setiap pin digital Arduino bisa dikonfigurasi sebagai **INPUT** atau **OUTPUT**:

```
pinMode(13, OUTPUT);    // Pin 13 = output (LED)
pinMode(2, INPUT_PULLUP); // Pin 2 = input dengan pullup
```

### Apa itu INPUT_PULLUP?

Tanpa resistor, pin input Arduino bisa membaca nilai **acak** (mengambang).
`INPUT_PULLUP` mengaktifkan resistor internal Arduino yang menarik pin ke **HIGH** (5V).

```
Tanpa pullup:  Pin ──?──  (nilai acak: HIGH atau LOW)
Dengan pullup: Pin ──R──► 5V  (default HIGH, jadi LOW saat ditekan)
```

Saat tombol **tidak ditekan**: `digitalRead()` = `HIGH` (1)
Saat tombol **ditekan**: `digitalRead()` = `LOW` (0)

> **Perhatikan:** Logikanya terbalik! Tombol ditekan = LOW, tidak ditekan = HIGH.

## Fungsi digitalRead()

```
int nilai = digitalRead(2);  // Baca pin 2
if (nilai == LOW) {
  // Tombol sedang ditekan
}
```

## Rangkaian

Hubungkan push button dan LED ke Arduino:

```
Pin 2  ──► Button pin 1.l (input)
Button pin 2.l ──► GND    (ground)

Pin 13 ──► LED Anode (A)
LED Cathode (C) ──► GND
```

Push button menggunakan `INPUT_PULLUP`, jadi hanya perlu 2 kabel: dari pin Arduino ke tombol, dan dari tombol ke GND. Tidak perlu resistor eksternal!

## Contoh Program

```
const int BUTTON_PIN = 2;
const int LED_PIN = 13;

void setup() {
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  int state = digitalRead(BUTTON_PIN);
  
  if (state == LOW) {
    digitalWrite(LED_PIN, HIGH);
    Serial.println("PRESSED");
  } else {
    digitalWrite(LED_PIN, LOW);
    Serial.println("RELEASED");
  }
  
  delay(100);
}
```

---EXERCISE---
### Tantangan

**Kode Arduino:**
Tulis program yang membaca tombol di **pin 2** dan mengontrol LED di **pin 13**:
- Saat tombol ditekan → LED menyala, cetak `PRESSED` ke Serial Monitor
- Saat tombol dilepas → LED mati, cetak `RELEASED` ke Serial Monitor

Gunakan `INPUT_PULLUP` agar tidak perlu resistor tambahan untuk tombol.

**Rangkaian:**
Hubungkan komponen berikut di simulator:
- Pin 2 Arduino → Button (pin 1.l)
- Button (pin 2.l) → GND Arduino
- Pin 13 Arduino → LED Anode (A)
- LED Cathode (C) → GND Arduino

Setelah selesai, tekan **Compile & Run**, lalu **klik tombol** di simulator untuk menguji.
---

---INITIAL_CODE_ARDUINO---
// Button Input - Membaca Tombol
// Tekan tombol untuk menyalakan LED

const int BUTTON_PIN = 2;
const int LED_PIN = 13;

void setup() {
  // Setup pin mode
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  int buttonState = digitalRead(BUTTON_PIN);

  if (buttonState == LOW) {
    // Tombol ditekan
    digitalWrite(LED_PIN, HIGH);
    Serial.println("PRESSED");
  } else {
    // Tombol dilepas
    digitalWrite(LED_PIN, LOW);
    Serial.println("RELEASED");
  }

  delay(100);
}
---END_INITIAL_CODE_ARDUINO---

---VELXIO_CIRCUIT---
{
  "board": "arduino:avr:uno",
  "components": [
    {
      "type": "led",
      "id": "led-builtin",
      "x": 188,
      "y": -158,
      "rotation": 0,
      "props": {
        "color": "red",
        "pin": 13,
        "state": false
      }
    },
    {
      "type": "pushbutton",
      "id": "pushbutton-1778378142489-v899irppo",
      "x": 300,
      "y": 59,
      "rotation": 0,
      "props": {
        "color": "red",
        "pressed": false,
        "label": "",
        "xray": false
      }
    },
    {
      "type": "resistor",
      "id": "resistor-1778378159414-9y3d8f1uk",
      "x": 409,
      "y": 68,
      "rotation": 0,
      "props": {
        "value": "1000"
      }
    },
    {
      "type": "resistor",
      "id": "resistor-1778378205248-h9g1m1wml",
      "x": 114,
      "y": -89,
      "rotation": 0,
      "props": {
        "value": "1000"
      }
    }
  ],
  "wires": [
 
  ]
}

---END_VELXIO_CIRCUIT---

---EXPECTED_SERIAL_OUTPUT---
PRESSED
---END_EXPECTED_SERIAL_OUTPUT---

---EXPECTED_WIRING---
{
  "wires": [
   {
      "start": {
        "componentId": "resistor-1778378205248-h9g1m1wml",
        "pinName": "2"
      },
      "end": {
        "componentId": "led-builtin",
        "pinName": "A"
      }
    },
    {
      "start": {
        "componentId": "resistor-1778378205248-h9g1m1wml",
        "pinName": "1"
      },
      "end": {
        "componentId": "arduino-uno",
        "pinName": "13"
      }
    },
    {
      "start": {
        "componentId": "arduino-uno",
        "pinName": "GND.1"
      },
      "end": {
        "componentId": "led-builtin",
        "pinName": "C"
      }
    },
    {
      "start": {
        "componentId": "arduino-uno",
        "pinName": "5V"
      },
      "end": {
        "componentId": "resistor-1778378159414-9y3d8f1uk",
        "pinName": "2"
      }
    },
    {
      "start": {
        "componentId": "resistor-1778378159414-9y3d8f1uk",
        "pinName": "1"
      },
      "end": {
        "componentId": "pushbutton-1778378142489-v899irppo",
        "pinName": "1.r"
      }
    },
    {
      "start": {
        "componentId": "arduino-uno",
        "pinName": "GND.3"
      },
      "end": {
        "componentId": "pushbutton-1778378142489-v899irppo",
        "pinName": "2.r"
      }
    },
    {
      "start": {
        "componentId": "arduino-uno",
        "pinName": "2"
      },
      "end": {
        "componentId": "pushbutton-1778378142489-v899irppo",
        "pinName": "1.r"
      }
    }
  ]
}
---END_EXPECTED_WIRING---

---KEY_TEXT---
digitalRead
INPUT_PULLUP
digitalWrite
Serial
---END_KEY_TEXT---
