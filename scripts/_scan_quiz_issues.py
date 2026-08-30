import sys, glob
sys.path.insert(0, '/home/a2nr/lms-dev/elemes')
from services.lesson_service import _parse_flashcards, _extract_section

issues = 0
for f in glob.glob('/home/a2nr/lms-dev/content/**/*.md', recursive=True):
    txt = open(f, encoding='utf-8').read()
    if '---QUIZ_FLASHCARD---' not in txt:
        continue
    raw, _ = _extract_section(txt, '---QUIZ_FLASHCARD---', '---END_QUIZ_FLASHCARD---')
    if not raw.strip():
        continue
    try:
        cards = _parse_flashcards(raw)
    except ValueError as e:
        print(f'[RAISE] {f}: {e}')
        issues += 1
        continue
    for c in cards:
        if c['type'] == 'mcq' and len(c.get('options') or []) < 2:
            print(f'[<2 OPSI] {f}: {c["question"][:60]!r} opsi={len(c.get("options") or [])}')
            issues += 1

print('ISSUES:', issues)
