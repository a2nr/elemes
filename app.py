#!/usr/bin/env python3
"""
C Programming Learning Management System
A web-based application for learning C programming with exercise compilation
"""

import os
import subprocess
import tempfile
import markdown
from flask import Flask, render_template, request, jsonify, send_from_directory
import glob

app = Flask(__name__)

# Configuration
CONTENT_DIR = 'content'
STATIC_DIR = 'static'
TEMPLATES_DIR = 'templates'

def get_lessons():
    """Get all lesson files from the content directory"""
    lesson_files = glob.glob(os.path.join(CONTENT_DIR, "*.md"))
    lessons = []

    for file_path in lesson_files:
        filename = os.path.basename(file_path)
        # Skip home.md as it's not a lesson
        if filename == "home.md":
            continue

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Extract title from first line if it starts with #
            lines = content.split('\n')
            title = "Untitled"
            description = "Learn C programming concepts with practical examples."

            for i, line in enumerate(lines):
                if line.startswith('# '):
                    title = line[2:].strip()
                # Look for a line after the title that might be a description
                elif title != "Untitled" and line.strip() != "" and not line.startswith('#') and i < 10:
                    # Take the first substantial line as description
                    clean_line = line.strip().replace('#', '').strip()
                    if len(clean_line) > 10:  # Only if it's a meaningful description
                        description = clean_line
                        break

            lessons.append({
                'filename': filename,
                'title': title,
                'description': description,
                'path': file_path
            })

    return lessons

def get_ordered_lessons():
    """Get lessons in the order specified in home.md if available"""
    # Read home content to check for lesson order
    home_file_path = os.path.join(CONTENT_DIR, "home.md")
    if os.path.exists(home_file_path):
        with open(home_file_path, 'r', encoding='utf-8') as f:
            home_content = f.read()

        # Split content to get only the lesson list part
        parts = home_content.split('---Available_Lessons---')
        if len(parts) > 1:
            lesson_list_content = parts[1]

            # Find lesson links in the lesson list content
            import re
            # Look for markdown links that point to lessons
            lesson_links = re.findall(r'\[([^\]]+)\]\(lesson/([^\)]+)\)', lesson_list_content)

            if lesson_links:
                # Create ordered list based on home.md
                all_lessons = get_lessons()
                ordered_lessons = []

                for link_text, filename in lesson_links:
                    for lesson in all_lessons:
                        if lesson['filename'] == filename:
                            # Update title to use the link text from home.md if needed
                            lesson_copy = lesson.copy()
                            lesson_copy['title'] = link_text
                            ordered_lessons.append(lesson_copy)
                            break

                # Add any remaining lessons not mentioned in home.md
                for lesson in all_lessons:
                    if not any(l['filename'] == lesson['filename'] for l in ordered_lessons):
                        ordered_lessons.append(lesson)

                return ordered_lessons

    # If no specific order is defined in home.md, return lessons in default order
    return get_lessons()

def render_markdown_content(file_path):
    """Render markdown content to HTML"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check if there's additional lesson info at the beginning
    lesson_info = ""
    lesson_content = content
    initial_code = ""
    solution_code = ""
    expected_output = ""

    # Look for expected output separator - format: [content] ---EXPECTED_OUTPUT--- [output] ---END_EXPECTED_OUTPUT--- [content]
    if '---EXPECTED_OUTPUT---' in lesson_content and '---END_EXPECTED_OUTPUT---' in lesson_content:
        start_idx = lesson_content.find('---EXPECTED_OUTPUT---')
        end_idx = lesson_content.find('---END_EXPECTED_OUTPUT---')

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            # Extract the expected output between the separators
            expected_start = start_idx + len('---EXPECTED_OUTPUT---')
            expected_output = lesson_content[expected_start:end_idx].strip()
            # Remove the expected output section from the lesson content
            lesson_content = lesson_content[:start_idx] + lesson_content[end_idx + len('---END_EXPECTED_OUTPUT---'):]

    # Look for lesson info separator - format: ---LESSON_INFO--- [info] ---END_LESSON_INFO--- [content]
    if '---LESSON_INFO---' in lesson_content and '---END_LESSON_INFO---' in lesson_content:
        start_idx = lesson_content.find('---LESSON_INFO---') + len('---LESSON_INFO---')
        end_idx = lesson_content.find('---END_LESSON_INFO---')

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            lesson_info = lesson_content[start_idx:end_idx].strip()
            lesson_content = lesson_content[end_idx + len('---END_LESSON_INFO---'):].strip()
        else:
            # If the format is not correct, treat as before
            pass  # lesson_content remains the same
    elif '---LESSON_INFO---' in lesson_content:
        # Fallback for old format: content before first separator is info, after is lesson
        parts = lesson_content.split('---LESSON_INFO---', 1)
        if len(parts) == 2:
            lesson_info = parts[0].strip()
            lesson_content = parts[1].strip()

    # Look for solution code separator - format: [content] ---SOLUTION_CODE--- [code] ---END_SOLUTION_CODE---
    if '---SOLUTION_CODE---' in lesson_content and '---END_SOLUTION_CODE---' in lesson_content:
        start_idx = lesson_content.find('---SOLUTION_CODE---')
        end_idx = lesson_content.find('---END_SOLUTION_CODE---')

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            # Extract the code between the separators
            code_start = start_idx + len('---SOLUTION_CODE---')
            solution_code = lesson_content[code_start:end_idx].strip()
            # Remove the solution code section from the lesson content
            lesson_content = lesson_content[:start_idx] + lesson_content[end_idx + len('---END_SOLUTION_CODE---'):]

    # Look for initial code separator - format: [content] ---INITIAL_CODE--- [code] ---END_INITIAL_CODE---
    if '---INITIAL_CODE---' in lesson_content and '---END_INITIAL_CODE---' in lesson_content:
        start_idx = lesson_content.find('---INITIAL_CODE---')
        end_idx = lesson_content.find('---END_INITIAL_CODE---')

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            # Extract the code between the separators
            code_start = start_idx + len('---INITIAL_CODE---')
            initial_code = lesson_content[code_start:end_idx].strip()
            # Remove the initial code section from the lesson content
            lesson_content = lesson_content[:start_idx] + lesson_content[end_idx + len('---END_INITIAL_CODE---'):]

    # Split content into lesson and exercise parts
    parts = lesson_content.split('---EXERCISE---')
    lesson_content = parts[0] if len(parts) > 0 else lesson_content
    exercise_content = parts[1] if len(parts) > 1 else ""

    lesson_html = markdown.markdown(lesson_content, extensions=['fenced_code', 'codehilite', 'tables'])
    exercise_html = markdown.markdown(exercise_content, extensions=['fenced_code', 'codehilite', 'tables']) if exercise_content else ""
    lesson_info_html = markdown.markdown(lesson_info, extensions=['fenced_code', 'codehilite', 'tables']) if lesson_info else ""

    return lesson_html, exercise_html, expected_output, lesson_info_html, initial_code, solution_code

@app.route('/')
def index():
    """Main page showing all lessons"""
    lessons = get_ordered_lessons()

    # Read home content from a home.md file if it exists
    home_content = ""
    home_file_path = os.path.join(CONTENT_DIR, "home.md")
    if os.path.exists(home_file_path):
        with open(home_file_path, 'r', encoding='utf-8') as f:
            full_content = f.read()

        # Split content to get only the main content part (before the lesson list)
        parts = full_content.split('---Available_Lessons---')
        main_content = parts[0] if len(parts) > 0 else full_content
        home_content = markdown.markdown(main_content, extensions=['fenced_code', 'codehilite', 'tables'])

    return render_template('index.html', lessons=lessons, home_content=home_content)

@app.route('/lesson/<filename>')
def lesson(filename):
    """Display a specific lesson"""
    file_path = os.path.join(CONTENT_DIR, filename)
    if not os.path.exists(file_path):
        return "Lesson not found", 404

    lesson_html, exercise_html, expected_output, lesson_info, initial_code, solution_code = render_markdown_content(file_path)

    # If no initial code is provided, use a default template
    if not initial_code:
        initial_code = """#include <stdio.h>

int main() {
    // Write your code here
    printf("Hello, World!\\n");
    return 0;
}"""

    return render_template('lesson.html',
                          lesson_content=lesson_html,
                          exercise_content=exercise_html,
                          expected_output=expected_output,
                          lesson_info=lesson_info,
                          initial_code=initial_code,
                          solution_code=solution_code,
                          lesson_title=filename.replace('.md', '').replace('_', ' ').title())

@app.route('/compile', methods=['POST'])
def compile_code():
    """Compile and run C code submitted by the user"""
    try:
        code = None

        # Try to get code from JSON data
        if request.content_type and 'application/json' in request.content_type:
            try:
                json_data = request.get_json(force=True)
                if json_data and 'code' in json_data:
                    code = json_data['code']
            except Exception as e:
                # Log the error for debugging
                print(f"JSON parsing error: {e}")
                pass  # If JSON parsing fails, continue to try form data

        # If not found in JSON, try form data
        if not code:
            code = request.form.get('code', '')

        if not code:
            return jsonify({
                'success': False,
                'output': '',
                'error': 'No code provided'
            })

        # Create a temporary file for the C code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as temp_c:
            temp_c.write(code)
            temp_c_path = temp_c.name

        # Create a temporary file for the executable
        temp_exe_path = temp_c_path.replace('.c', '')

        # Compile the C code
        compile_result = subprocess.run(
            ['gcc', temp_c_path, '-o', temp_exe_path],
            capture_output=True,
            text=True,
            timeout=10
        )

        if compile_result.returncode != 0:
            # Compilation failed
            result = {
                'success': False,
                'output': compile_result.stdout,  # Include any stdout if available
                'error': compile_result.stderr  # Show GCC error messages
            }
        else:
            # Compilation succeeded, run the program
            try:
                run_result = subprocess.run(
                    [temp_exe_path],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                result = {
                    'success': True,
                    'output': run_result.stdout,
                    'error': run_result.stderr if run_result.stderr else None
                }
            except subprocess.TimeoutExpired:
                result = {
                    'success': False,
                    'output': '',
                    'error': 'Program execution timed out'
                }

        # Clean up temporary files
        try:
            os.remove(temp_c_path)
            if os.path.exists(temp_exe_path):
                os.remove(temp_exe_path)
        except:
            pass  # Ignore cleanup errors

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'success': False,
            'output': '',
            'error': f'An error occurred: {str(e)}'
        })

@app.route('/static/<path:path>')
def send_static(path):
    """Serve static files"""
    return send_from_directory('static', path)

@app.route('/assets/<path:path>')
def send_assets(path):
    """Serve asset files (images, etc.)"""
    return send_from_directory('assets', path)

@app.context_processor
def inject_functions():
    """Make get_lessons function available in templates"""
    return dict(get_lessons=get_lessons)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)