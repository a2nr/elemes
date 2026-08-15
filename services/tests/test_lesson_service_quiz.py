import pytest

from services.lesson_service import _parse_flashcards


def test_mcq_multiline_prompt_code_fence_and_paragraph():
    md_text = """### Perhatikan program berikut
```c
int x = 2;
printf("%d", x * 3);
```
Berapakah keluarannya?
- [] 2
- [] 3
- [x] 6
- [] Error

> `x * 3` menghasilkan `6`.
"""
    quiz = _parse_flashcards(md_text)
    assert len(quiz) == 1
    q = quiz[0]
    assert q['type'] == 'mcq'
    # Code fence dirender di question, bukan hilang
    assert '<pre><code' in q['question']
    assert 'language-c' in q['question']
    # Paragraf tambahan ikut masuk question
    assert 'Berapakah keluarannya?' in q['question']
    # Opsi tidak bocor ke question
    assert '- []' not in q['question']
    assert len(q['options']) == 4
    # Opsi dirender markdown (inline code)
    assert q['options'][2]['text'].strip() == '<p>6</p>'
    assert q['options'][2]['is_correct'] is True


def test_mcq_table_and_math_rendered_in_question():
    md_text = """### Dari tabel berikut, berapa totalnya?

| A | B |
|---|---|
| 1 | 2 |
| 3 | 4 |

$$x^2 + y = 10$$

- [x] 10
- [] 9
- [] 11
"""
    quiz = _parse_flashcards(md_text)
    assert len(quiz) == 1
    q = quiz[0]
    assert '<table' in q['question']
    assert 'x^2' in q['question']
    assert len(q['options']) == 3


def test_mcq_image_directive_extracted_not_in_question():
    md_text = """### Apa warna langit pada siang hari?
image: demo_quiz.png
- [x] Biru
- [] Hijau
- [] Merah
"""
    quiz = _parse_flashcards(md_text)
    assert len(quiz) == 1
    q = quiz[0]
    assert q['image'] == '/assets/demo_quiz.png'
    assert 'image:' not in q['question']
    assert 'demo_quiz.png' not in q['question']


def test_mcq_explanation_after_options_not_in_question_or_options():
    md_text = """### Apa output dari `printf("%d", 5 + 5);`?
- [] 55
- [x] 10
- [] 5 + 5

> Penjelasan: Operasi `5 + 5` dihitung dulu menjadi `10`.
"""
    quiz = _parse_flashcards(md_text)
    assert len(quiz) == 1
    q = quiz[0]
    assert q['explanation'] != ''
    assert 'Penjelasan' in q['explanation']
    assert 'Penjelasan' not in q['question']
    for opt in q['options']:
        assert 'Penjelasan' not in opt['text']


def test_flashcard_simple_compat():
    md_text = """### Apa fungsi dari `return 0;` di dalam fungsi `main()`?
Menandakan bahwa program telah selesai berjalan dengan sukses.
"""
    quiz = _parse_flashcards(md_text)
    assert len(quiz) == 1
    q = quiz[0]
    assert q['type'] == 'flashcard'
    assert 'return' in q['front']
    assert 'Menandakan bahwa program' in q['back']
    assert q['options'] is None or q['options'] == []


def test_flashcard_with_explanation_back_clean():
    md_text = """### Bagaimana cara menulis komentar satu baris di bahasa C?
Cukup gunakan dua garis miring di awal baris.

> Penjelasan: Komentar diabaikan oleh compiler.
"""
    quiz = _parse_flashcards(md_text)
    assert len(quiz) == 1
    q = quiz[0]
    assert q['type'] == 'flashcard'
    assert 'Penjelasan' in q['explanation']
    assert 'Penjelasan' not in q['back']
    assert 'dua garis miring' in q['back']


def test_stable_ids_questions_and_options():
    md_text = """### Soal pertama?
- [x] A
- [] B

### Soal kedua?
- [] C
- [x] D
"""
    quiz = _parse_flashcards(md_text)
    assert [q['id'] for q in quiz] == ['q-0', 'q-1']
    assert [o['id'] for o in quiz[0]['options']] == ['q-0-o-0', 'q-0-o-1']
    assert [o['id'] for o in quiz[1]['options']] == ['q-1-o-0', 'q-1-o-1']


def test_mcq_zero_correct_raises_valueerror():
    md_text = """### Soal tanpa jawaban benar?
- [] A
- [] B
- [] C
"""
    with pytest.raises(ValueError):
        _parse_flashcards(md_text)


def test_mcq_two_correct_raises_valueerror():
    md_text = """### Soal dengan dua jawaban benar?
- [x] A
- [] B
- [x] C
"""
    with pytest.raises(ValueError):
        _parse_flashcards(md_text)


def test_options_inside_code_fence_ignored():
    md_text = """### Mana yang benar?
```markdown
- [x] ini bukan opsi, ini contoh di dalam code fence
- [] juga bukan
```
- [x] Opsi asli 1
- [] Opsi asli 2
"""
    quiz = _parse_flashcards(md_text)
    assert len(quiz) == 1
    q = quiz[0]
    assert len(q['options']) == 2
    # Isi code fence tetap ada di question
    assert 'ini bukan opsi' in q['question']
    assert 'Opsi asli 1' not in q['question']


def test_image_markdown_in_question_heading():
    md_text = """### Pilih gambar yang melambangkan bahasa C:
![C Logo](https://upload.wikimedia.org/wikipedia/commons/1/18/C_Programming_Language.svg)
- [x] Benar
- [] Salah
"""
    quiz = _parse_flashcards(md_text)
    assert len(quiz) == 1
    q = quiz[0]
    assert q['image'] == 'https://upload.wikimedia.org/wikipedia/commons/1/18/C_Programming_Language.svg'


def test_empty_and_blank_text_returns_empty_list():
    assert _parse_flashcards("") == []
    assert _parse_flashcards("   \n  ") == []


def test_old_flat_format_still_parses_with_ids():
    md_text = """### Bahasa C adalah bahasa tingkat rendah.
- [] Benar
- [x] Salah
"""
    quiz = _parse_flashcards(md_text)
    assert len(quiz) == 1
    assert quiz[0]['id'] == 'q-0'
    assert quiz[0]['type'] == 'mcq'
    assert len(quiz[0]['options']) == 2
    assert quiz[0]['options'][1]['is_correct'] is True


def test_default_category_is_evaluasi():
    md_text = """### Mana yang benar?
- [] Salah
- [x] Benar
"""
    quiz = _parse_flashcards(md_text)
    assert len(quiz) == 1
    assert quiz[0]['category'] == 'evaluasi'


def test_diagnostic_marker_on_own_line_sets_category_mcq():
    md_text = """### Apa output dari `printf("%d", 5 + 5);`?
::diagnostic
- [] 55
- [x] 10
- [] 5 + 5

> Penjelasan: 5 + 5 = 10.
"""
    quiz = _parse_flashcards(md_text)
    assert len(quiz) == 1
    q = quiz[0]
    assert q['category'] == 'diagnostik'
    # Marker tidak boleh bocor ke teks yang dirender
    assert '::diagnostic' not in q['question']
    assert len(q['options']) == 3


def test_diagnostic_marker_on_own_line_sets_category_flashcard():
    md_text = """### Apa fungsi `return 0;`?
::diagnostic
Program selesai dengan sukses.
"""
    quiz = _parse_flashcards(md_text)
    assert len(quiz) == 1
    q = quiz[0]
    assert q['category'] == 'diagnostik'
    assert '::diagnostic' not in q['front']
    assert 'sukses' in q['back']


def test_diagnostic_marker_inline_in_heading_does_not_set_category():
    """Kontrak: marker wajib di baris sendiri — format inline (lama) diabaikan."""
    md_text = """### Apa output dari `printf("%d", 5 + 5);`  <-- ::diagnostic
- [] 55
- [x] 10
- [] 5 + 5
"""
    quiz = _parse_flashcards(md_text)
    assert len(quiz) == 1
    q = quiz[0]
    assert q['category'] == 'evaluasi'
    # Konten heading tetap dipertahankan apa adanya (termasuk komentar)
    assert '::diagnostic' in q['question']


def test_diagnostic_mixed_questions_categorized_independently():
    md_text = """### Soal evaluasi 1
- [] a
- [x] b

### Soal diagnostik 1
::diagnostic
- [] a
- [x] b

### Soal evaluasi 2
- [] a
- [x] b
"""
    quiz = _parse_flashcards(md_text)
    assert [q['category'] for q in quiz] == ['evaluasi', 'diagnostik', 'evaluasi']
