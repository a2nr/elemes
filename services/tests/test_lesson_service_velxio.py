import pytest

pytestmark = pytest.mark.unit

from services.lesson_service import _render_markdown_string


def test_render_markdown_velxio_with_code_and_circuit():
    content = """# LED Blink
Berikut adalah materi kendali LED pada Arduino.

---INITIAL_CODE_ARDUINO---
void setup() {
  pinMode(13, OUTPUT);
}
void loop() {
  digitalWrite(13, HIGH);
  delay(500);
  digitalWrite(13, LOW);
  delay(500);
}
---END_INITIAL_CODE_ARDUINO---

---VELXIO_CIRCUIT---
{
  "board": "arduino:avr:uno",
  "components": [
    { "id": "uno-1", "type": "arduino-uno", "x": 0, "y": 0 }
  ]
}
---END_VELXIO_CIRCUIT---
"""
    parsed = _render_markdown_string(content)
    assert 'velxio' in parsed['active_tabs']
    assert parsed['initial_code_arduino'].startswith('void setup()')
    assert 'arduino:avr:uno' in parsed['velxio_circuit']


def test_render_markdown_velxio_circuit_only():
    content = """# Sirkuit Saja
---VELXIO_CIRCUIT---
{"board": "arduino:avr:uno"}
---END_VELXIO_CIRCUIT---
"""
    parsed = _render_markdown_string(content)
    assert parsed['active_tabs'] == ['velxio']
    assert parsed.get('velxio_circuit') == '{"board": "arduino:avr:uno"}'


def test_render_markdown_velxio_exclusive_priority_over_c():
    content = """# Prioritas Arduino
---INITIAL_CODE_ARDUINO---
void setup() {}
---END_INITIAL_CODE_ARDUINO---

---INITIAL_CODE---
int main() { return 0; }
---END_INITIAL_CODE---
"""
    parsed = _render_markdown_string(content)
    # INITIAL_CODE_ARDUINO harus menjadikan mode velxio eksklusif tanpa tab 'c'
    assert 'velxio' in parsed['active_tabs']
    assert 'c' not in parsed['active_tabs']
