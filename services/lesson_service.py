"""
Lesson loading, ordering, and markdown rendering.
"""

import os
import re
import html as html_module
from functools import lru_cache

import markdown as md

from config import CONTENT_DIR


@lru_cache(maxsize=1)
def _read_home_md():
    """Read home.md and return its content, or empty string if missing."""
    path = os.path.join(CONTENT_DIR, "home.md")
    if not os.path.exists(path):
        return ""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def _parse_lesson_links(home_content):
    """Extract (link_text, filename) pairs from the Available_Lessons section."""
    parts = home_content.split('---Available_Lessons---')
    if len(parts) <= 1:
        return []
    lesson_list_content = parts[1]
    return re.findall(r'\[([^\]]+)\]\((?:lesson/)?([^\)]+)\)', lesson_list_content)


# ---------------------------------------------------------------------------
# Lesson listing
# ---------------------------------------------------------------------------

@lru_cache(maxsize=32)
def get_lessons():
    """Get lessons from the Available_Lessons section in home.md."""
    lessons = []
    home_content = _read_home_md()
    if not home_content:
        return lessons

    for link_text, filename in _parse_lesson_links(home_content):
        file_path = os.path.join(CONTENT_DIR, filename)
        if not os.path.exists(file_path):
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
        file_path = os.path.join(CONTENT_DIR, filename)
        if os.path.exists(file_path):
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
        file_path = os.path.join(CONTENT_DIR, filename)
        if not os.path.exists(file_path):
            continue

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        title = link_text
        description = "Learn C programming concepts with practical examples."

        lesson_info_start = content.find('---LESSON_INFO---')
        lesson_info_end = content.find('---END_LESSON_INFO---')

        if lesson_info_start != -1 and lesson_info_end != -1:
            lesson_info_section = content[lesson_info_start + len('---LESSON_INFO---'):lesson_info_end]

            objectives_start = lesson_info_section.find('**Learning Objectives:**')
            if objectives_start != -1:
                objectives_section = lesson_info_section[objectives_start:]
                objective_matches = re.findall(r'- ([^\n]+)', objectives_section)
                if objective_matches:
                    description = '; '.join(objective_matches[:3])
                else:
                    lines_after = lesson_info_section[objectives_start:].split('\n')[1:4]
                    description = ' '.join(line.strip() for line in lines_after if line.strip())

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
        })

    return lessons


def get_ordered_lessons_with_learning_objectives(progress=None):
    """Get lessons ordered per home.md with completion status from progress dict."""
    home_content = _read_home_md()
    lesson_links = _parse_lesson_links(home_content) if home_content else []

    all_lessons = get_lessons_with_learning_objectives()

    def _add_completion(lesson, progress):
        if progress:
            lesson_key = lesson['filename'].replace('.md', '')
            lesson['completed'] = progress.get(lesson_key) == 'completed'
        else:
            lesson['completed'] = False
        return lesson

    if lesson_links:
        ordered = []
        for link_text, filename in lesson_links:
            for lesson in all_lessons:
                if lesson['filename'] == filename:
                    copy = lesson.copy()
                    copy['title'] = link_text
                    _add_completion(copy, progress)
                    ordered.append(copy)
                    break

        seen = {l['filename'] for l in ordered}
        for lesson in all_lessons:
            if lesson['filename'] not in seen:
                copy = lesson.copy()
                _add_completion(copy, progress)
                ordered.append(copy)

        return ordered

    ordered_fallback = []
    for lesson in all_lessons:
        copy = lesson.copy()
        _add_completion(copy, progress)
        ordered_fallback.append(copy)
    return ordered_fallback


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

MD_EXTENSIONS = ['fenced_code', 'tables', 'nl2br', 'toc']


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


@lru_cache(maxsize=32)
def render_markdown_content(file_path):
    """Parse a lesson markdown file and return structured HTML parts as a dictionary."""
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
    if '---INITIAL_QUIZ---' in lesson_content:
        active_tabs.append('quiz')
    # Velxio circuit-only: has VELXIO_CIRCUIT but no INITIAL_CODE_ARDUINO
    if '---VELXIO_CIRCUIT---' in lesson_content and 'velxio' not in active_tabs:
        active_tabs.append('velxio')

    # Default to 'c' if nothing specified (for backwards compatibility)
    if not active_tabs and '---INITIAL_CODE---' not in lesson_content and '---INITIAL_PYTHON---' not in lesson_content and '---INITIAL_CIRCUIT---' not in lesson_content and '---INITIAL_QUIZ---' not in lesson_content:
        # If it's a completely plain old file, assume it has a code editor available
        if '---EXERCISE---' in lesson_content:
            active_tabs.append('c')

    # Extract special sections (order matters — each extraction removes the section)
    expected_output, lesson_content = _extract_section(
        lesson_content, '---EXPECTED_OUTPUT---', '---END_EXPECTED_OUTPUT---')

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

    initial_quiz, lesson_content = _extract_section(
        lesson_content, '---INITIAL_QUIZ---', '---END_INITIAL_QUIZ---')

    # Arduino/Velxio sections
    initial_code_arduino, lesson_content = _extract_section(
        lesson_content, '---INITIAL_CODE_ARDUINO---', '---END_INITIAL_CODE_ARDUINO---')

    velxio_circuit, lesson_content = _extract_section(
        lesson_content, '---VELXIO_CIRCUIT---', '---END_VELXIO_CIRCUIT---')

    expected_serial_output, lesson_content = _extract_section(
        lesson_content, '---EXPECTED_SERIAL_OUTPUT---', '---END_EXPECTED_SERIAL_OUTPUT---')

    expected_wiring, lesson_content = _extract_section(
        lesson_content, '---EXPECTED_WIRING---', '---END_EXPECTED_WIRING---')

    evaluation_config, lesson_content = _extract_section(
        lesson_content, '---EVALUATION_CONFIG---', '---END_EVALUATION_CONFIG---')

    # Just use whichever initial code matched as the generic 'initial_code' for simplicity 
    # if only one type exists, but return all as dictionary values.
    # Typically frontend uses 'initial_code' for legacy. 
    initial_code = initial_code_c or initial_python or initial_circuit or initial_quiz

    # Split lesson vs exercise
    parts = lesson_content.split('---EXERCISE---')
    lesson_content = parts[0] if parts else lesson_content
    exercise_content = parts[1] if len(parts) > 1 else ""

    # Convert ```circuit fences to embed divs before markdown rendering
    lesson_content = _process_circuit_embeds(lesson_content)
    if exercise_content:
        exercise_content = _process_circuit_embeds(exercise_content)
    if lesson_info:
        lesson_info = _process_circuit_embeds(lesson_info)

    lesson_html = md.markdown(lesson_content, extensions=MD_EXTENSIONS)
    exercise_html = md.markdown(exercise_content, extensions=MD_EXTENSIONS) if exercise_content else ""
    lesson_info_html = md.markdown(lesson_info, extensions=MD_EXTENSIONS) if lesson_info else ""

    return {
        'lesson_html': lesson_html,
        'exercise_html': exercise_html,
        'expected_output': expected_output,
        'expected_circuit_output': expected_circuit_output,
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
        'initial_quiz': initial_quiz,
        'initial_code_arduino': initial_code_arduino,
        'velxio_circuit': velxio_circuit,
        'expected_serial_output': expected_serial_output,
        'expected_wiring': expected_wiring,
        'evaluation_config': evaluation_config,
        'active_tabs': active_tabs
    }


@lru_cache(maxsize=1)
def render_home_content():
    """Render the home.md intro section (before Available_Lessons) as HTML."""
    home_content = _read_home_md()
    if not home_content:
        return ""

    parts = home_content.split('---Available_Lessons---')
    main_content = parts[0] if parts else home_content
    return md.markdown(main_content, extensions=['fenced_code', 'tables'])
