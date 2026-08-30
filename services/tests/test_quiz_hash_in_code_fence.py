import pytest

pytestmark = pytest.mark.unit
from services.lesson_service import _parse_flashcards


def test_mcq_code_fence_with_hash_comment_is_single_question():
    """Soal yang prompt-nya berisi code fence dengan komentar `#` (python/shell)
    tidak boleh di-split menjadi soal ganda — opsi tetap milik soal tersebut.

    REGRESI: splitter `^#{1,3}\\s+` di _parse_flashcards membelah teks
    pada baris `# ini komentar`, sehingga opsi meleset ke 'soal hantu'.
    """
    md_text = """### Berapa hasil dari kode berikut?
```python
# ini komentar python
x = 5
print(x)
```
- [] 3
- [x] 5
- [] 5.0
"""
    quiz = _parse_flashcards(md_text)
    # Harus 1 soal, bukan 2 (soal asli + 'ini komentar python' sebagai phantom)
    assert len(quiz) == 1, f"ter-split menjadi {len(quiz)} soal: {[q.get('question', q.get('front')) for q in quiz]}"
    q = quiz[0]
    assert q['type'] == 'mcq'
    assert len(q['options']) == 3, f"opsi cuma {len(q['options'])}: {q['options']}"
    assert q['options'][1]['is_correct'] is True


def test_mcq_code_fence_with_hash_comment_in_middle():
    """Kasus `#` komentar muncul di tengah kode (bukan baris pertama)."""
    md_text = """### Apa output?
```bash
echo "hi"  # comment di sini
echo "bye"
```
- [x] hi
- [] bye
"""
    quiz = _parse_flashcards(md_text)
    assert len(quiz) == 1, f"ter-split menjadi {len(quiz)} soal"
    assert len(quiz[0]['options']) == 2
