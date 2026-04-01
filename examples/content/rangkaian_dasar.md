---LESSON_INFO---
Pelajaran hybrid: Pemrograman C + Simulator Rangkaian Elektronika.

**Learning Objectives:**
- Memahami konsep voltage divider
- Menulis program C untuk menghitung tegangan
- Menggunakan simulator rangkaian

**Prerequisites:**
- Hello, World!
- Variabel
---END_LESSON_INFO---

# Rangkaian Voltage Divider

Rangkaian **voltage divider** membagi tegangan input menjadi tegangan yang lebih kecil
menggunakan dua resistor.

## Rumus

```
Vout = Vin * (R2 / (R1 + R2))
```

Jika R1 = R2 = 1kΩ dan Vin = 5V:
```
Vout = 5 * (1000 / (1000 + 1000)) = 2.5V
```

## Contoh Rangkaian

Berikut rangkaian voltage divider sederhana:

```circuit
<cir f="1" ts="0.000005" ic="10.20027730826997" cb="50" pb="50" vr="5" mts="5e-11">
  <v x="80 200 80 112" f="0" wf="0" maxv="5"/>
  <r x="80 112 176 112" f="0" r="1000"/>
  <r x="176 112 176 200" f="0" r="1000"/>
  <w x="176 200 80 200" f="0"/>
  <ln x="176 112 208 32" f="0" te="Vout"/>
</cir>
```

Perhatikan tegangan di **Vout** adalah ~2.5V.

---EXERCISE---
### Tantangan 1: Pemrograman C
Buat program yang mencetak hasil perhitungan voltage divider.

### Tantangan 2: Elektronika
Lengkapi rangkaian agar tegangan di **Vout** bernilai **2.5V**.
---

---INITIAL_CODE---
#include <stdio.h>

int main() {
    // Hitung voltage divider: Vout = Vin * R2 / (R1 + R2)
    // Vin=5, R1=1000, R2=1000

    return 0;
}
---END_INITIAL_CODE---

---INITIAL_CIRCUIT---
<cir f="1" ts="0.000005" ic="10.20027730826997" cb="50" pb="50" vr="5" mts="5e-11">
  <v x="80 200 80 112" f="0" wf="0" maxv="5"/>
  <r x="80 112 176 112" f="0" r="1000"/>
  <w x="176 200 80 200" f="0"/>
  <ln x="176 112 208 32" f="0" te="Vout"/>
</cir>
---END_INITIAL_CIRCUIT---

---EXPECTED_OUTPUT---
Vout = 2.50V
---END_EXPECTED_OUTPUT---

---EXPECTED_CIRCUIT_OUTPUT---
{
  "nodes": {
    "Vout": { "voltage": 2.5, "tolerance": 0.2 }
  }
}
---END_EXPECTED_CIRCUIT_OUTPUT---

---KEY_TEXT---
printf
---END_KEY_TEXT---

---KEY_TEXT_CIRCUIT---
Vout
---END_KEY_TEXT_CIRCUIT---
