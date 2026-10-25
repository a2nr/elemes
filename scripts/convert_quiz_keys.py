#!/usr/bin/env python3
"""Konversi key quiz legacy ---QUIZ_FLASHCARD--- ke key baru per jenis.

Fitur B (taksonomi key quiz): setiap jenis quiz kini punya key sendiri:

  ---QUIZ_MCQ---      soal pilihan ganda biner (tepat satu [x]; ::diagnostic
                      tetap valid sebagai penanda kategori di dalamnya)
  ---QUIZ_WEIGHTED--- soal pilihan ganda berbobot ([N], N >= 1)
  ---FLASHCARD---     kartu hafalan tanpa opsi

Script ini menulis ulang blok legacy menjadi rangkaian blok baru dengan
aturan "run berurutan": soal-soal MCQ dan flashcard yang BERSAMBUNG di blok
legacy digabung ke satu blok baru masing-masing, sehingga URUTAN soal (dan
dengan itu id `q-0`, `q-1`, ...) tetap persis sama setelah konversi.

Contoh: [MCQ, MCQ, Flash, MCQ] → QUIZ_MCQ(2) + FLASHCARD(1) + QUIZ_MCQ(1).

Sifat:
- Idempoten — dijalankan kedua kali tidak mengubah apa pun (tidak ada blok
  legacy tersisa setelah konversi pertama).
- Terverifikasi — setelah menulis, hasil parse `_render_markdown_string`
  dibandingkan dengan hasil parse SEBELUM konversi; mismatch → exit 1.

Pemakaian:
  python scripts/convert_quiz_keys.py                 # proses examples/content
  python scripts/convert_quiz_keys.py content/        # path folder/file lain
  python scripts/convert_quiz_keys.py --dry-run       # lihat rencana saja
"""

import argparse
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

LEGACY_START = '---QUIZ_FLASHCARD---'
LEGACY_END = '---END_QUIZ_FLASHCARD---'

# Regex opsi legacy — sama dengan services/lesson_service.py::_OPTION_LINE_RE.
_OPTION_LINE_RE = re.compile(r'^\s*-\s*\[([ xX]?)\]\s*(.*)$')


def split_question_blocks(text):
    """Pecah markdown jadi blok per soal pada heading (`^#{1,3}\\s+`),
    mengabaikan heading di dalam fenced code block. Mirror dari
    `_split_flashcard_parts` (services/lesson_service.py).
    """
    parts = []
    buf = []
    in_fence = False
    for line in text.split('\n'):
        if line.strip().startswith('```'):
            in_fence = not in_fence
            buf.append(line)
            continue
        if not in_fence and re.match(r'^#{1,3}\s+', line):
            if buf:
                parts.append('\n'.join(buf))
            buf = [line]
            continue
        buf.append(line)
    if buf:
        parts.append('\n'.join(buf))
    return [p for p in parts if p.strip()]


def is_mcq_block(block):
    """True bila blok soal punya minimal satu baris opsi legacy."""
    in_fence = False
    for line in block.split('\n'):
        if line.strip().startswith('```'):
            in_fence = not in_fence
            continue
        if not in_fence and _OPTION_LINE_RE.match(line):
            return True
    return False


def group_runs(blocks):
    """Kelompokkan blok soal berurutan dengan jenis sama → list of (kind, text)."""
    runs = []
    for block in blocks:
        kind = 'mcq' if is_mcq_block(block) else 'flashcard'
        if runs and runs[-1][0] == kind:
            runs[-1] = (kind, runs[-1][1].rstrip('\n') + '\n\n' + block)
        else:
            runs.append((kind, block))
    return runs


RUN_MARKER = {
    'mcq': ('---QUIZ_MCQ---', '---END_QUIZ_MCQ---'),
    'flashcard': ('---FLASHCARD---', '---END_FLASHCARD---'),
}


def convert_text(text):
    """Return (converted_text, jumlah_blok_legacy, jumlah_soal) atau
    (text, 0, 0) bila tidak ada blok legacy."""
    if LEGACY_START not in text:
        return text, 0, 0

    out = []
    question_count = 0
    legacy_blocks = 0
    rest = text
    while LEGACY_START in rest:
        start_idx = rest.find(LEGACY_START)
        end_idx = rest.find(LEGACY_END, start_idx + len(LEGACY_START))
        if end_idx == -1:
            # Marker end hilang — biarkan apa adanya (parser juga melewatinya).
            out.append(rest)
            rest = ''
            break
        before = rest[:start_idx]
        inner = rest[start_idx + len(LEGACY_START):end_idx]
        after = rest[end_idx + len(LEGACY_END):]

        blocks = split_question_blocks(inner)
        legacy_blocks += 1
        if not blocks:
            # Blok kosong — biarkan legacy (menghapus marker mengubah status
            # tab quiz; lebih aman dibiarkan & dilaporkan).
            out.append(rest[:end_idx + len(LEGACY_END)])
            rest = after
            continue

        segments = []
        for kind, run_text in group_runs(blocks):
            m_start, m_end = RUN_MARKER[kind]
            segments.append(f"{m_start}\n{run_text.strip()}\n{m_end}")
            question_count += len(split_question_blocks(run_text))

        out.append(before + '\n\n' + '\n\n'.join(segments) + '\n\n')
        rest = after

    if rest:
        out.append(rest)
    return ''.join(out), legacy_blocks, question_count


def render_quiz_summary(parsed):
    """Ringkasan quiz_data utk perbandingan sebelum/sesudah konversi."""
    summary = []
    for q in parsed.get('quiz_data') or []:
        summary.append({
            'id': q.get('id'),
            'type': q.get('type'),
            'quiz_type': q.get('quiz_type'),
            'category': q.get('category'),
            'image': q.get('image'),
            'question': q.get('question'),
            'front': q.get('front'),
            'back': q.get('back'),
            'explanation': q.get('explanation'),
            'options': [
                {
                    'id': o.get('id'),
                    'text': o.get('text'),
                    'is_correct': o.get('is_correct'),
                    'weight': o.get('weight'),
                }
                for o in (q.get('options') or [])
            ],
        })
    return summary


def verify_parse_parity(path, before_raw, after_raw):
    """Bandingkan hasil parse (quiz_data + active_tabs) sebelum vs sesudah."""
    from services.lesson_service import _render_markdown_string

    before = _render_markdown_string(before_raw)
    after = _render_markdown_string(after_raw)
    problems = []
    if render_quiz_summary(before) != render_quiz_summary(after):
        problems.append('quiz_data berubah setelah konversi')
    if before.get('active_tabs') != after.get('active_tabs'):
        problems.append(
            f"active_tabs berubah: {before.get('active_tabs')} -> {after.get('active_tabs')}"
        )
    return problems


def iter_markdown_files(paths):
    for p in paths:
        if os.path.isfile(p):
            yield p
        elif os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                for name in sorted(files):
                    if name.endswith('.md'):
                        yield os.path.join(root, name)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        'paths', nargs='*',
        default=[os.path.join(REPO_ROOT, 'examples', 'content')],
        help='File/folder markdown yang diproses (default: examples/content)',
    )
    parser.add_argument('--dry-run', action='store_true', help='Tidak menulis file')
    parser.add_argument(
        '--no-verify', action='store_true',
        help='Lewati verifikasi parse sebelum/sesudah konversi',
    )
    args = parser.parse_args()

    # Import parser backend hanya untuk verifikasi.
    if not args.no_verify:
        try:
            import services.lesson_service  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            print(f"Peringatan: parser backend tidak bisa diimport ({exc}); "
                  f"verifikasi dilewati.", file=sys.stderr)
            args.no_verify = True

    converted = skipped = 0
    failures = 0
    for path in iter_markdown_files(args.paths):
        with open(path, 'r', encoding='utf-8') as f:
            original = f.read()
        if LEGACY_START not in original:
            continue

        converted_text, legacy_blocks, question_count = convert_text(original)
        if legacy_blocks == 0:
            continue

        rel = os.path.relpath(path, REPO_ROOT)
        if not question_count:
            print(f"LEWATI  {rel} — blok legacy tanpa soal (dibiarkan apa adanya)")
            skipped += 1
            continue

        label = 'DRY-RUN' if args.dry_run else 'KONVERSI'
        print(f"{label}  {rel} — {legacy_blocks} blok legacy, {question_count} soal")
        if not args.dry_run:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(converted_text)
            if not args.no_verify:
                problems = verify_parse_parity(path, original, converted_text)
                if problems:
                    failures += 1
                    print(f"  GAGAL verifikasi: {'; '.join(problems)}", file=sys.stderr)
                    # Pulihkan konten asli agar repo tidak setengah terkonversi.
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(original)
                    continue
                print("  verifikasi parse OK (quiz_data & active_tabs identik)")
        converted += 1

    print(f"\nSelesai: {converted} file dikonversi, {skipped} dilewati, {failures} gagal verifikasi.")
    if args.dry_run:
        print("(dry-run — tidak ada file yang ditulis)")
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
