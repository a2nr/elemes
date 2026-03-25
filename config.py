"""
Application configuration loaded from environment variables.
"""

import os


CONTENT_DIR = os.environ.get('CONTENT_DIR', 'content')
STATIC_DIR = os.environ.get('STATIC_DIR', 'static')
TEMPLATES_DIR = os.environ.get('TEMPLATES_DIR', 'templates')
TOKENS_FILE = os.environ.get('TOKENS_FILE', 'tokens.csv')

APP_BAR_TITLE = os.environ.get('APP_BAR_TITLE', 'C Programming Learning System')
COPYRIGHT_TEXT = os.environ.get('COPYRIGHT_TEXT', 'C Programming Learning System &copy; 2025')
PAGE_TITLE_SUFFIX = os.environ.get('PAGE_TITLE_SUFFIX', 'C Programming Learning System')

DEFAULT_PROGRAMMING_LANGUAGE = os.environ.get('DEFAULT_PROGRAMMING_LANGUAGE', 'c').lower()
