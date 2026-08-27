import os, sys

# Forward to scripts/dump_markdown_fixtures.py
SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', 'dump_markdown_fixtures.py'))
with open(SCRIPT_PATH, 'r', encoding='utf-8') as f:
    code = compile(f.read(), SCRIPT_PATH, 'exec')
    exec(code)
