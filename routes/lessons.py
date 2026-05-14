"""
Lesson JSON API routes consumed by the SvelteKit frontend.
"""

import os

from flask import Blueprint, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

from compiler import compiler_factory
from config import CONTENT_DIR
from services.lesson_service import (
    get_ordered_lessons_with_learning_objectives,
    render_markdown_content,
    render_home_content,
    find_lesson_file,
)
from services.token_service import get_student_progress

lessons_bp = Blueprint('lessons', __name__)


@lessons_bp.route('/lessons')
def api_lessons():
    """Return lesson list + home content as JSON."""
    token = request.args.get('token', '') or request.cookies.get('student_token', '')

    progress = None
    if token:
        progress = get_student_progress(token)

    lessons = get_ordered_lessons_with_learning_objectives(progress)
    
    # Calculate locked status
    for lesson in lessons:
        prereqs = lesson.get('prerequisites', [])
        is_locked = False
        if prereqs:
            for p_slug in prereqs:
                if not progress or progress.get(p_slug) != 'completed':
                    is_locked = True
                    break
        lesson['locked'] = is_locked

    home_content = render_home_content()

    return jsonify({
        'lessons': lessons,
        'home_content': home_content,
    })


@lessons_bp.route('/lesson/<filename>.json')
def api_lesson(filename):
    """Return single lesson data as JSON."""
    full_filename = filename if filename.endswith('.md') else f'{filename}.md'
    file_path = find_lesson_file(full_filename)
    if not file_path:
        return jsonify({'error': 'Lesson not found'}), 404

    parsed_data = render_markdown_content(file_path)
    lesson_html = parsed_data['lesson_html']
    exercise_html = parsed_data['exercise_html']
    expected_output = parsed_data['expected_output']
    expected_output_python = parsed_data.get('expected_output_python', '')
    expected_circuit_output = parsed_data.get('expected_circuit_output', '')
    key_text_circuit = parsed_data.get('key_text_circuit', '')
    lesson_info = parsed_data['lesson_info']
    initial_code = parsed_data['initial_code']
    solution_code = parsed_data['solution_code']
    solution_circuit = parsed_data.get('solution_circuit', '')
    solution_python = parsed_data.get('solution_python', '')
    key_text = parsed_data['key_text']
    active_tabs = parsed_data['active_tabs']
    quiz_data = parsed_data.get('quiz_data', [])

    # New specific fields for hybrid lessons
    initial_circuit = parsed_data.get('initial_circuit', '')
    initial_code_c = parsed_data.get('initial_code_c', '')
    initial_python = parsed_data.get('initial_python', '')
    initial_flowchart = parsed_data.get('initial_flowchart', None)
    initial_quiz = parsed_data.get('initial_quiz', '')

    # Arduino/Velxio fields
    initial_code_arduino = parsed_data.get('initial_code_arduino', '')
    velxio_circuit = parsed_data.get('velxio_circuit', '')
    expected_serial_output = parsed_data.get('expected_serial_output', '')
    expected_wiring = parsed_data.get('expected_wiring', '')
    expected_flowchart = parsed_data.get('expected_flowchart', '')
    
    evaluation_config_raw = parsed_data.get('evaluation_config', '')
    evaluation_config = {}
    if evaluation_config_raw:
        import json
        try:
            evaluation_config = json.loads(evaluation_config_raw)
        except Exception:
            pass

    if not initial_code:
        initial_code = (
            '#include <stdio.h>\n\nint main() {\n'
            '    // Write your code here\n'
            '    printf("Hello, World!\\n");\n'
            '    return 0;\n}'
        )

    token = request.args.get('token', '') or request.cookies.get('student_token', '')
    progress = None
    lesson_completed = False
    lesson_progress_status = ''
    if token:
        progress = get_student_progress(token)
        if progress:
            status = progress.get(full_filename.replace('.md', ''), '')
            lesson_progress_status = status
            lesson_completed = status not in (None, '', 'not_started')

    all_lessons = get_ordered_lessons_with_learning_objectives(progress)

    current_idx = -1
    current_lesson_meta = None
    for i, les in enumerate(all_lessons):
        if les['filename'] == full_filename:
            current_idx = i
            current_lesson_meta = les
            break

    # Prerequisite check
    is_locked = False
    missing_prereqs = []
    if current_lesson_meta:
        prereqs = current_lesson_meta.get('prerequisites', [])
        for p_slug in prereqs:
            if not progress or progress.get(p_slug) != 'completed':
                is_locked = True
                missing_prereqs.append(p_slug)

    prev_lesson = all_lessons[current_idx - 1] if current_idx > 0 else None
    next_lesson = all_lessons[current_idx + 1] if 0 <= current_idx < len(all_lessons) - 1 else None

    # Derive default language from active_tabs (frontend manages switching)
    if 'python' in active_tabs and 'c' not in active_tabs:
        programming_language = 'python'
    else:
        programming_language = 'c'
    language_display_name = compiler_factory.get_language_display_name(programming_language)

    if is_locked:
        # Strip sensitive data to prevent inspection bypass
        exercise_html = ""
        expected_output = ""
        expected_output_python = ""
        expected_circuit_output = ""
        initial_code = "// Konten terkunci. Selesaikan prasyarat untuk melihat."
        initial_circuit = ""
        initial_code_c = ""
        initial_python = ""
        initial_flowchart = None
        initial_quiz = ""
        initial_code_arduino = ""
        velxio_circuit = ""
        expected_serial_output = ""
        expected_wiring = ""
        expected_flowchart = ""
        solution_code = ""
        solution_circuit = ""
        solution_python = ""
        key_text = ""
        key_text_circuit = ""
        quiz_data = []
        parsed_data['slides'] = []
        # Keep lesson_html, lesson_info, etc. for reading

    return jsonify({
        'lesson_content': lesson_html,
        'exercise_content': exercise_html,
        'expected_output': expected_output,
        'expected_output_python': expected_output_python,
        'expected_circuit_output': expected_circuit_output,
        'lesson_info': lesson_info,
        'initial_code': initial_code,
        'initial_circuit': initial_circuit,
        'initial_code_c': initial_code_c,
        'initial_python': initial_python,
        'initial_flowchart': initial_flowchart,
        'initial_quiz': initial_quiz,
        'initial_code_arduino': initial_code_arduino,
        'velxio_circuit': velxio_circuit,
        'expected_serial_output': expected_serial_output,
        'expected_wiring': expected_wiring,
        'expected_flowchart': expected_flowchart,
        'evaluation_config': evaluation_config,
        'solution_code': solution_code,
        'solution_circuit': solution_circuit,
        'solution_python': solution_python,
        'key_text': key_text,
        'key_text_circuit': key_text_circuit,
        'active_tabs': active_tabs,
        'quiz_data': quiz_data,
        'slides': parsed_data.get('slides', []),
        'lesson_progress_status': lesson_progress_status,
        'lesson_title': full_filename.replace('.md', '').replace('_', ' ').title(),
        'lesson_completed': lesson_completed,
        'locked': is_locked,
        'missing_prerequisites': missing_prereqs,
        'prev_lesson': prev_lesson,
        'next_lesson': next_lesson,
        'ordered_lessons': all_lessons,
        'language': programming_language,
        'language_display_name': language_display_name,
    })


@lessons_bp.route('/get-key-text/<filename>')
def get_key_text(filename):
    """Get the key text for a specific lesson."""
    file_path = find_lesson_file(filename)
    if not file_path:
        return jsonify({'success': False, 'error': 'Lesson not found'}), 404

    parsed_data = render_markdown_content(file_path)
    return jsonify({'success': True, 'key_text': parsed_data['key_text']})


@lessons_bp.route('/assets/<path:path>')
def send_assets(path):
    """Serve asset files (images, etc.)."""
    return send_from_directory('assets', path)
