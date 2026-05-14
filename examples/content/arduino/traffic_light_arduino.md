---LESSON_INFO---
Pelajaran Arduino: Membuat simulasi lampu lalu lintas dengan 3 LED.

**Learning Objectives:**
- Mengontrol beberapa LED secara berurutan
- Menerapkan pola sequence/timing dengan `delay()`
- Merangkai 3 LED ke Arduino
- Menggunakan `const int` untuk nama pin yang mudah dibaca

**Prerequisites:**
- Hello, World!
- LED Blink
- Hello Serial
- Button Input
---END_LESSON_INFO---

# Traffic Light — Lampu Lalu Lintas

Proyek ini mensimulasikan **lampu lalu lintas** menggunakan 3 LED:
merah, kuning, dan hijau. Kita akan mengontrol urutan nyala-mati
LED persis seperti lampu lalu lintas sungguhan.

## Urutan Lampu Lalu Lintas

```
1. MERAH menyala   (3 detik)  → Berhenti
2. KUNING menyala  (1 detik)  → Bersiap
3. HIJAU menyala   (3 detik)  → Jalan
4. KUNING menyala  (1 detik)  → Bersiap berhenti
5. Kembali ke MERAH...
```

## Menggunakan Konstanta untuk Pin

Daripada mengingat nomor pin, gunakan **konstanta bernama**:

```
const int RED_PIN = 13;
const int YELLOW_PIN = 12;
const int GREEN_PIN = 11;
```

Keuntungan:
- Kode lebih mudah dibaca: `digitalWrite(RED_PIN, HIGH)` vs `digitalWrite(13, HIGH)`
- Jika ingin ganti pin, cukup ubah di satu tempat

## Mengontrol Beberapa LED

Setiap LED memerlukan pin output sendiri:

```
void setup() {
  pinMode(RED_PIN, OUTPUT);
  pinMode(YELLOW_PIN, OUTPUT);
  pinMode(GREEN_PIN, OUTPUT);
}
```

Pastikan hanya **satu LED menyala** pada satu waktu:

```
// Nyalakan merah, matikan yang lain
digitalWrite(RED_PIN, HIGH);
digitalWrite(YELLOW_PIN, LOW);
digitalWrite(GREEN_PIN, LOW);
```

## Serial Monitor untuk Debugging

Cetak status lampu ke Serial Monitor agar mudah di-debug:

```
Serial.println("RED");
delay(3000);  // Merah menyala 3 detik
```

---EXERCISE---
### Tantangan

**Kode Arduino:**
Buat program yang mensimulasikan lampu lalu lintas:
1. **Merah** di pin 13 menyala selama 3 detik, cetak `RED` ke Serial
2. **Kuning** di pin 12 menyala selama 1 detik, cetak `YELLOW` ke Serial
3. **Hijau** di pin 11 menyala selama 3 detik, cetak `GREEN` ke Serial
4. **Kuning** lagi selama 1 detik, cetak `YELLOW` ke Serial
5. Ulangi dari merah

Pastikan hanya satu LED yang menyala pada satu waktu!

**Rangkaian:**
Hubungkan 3 LED ke Arduino:
- Pin 13 → LED Merah (Anode A), Cathode C → GND
- Pin 12 → LED Kuning (Anode A), Cathode C → GND
- Pin 11 → LED Hijau (Anode A), Cathode C → GND

Setelah selesai, tekan **Compile & Run** dan perhatikan LED menyala bergantian.
---

---INITIAL_CODE_ARDUINO---
// Traffic Light - Lampu Lalu Lintas
// Simulasi lampu merah, kuning, hijau

const int RED_PIN = 13;
const int YELLOW_PIN = 12;
const int GREEN_PIN = 11;

void setup() {
  pinMode(RED_PIN, OUTPUT);
  pinMode(YELLOW_PIN, OUTPUT);
  pinMode(GREEN_PIN, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  // Lampu MERAH
  digitalWrite(RED_PIN, HIGH);
  digitalWrite(YELLOW_PIN, LOW);
  digitalWrite(GREEN_PIN, LOW);
  Serial.println("RED");
  delay(3000);

  // Lampu KUNING
  digitalWrite(RED_PIN, LOW);
  digitalWrite(YELLOW_PIN, HIGH);
  digitalWrite(GREEN_PIN, LOW);
  Serial.println("YELLOW");
  delay(1000);

  // Lampu HIJAU
  digitalWrite(RED_PIN, LOW);
  digitalWrite(YELLOW_PIN, LOW);
  digitalWrite(GREEN_PIN, HIGH);
  Serial.println("GREEN");
  delay(3000);

  // Lampu KUNING lagi
  digitalWrite(RED_PIN, LOW);
  digitalWrite(YELLOW_PIN, HIGH);
  digitalWrite(GREEN_PIN, LOW);
  Serial.println("YELLOW");
  delay(1000);
}
---END_INITIAL_CODE_ARDUINO---

---VELXIO_CIRCUIT---
{
  "board": "arduino:avr:uno",
  "components": [
    {
      "type": "led",
      "id": "led-red",
      "x": 409.6091884525257,
      "y": 65.40692157090741,
      "rotation": 0,
      "props": {
        "color": "red",
        "pin": 13,
        "state": true,
        "value": true
      }
    },
    {
      "type": "led",
      "id": "led-yellow",
      "x": 466.09101803924966,
      "y": 66.43228050989252,
      "rotation": 0,
      "props": {
        "color": "yellow",
        "pin": 12,
        "state": false,
        "value": false
      }
    },
    {
      "type": "led",
      "id": "led-green",
      "x": 522.0366933470766,
      "y": 63.613964067867315,
      "rotation": 0,
      "props": {
        "color": "green",
        "pin": 11,
        "state": false,
        "value": false
      }
    },
    {
      "type": "resistor",
      "id": "resistor-1776300566703-7pi4wei9j",
      "x": 275.08055011716567,
      "y": 133.79325981817132,
      "rotation": 0,
      "props": {
        "value": true,
        "state": true
      }
    },
    {
      "type": "resistor",
      "id": "resistor-1776300590088-k4l87u1rf",
      "x": 273.3198126609919,
      "y": 178.95644554504224,
      "rotation": 0,
      "props": {
        "value": false,
        "state": false
      }
    },
    {
      "type": "resistor",
      "id": "resistor-1776300593575-rklkixiwy",
      "x": 270.5981563595655,
      "y": 220.2759558909028,
      "rotation": 0,
      "props": {
        "value": false,
        "state": false
      }
    }
  ],
  "wires": [
   
  ]
}
---END_VELXIO_CIRCUIT---

---EXPECTED_SERIAL_OUTPUT---
RED
YELLOW
GREEN
YELLOW
---END_EXPECTED_SERIAL_OUTPUT---

---EXPECTED_WIRING---
{
  "wires": [
     {
      "start": {
        "componentId": "resistor-1776300566703-7pi4wei9j",
        "pinName": "2"
      },
      "end": {
        "componentId": "led-red",
        "pinName": "A"
      }
    },
    {
      "start": {
        "componentId": "resistor-1776300590088-k4l87u1rf",
        "pinName": "2"
      },
      "end": {
        "componentId": "led-yellow",
        "pinName": "A"
      }
    },
    {
      "start": {
        "componentId": "resistor-1776300593575-rklkixiwy",
        "pinName": "2"
      },
      "end": {
        "componentId": "led-green",
        "pinName": "A"
      }
    },
    {
      "start": {
        "componentId": "arduino-uno",
        "pinName": "GND.3"
      },
      "end": {
        "componentId": "led-red",
        "pinName": "C"
      }
    },
    {
      "start": {
        "componentId": "arduino-uno",
        "pinName": "GND.3"
      },
      "end": {
        "componentId": "led-yellow",
        "pinName": "C"
      }
    },
    {
      "start": {
        "componentId": "arduino-uno",
        "pinName": "GND.3"
      },
      "end": {
        "componentId": "led-green",
        "pinName": "C"
      }
    },
    {
      "start": {
        "componentId": "resistor-1776300566703-7pi4wei9j",
        "pinName": "1"
      },
      "end": {
        "componentId": "arduino-uno",
        "pinName": "13"
      }
    },
    {
      "start": {
        "componentId": "resistor-1776300590088-k4l87u1rf",
        "pinName": "1"
      },
      "end": {
        "componentId": "arduino-uno",
        "pinName": "12"
      }
    },
    {
      "start": {
        "componentId": "resistor-1776300593575-rklkixiwy",
        "pinName": "1"
      },
      "end": {
        "componentId": "arduino-uno",
        "pinName": "11"
      }
    }
  ]
}
---END_EXPECTED_WIRING---

---KEY_TEXT---
pinMode
digitalWrite
const int
Serial
delay
---END_KEY_TEXT---

---EVALUATION_CONFIG---
{
  "timeout_ms": 10000
}
---END_EVALUATION_CONFIG---
