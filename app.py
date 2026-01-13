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
from flask_talisman import Talisman
import glob
import csv
import uuid
import os
from datetime import datetime
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load configuration from environment variables with defaults
CONTENT_DIR = os.environ.get('CONTENT_DIR', 'content')
STATIC_DIR = os.environ.get('STATIC_DIR', 'static')
TEMPLATES_DIR = os.environ.get('TEMPLATES_DIR', 'templates')
TOKENS_FILE = os.environ.get('TOKENS_FILE', 'tokens.csv')

# Get application titles from environment variables
APP_BAR_TITLE = os.environ.get('APP_BAR_TITLE', 'C Programming Learning System')
COPYRIGHT_TEXT = os.environ.get('COPYRIGHT_TEXT', 'C Programming Learning System &copy; 2025')
PAGE_TITLE_SUFFIX = os.environ.get('PAGE_TITLE_SUFFIX', 'C Programming Learning System')

# Log the values to ensure they are loaded correctly
print(f"APP_BAR_TITLE: {APP_BAR_TITLE}")
print(f"COPYRIGHT_TEXT: {COPYRIGHT_TEXT}")
print(f"PAGE_TITLE_SUFFIX: {PAGE_TITLE_SUFFIX}")

# Security configuration using Talisman
Talisman(app,
    force_https=False,  # Set to True if using SSL
    strict_transport_security=True,
    strict_transport_security_max_age=31536000,
    frame_options='DENY',
    content_security_policy={
        'default-src': "'self'",
        'script-src': "'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net",
        'style-src': "'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
        'img-src': "'self' data: https:",
        'font-src': "'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
        'connect-src': "'self'",
        'frame-ancestors': "'none'",
    },
    referrer_policy='strict-origin-when-cross-origin'
)

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

def get_lesson_names():
    """Get all lesson names from the content directory (excluding home.md)"""
    lesson_files = glob.glob(os.path.join(CONTENT_DIR, "*.md"))
    lesson_names = []

    for file_path in lesson_files:
        filename = os.path.basename(file_path)
        # Skip home.md as it's not a lesson
        if filename == "home.md":
            continue
        lesson_names.append(filename.replace('.md', ''))

    return lesson_names

def initialize_tokens_file():
    """Initialize the tokens CSV file with headers and lesson columns"""
    lesson_names = get_lesson_names()

    # Check if file exists
    if not os.path.exists(TOKENS_FILE):
        # Create the file with headers
        headers = ['token', 'nama_siswa'] + lesson_names

        with open(TOKENS_FILE, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, delimiter=';')
            writer.writerow(headers)

        print(f"Created new tokens file: {TOKENS_FILE} with headers: {headers}")

def validate_token(token):
    """Validate if a token exists in the CSV file and return student info"""
    if not os.path.exists(TOKENS_FILE):
        return None

    with open(TOKENS_FILE, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        for row in reader:
            if row['token'] == token:
                return {
                    'token': row['token'],
                    'student_name': row['nama_siswa']
                }

    return None

def get_student_progress(token):
    """Get the progress of a student based on their token"""
    if not os.path.exists(TOKENS_FILE):
        return None

    with open(TOKENS_FILE, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        for row in reader:
            if row['token'] == token:
                # Return the entire row as progress data
                return row

    return None

def update_student_progress(token, lesson_name, status="completed"):
    """Update the progress of a student for a specific lesson"""
    if not os.path.exists(TOKENS_FILE):
        logging.warning(f"Tokens file {TOKENS_FILE} does not exist")
        return False

    # Read all rows
    rows = []
    with open(TOKENS_FILE, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        fieldnames = reader.fieldnames
        rows = list(reader)

    # Find and update the specific student's lesson status
    updated = False
    for row in rows:
        if row['token'] == token:
            # Check if the lesson_name exists in fieldnames
            if lesson_name in fieldnames:
                row[lesson_name] = status
                updated = True
                logging.info(f"Updating progress for token {token}, lesson {lesson_name}, status {status}")
            else:
                logging.warning(f"Lesson '{lesson_name}' not found in CSV columns: {fieldnames}")
            break

    # Write the updated data back to the file
    if updated:
        with open(TOKENS_FILE, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(rows)
        logging.info(f"Updated progress for token {token}, lesson {lesson_name}, status {status}")
    else:
        logging.warning(f"Failed to update progress for token {token}, lesson {lesson_name}")

    return updated

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


def get_lessons_with_learning_objectives():
    """Get all lesson files from the content directory with learning objectives as descriptions"""
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

            # Look for lesson info section to extract learning objectives
            lesson_info_start = content.find('---LESSON_INFO---')
            lesson_info_end = content.find('---END_LESSON_INFO---')

            if lesson_info_start != -1 and lesson_info_end != -1:
                lesson_info_section = content[lesson_info_start + len('---LESSON_INFO---'):lesson_info_end]

                # Extract learning objectives
                objectives_start = lesson_info_section.find('**Learning Objectives:**')
                if objectives_start != -1:
                    objectives_section = lesson_info_section[objectives_start:]

                    # Find the objectives list
                    import re
                    # Look for bullet points after Learning Objectives
                    objective_matches = re.findall(r'- ([^\n]+)', objectives_section)

                    if objective_matches:
                        # Combine first few objectives as description
                        description = '; '.join(objective_matches[:3])  # Take first 3 objectives
                    else:
                        # If no bullet points found, take a few lines after the heading
                        lines_after = lesson_info_section[objectives_start:].split('\n')[1:4]
                        description = ' '.join(line.strip() for line in lines_after if line.strip())

                # Look for the main title after the lesson info section
                # Find the content after END_LESSON_INFO
                content_after_info = content[lesson_info_end + len('---END_LESSON_INFO---'):].strip()
                content_lines = content_after_info.split('\n')

                # Find the first line that starts with # (the main title)
                for line in content_lines:
                    if line.startswith('# '):
                        title = line[2:].strip()
                        break
            else:
                # If no lesson info section, use the original method
                for i, line in enumerate(lines):
                    if line.startswith('# '):
                        title = line[2:].strip()
                        break

            lessons.append({
                'filename': filename,
                'title': title,
                'description': description,
                'path': file_path
            })

    return lessons


def get_ordered_lessons_with_learning_objectives(progress=None):
    """Get lessons in the order specified in home.md if available with learning objectives as descriptions"""
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
            lesson_links = re.findall(r'\[([^\]]+)\]\((?:lesson/)?([^\)]+)\)', lesson_list_content)

            if lesson_links:
                # Create ordered list based on home.md
                all_lessons = get_lessons_with_learning_objectives()
                ordered_lessons = []

                for link_text, filename in lesson_links:
                    for lesson in all_lessons:
                        if lesson['filename'] == filename:
                            # Update title to use the link text from home.md if needed
                            lesson_copy = lesson.copy()
                            lesson_copy['title'] = link_text

                            # Add completion status if progress is provided
                            if progress:
                                lesson_key = filename.replace('.md', '')
                                if lesson_key in progress:
                                    lesson_copy['completed'] = progress[lesson_key] == 'completed'
                                else:
                                    lesson_copy['completed'] = False
                            else:
                                lesson_copy['completed'] = False

                            ordered_lessons.append(lesson_copy)
                            break

                # Add any remaining lessons not mentioned in home.md
                for lesson in all_lessons:
                    if not any(l['filename'] == lesson['filename'] for l in ordered_lessons):
                        # Add completion status if progress is provided
                        if progress:
                            lesson_key = lesson['filename'].replace('.md', '')
                            if lesson_key in progress:
                                lesson['completed'] = progress[lesson_key] == 'completed'
                            else:
                                lesson['completed'] = False
                        else:
                            lesson['completed'] = False
                        ordered_lessons.append(lesson)

                return ordered_lessons

    # If no specific order is defined in home.md, return lessons in default order
    all_lessons = get_lessons_with_learning_objectives()

    # Add completion status if progress is provided
    if progress:
        for lesson in all_lessons:
            lesson_key = lesson['filename'].replace('.md', '')
            if lesson_key in progress:
                lesson['completed'] = progress[lesson_key] == 'completed'
            else:
                lesson['completed'] = False
    else:
        for lesson in all_lessons:
            lesson['completed'] = False

    return all_lessons

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
    print("Index function called")  # Logging for debugging
    print(f"APP_BAR_TITLE value: {APP_BAR_TITLE}")  # Logging for debugging
    print(f"COPYRIGHT_TEXT value: {COPYRIGHT_TEXT}")  # Logging for debugging
    print(f"PAGE_TITLE_SUFFIX value: {PAGE_TITLE_SUFFIX}")  # Logging for debugging

    # Get token from session or request (for now, we'll pass it in the template context)
    token = request.args.get('token', '')  # This would typically come from session after login

    # If no token provided in URL, try to get from cookie
    if not token:
        token = request.cookies.get('student_token', '')

    # Get student progress if token is provided
    progress = None
    if token:
        progress = get_student_progress(token)
        print(f"Progress for token {token}: {progress}")  # Logging for debugging

    lessons = get_ordered_lessons_with_learning_objectives(progress)

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

    print(f"Sending to template - token: {token}, progress: {progress}, lessons count: {len(lessons)}")  # Logging for debugging
    for lesson in lessons:
        print(f"Lesson: {lesson['title']}, completed: {lesson.get('completed', 'N/A')}")  # Logging for debugging

    try:
        result = render_template('index.html',
                               lessons=lessons,
                               home_content=home_content,
                               token=token,
                               progress=progress,
                               app_bar_title=APP_BAR_TITLE,
                               copyright_text=COPYRIGHT_TEXT,
                               page_title_suffix=PAGE_TITLE_SUFFIX)
        print("Template rendered successfully")
        return result
    except Exception as e:
        print(f"Error rendering template: {str(e)}")
        import traceback
        traceback.print_exc()
        # Return a simple error page
        return f"Error rendering template: {str(e)}"

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

    # Get token from session or request (for now, we'll pass it in the template context)
    token = request.args.get('token', '')  # This would typically come from session after login

    # If no token provided in URL, try to get from cookie
    if not token:
        token = request.cookies.get('student_token', '')

    # Get student progress if token is provided
    progress = None
    lesson_completed = False
    if token:
        progress = get_student_progress(token)
        if progress and filename.replace('.md', '') in progress:
            lesson_completed = progress[filename.replace('.md', '')] == 'completed'

    # Get ordered lessons to determine next and previous lessons
    all_lessons = get_ordered_lessons_with_learning_objectives(progress)

    # Find current lesson index
    current_lesson_idx = -1
    for i, lesson in enumerate(all_lessons):
        if lesson['filename'] == filename:
            current_lesson_idx = i
            break

    # Determine previous and next lessons
    prev_lesson = None
    next_lesson = None

    if current_lesson_idx != -1:
        if current_lesson_idx > 0:
            prev_lesson = all_lessons[current_lesson_idx - 1]
        if current_lesson_idx < len(all_lessons) - 1:
            next_lesson = all_lessons[current_lesson_idx + 1]

    # Get ordered lessons for the sidebar
    ordered_lessons = get_ordered_lessons_with_learning_objectives(progress)

    return render_template('lesson.html',
                          lesson_content=lesson_html,
                          exercise_content=exercise_html,
                          expected_output=expected_output,
                          lesson_info=lesson_info,
                          initial_code=initial_code,
                          solution_code=solution_code,
                          lesson_title=filename.replace('.md', '').replace('_', ' ').title(),
                          token=token,
                          progress=progress,
                          lesson_completed=lesson_completed,
                          prev_lesson=prev_lesson,
                          next_lesson=next_lesson,
                          ordered_lessons=ordered_lessons,
                          app_bar_title=APP_BAR_TITLE,
                          copyright_text=COPYRIGHT_TEXT,
                          page_title_suffix=PAGE_TITLE_SUFFIX)

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

@app.route('/login', methods=['POST'])
def login():
    """Handle student login with token"""
    try:
        data = request.get_json()
        token = data.get('token', '').strip()

        if not token:
            return jsonify({'success': False, 'message': 'Token is required'})

        # Validate the token
        student_info = validate_token(token)
        if student_info:
            response = jsonify({
                'success': True,
                'student_name': student_info['student_name'],
                'message': 'Login successful'
            })
            # Set token in cookie with expiration
            response.set_cookie('student_token', token, httponly=True, secure=False, samesite='Lax', max_age=86400)  # 24 hours
            return response
        else:
            return jsonify({'success': False, 'message': 'Invalid token'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error processing login: {str(e)}'})

@app.route('/logout', methods=['POST'])
def logout():
    """Handle student logout"""
    try:
        # Create response that clears the cookie
        response = jsonify({
            'success': True,
            'message': 'Logout successful'
        })
        # Clear the student_token cookie
        response.set_cookie('student_token', '', expires=0)
        return response
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error processing logout: {str(e)}'})

@app.route('/validate-token', methods=['POST'])
def validate_token_route():
    """Validate a token without logging in"""
    try:
        data = request.get_json()
        token = data.get('token', '').strip()

        # If no token provided in request, try to get from cookie
        if not token:
            token = request.cookies.get('student_token', '').strip()

        if not token:
            return jsonify({'success': False, 'message': 'Token is required'})

        # Validate the token
        student_info = validate_token(token)
        if student_info:
            return jsonify({
                'success': True,
                'student_name': student_info['student_name']
            })
        else:
            return jsonify({'success': False, 'message': 'Invalid token'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error validating token: {str(e)}'})

@app.route('/track-progress', methods=['POST'])
def track_progress():
    """Track student progress for a lesson"""
    try:
        data = request.get_json()
        token = data.get('token', '').strip()
        lesson_name = data.get('lesson_name', '').strip()
        status = data.get('status', 'completed').strip()

        logging.info(f"Received track-progress request: token={token}, lesson_name={lesson_name}, status={status}")

        if not token or not lesson_name:
            return jsonify({'success': False, 'message': 'Token and lesson name are required'})

        # Validate the token first
        student_info = validate_token(token)
        if not student_info:
            return jsonify({'success': False, 'message': 'Invalid token'})

        # Update progress
        updated = update_student_progress(token, lesson_name, status)
        if updated:
            logging.info(f"Progress updated successfully for token {token}, lesson {lesson_name}")
            return jsonify({
                'success': True,
                'message': 'Progress updated successfully'
            })
        else:
            logging.warning(f"Failed to update progress for token {token}, lesson {lesson_name}")
            return jsonify({'success': False, 'message': 'Failed to update progress'})

    except Exception as e:
        logging.error(f"Error in track-progress: {str(e)}")
        return jsonify({'success': False, 'message': f'Error tracking progress: {str(e)}'})

@app.context_processor
def inject_functions():
    """Make functions available in templates"""
    return dict(
        get_lessons=get_lessons,
        get_ordered_lessons_with_learning_objectives=get_ordered_lessons_with_learning_objectives
    )

# Initialize the tokens file when the app starts
initialize_tokens_file()

if __name__ == '__main__':
    import os
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)