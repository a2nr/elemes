import json, sys, os, glob, types

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Stub config module if needed
if "config" not in sys.modules:
    config = types.ModuleType("config")
    config.CONTENT_DIR = os.path.join(REPO_ROOT, "examples", "content")
    sys.modules["config"] = config

# Stub bleach minimal if bleach is not installed in the current environment
try:
    import bleach
except ImportError:
    bleach = types.ModuleType("bleach")
    def clean(html, **kw):
        return html
    bleach.clean = clean
    css_san = types.ModuleType("bleach.css_sanitizer")
    class CSSSanitizer:
        def __init__(self, *a, **k): pass
    css_san.CSSSanitizer = CSSSanitizer
    sys.modules["bleach"] = bleach
    sys.modules["bleach.css_sanitizer"] = css_san

from services.lesson_service import _render_markdown_string

FIXTURES_DIR = os.path.join(REPO_ROOT, 'frontend', 'src', 'lib', 'services', 'markdown', '__fixtures__')
os.makedirs(FIXTURES_DIR, exist_ok=True)

content_dir = os.path.join(REPO_ROOT, 'examples', 'content')
pattern = os.path.join(content_dir, '**', '*.md')

count = 0
for path in glob.glob(pattern, recursive=True):
    rel_path = os.path.relpath(path, content_dir)
    with open(path, 'r', encoding='utf-8') as f:
        raw = f.read()
    try:
        parsed = _render_markdown_string(raw)
        result = {
            'source_path': rel_path,
            'source_body': raw,
            'lesson_content': parsed.get('lesson_html', ''),
            'exercise_content': parsed.get('exercise_html', ''),
            'quiz_data': parsed.get('quiz_data', []),
            'slides': parsed.get('slides', []),
            'active_tabs': parsed.get('active_tabs', [])
        }
    except ValueError as e:
        result = {
            'source_path': rel_path,
            'source_body': raw,
            'error': str(e)
        }
    
    fixture_name = rel_path.replace('/', '__').replace('\\', '__') + '.json'
    out_file = os.path.join(FIXTURES_DIR, fixture_name)
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    count += 1

print(f"Dumped {count} markdown fixtures to {FIXTURES_DIR}")
