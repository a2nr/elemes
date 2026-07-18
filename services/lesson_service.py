"""
Lesson loading, ordering, and markdown rendering.
"""

import os
import re
import html as html_module
from functools import lru_cache
from threading import Lock

import markdown as md

from config import CONTENT_DIR

_home_cache = {'content': None, 'mtime': -1.0}
_home_lock = Lock()

_markdown_cache = {}
_markdown_lock = Lock()


def _read_home_md():
    """Read home.md and return its content, or empty string if missing."""
    path = os.path.join(CONTENT_DIR, "home.md")
    if not os.path.exists(path):
        return ""
    try:
        current_mtime = os.path.getmtime(path)
    except OSError:
        return _home_cache.get('content') or ""
        
    with _home_lock:
        if current_mtime != _home_cache['mtime']:
            with open(path, 'r', encoding='utf-8') as f:
                _home_cache['content'] = f.read()
            _home_cache['mtime'] = current_mtime
            # Invalidate all downstream caches
            find_lesson_file.cache_clear()
            get_lessons.cache_clear()
            get_lesson_names.cache_clear()
            get_lessons_with_learning_objectives.cache_clear()
            with _markdown_lock:
                _markdown_cache.clear()
        return _home_cache['content']


def _parse_lesson_links(home_content):
    """Extract (link_text, filename) pairs from the Available_Lessons section."""
    parts = re.split(r'-{3,}Available_Lessons-{3,}', home_content)
    if len(parts) <= 1:
        return []
    lesson_list_content = parts[-1]
    
    # Allow optional leading slash in /lesson/ prefix
    links = re.findall(r'\[([^\]]+)\]\((?:/?lesson/)?([^\)]+)\)', lesson_list_content)
    
    processed_links = []
    for title, slug in links:
        filename = slug if slug.endswith('.md') else slug + '.md'
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
        
    for root, _, files in os.walk(CONTENT_DIR):
        if filename in files:
            return os.path.join(root, filename)
    return None


@lru_cache(maxsize=32)
def get_lessons():
    """Get lessons from the Available_Lessons section in home.md."""
    lessons = []
    home_content = _read_home_md()
    if not home_content:
        return lessons

    for link_text, filename in _parse_lesson_links(home_content):
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


@lru_cache(maxsize=32)
def get_lessons_with_learning_objectives():
    """Get lessons with learning objectives extracted from LESSON_INFO sections."""
    lessons = []
    home_content = _read_home_md()
    if not home_content:
        return lessons

    for link_text, filename in _parse_lesson_links(home_content):
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


def get_ordered_lessons_with_learning_objectives(progress=None):
    """Get lessons ordered per home.md with completion status from progress dict."""
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
# Markdown rendering
# ---------------------------------------------------------------------------

MD_EXTENSIONS = ['fenced_code', 'tables', 'nl2br', 'toc', 'mdx_math']


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


def _parse_flashcards(text):
    """Parse a string of markdown with headings and options into a list of dicts.
    
    Supports two formats:
    1. Simple Flashcard: '### Question\nAnswer'
    2. Multiple Choice (MCQ): 
       '### Question
        - [] option 1
        - [x] option 2 (Correct)
        - [] option 3
        > Explanation'
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
        body = subparts[1].strip() if len(subparts) > 1 else ""
        
        if not question:
            continue

        # Check for MCQ options: - [ ] or - [x]
        option_pattern = re.compile(r'^\s*-\s*\[([ xX]?)\]\s*(.*)$', re.MULTILINE)
        options = option_pattern.findall(body)
        
        # Check for image: URL
        image_match = re.search(r'^\s*image:\s*(.*)$', body, re.MULTILINE)
        image_url = image_match.group(1).strip() if image_match else ""
        if image_match:
            body = re.sub(r'^\s*image:\s*.*$', '', body, flags=re.MULTILINE).strip()
        
        # Check for explanation (blockquote starting with >)
        explanation_match = re.search(r'^\s*(>.*)$', body, re.MULTILINE | re.DOTALL)
        explanation = explanation_match.group(1).strip() if explanation_match else ""
        
        # If MCQ options exist, it's an MCQ. We also remove the options from the body to find clean explanation.
        if options:
            parsed_options = []
            for mark, content in options:
                is_correct = mark.lower() == 'x'
                parsed_options.append({
                    'text': md.markdown(content.strip(), extensions=MD_EXTENSIONS),
                    'is_correct': is_correct
                })
            
            flashcards.append({
                'type': 'mcq',
                'question': md.markdown(question, extensions=MD_EXTENSIONS),
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
                'type': 'flashcard',
                'front': md.markdown(question, extensions=MD_EXTENSIONS),
                'back': md.markdown(clean_back, extensions=MD_EXTENSIONS),
                'explanation': md.markdown(explanation, extensions=MD_EXTENSIONS) if explanation else "",
                'image': image_url
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
    if exercise_content:
        exercise_content = _process_circuit_embeds(exercise_content)
        exercise_content = _process_flowchart_embeds(exercise_content)
    if lesson_info:
        lesson_info = _process_circuit_embeds(lesson_info)
        lesson_info = _process_flowchart_embeds(lesson_info)

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
