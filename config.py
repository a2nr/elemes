"""
Application configuration loaded from environment variables.
"""

import os


CONTENT_DIR = os.environ.get('CONTENT_DIR', 'content')
TOKENS_FILE = os.environ.get('TOKENS_FILE', 'tokens.csv')
