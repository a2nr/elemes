"""
Token and student progress operations backed by CSV file.
"""

import csv
import logging
import os

from config import TOKENS_FILE


def validate_token(token):
    """Validate if a token exists in the CSV file and return student info."""
    if not os.path.exists(TOKENS_FILE):
        return None

    with open(TOKENS_FILE, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        for row in reader:
            if row['token'] == token:
                return {
                    'token': row['token'],
                    'student_name': row['nama_siswa'],
                }

    return None


def get_student_progress(token):
    """Get the progress of a student based on their token."""
    if not os.path.exists(TOKENS_FILE):
        return None

    with open(TOKENS_FILE, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        for row in reader:
            if row['token'] == token:
                return row

    return None


def update_student_progress(token, lesson_name, status="completed"):
    """Update the progress of a student for a specific lesson."""
    if not os.path.exists(TOKENS_FILE):
        logging.warning(f"Tokens file {TOKENS_FILE} does not exist")
        return False

    rows = []
    with open(TOKENS_FILE, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        fieldnames = reader.fieldnames
        rows = list(reader)

    updated = False
    for row in rows:
        if row['token'] == token:
            if lesson_name in fieldnames:
                row[lesson_name] = status
                updated = True
                logging.info(f"Updating progress for token {token}, lesson {lesson_name}, status {status}")
            else:
                logging.warning(f"Lesson '{lesson_name}' not found in CSV columns: {fieldnames}")
            break

    if updated:
        with open(TOKENS_FILE, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(rows)
        logging.info(f"Updated progress for token {token}, lesson {lesson_name}, status {status}")
    else:
        logging.warning(f"Failed to update progress for token {token}, lesson {lesson_name}")

    return updated


def initialize_tokens_file(lesson_names):
    """Initialize the tokens CSV file with headers and lesson columns."""
    if not os.path.exists(TOKENS_FILE):
        headers = ['token', 'nama_siswa'] + lesson_names
        with open(TOKENS_FILE, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, delimiter=';')
            writer.writerow(headers)
        print(f"Created new tokens file: {TOKENS_FILE} with headers: {headers}")


def calculate_student_completion(student_data, all_lessons):
    """Calculate the number of completed lessons for a student."""
    completed_count = 0
    for lesson in all_lessons:
        if isinstance(lesson, dict) and 'filename' in lesson:
            lesson_key = lesson['filename'].replace('.md', '')
        else:
            lesson_key = lesson.replace('.md', '')

        if lesson_key in student_data and student_data[lesson_key] == 'completed':
            completed_count += 1
    return completed_count


def get_all_students_progress(all_lessons_func):
    """Get all students' progress data for the progress report.

    Returns (all_students_progress, ordered_lessons).
    """
    all_students_progress = []
    ordered_lessons = []
    lesson_headers = []

    if not os.path.exists(TOKENS_FILE):
        return all_students_progress, ordered_lessons

    with open(TOKENS_FILE, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        lesson_headers = [field for field in reader.fieldnames if field not in ['token', 'nama_siswa']]

        all_lessons_dict = {}
        for lesson in all_lessons_func():
            lesson_key = lesson['filename'].replace('.md', '')
            all_lessons_dict[lesson_key] = lesson

        for lesson_header in lesson_headers:
            if lesson_header in all_lessons_dict:
                ordered_lessons.append(all_lessons_dict[lesson_header])
            else:
                ordered_lessons.append({
                    'filename': f"{lesson_header}.md",
                    'title': lesson_header.replace('_', ' ').title(),
                    'description': 'Lesson information not available',
                })

        for row in reader:
            student_data = dict(row)
            del student_data['token']
            student_data['completed_count'] = calculate_student_completion(student_data, ordered_lessons)
            all_students_progress.append(student_data)

    return all_students_progress, ordered_lessons
