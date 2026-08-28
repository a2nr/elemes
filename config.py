"""
Application configuration loaded from environment variables.
"""

import os


CONTENT_DIR = os.environ.get('CONTENT_DIR', 'content')

# Assets directory: derived from parent of CONTENT_DIR
# E.g. CONTENT_DIR='content' → ASSETS_DIR='assets'
#      CONTENT_DIR='examples/content' → ASSETS_DIR='examples/assets'
#      CONTENT_DIR='/app/content' → ASSETS_DIR='/app/assets'
ASSETS_DIR = os.path.join(os.path.dirname(CONTENT_DIR.rstrip(os.sep)), 'assets')

# ── Evaluation weights & done threshold ───────────────────────────
# Bobot exercise (0-100) dan quiz (0-100) untuk composite score.
LESSON_EXERCISE_WEIGHT = float(os.environ.get('LESSON_EXERCISE_WEIGHT', '70'))
LESSON_QUIZ_WEIGHT = float(os.environ.get('LESSON_QUIZ_WEIGHT', '30'))
# Ambang minimum composite score (0-100) untuk status lesson "done".
LESSON_DONE_MIN_PERCENT = float(os.environ.get('LESSON_DONE_MIN_PERCENT', '75'))

# Validasi: weights harus berjumlah 100
_total_weight = LESSON_EXERCISE_WEIGHT + LESSON_QUIZ_WEIGHT
if abs(_total_weight - 100.0) > 0.01:
    raise RuntimeError(
        f"LESSON_EXERCISE_WEIGHT + LESSON_QUIZ_WEIGHT must equal 100, got {_total_weight}"
    )
