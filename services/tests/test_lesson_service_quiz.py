import pytest

pytestmark = pytest.mark.unit
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


# ── Fitur B: taksonomi key quiz (QUIZ_MCQ / QUIZ_WEIGHTED / FLASHCARD) ──


class TestQuizMcqKey:
    """Key ---QUIZ_MCQ--- — MCQ biner, validasi ketat."""

    def test_basic_parse(self):
        md_text = """### Berapa 1+1?
- [] 3
- [x] 2
"""
        quiz = _parse_flashcards(md_text, kind='mcq')
        assert len(quiz) == 1
        q = quiz[0]
        assert q['type'] == 'mcq'
        assert q['quiz_type'] == 'mcq'
        assert q['id'] == 'q-0'
        assert [o['weight'] for o in q['options']] == [0, 1]
        assert q['options'][1]['is_correct'] is True

    def test_weighted_syntax_rejected(self):
        md_text = """### Soal MCQ dengan bobot?
- [10] A
- [ ] B
"""
        with pytest.raises(ValueError, match="tidak boleh memakai bobot angka"):
            _parse_flashcards(md_text, kind='mcq')

    def test_two_correct_rejected(self):
        md_text = """### Dua kunci?
- [x] A
- [x] B
"""
        with pytest.raises(ValueError, match="tepat satu opsi benar"):
            _parse_flashcards(md_text, kind='mcq')

    def test_zero_correct_rejected(self):
        md_text = """### Tanpa kunci?
- [] A
- [] B
"""
        with pytest.raises(ValueError, match="tepat satu opsi benar"):
            _parse_flashcards(md_text, kind='mcq')

    def test_without_options_rejected(self):
        """QUIZ_MCQ tanpa opsi tidak valid — bukan flashcard."""
        md_text = "### Pertanyaan tanpa opsi\njawaban bebas\n"
        with pytest.raises(ValueError, match="wajib punya opsi jawaban"):
            _parse_flashcards(md_text, kind='mcq')

    def test_diagnostic_marker_still_works(self):
        """::diagnostic tetap kategori di dalam QUIZ_MCQ dan masuk skor resmi."""
        md_text = """### Soal diagnostik
::diagnostic
- [x] a
- [] b
"""
        quiz = _parse_flashcards(md_text, kind='mcq')
        assert quiz[0]['category'] == 'diagnostik'
        assert quiz[0]['quiz_type'] == 'mcq'


class TestQuizWeightedKey:
    """Key ---QUIZ_WEIGHTED--- — MCQ berbobot [N]."""

    def test_basic_parse_max_weight_is_key(self):
        md_text = """### Seberapa tepat pernyataan ini?
- [10] Paling tepat
- [7] Kurang tepat
- [ ] Salah
"""
        quiz = _parse_flashcards(md_text, kind='weighted')
        assert len(quiz) == 1
        q = quiz[0]
        assert q['type'] == 'mcq'
        assert q['quiz_type'] == 'weighted'
        assert [o['weight'] for o in q['options']] == [10, 7, 0]
        # is_correct = opsi bobot tertinggi
        assert [o['is_correct'] for o in q['options']] == [True, False, False]

    def test_x_mark_rejected(self):
        md_text = """### Campur [x] dengan bobot?
- [x] A
- [7] B
- [ ] C
"""
        with pytest.raises(ValueError, match="tidak boleh memakai penanda"):
            _parse_flashcards(md_text, kind='weighted')

    def test_zero_weight_rejected(self):
        md_text = """### Bobot nol?
- [10] A
- [0] B
- [ ] C
"""
        with pytest.raises(ValueError, match="bobot harus berupa bilangan bulat >= 1"):
            _parse_flashcards(md_text, kind='weighted')

    def test_missing_blank_option_rejected(self):
        """Semua opsi berbobot — tidak ada [ ] sbg jawaban salah → error."""
        md_text = """### Tanpa opsi kosong?
- [10] A
- [7] B
- [3] C
"""
        with pytest.raises(ValueError, match="minimal satu opsi tanpa bobot"):
            _parse_flashcards(md_text, kind='weighted')

    def test_duplicate_max_weight_rejected(self):
        md_text = """### Bobot tertinggi dobel?
- [10] A
- [10] B
- [ ] C
"""
        with pytest.raises(ValueError, match="bobot tertinggi harus unik"):
            _parse_flashcards(md_text, kind='weighted')

    def test_without_options_rejected(self):
        md_text = "### Pertanyaan tanpa opsi\njawaban bebas\n"
        with pytest.raises(ValueError, match="wajib punya opsi jawaban"):
            _parse_flashcards(md_text, kind='weighted')

    def test_partial_credit_possible(self):
        """Opsi [7] bukan kunci tapi tetap membawa poin parsial."""
        md_text = """### Penilaian bertingkat?
- [10] Sempurna
- [7] Cukup
- [ ] Salah
"""
        q = _parse_flashcards(md_text, kind='weighted')[0]
        weights = {o['text']: o['weight'] for o in q['options']}
        assert weights['<p>Sempurna</p>'] == 10
        assert weights['<p>Cukup</p>'] == 7
        assert weights['<p>Salah</p>'] == 0

    def test_explanation_still_parsed(self):
        md_text = """### Soal berbobot?
- [10] A
- [ ] B
> Pembahasan soal berbobot.
"""
        q = _parse_flashcards(md_text, kind='weighted')[0]
        assert 'Pembahasan soal berbobot' in q['explanation']


class TestFlashcardKey:
    """Key ---FLASHCARD--- — tanpa opsi jawaban."""

    def test_basic_parse(self):
        md_text = """### Pertanyaan hafalan?
Ini jawabannya.
> Penjelasan tambahan.
"""
        quiz = _parse_flashcards(md_text, kind='flashcard')
        assert len(quiz) == 1
        q = quiz[0]
        assert q['type'] == 'flashcard'
        assert q['quiz_type'] == 'flashcard'
        assert q['options'] is None
        assert 'Pertanyaan hafalan' in q['front']
        assert 'Ini jawabannya' in q['back']
        assert 'Penjelasan tambahan' in q['explanation']

    def test_with_options_rejected(self):
        md_text = """### Flashcard dengan opsi?
- [x] A
- [] B
"""
        with pytest.raises(ValueError, match="tidak boleh punya opsi jawaban"):
            _parse_flashcards(md_text, kind='flashcard')


class TestLegacyZeroRegression:
    """Key legacy ---QUIZ_FLASHCARD--- berperilaku 100% sama seperti sebelumnya."""

    def test_legacy_bracket_number_is_not_an_option(self):
        """'- [10]' di konten legacy BUKAN opsi — tetap bagian body soal.

        Kontrak zero-regression: regex legacy sengaja tidak mengenali bobot.
        """
        md_text = """### Contoh format jawaban
- [10] ini bukan opsi, hanya teks
- [x] opsi asli
- [] bukan kunci
"""
        quiz = _parse_flashcards(md_text, kind='legacy')
        assert len(quiz) == 1
        q = quiz[0]
        # Hanya 2 opsi asli; '- [10]' tidak menjadi opsi
        assert len(q['options']) == 2
        # '- [10]' tetap ada di body question
        assert '[10]' in q['question']

    def test_legacy_implicit_typing(self):
        """Legacy: ada opsi → mcq, tanpa opsi → flashcard."""
        md_text = """### Soal pilihan?
- [x] a
- [] b

### Kartu hafalan?
jawaban bebas
"""
        quiz = _parse_flashcards(md_text, kind='legacy')
        assert [q['type'] for q in quiz] == ['mcq', 'flashcard']
        assert [q['quiz_type'] for q in quiz] == ['mcq', 'flashcard']

    def test_legacy_validation_unchanged(self):
        md_text = """### Dua kunci?
- [x] A
- [x] B
"""
        with pytest.raises(ValueError, match="tepat satu opsi benar"):
            _parse_flashcards(md_text, kind='legacy')

    def test_legacy_flashcard_with_options_allowed(self):
        """Legacy: opsi diperbolehkan di soal tanpa opsi? Tidak — opsi = mcq.
        Tapi flashcard legacy + opsi di soal LAIN tetap sah (inspeksi per soal)."""
        md_text = """### Kartu A?
jawaban bebas

### Soal B?
- [x] a
- [] b
"""
        quiz = _parse_flashcards(md_text, kind='legacy')
        assert [q['type'] for q in quiz] == ['flashcard', 'mcq']


class TestFieldsAlwaysEmitted:
    """weight & quiz_type wajib ada di SEMUA soal/opsi, termasuk legacy."""

    def test_legacy_mcq_weights_derived(self):
        md_text = """### Q?
- [] a
- [x] b
"""
        q = _parse_flashcards(md_text, kind='legacy')[0]
        assert all('weight' in o for o in q['options'])
        assert [o['weight'] for o in q['options']] == [0, 1]
        assert q['quiz_type'] == 'mcq'

    def test_legacy_flashcard_fields(self):
        q = _parse_flashcards("### F?\njawaban\n", kind='legacy')[0]
        assert q['quiz_type'] == 'flashcard'
        assert q['options'] is None

    def test_weighted_weights_explicit(self):
        q = _parse_flashcards("### W?\n- [5] a\n- [ ] b\n", kind='weighted')[0]
        assert [o['weight'] for o in q['options']] == [5, 0]
        assert q['quiz_type'] == 'weighted'


class TestExtractQuizSections:
    """Ekstraksi multi-key urut dokumen + beberapa blok per key."""

    def test_document_order_across_keys(self):
        from services.lesson_service import _extract_quiz_sections
        content = (
            "prosa\n"
            "---FLASHCARD---\n### F?\njawab\n---END_FLASHCARD---\n"
            "tengah\n"
            "---QUIZ_MCQ---\n### M?\n- [x] a\n- [] b\n---END_QUIZ_MCQ---\n"
            "penutup\n"
        )
        sections, remaining = _extract_quiz_sections(content)
        assert [kind for kind, _ in sections] == ['flashcard', 'mcq']
        assert '### F?' in sections[0][1]
        assert '- [x] a' in sections[1][1]
        # Semua blok quiz terangkat dari konten tersisa
        assert 'QUIZ_MCQ' not in remaining
        assert 'FLASHCARD' not in remaining
        assert 'prosa' in remaining and 'tengah' in remaining

    def test_multiple_blocks_per_key(self):
        from services.lesson_service import _extract_quiz_sections
        content = (
            "---QUIZ_MCQ---\n### M1?\n- [x] a\n- [] b\n---END_QUIZ_MCQ---\n"
            "---FLASHCARD---\n### F?\njawab\n---END_FLASHCARD---\n"
            "---QUIZ_MCQ---\n### M2?\n- [x] c\n- [] d\n---END_QUIZ_MCQ---\n"
        )
        sections, _ = _extract_quiz_sections(content)
        assert [kind for kind, _ in sections] == ['mcq', 'flashcard', 'mcq']
        assert '### M1?' in sections[0][1]
        assert '### M2?' in sections[2][1]

    def test_missing_end_marker_skipped(self):
        from services.lesson_service import _extract_quiz_sections
        content = "---QUIZ_MCQ---\n### M?\n- [x] a\n- [] b\n"  # tanpa END
        sections, remaining = _extract_quiz_sections(content)
        assert sections == []
        assert '### M?' in remaining


class TestRenderMarkdownStringMixedKeys:
    """Integrasi via _render_markdown_string — gabungan blok & id berantai."""

    MCQ1 = "---QUIZ_MCQ---\n### M1?\n- [x] a\n- [] b\n---END_QUIZ_MCQ---\n"
    CARD = "---FLASHCARD---\n### F?\njawab\n---END_FLASHCARD---\n"
    MCQ2 = "---QUIZ_MCQ---\n### M2?\n- [x] c\n- [] d\n---END_QUIZ_MCQ---\n"
    WEIGHTED = (
        "---QUIZ_WEIGHTED---\n### W?\n- [10] a\n- [7] b\n- [ ] c\n"
        "---END_QUIZ_WEIGHTED---\n"
    )

    def _render(self, *quiz_blocks):
        from services.lesson_service import _render_markdown_string
        return _render_markdown_string("# Judul\n\n" + "".join(quiz_blocks))

    def test_ids_chain_across_sections(self):
        parsed = self._render(self.MCQ1, self.CARD, self.MCQ2)
        ids = [q['id'] for q in parsed['quiz_data']]
        assert ids == ['q-0', 'q-1', 'q-2']
        assert [q['quiz_type'] for q in parsed['quiz_data']] == [
            'mcq', 'flashcard', 'mcq'
        ]

    def test_tab_deduped_across_keys(self):
        parsed = self._render(self.MCQ1, self.CARD, self.WEIGHTED)
        assert parsed['active_tabs'].count('quiz') == 1

    def test_weighted_question_renders_h3_with_id(self):
        parsed = self._render(self.WEIGHTED)
        q = parsed['quiz_data'][0]
        assert q['question'].startswith('<h3 id=')
        assert [o['weight'] for o in q['options']] == [10, 7, 0]

    def test_question_heading_renders_h3(self):
        """Heading soal → <h3 id="..."> (paritas backend↔frontend)."""
        parsed = self._render(self.MCQ1)
        q = parsed['quiz_data'][0]
        assert '<h3 id="m1">M1?</h3>' in q['question']


class TestGetLessonQuizTotal:
    """get_lesson_quiz_total: 100 utk kuis berbobot, N soal selainnya."""

    def _write_lesson(self, tmp_path, monkeypatch, name, body):
        p = tmp_path / f"{name}.md"
        p.write_text(body, encoding='utf-8')
        monkeypatch.setattr('services.lesson_service.CONTENT_DIR', str(tmp_path))
        return p

    def test_weighted_quiz_total_is_100(self, tmp_path, monkeypatch):
        from services.lesson_service import get_lesson_quiz_total
        self._write_lesson(
            tmp_path, monkeypatch, 'quiz_weighted_total',
            "# L\n" + TestRenderMarkdownStringMixedKeys.WEIGHTED,
        )
        assert get_lesson_quiz_total('quiz_weighted_total') == 100

    def test_mcq_quiz_total_is_question_count(self, tmp_path, monkeypatch):
        from services.lesson_service import get_lesson_quiz_total
        self._write_lesson(
            tmp_path, monkeypatch, 'quiz_mcq_total',
            "# L\n" + TestRenderMarkdownStringMixedKeys.MCQ1,
        )
        assert get_lesson_quiz_total('quiz_mcq_total') == 1

    def test_no_quiz_returns_none(self, tmp_path, monkeypatch):
        from services.lesson_service import get_lesson_quiz_total
        self._write_lesson(tmp_path, monkeypatch, 'quiz_none_total', "# L\nprosa\n")
        assert get_lesson_quiz_total('quiz_none_total') is None
