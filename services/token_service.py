"""
Token and student progress operations backed by CSV file.
Optimized with in-memory caching and cross-process file locking.
"""

import csv
import logging
import os
import fcntl
import threading
from typing import Dict, List, Optional, Tuple

from config import TOKENS_FILE

# Global cache and synchronization for the current process
_cache_lock = threading.Lock()
_cached_tokens: Dict[str, dict] = {}
_cached_mtime: float = 0.0
_cached_fieldnames: List[str] = []


def _load_tokens_safely() -> Tuple[Dict[str, dict], List[str]]:
    """Load tokens from CSV with file locking and return (tokens_dict, fieldnames)."""
    if not os.path.exists(TOKENS_FILE):
        return {}, []

    try:
        with open(TOKENS_FILE, 'r', newline='', encoding='utf-8') as f:
            # Acquire shared lock for reading (blocks if an exclusive lock is held)
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                reader = csv.DictReader(f, delimiter=';')
                fieldnames = reader.fieldnames or []
                # Use a dictionary for O(1) lookups by token
                tokens = {row['token']: row for row in reader if 'token' in row}
                return tokens, fieldnames
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        logging.error(f"Error loading tokens file: {e}")
        return {}, []


def _get_tokens() -> Tuple[Dict[str, dict], List[str]]:
    """Get tokens from cache or reload if file has changed on disk."""
    global _cached_tokens, _cached_mtime, _cached_fieldnames
    
    if not os.path.exists(TOKENS_FILE):
        return {}, []

    try:
        current_mtime = os.path.getmtime(TOKENS_FILE)
    except OSError:
        return {}, []
    
    with _cache_lock:
        if current_mtime > _cached_mtime:
            # File has been modified by this or another process
            new_tokens, new_fieldnames = _load_tokens_safely()
            if new_tokens: # Only update if we successfully read something
                _cached_tokens = new_tokens
                _cached_fieldnames = new_fieldnames
                _cached_mtime = current_mtime
                logging.debug(f"Reloaded {len(_cached_tokens)} tokens from {TOKENS_FILE}")
            
        return _cached_tokens, _cached_fieldnames


def get_teacher_token():
    """Return the teacher token (first data row in CSV)."""
    tokens, _ = _get_tokens()
    if not tokens:
        return None
    # Python 3.7+ preserves insertion order in dicts
    return next(iter(tokens.keys()))


def is_teacher_token(token):
    """Check if the given token belongs to the teacher."""
    return token == get_teacher_token()


def validate_token(token):
    """Validate if a token exists and return student info."""
    if not token:
        return None
    tokens, _ = _get_tokens()
    row = tokens.get(token)
    if row:
        return {
            'token': row['token'],
            'student_name': row['nama_siswa'],
            'is_teacher': is_teacher_token(token),
        }
    return None


def get_student_progress(token):
    """Get the progress of a student based on their token."""
    if not token:
        return None
    tokens, _ = _get_tokens()
    return tokens.get(token)


def update_student_progress(token, lesson_name, status="completed"):
    """Update the progress of a student for a specific lesson with cross-process locking."""
    if not os.path.exists(TOKENS_FILE):
        logging.warning(f"Tokens file {TOKENS_FILE} does not exist")
        return False

    # Use 'r+' to allow reading and writing in the same file handle with one lock
    try:
        with open(TOKENS_FILE, 'r+', newline='', encoding='utf-8') as f:
            # Acquire exclusive lock for the whole read-modify-write cycle
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                reader = csv.DictReader(f, delimiter=';')
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
                            logging.warning(f"Lesson '{lesson_name}' not found in CSV columns")
                        break
                
                if updated:
                    # Clear and write back
                    f.seek(0)
                    f.truncate()
                    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
                    writer.writeheader()
                    writer.writerows(rows)
                    f.flush()
                    os.fsync(f.fileno()) # Guarantee write to disk
                    return True
                else:
                    return False
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        logging.error(f"Error updating student progress: {e}")
        return False


def initialize_tokens_file(lesson_names):
    """Initialize the tokens CSV file with headers and lesson columns."""
    if not os.path.exists(TOKENS_FILE):
        headers = ['token', 'nama_siswa'] + lesson_names
        try:
            with open(TOKENS_FILE, 'w', newline='', encoding='utf-8') as csvfile:
                # No lock needed for initial creation
                writer = csv.writer(csvfile, delimiter=';')
                writer.writerow(headers)
            print(f"Created new tokens file: {TOKENS_FILE} with headers: {headers}")
        except Exception as e:
            logging.error(f"Error initializing tokens file: {e}")


def calculate_student_completion(student_data, all_lessons):
    """Calculate the number of completed lessons for a student."""
    completed_count = 0
    for lesson in all_lessons:
        if isinstance(lesson, dict) and 'filename' in lesson:
            lesson_key = lesson['filename'].replace('.md', '')
        else:
            lesson_key = lesson.replace('.md', '')

        status = student_data.get(lesson_key, '')
        if status and status not in ('not_started', ''):
            completed_count += 1
    return completed_count


def get_all_students_progress(all_lessons_func):
    """Get all students' progress data for the progress report."""
    all_students_progress = []
    ordered_lessons = []

    tokens, fieldnames = _get_tokens()
    if not tokens:
        return all_students_progress, ordered_lessons

    lesson_headers = [field for field in fieldnames if field not in ['token', 'nama_siswa']]

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

    for row in tokens.values():
        student_data_copy = dict(row)
        student_data_copy['completed_count'] = calculate_student_completion(student_data_copy, ordered_lessons)
        all_students_progress.append(student_data_copy)

    return all_students_progress, ordered_lessons
