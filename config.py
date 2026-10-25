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

# Cache varian ringan (WebP) untuk asset gambar raster.
#
# WAJIB di luar ASSETS_DIR — sibling, bukan `assets/.cache/`. Alasan:
# `export_bundle` (routes/content_editor.py) men-zip SELURUH isi ASSETS_DIR
# tanpa filter, jadi file cache di dalam ASSETS_DIR akan ikut ter-zip lalu
# ter-import ulang sebagai asset biasa (menggandakan file & merusak bundel).
# Dengan cache di luar, export 100% lossless — hanya original yang ikut.
#
# E.g. CONTENT_DIR='content'          → CACHE_DIR='assets-cache'
#      CONTENT_DIR='/app/content'     → CACHE_DIR='/app/assets-cache'
CACHE_DIR = os.path.join(os.path.dirname(CONTENT_DIR.rstrip(os.sep)), 'assets-cache')

# Dimensi maksimum (sisi terpanjang, px) untuk varian WebP yang di-generate.
ASSET_VARIANT_MAX_DIM = int(os.environ.get('ASSET_VARIANT_MAX_DIM', '1600'))
# Kualitas WebP (1-100).
ASSET_VARIANT_QUALITY = int(os.environ.get('ASSET_VARIANT_QUALITY', '80'))
# Cache-Control max-age untuk respons asset (detik).
ASSET_CACHE_MAX_AGE = int(os.environ.get('ASSET_CACHE_MAX_AGE', '3600'))

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
