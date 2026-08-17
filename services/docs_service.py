"""
Service layer untuk Docs Viewer — rendering markdown dokumentasi teknis.

Pola mtime-cache yang sama dengan lesson_service._read_md_cached:
- Cache berdasarkan mtime file — segar bila file diubah tanpa restart.
- Jangan gunakan lru_cache untuk file-based content (mtime bisa berubah).
- Path traversal protection: hanya file di dalam DOCS_DIR yang boleh dibaca.

Frontmatter parsing:
- YAML frontmatter (---\ntitle: ...\norder: N\ncategory: ...\n---).
- Fallback bila frontmatter tidak ada/rusak: urutkan berdasarkan prefix angka
  nama file, gunakan H1 pertama sebagai title.
"""

import os
import re
import threading

import markdown as md
from bleach import clean as bleach_clean

from config import CONTENT_DIR

# Docs directory — berada di root proyek, sejajar dengan content/
_DOCS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_file_cache = {}       # {path: {'content': str, 'mtime': float}}
_file_cache_lock = threading.Lock()

_docs_index_cache = None       # [(filename, metadata, mtime)]
_docs_index_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)


def _parse_frontmatter(filename):
    """Parse frontmatter dari file docs/<filename>.md.

    Returns dict dengan keys: title, order, category, body (markdown tanpa frontmatter).
    Jika frontmatter tidak ada atau rusak, gunakan fallback:
    - title: H1 pertama di body
    - order: prefix angka dari nama file (01-13)
    - category: "general"
    """
    file_path = os.path.join(_DOCS_DIR, filename)

    # Path traversal protection
    abs_path = os.path.abspath(file_path)
    if not abs_path.startswith(_DOCS_DIR + os.sep) and abs_path != _DOCS_DIR:
        return None

    with _file_cache_lock:
        cached = _file_cache.get(abs_path)
        if cached and cached.get("mtime") == os.path.getmtime(file_path) if os.path.exists(file_path) else False:
            cached_mtime = os.path.getmtime(file_path)
            if cached and cached.get("mtime") == cached_mtime:
                return cached["data"]

    if not os.path.exists(file_path):
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, PermissionError) as e:
        print(f"Warning: Could not read {file_path}: {e}")
        return None

    current_mtime = os.path.getmtime(file_path)

    # Parse frontmatter
    title = None
    order = None
    category = "general"

    fm_match = _FRONTMATTER_RE.match(content)
    if fm_match:
        fm_text = fm_match.group(1)
        body = content[fm_match.end():]
        for line in fm_text.splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                key = key.strip()
                val = val.strip()
                if key == "title":
                    title = val
                elif key == "order":
                    try:
                        order = int(val)
                    except ValueError:
                        order = None
                elif key == "category":
                    category = val
    else:
        body = content

    # Fallback: title dari H1, order dari prefix angka nama file
    if not title:
        for line in body.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
    if title is None:
        title = filename.replace(".md", "").replace("_", " ").title()

    if order is None:
        # Extract leading digits from filename
        m = re.match(r'(\d+)', filename)
        if m:
            order = int(m.group(1))

    result = {
        "title": title,
        "order": order,
        "category": category,
        "body": body,
    }

    with _file_cache_lock:
        _file_cache[abs_path] = {"content": content, "mtime": current_mtime, "data": result}

    return result


def _read_md_cached(path):
    """Read any markdown file with mtime-based caching (mirrors lesson_service pattern)."""
    if not os.path.exists(path):
        return ""
    try:
        current_mtime = os.path.getmtime(path)
    except OSError:
        cached = _file_cache.get(path)
        return (cached["content"] if cached else "") or ""

    with _file_cache_lock:
        cached = _file_cache.get(path)
        if cached and cached.get("mtime") == current_mtime:
            return cached["content"]

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, PermissionError) as e:
        print(f"Warning: Could not read {path}: {e}")
        cached = _file_cache.get(path)
        return (cached["content"] if cached else "") or ""

    with _file_cache_lock:
        _file_cache[path] = {"content": content, "mtime": current_mtime}

    return content


# ---------------------------------------------------------------------------
# Docs index (list all docs files, sorted by order)
# ---------------------------------------------------------------------------

def get_docs_index():
    """Return list of docs metadata, sorted by order then filename.

    Cached mtime-aware: rescans and refreshes when any docs/*.md changes.
    """
    if not os.path.isdir(_DOCS_DIR):
        return []

    # Collect mtimes of all docs/*.md files to detect cache invalidation
    docs_files = []
    current_mtimes = {}
    try:
        for entry in os.scandir(_DOCS_DIR):
            if entry.is_file() and entry.name.endswith(".md"):
                slug = entry.name[:-3]  # strip .md
                docs_files.append((slug, entry.path))
                try:
                    current_mtimes[entry.path] = entry.stat().st_mtime
                except OSError:
                    current_mtimes[entry.path] = 0.0
    except OSError:
        return []

    with _docs_index_lock:
        global _docs_index_cache
        # Check if cache is still valid
        if _docs_index_cache is not None:
            cached_mtimes, cached_list = _docs_index_cache
            if cached_mtimes == current_mtimes:
                return cached_list

        # Rebuild index
        results = []
        for slug, path in docs_files:
            meta = _parse_frontmatter(os.path.basename(path))
            if meta is None:
                continue

            # Path traversal — double-check slug doesn't escape
            safe_path = os.path.abspath(path)
            if not safe_path.startswith(_DOCS_DIR + os.sep):
                continue

            results.append({
                "slug": slug,
                "title": meta["title"],
                "order": meta["order"],
                "category": meta["category"],
            })

        # Sort by order, then filename
        results.sort(key=lambda x: (x["order"] if x["order"] is not None else 9999, x["slug"]))

        _docs_index_cache = (dict(current_mtimes), results)
        return results


def get_doc_content(slug):
    """Return rendered HTML + metadata for a single doc by slug.

    Returns dict: {title, order, category, html, markdown}
    Returns None if not found or path traversal attempt.
    """
    # Path traversal protection
    safe_slug = re.sub(r'[^a-zA-Z0-9_\-]', '', slug)
    file_path = os.path.join(_DOCS_DIR, safe_slug + ".md")

    abs_path = os.path.abspath(file_path)
    if not abs_path.startswith(_DOCS_DIR + os.sep):
        return None
    if not os.path.exists(file_path):
        return None

    meta = _parse_frontmatter(os.path.basename(file_path))
    if meta is None:
        return None

    # Render markdown → HTML (reuse MD_EXTENSIONS from lesson_service for consistency)
    from services.lesson_service import MD_EXTENSIONS
    html = md.markdown(meta["body"], extensions=MD_EXTENSIONS)

    # Sanitize: allow common markdown HTML tags, strip scripts
    html = bleach_clean(
        html,
        tags=[
            "p", "br", "strong", "em", "u", "code", "pre", "blockquote",
            "h1", "h2", "h3", "h4", "h5", "h6",
            "ul", "ol", "li", "a", "img", "table", "thead", "tbody",
            "tr", "th", "td", "hr", "span", "div", "kbd", "var",
        ],
        attributes={
            "a": ["href", "title", "target", "rel"],
            "img": ["src", "alt", "title"],
            "code": ["class"],
            "span": ["class"],
            "div": ["class"],
            "pre": ["class"],
        },
        strip=True,
    )

    return {
        "title": meta["title"],
        "order": meta["order"],
        "category": meta["category"],
        "html": html,
    }
