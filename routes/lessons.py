"""
Lesson JSON API routes consumed by the SvelteKit frontend.
"""

import os

from flask import Blueprint, request, jsonify, send_from_directory

from compiler import compiler_factory
from config import CONTENT_DIR, DEFAULT_PROGRAMMING_LANGUAGE
from services.lesson_service import (
    get_ordered_lessons_with_learning_objectives,
    render_markdown_content,
    render_home_content,
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
    home_content = render_home_content()

    return jsonify({
        'lessons': lessons,
        'home_content': home_content,
    })


@lessons_bp.route('/lesson/<filename>.json')
def api_lesson(filename):
    """Return single lesson data as JSON."""
    full_filename = filename if filename.endswith('.md') else f'{filename}.md'
    file_path = os.path.join(CONTENT_DIR, full_filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'Lesson not found'}), 404

    parsed_data = render_markdown_content(file_path)
    lesson_html = parsed_data['lesson_html']
    exercise_html = parsed_data['exercise_html']
    expected_output = parsed_data['expected_output']
    expected_circuit_output = parsed_data.get('expected_circuit_output', '')
    key_text_circuit = parsed_data.get('key_text_circuit', '')
    lesson_info = parsed_data['lesson_info']
    initial_code = parsed_data['initial_code']
    solution_code = parsed_data['solution_code']
    solution_circuit = parsed_data.get('solution_circuit', '')
    key_text = parsed_data['key_text']
    active_tabs = parsed_data['active_tabs']

    # New specific fields for hybrid lessons
    initial_circuit = parsed_data.get('initial_circuit', '')
    initial_code_c = parsed_data.get('initial_code_c', '')
    initial_python = parsed_data.get('initial_python', '')
    initial_quiz = parsed_data.get('initial_quiz', '')

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
    if token:
        progress = get_student_progress(token)
        if progress and full_filename.replace('.md', '') in progress:
            lesson_completed = progress[full_filename.replace('.md', '')] == 'completed'

    all_lessons = get_ordered_lessons_with_learning_objectives(progress)

    current_idx = -1
    for i, les in enumerate(all_lessons):
        if les['filename'] == full_filename:
            current_idx = i
            break

    prev_lesson = all_lessons[current_idx - 1] if current_idx > 0 else None
    next_lesson = all_lessons[current_idx + 1] if 0 <= current_idx < len(all_lessons) - 1 else None

    programming_language = DEFAULT_PROGRAMMING_LANGUAGE
    language_display_name = compiler_factory.get_language_display_name(programming_language)

    return jsonify({
        'lesson_content': lesson_html,
        'exercise_content': exercise_html,
        'expected_output': expected_output,
        'expected_circuit_output': expected_circuit_output,
        'lesson_info': lesson_info,
        'initial_code': initial_code,
        'initial_circuit': initial_circuit,
        'initial_code_c': initial_code_c,
        'initial_python': initial_python,
        'initial_quiz': initial_quiz,
        'solution_code': solution_code,
        'solution_circuit': solution_circuit,
        'key_text': key_text,
        'key_text_circuit': key_text_circuit,
        'active_tabs': active_tabs,
        'lesson_title': full_filename.replace('.md', '').replace('_', ' ').title(),
        'lesson_completed': lesson_completed,
        'prev_lesson': prev_lesson,
        'next_lesson': next_lesson,
        'ordered_lessons': all_lessons,
        'language': programming_language,
        'language_display_name': language_display_name,
    })


@lessons_bp.route('/get-key-text/<filename>')
def get_key_text(filename):
    """Get the key text for a specific lesson."""
    file_path = os.path.join(CONTENT_DIR, filename)
    if not os.path.exists(file_path):
        return jsonify({'success': False, 'error': 'Lesson not found'}), 404

    parsed_data = render_markdown_content(file_path)
    return jsonify({'success': True, 'key_text': parsed_data['key_text']})


@lessons_bp.route('/assets/<path:path>')
def send_assets(path):
    """Serve asset files (images, etc.)."""
    return send_from_directory('assets', path)
