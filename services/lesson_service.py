"""
Lesson loading, ordering, and markdown rendering.
"""

import os
import re
import html as html_module
import bleach
from functools import lru_cache
from threading import Lock
from urllib.parse import urlparse

import markdown as md

from config import CONTENT_DIR

# Generic file cache (path -> {content, mtime})
_file_cache = {}  # {path: {'content': str, 'mtime': float}}
_file_cache_lock = Lock()

_markdown_cache = {}
_markdown_lock = Lock()

# Parsed sub-home data cache (folder -> {mtime, data}) — mtime-based, agar
# hasil parsing sub-home.md selalu segar bila file-nya berubah (bukan lru_cache
# yang bisa mengembalikan data basi sampai proses restart).
_sub_home_cache = {}  # {folder_name: {'mtime': float, 'data': dict}}
_sub_home_cache_lock = Lock()

# Pre-computed absolute path for home.md (avoids repeated syscall on hot path)
_HOME_MD_PATH = os.path.abspath(os.path.join(CONTENT_DIR, "home.md"))


def _read_md_cached(path):
    """Read any markdown file with mtime-based caching.
    
    Uses a single dict cache keyed by absolute path.
    Returns empty string if file is missing or unreadable.
    """
    if not os.path.exists(path):
        return ""
    try:
        current_mtime = os.path.getmtime(path)
    except OSError:
        cached = _file_cache.get(path)
        return (cached['content'] if cached else "") or ""

    with _file_cache_lock:
        cached = _file_cache.get(path)
        if cached and cached['mtime'] == current_mtime:
            return cached['content']

    # Read outside the lock (no file I/O under lock)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except (OSError, PermissionError) as e:
        print(f"Warning: Could not read {path}: {e}")
        cached = _file_cache.get(path)
        return (cached['content'] if cached else "") or ""

    with _file_cache_lock:
        _file_cache[path] = {'content': content, 'mtime': current_mtime}

    # If this is the root home.md, invalidate downstream caches
    if os.path.abspath(path) == _HOME_MD_PATH:
        find_lesson_file.cache_clear()
        get_lessons.cache_clear()
        get_lesson_names.cache_clear()
        get_lessons_with_learning_objectives.cache_clear()
        with _markdown_lock:
            _markdown_cache.clear()

    # If this is a sub-home.md, invalidate its parsed data cache so edits to
    # the file (new lessons, reorder) show up without restarting the app.
    if os.path.basename(path) == 'sub-home.md':
        with _sub_home_cache_lock:
            _sub_home_cache.clear()
        find_lesson_file.cache_clear()

    return content


def _read_home_md():
    """Read root home.md — thin wrapper for backwards compatibility."""
    path = os.path.join(CONTENT_DIR, "home.md")
    return _read_md_cached(path)


def _parse_lesson_links(home_content):
    """Extract (link_text, filename) pairs from the Available_Lessons section.
    
    Skips sub-home.md entries so they don't appear as lessons.
    """
    parts = re.split(r'-{3,}Available_Lessons-{3,}', home_content)
    if len(parts) <= 1:
        return []
    lesson_list_content = parts[-1]
    
    # Allow optional leading slash in /lesson/ prefix
    links = re.findall(r'\[([^\]]+)\]\((?:/?lesson/)?([^\)]+)\)', lesson_list_content)
    
    processed_links = []
    for title, slug in links:
        filename = slug if slug.endswith('.md') else slug + '.md'
        # Skip sub-home.md — it's not a lesson
        if filename == 'sub-home.md':
            continue
        processed_links.append((title, filename))
    return processed_links


# ---------------------------------------------------------------------------
# Lesson listing
# ---------------------------------------------------------------------------

@lru_cache(maxsize=128)
def find_lesson_file(filename):
    """Recursively search for filename in CONTENT_DIR and return its full path."""
    # Security: Prevent directory traversal
    if '/' in filename or '\\' in filename:
        return None
    # Skip sub-home.md — it's not a lesson
    if filename == 'sub-home.md':
        return None
        
    for root, _, files in os.walk(CONTENT_DIR):
        if filename in files:
            return os.path.join(root, filename)
    return None


@lru_cache(maxsize=32)
def get_lessons(source_path=None):
    """Get lessons from the Available_Lessons section in home.md.

    `source_path` opsional: bila diberikan, daftar materi diambil dari file
    markdown tersebut (mis. sub-home.md) alih-alih home.md root.
    """
    lessons = []
    source_content = _read_md_cached(source_path) if source_path else _read_home_md()
    if not source_content:
        return lessons

    for link_text, filename in _parse_lesson_links(source_content):
        file_path = find_lesson_file(filename)
        if not file_path:
            continue

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        lines = content.split('\n')
        title = link_text
        description = "Learn C programming concepts with practical examples."

        for i, line in enumerate(lines):
            if line.startswith('# ') and title == link_text:
                if title == "Untitled" or title == link_text:
                    title = line[2:].strip()
            elif title != "Untitled" and line.strip() != "" and not line.startswith('#') and i < 10:
                clean_line = line.strip().replace('#', '').strip()
                if len(clean_line) > 10:
                    description = clean_line
                    break

        lessons.append({
            'filename': filename,
            'title': title,
            'description': description,
            'path': file_path,
        })

    return lessons


@lru_cache(maxsize=32)
def get_lesson_names():
    """Get lesson names (without .md extension) from Available_Lessons."""
    home_content = _read_home_md()
    if not home_content:
        return []

    names = []
    for _link_text, filename in _parse_lesson_links(home_content):
        file_path = find_lesson_file(filename)
        if file_path:
            names.append(filename.replace('.md', ''))
    return names


def _build_lessons_with_objectives(lesson_links):
    """Build enriched lesson dicts (title, description, prerequisite_titles)
    from parsed (link_text, filename) pairs, reading each lesson file."""
    lessons = []

    for link_text, filename in lesson_links:
        file_path = find_lesson_file(filename)
        if not file_path:
            continue

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        title = link_text
        description = "Learn C programming concepts with practical examples."

        lesson_info_start = content.find('---LESSON_INFO---')
        lesson_info_end = content.find('---END_LESSON_INFO---')
        prerequisite_titles = []

        if lesson_info_start != -1 and lesson_info_end != -1:
            lesson_info_section = content[lesson_info_start + len('---LESSON_INFO---'):lesson_info_end]

            # Extract Learning Objectives
            objectives_start = lesson_info_section.find('**Learning Objectives:**')
            if objectives_start != -1:
                objectives_section = lesson_info_section[objectives_start:]
                objective_matches = re.findall(r'- ([^\n]+)', objectives_section)
                if objective_matches:
                    description = '; '.join(objective_matches[:3])
                else:
                    lines_after = lesson_info_section[objectives_start:].split('\n')[1:4]
                    description = ' '.join(line.strip() for line in lines_after if line.strip())

            # Extract Prerequisites
            prereq_start = lesson_info_section.find('**Prerequisites:**')
            if prereq_start != -1:
                prereq_section = lesson_info_section[prereq_start + len('**Prerequisites:**'):]
                # Look for bullet points - support both plain text and markdown link format
                # Plain text: - Hello, World!
                # Markdown link: - [Hello, World!](lesson/hello_world.md)
                bullet_lines = re.findall(r'- ([^\n]+)', prereq_section)
                
                prerequisite_slugs = []
                for bullet in bullet_lines:
                    bullet = bullet.strip()
                    # Filter out "None" or "Tidak ada"
                    if bullet.lower() in ('tidak ada', 'none', '-', ''):
                        continue
                    
                    # Check if it's a markdown link format [title](path)
                    md_link_match = re.match(r'\[([^\]]+)\]\(([^)]+)\)', bullet)
                    if md_link_match:
                        # Extract slug from the link path
                        link_path = md_link_match.group(2)
                        # Handle paths like lesson/hello_world.md or just hello_world.md
                        slug = link_path.replace('.md', '').split('/')[-1]
                        prerequisite_slugs.append(slug)
                    else:
                        # Plain text - keep as title for later resolution
                        prerequisite_slugs.append(bullet)
                
                prerequisite_titles = prerequisite_slugs

            content_after_info = content[lesson_info_end + len('---END_LESSON_INFO---'):].strip()
            for line in content_after_info.split('\n'):
                if line.startswith('# '):
                    title = line[2:].strip()
                    break
        else:
            lines = content.split('\n')
            for line in lines:
                if line.startswith('# ') and title == link_text:
                    if title == "Untitled" or title == link_text:
                        title = line[2:].strip()
                    break

        lessons.append({
            'filename': filename,
            'title': title,
            'description': description,
            'path': file_path,
            'prerequisite_titles': prerequisite_titles,
        })

    return lessons


@lru_cache(maxsize=32)
def get_lessons_with_learning_objectives():
    """Get lessons with learning objectives extracted from LESSON_INFO sections."""
    home_content = _read_home_md()
    if not home_content:
        return []
    return _build_lessons_with_objectives(_parse_lesson_links(home_content))


def get_ordered_lessons_with_learning_objectives(progress=None, source_path=None):
    """Get lessons ordered per home.md with completion status from progress dict.

    `source_path` opsional: bila diberikan (mis. path ke sub-home.md), daftar
    materi & urutannya diambil dari file tersebut, bukan dari home.md root.
    """
    if source_path:
        content = _read_md_cached(source_path)
        lesson_links = _parse_lesson_links(content) if content else []
        all_lessons = _build_lessons_with_objectives(lesson_links)
    else:
        home_content = _read_home_md()
        lesson_links = _parse_lesson_links(home_content) if home_content else []
        all_lessons = get_lessons_with_learning_objectives()

    # Build title -> slug mapping for prerequisite resolution
    title_to_slug = {lesson['title']: lesson['filename'].replace('.md', '') for lesson in all_lessons}
    # Also map link text from home.md
    for link_text, filename in lesson_links:
        title_to_slug[link_text] = filename.replace('.md', '')

    def _add_completion_and_prereqs(lesson, progress):
        slug = lesson['filename'].replace('.md', '')
        if progress:
            status = progress.get(slug, '')
            lesson['completed'] = status not in (None, '', 'not_started')
        else:
            lesson['completed'] = False
        
        # Resolve prerequisites - now contains slugs directly from markdown links
        # or still contains plain text titles that need resolution
        items = lesson.get('prerequisite_titles', [])
        resolved_prereqs = []
        for item in items:
            # If it's already a valid slug (exists in all_lessons), use it directly
            if item in title_to_slug.values():
                resolved_prereqs.append(item)
            # Otherwise try to resolve via title mapping
            elif item in title_to_slug:
                resolved_prereqs.append(title_to_slug[item])
        lesson['prerequisites'] = resolved_prereqs
        return lesson

    if lesson_links:
        ordered = []
        for link_text, filename in lesson_links:
            for lesson in all_lessons:
                if lesson['filename'] == filename:
                    copy = lesson.copy()
                    copy['title'] = link_text
                    _add_completion_and_prereqs(copy, progress)
                    ordered.append(copy)
                    break

        seen = {l['filename'] for l in ordered}
        for lesson in all_lessons:
            if lesson['filename'] not in seen:
                copy = lesson.copy()
                _add_completion_and_prereqs(copy, progress)
                ordered.append(copy)

        return ordered

    ordered_fallback = []
    for lesson in all_lessons:
        copy = lesson.copy()
        _add_completion_and_prereqs(copy, progress)
        ordered_fallback.append(copy)
    return ordered_fallback


# ---------------------------------------------------------------------------
# Sub-Home helpers
# ---------------------------------------------------------------------------

def find_sub_home_for_lesson(file_path):
    """Find sub-home.md in the same folder as file_path, or None.
    
    Returns (sub_home_path, folder_name) or (None, None).
    Handles PermissionError gracefully.
    """
    if not file_path:
        return None, None
    folder = os.path.dirname(file_path)
    sub_home_path = os.path.join(folder, 'sub-home.md')
    if not os.path.exists(sub_home_path):
        return None, None
    # Permission check
    try:
        if not os.access(sub_home_path, os.R_OK):
            print(f"Warning: Cannot read {sub_home_path} (permission denied)")
            return None, None
    except OSError:
        return None, None
    folder_name = os.path.basename(folder)
    return sub_home_path, folder_name


def get_sub_home_data(folder_name):
    """Return parsed sub-home data for a given folder name (mtime-cached).
    
    Returns dict with keys: title, intro_html, lessons, folder, url.
    Returns None if no sub-home.md found or unreadable.
    """
    folder_path = os.path.join(CONTENT_DIR, folder_name)
    if not os.path.isdir(folder_path):
        return None
    sub_home_path = os.path.join(folder_path, 'sub-home.md')
    if not os.path.exists(sub_home_path):
        return None
    # Permission check
    try:
        if not os.access(sub_home_path, os.R_OK):
            print(f"Warning: Cannot read {sub_home_path} (permission denied)")
            return None
    except OSError:
        return None
    # mtime-based cache: refresh bila sub-home.md diubah, tanpa menunggu restart
    try:
        current_mtime = os.path.getmtime(sub_home_path)
    except OSError:
        current_mtime = 0.0
    with _sub_home_cache_lock:
        cached = _sub_home_cache.get(folder_name)
        if cached and cached['mtime'] == current_mtime:
            return cached['data']
    content = _read_md_cached(sub_home_path)
    if not content:
        return None

    # Extract intro (before Available_Lessons)
    parts = re.split(r'-{3,}Available_Lessons-{3,}', content)
    intro_raw = parts[0] if parts else content
    # Remove heading from intro if present (it becomes the title)
    title = folder_name.replace('_', ' ').title()
    intro_lines = intro_raw.strip().split('\n')
    if intro_lines and intro_lines[0].startswith('# '):
        title = intro_lines[0][2:].strip()
        intro_raw = '\n'.join(intro_lines[1:])
    intro_html = md.markdown(intro_raw, extensions=['fenced_code', 'tables', 'mdx_math']) if intro_raw.strip() else ''

    # Parse lesson links from Available_Lessons
    lesson_links = _parse_lesson_links(content)
    lessons = []
    for link_text, filename in lesson_links:
        file_path = find_lesson_file(filename)
        if not file_path:
            continue
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lesson_content = f.read()
        except (OSError, PermissionError):
            continue

        lesson_title = link_text
        description = "Learn C programming concepts with practical examples."
        prerequisite_titles = []
        lesson_info_start = lesson_content.find('---LESSON_INFO---')
        lesson_info_end = lesson_content.find('---END_LESSON_INFO---')
        if lesson_info_start != -1 and lesson_info_end != -1:
            lesson_info_section = lesson_content[lesson_info_start + len('---LESSON_INFO---'):lesson_info_end]
            objectives_start = lesson_info_section.find('**Learning Objectives:**')
            if objectives_start != -1:
                objectives_section = lesson_info_section[objectives_start:]
                objective_matches = re.findall(r'- ([^\n]+)', objectives_section)
                if objective_matches:
                    description = '; '.join(objective_matches[:3])
            # Extract Prerequisites
            prereq_start = lesson_info_section.find('**Prerequisites:**')
            if prereq_start != -1:
                prereq_section = lesson_info_section[prereq_start + len('**Prerequisites:**'):]
                bullet_lines = re.findall(r'- ([^\n]+)', prereq_section)
                for bullet in bullet_lines:
                    bullet = bullet.strip()
                    if bullet.lower() in ('tidak ada', 'none', '-', ''):
                        continue
                    md_link_match = re.match(r'\[([^\]]+)\]\(([^)]+)\)', bullet)
                    if md_link_match:
                        link_path = md_link_match.group(2)
                        slug = link_path.replace('.md', '').split('/')[-1]
                        prerequisite_titles.append(slug)
                    else:
                        prerequisite_titles.append(bullet)
        else:
            for line in lesson_content.split('\n')[:10]:
                if line.startswith('# '):
                    lesson_title = line[2:].strip()
                    break

        lessons.append({
            'filename': filename,
            'title': lesson_title,
            'description': description,
            'path': file_path,
            'prerequisite_titles': prerequisite_titles,
        })

    data = {
        'title': title,
        'intro_html': intro_html,
        'lessons': lessons,
        'folder': folder_name,
        'url': f'/bab/{folder_name}',
    }
    with _sub_home_cache_lock:
        if len(_sub_home_cache) >= 64:
            _sub_home_cache.clear()
        _sub_home_cache[folder_name] = {'mtime': current_mtime, 'data': data}
    return data


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

MD_EXTENSIONS = ['fenced_code', 'tables', 'nl2br', 'toc', 'mdx_math']

# Domain blacklist for embed iframe src (must be https).
EMBED_BLOCKED_HOSTS = {
    'localhost', '127.0.0.1', '0.0.0.0',
    'metadata.google.internal', '169.254.169.254',
}

# HTML sanitization config for ```embed fences (raw HTML embed code)
EMBED_ALLOWED_TAGS = ['div', 'iframe', 'a', 'span', 'p', 'br', 'img']
EMBED_ALLOWED_ATTRS = {
    'div': ['style', 'class'],
    'iframe': ['src', 'style', 'loading', 'allowfullscreen', 'allow', 'title', 'class'],
    'a': ['href', 'target', 'rel', 'style', 'class'],
    'span': ['style', 'class'],
    'p': ['style', 'class'],
    'img': ['src', 'alt', 'style', 'class', 'loading'],
    '*': ['class'],
}
EMBED_ALLOWED_STYLES = [
    'position', 'width', 'height', 'padding', 'padding-top', 'padding-bottom',
    'padding-left', 'padding-right', 'margin', 'margin-top', 'margin-bottom',
    'margin-left', 'margin-right', 'border', 'border-radius',
    'overflow', 'box-shadow', 'top', 'left', 'right', 'bottom',
    'will-change', 'display', 'flex-direction', 'gap',
    'max-width', 'max-height', 'min-height',
]


def _process_circuit_embeds(text):
    """Replace ```circuit[,width][,height] code fences with embeddable HTML divs.

    Supported formats:
        ```circuit          -> width=100%, height=400px
        ```circuit,500px    -> width=100%, height=500px
        ```circuit,80%,500px -> width=80%, height=500px
    """
    pattern = re.compile(
        r'```circuit(?:,([^\s,`]+))?(?:,([^\s,`]+))?\s*\n(.*?)```',
        re.DOTALL,
    )

    def _replacer(match):
        param1 = match.group(1)
        param2 = match.group(2)
        # One param = height only; two params = width, height
        if param1 and param2:
            width, height = param1, param2
        elif param1:
            width, height = '100%', param1
        else:
            width, height = '100%', '400px'
        data = html_module.escape(match.group(3).strip())
        return (
            f'<div class="circuit-embed" '
            f'data-width="{html_module.escape(width)}" '
            f'data-height="{html_module.escape(height)}">'
            f'<pre class="circuit-data" style="display:none">{data}</pre>'
            f'<div class="circuit-embed-loading">Memuat simulator...</div>'
            f'</div>'
        )

    return pattern.sub(_replacer, text)


def _process_flowchart_embeds(text):
    """Replace ```flowchart[,width][,height] code fences with embeddable HTML divs.

    Supported formats:
        ```flowchart          -> width=100%, height=400px
        ```flowchart,500px    -> width=100%, height=500px
        ```flowchart,80%,500px -> width=80%, height=500px
    """
    pattern = re.compile(
        r'```flowchart(?:,([^\s,`]+))?(?:,([^\s,`]+))?\s*\n(.*?)```',
        re.DOTALL,
    )

    def _replacer(match):
        param1 = match.group(1)
        param2 = match.group(2)
        # One param = height only; two params = width, height
        if param1 and param2:
            width, height = param1, param2
        elif param1:
            width, height = '100%', param1
        else:
            width, height = '100%', '400px'
        data = html_module.escape(match.group(3).strip())
        return (
            f'<div class="flowchart-embed" '
            f'data-width="{html_module.escape(width)}" '
            f'data-height="{html_module.escape(height)}">'
            f'<pre class="flowchart-data" style="display:none">{data}</pre>'
            f'<div class="flowchart-embed-loading">Memuat flowchart...</div>'
            f'</div>'
        )

    return pattern.sub(_replacer, text)


def _sanitize_embed_html(html_text):
    """Sanitize raw embed HTML: whitelist tags/attrs/styles + check iframe src domain."""
    cleaned = bleach.clean(
        html_text,
        tags=EMBED_ALLOWED_TAGS,
        attributes=EMBED_ALLOWED_ATTRS,
        strip=True,
    )
    # Optional CSS sanitization — requires tinycss2 (skip if not installed)
    try:
        from bleach.css_sanitizer import CSSSanitizer
        css_sanitizer = CSSSanitizer(allowed_css_properties=EMBED_ALLOWED_STYLES)
        cleaned = bleach.clean(
            html_text,
            tags=EMBED_ALLOWED_TAGS,
            attributes=EMBED_ALLOWED_ATTRS,
            css_sanitizer=css_sanitizer,
            strip=True,
        )
    except ImportError:
        pass  # tinycss2 missing — CSS styles left unsanitized but tags/attrs still stripped
    # Check every iframe src: must be https + not blacklisted
    for match in re.finditer(r'<iframe[^>]+src="([^"]*)"', cleaned):
        src = match.group(1)
        try:
            host = (urlparse(src).hostname or '').lower()
        except Exception:
            return '<div class="embed-error">Konten embed ditolak: URL iframe tidak valid.</div>'
        if not src.startswith('https://'):
            return '<div class="embed-error">Konten embed ditolak: iframe harus https.</div>'
        if host in EMBED_BLOCKED_HOSTS or any(host.endswith('.' + h) for h in EMBED_BLOCKED_HOSTS):
            return '<div class="embed-error">Konten embed ditolak: domain iframe diblokir.</div>'
    return cleaned


def _process_embed_embeds(text):
    """Replace ```embed fences containing raw HTML embed code with sanitized HTML.

    User pastes embed code from Canva/YouTube/Google Docs (Share → Embed).
    HTML is sanitized via bleach (whitelist tags/attrs/styles) and iframe src
    is checked against EMBED_BLOCKED_HOSTS.
    """
    pattern = re.compile(
        r'```embed\s*\n(.*?)```',
        re.DOTALL,
    )

    def _replacer(match):
        raw_html = match.group(1).strip()
        if not raw_html:
            return '<div class="embed-error">Konten embed kosong.</div>'
        return _sanitize_embed_html(raw_html)

    return pattern.sub(_replacer, text)


_OPTION_LINE_RE = re.compile(r'^\s*-\s*\[([ xX]?)\]\s*(.*)$')


def _iter_option_lines(body):
    """Yield (char_index, mark, content) for option lines outside fenced code.

    Lines inside ``` fenced blocks are skipped so code examples containing
    '- [x] ...' are never mistaken for real options.
    """
    in_fence = False
    pos = 0
    for line in body.split('\n'):
        if line.strip().startswith('```'):
            in_fence = not in_fence
        elif not in_fence:
            m = _OPTION_LINE_RE.match(line)
            if m:
                yield pos, m.group(1), m.group(2)
        pos += len(line) + 1


def _extract_body_image(text):
    """Return (image_url, cleaned_text) for the first markdown image found
    outside fenced code blocks. cleaned_text has that image markup removed.
    Returns (None, text) when no image is found.
    """
    lines = text.split('\n')
    fence = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('```'):
            fence = not fence
            continue
        if fence:
            continue
        m = re.search(r'!\[[^\]]*\]\(([^)]+)\)', line)
        if m:
            url = m.group(1).strip()
            cleaned_line = line[:m.start()] + line[m.end():]
            cleaned_lines = lines[:idx] + ([cleaned_line] if cleaned_line.strip() else []) + lines[idx + 1:]
            return url, '\n'.join(cleaned_lines).strip()
    return None, text


def _parse_flashcards(text):
    """Parse a string of markdown with headings and options into a list of dicts.
    
    Supports two formats:
    1. Simple Flashcard: '### Question\nAnswer'
    2. Multiple Choice (MCQ): 
       '### Question
        [optional rich markdown body: paragraphs, fenced code, tables, math]
        - [] option 1
        - [x] option 2 (Correct)
        - [] option 3
        > Explanation'

    Every question and option receives a stable id based on original parse
    order ('q-0', 'q-0-o-0', ...) — the frontend uses these ids for shuffling
    and scoring, so they must never depend on display order.
    """
    if not text.strip():
        return []
        
    # Split by headings starting with #, ##, or ###
    parts = re.split(r'^#{1,3}\s+', text, flags=re.MULTILINE)
    flashcards = []
    
    for part in parts:
        if not part.strip():
            continue
            
        # First line is the question (Front)
        subparts = part.split('\n', 1)
        question = subparts[0].strip()
        body = subparts[1] if len(subparts) > 1 else ""
        
        if not question:
            continue

        # Initialize image_url - will be set from markdown image or 'image:' directive
        image_url = ""
        
        # Extract image from markdown syntax ![...](path) in question
        md_image_match = re.search(r'!\[.*?\]\(([^)]+)\)', question)
        if md_image_match:
            md_image_path = md_image_match.group(1).strip()
            # Jika path lokal (/assets/ atau bare filename) dan belum ada image dari 'image:' directive
            if md_image_path.startswith('/assets/') or (not md_image_path.startswith(('http://', 'https://')) and not image_url):
                image_url = md_image_path

        # Check for image: URL
        image_match = re.search(r'^\s*image:\s*(.*)$', body, re.MULTILINE)
        if image_match:
            image_url = image_match.group(1).strip()  # Override jika ada 'image:' directive
            if image_url.startswith('/assets/'):
                # Path sudah lengkap, tidak perlu konversi
                pass
            elif not image_url.startswith(('http://', 'https://', '/')):
                image_url = f'/assets/{image_url}'
            body = re.sub(r'^\s*image:\s*.*$', '', body, flags=re.MULTILINE).strip()

        # Option lines outside fenced code, in original order
        option_lines = list(_iter_option_lines(body))
        first_option_idx = option_lines[0][0] if option_lines else len(body)

        # Explanation blockquote: after the options for MCQ, anywhere for flashcard
        explanation_search_region = body[first_option_idx:] if option_lines else body
        explanation_match = re.search(r'^\s*(>.*)$', explanation_search_region, re.MULTILINE | re.DOTALL)
        explanation = explanation_match.group(1).strip() if explanation_match else ""

        q_id = f'q-{len(flashcards)}'

        # If MCQ options exist, it's an MCQ.
        if option_lines:
            parsed_options = []
            for _, mark, content in option_lines:
                is_correct = mark.lower() == 'x'
                parsed_options.append({
                    'id': f'{q_id}-o-{len(parsed_options)}',
                    'text': md.markdown(content.strip(), extensions=MD_EXTENSIONS),
                    'is_correct': is_correct
                })

            correct_count = sum(1 for opt in parsed_options if opt['is_correct'])
            if correct_count != 1:
                raise ValueError(
                    f"Soal kuis ke-{len(flashcards) + 1} wajib punya tepat satu opsi benar "
                    f"(ditemukan {correct_count})."
                )

            # Rich question prompt: heading + everything before the first option
            # line (paragraphs, fenced code, tables, math), through the same
            # embed pipeline used for lesson material.
            prompt_body = body[:first_option_idx].strip()

            # Extract markdown image from the prompt body (outside code fences)
            # if no image was found in the heading / image: directive yet, and
            # drop it from the prompt so it is not rendered twice.
            if not image_url:
                extracted_url, prompt_body = _extract_body_image(prompt_body)
                if extracted_url:
                    image_url = extracted_url

            prompt_text = f"{question}\n\n{prompt_body}" if prompt_body else question
            prompt_text = _process_circuit_embeds(prompt_text)
            prompt_text = _process_flowchart_embeds(prompt_text)
            prompt_text = _process_embed_embeds(prompt_text)

            flashcards.append({
                'id': q_id,
                'type': 'mcq',
                'question': md.markdown(prompt_text, extensions=MD_EXTENSIONS),
                'options': parsed_options,
                'explanation': md.markdown(explanation, extensions=MD_EXTENSIONS) if explanation else "",
                'image': image_url
            })
        else:
            # It's a simple Flashcard
            # Remove explanation from body if it's there to keep 'back' clean
            clean_back = body
            if explanation_match:
                clean_back = body[:explanation_match.start()].strip()
                
            flashcards.append({
                'id': q_id,
                'type': 'flashcard',
                'front': md.markdown(question, extensions=MD_EXTENSIONS),
                'back': md.markdown(clean_back, extensions=MD_EXTENSIONS),
                'explanation': md.markdown(explanation, extensions=MD_EXTENSIONS) if explanation else "",
                'image': image_url,
                'options': None
            })
            
    return flashcards


def _extract_section(content, start_marker, end_marker):
    """Extract text between markers and return (extracted, remaining_content)."""
    if start_marker not in content or end_marker not in content:
        return "", content

    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        return "", content

    extracted = content[start_idx + len(start_marker):end_idx].strip()
    remaining = content[:start_idx] + content[end_idx + len(end_marker):]
    return extracted, remaining


def render_markdown_content(file_path):
    """Parse a lesson markdown file and return structured HTML parts as a dictionary."""
    try:
        current_mtime = os.path.getmtime(file_path)
    except OSError:
        current_mtime = 0.0

    with _markdown_lock:
        cached = _markdown_cache.get(file_path)
        if cached and cached['mtime'] == current_mtime:
            return cached['data']

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lesson_content = content
    active_tabs = []

    # Check for collective tags before extracting them
    # Priority: INITIAL_CODE_ARDUINO → velxio mode (exclusive, ignores C/Python tabs)
    if '---INITIAL_CODE_ARDUINO---' in lesson_content:
        active_tabs.append('velxio')
    else:
        if '---INITIAL_CODE---' in lesson_content:
            active_tabs.append('c')
        if '---INITIAL_PYTHON---' in lesson_content:
            active_tabs.append('python')
    if '---INITIAL_CIRCUIT---' in lesson_content:
        active_tabs.append('circuit')
    if '---INITIAL_FLOWCHART---' in lesson_content:
        active_tabs.append('flowchart')
    if '---INITIAL_QUIZ---' in lesson_content:
        active_tabs.append('quiz')
    if '---QUIZ_FLASHCARD---' in lesson_content:
        active_tabs.append('quiz')
    # Velxio circuit-only: has VELXIO_CIRCUIT but no INITIAL_CODE_ARDUINO
    if '---VELXIO_CIRCUIT---' in lesson_content and 'velxio' not in active_tabs:
        active_tabs.append('velxio')

    # Default to 'c' if nothing specified (for backwards compatibility)
    if not active_tabs and '---INITIAL_CODE---' not in lesson_content and '---INITIAL_PYTHON---' not in lesson_content and '---INITIAL_CIRCUIT---' not in lesson_content and '---INITIAL_FLOWCHART---' not in lesson_content and '---INITIAL_QUIZ---' not in lesson_content and '---QUIZ_FLASHCARD---' not in lesson_content:
        # If it's a completely plain old file, assume it has a code editor available
        if '---EXERCISE---' in lesson_content:
            active_tabs.append('c')

    # Extract special sections (order matters — each extraction removes the section)
    expected_output, lesson_content = _extract_section(
        lesson_content, '---EXPECTED_OUTPUT---', '---END_EXPECTED_OUTPUT---')

    expected_output_python, lesson_content = _extract_section(
        lesson_content, '---EXPECTED_OUTPUT_PYTHON---', '---END_EXPECTED_OUTPUT_PYTHON---')

    expected_circuit_output, lesson_content = _extract_section(
        lesson_content, '---EXPECTED_CIRCUIT_OUTPUT---', '---END_EXPECTED_CIRCUIT_OUTPUT---')

    key_text, lesson_content = _extract_section(
        lesson_content, '---KEY_TEXT---', '---END_KEY_TEXT---')

    key_text_circuit, lesson_content = _extract_section(
        lesson_content, '---KEY_TEXT_CIRCUIT---', '---END_KEY_TEXT_CIRCUIT---')

    # Lesson info has a special fallback for old format
    lesson_info = ""
    if '---LESSON_INFO---' in lesson_content and '---END_LESSON_INFO---' in lesson_content:
        lesson_info, lesson_content = _extract_section(
            lesson_content, '---LESSON_INFO---', '---END_LESSON_INFO---')
    elif '---LESSON_INFO---' in lesson_content:
        parts = lesson_content.split('---LESSON_INFO---', 1)
        if len(parts) == 2:
            lesson_info = parts[0].strip()
            lesson_content = parts[1].strip()

    solution_code, lesson_content = _extract_section(
        lesson_content, '---SOLUTION_CODE---', '---END_SOLUTION_CODE---')

    solution_circuit, lesson_content = _extract_section(
        lesson_content, '---SOLUTION_CIRCUIT---', '---END_SOLUTION_CIRCUIT---')

    solution_python, lesson_content = _extract_section(
        lesson_content, '---SOLUTION_PYTHON---', '---END_SOLUTION_PYTHON---')

    # Initial codes (C, Python, Circuit, Quiz)
    initial_code_c, lesson_content = _extract_section(
        lesson_content, '---INITIAL_CODE---', '---END_INITIAL_CODE---')

    initial_python, lesson_content = _extract_section(
        lesson_content, '---INITIAL_PYTHON---', '---END_INITIAL_PYTHON---')

    initial_circuit, lesson_content = _extract_section(
        lesson_content, '---INITIAL_CIRCUIT---', '---END_INITIAL_CIRCUIT---')

    initial_flowchart_str, lesson_content = _extract_section(
        lesson_content, '---INITIAL_FLOWCHART---', '---END_INITIAL_FLOWCHART---')
        
    initial_flowchart = None
    if initial_flowchart_str:
        import json
        try:
            initial_flowchart = json.loads(initial_flowchart_str)
        except:
            initial_flowchart = {}

    initial_quiz, lesson_content = _extract_section(
        lesson_content, '---INITIAL_QUIZ---', '---END_INITIAL_QUIZ---')

    quiz_flashcard_raw, lesson_content = _extract_section(
        lesson_content, '---QUIZ_FLASHCARD---', '---END_QUIZ_FLASHCARD---')
    quiz_data = _parse_flashcards(quiz_flashcard_raw)

    # Arduino/Velxio sections
    initial_code_arduino, lesson_content = _extract_section(
        lesson_content, '---INITIAL_CODE_ARDUINO---', '---END_INITIAL_CODE_ARDUINO---')

    velxio_circuit, lesson_content = _extract_section(
        lesson_content, '---VELXIO_CIRCUIT---', '---END_VELXIO_CIRCUIT---')

    expected_serial_output, lesson_content = _extract_section(
        lesson_content, '---EXPECTED_SERIAL_OUTPUT---', '---END_EXPECTED_SERIAL_OUTPUT---')

    expected_wiring, lesson_content = _extract_section(
        lesson_content, '---EXPECTED_WIRING---', '---END_EXPECTED_WIRING---')

    expected_flowchart, lesson_content = _extract_section(
        lesson_content, '---EXPECTED_FLOWCHART---', '---END_EXPECTED_FLOWCHART---')

    evaluation_config, lesson_content = _extract_section(
        lesson_content, '---EVALUATION_CONFIG---', '---END_EVALUATION_CONFIG---')

    # Extract Slides
    slides_raw, _ = _extract_section(lesson_content, '---slide-start---', '---slide-end---')
    slides_html = []
    if slides_raw:
        # Replace the entire slide block with a mount point in the lesson_content
        # We need to find the exact indices to replace it surgically
        start_marker = '---slide-start---'
        end_marker = '---slide-end---'
        s_idx = lesson_content.find(start_marker)
        e_idx = lesson_content.find(end_marker)
        if s_idx != -1 and e_idx != -1 and e_idx > s_idx:
            lesson_content = (
                lesson_content[:s_idx] + 
                '<div id="slide-mount-point"></div>' + 
                lesson_content[e_idx + len(end_marker):]
            )
        
        # Parse slides
        slide_parts = re.split(r'^\s*---\s*$', slides_raw, flags=re.MULTILINE)
        for s in slide_parts:
            if s.strip():
                # Process embeds in slides too
                s = _process_circuit_embeds(s)
                s = _process_flowchart_embeds(s)
                s = _process_embed_embeds(s)
                slides_html.append(md.markdown(s.strip(), extensions=MD_EXTENSIONS))

    # Just use whichever initial code matched as the generic 'initial_code' for simplicity 
    # if only one type exists, but return all as dictionary values.
    # Typically frontend uses 'initial_code' for legacy. 
    initial_code = initial_code_c or initial_python or initial_circuit or initial_quiz

    # Split lesson vs exercise
    parts = lesson_content.split('---EXERCISE---')
    lesson_content = parts[0] if parts else lesson_content
    exercise_content = parts[1] if len(parts) > 1 else ""

    # Convert ```circuit and ```flowchart fences to embed divs before markdown rendering
    lesson_content = _process_circuit_embeds(lesson_content)
    lesson_content = _process_flowchart_embeds(lesson_content)
    lesson_content = _process_embed_embeds(lesson_content)
    if exercise_content:
        exercise_content = _process_circuit_embeds(exercise_content)
        exercise_content = _process_flowchart_embeds(exercise_content)
        exercise_content = _process_embed_embeds(exercise_content)
    if lesson_info:
        lesson_info = _process_circuit_embeds(lesson_info)
        lesson_info = _process_flowchart_embeds(lesson_info)
        lesson_info = _process_embed_embeds(lesson_info)

    lesson_html = md.markdown(lesson_content, extensions=MD_EXTENSIONS)
    exercise_html = md.markdown(exercise_content, extensions=MD_EXTENSIONS) if exercise_content else ""
    lesson_info_html = md.markdown(lesson_info, extensions=MD_EXTENSIONS) if lesson_info else ""

    parsed_data = {
        'lesson_html': lesson_html,
        'exercise_html': exercise_html,
        'expected_output': expected_output,
        'expected_output_python': expected_output_python,
        'expected_circuit_output': expected_circuit_output,
        'expected_flowchart': expected_flowchart,
        'lesson_info': lesson_info_html,
        'initial_code': initial_code,
        'solution_code': solution_code,
        'solution_circuit': solution_circuit,
        'solution_python': solution_python,
        'key_text': key_text,
        'key_text_circuit': key_text_circuit,
        'initial_code_c': initial_code_c,
        'initial_python': initial_python,
        'initial_circuit': initial_circuit,
        'initial_flowchart': initial_flowchart_str or initial_flowchart,
        'initial_quiz': initial_quiz,
        'initial_code_arduino': initial_code_arduino,
        'velxio_circuit': velxio_circuit,
        'expected_serial_output': expected_serial_output,
        'expected_wiring': expected_wiring,
        'evaluation_config': evaluation_config,
        'quiz_data': quiz_data,
        'active_tabs': active_tabs,
        'slides': slides_html
    }

    with _markdown_lock:
        if len(_markdown_cache) >= 128:
            _markdown_cache.clear()
        _markdown_cache[file_path] = {'data': parsed_data, 'mtime': current_mtime}

    return parsed_data


def render_home_content():
    """Render the home.md intro section (before Available_Lessons) as HTML.
    
    Not cached separately — relies on _read_home_md() mtime-based cache,
    which is already fast (1 syscall per request). This avoids the lru_cache
    multi-worker stale data problem.
    """
    home_content = _read_home_md()
    if not home_content:
        return ""

    # Use robust regex to split Available_Lessons
    parts = re.split(r'-{3,}Available_Lessons-{3,}', home_content)
    main_content = parts[0] if parts else home_content
    return md.markdown(main_content, extensions=['fenced_code', 'tables', 'mdx_math'])
