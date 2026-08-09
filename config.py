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
