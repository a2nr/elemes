"""Pindai konten markdown & laporkan masalah kuis (alat bantu dev, ad-hoc).

Mendukung SEMUA key quiz (baru + legacy):
  ---QUIZ_MCQ--- / ---QUIZ_WEIGHTED--- / ---FLASHCARD--- / ---QUIZ_FLASHCARD---

Dipakai manual dari root repo:
  python scripts/_scan_quiz_issues.py [CONTENT_DIR]
"""

import sys, glob, os

CONTENT_DIR = sys.argv[1] if len(sys.argv) > 1 else '/home/a2nr/lms-dev/elemes/content'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.lesson_service import (  # noqa: E402
    _parse_flashcards,
    _extract_quiz_sections,
    QUIZ_SECTION_SPECS,
)

issues = 0
for f in glob.glob(os.path.join(CONTENT_DIR, '**', '*.md'), recursive=True):
    txt = open(f, encoding='utf-8').read()
    if not any(start in txt for _, start, _ in QUIZ_SECTION_SPECS):
        continue
    sections, _ = _extract_quiz_sections(txt)
    for kind, raw in sections:
        if not raw.strip():
            continue
        try:
            cards = _parse_flashcards(raw, kind=kind)
        except ValueError as e:
            print(f'[RAISE] {f}: {e}')
            issues += 1
            continue
        for c in cards:
            if c['type'] == 'mcq' and len(c.get('options') or []) < 2:
                label = (c.get('question') or c.get('front') or '')[:60]
                print(f'[<2 OPSI] {f}: {label!r} opsi={len(c.get("options") or [])}')
                issues += 1

print('ISSUES:', issues)
