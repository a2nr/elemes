"""
Storage backend CSV — perilaku historis tokens_siswa.csv
(in-memory cache + cross-process file locking), dipertahankan utuh
untuk transisi & rollback.

Perbedaan sengaja vs versi lama:
- get_all_students_progress TIDAK lagi menyertakan kolom 'token' mentah
  (kontrak keamanan: report/export tidak boleh membocorkan credential).
"""

import csv
import fcntl
import hashlib
import logging
import os
import threading
from typing import Dict, List, Tuple

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
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                reader = csv.DictReader(f, delimiter=';')
                fieldnames = reader.fieldnames or []
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
            new_tokens, new_fieldnames = _load_tokens_safely()
            if new_tokens:
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
    return next(iter(tokens.keys()))


def is_teacher_token(token):
    return token == get_teacher_token()


def validate_token(token):
    if not token:
        return None
    tokens, _ = _get_tokens()
    row = tokens.get(token)
    if row:
        return {
            'student_name': row['nama_siswa'],
            'is_teacher': is_teacher_token(token),
        }
    return None


def get_student_progress(token):
    if not token:
        return None
    tokens, _ = _get_tokens()
    return tokens.get(token)


def update_student_progress(token, lesson_name, status="completed"):
    """Update progress dengan cross-process locking (read-modify-write atomik)."""
    if not os.path.exists(TOKENS_FILE):
        logging.warning(f"Tokens file {TOKENS_FILE} does not exist")
        return False

    try:
        with open(TOKENS_FILE, 'r+', newline='', encoding='utf-8') as f:
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
                        else:
                            logging.warning(f"Lesson '{lesson_name}' not found in CSV columns")
                        break

                if updated:
                    f.seek(0)
                    f.truncate()
                    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
                    writer.writeheader()
                    writer.writerows(rows)
                    f.flush()
                    os.fsync(f.fileno())
                    return True
                return False
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        logging.error(f"Error updating student progress: {e}")
        return False


def _student_id(token: str) -> str:
    """Id anonim per siswa (sha256 token) — stabil & tidak bisa dibalik jadi token."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def reset_progress(student_id, lesson_name):
    """Reset via id anonim (digest) — teacher tidak perlu memegang token siswa."""
    tokens, _ = _get_tokens()
    for token, _row in tokens.items():
        if _student_id(token) == student_id:
            return update_student_progress(token, lesson_name, 'not_started')
    return False


def initialize_tokens_file(lesson_names):
    """Initialize the tokens CSV file with headers and lesson columns."""
    if not os.path.exists(TOKENS_FILE):
        headers = ['token', 'nama_siswa'] + lesson_names
        try:
            with open(TOKENS_FILE, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile, delimiter=';')
                writer.writerow(headers)
            print(f"Created new tokens file: {TOKENS_FILE} with headers: {headers}")
        except Exception as e:
            logging.error(f"Error initializing tokens file: {e}")


def get_all_students_progress(all_lessons_func):
    """Semua progress siswa untuk laporan — TANPA kolom token mentah."""
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
        student_data_copy.pop('token', None)  # keamanan: jangan bocorkan token mentah
        student_data_copy['id'] = _student_id(row.get('token', ''))
        student_data_copy['completed_count'] = calculate_student_completion(
            student_data_copy, ordered_lessons
        )
        all_students_progress.append(student_data_copy)

    return all_students_progress, ordered_lessons


def calculate_student_completion(student_data, all_lessons):
    """Jumlah lesson selesai (status bukan '' / not_started, termasuk skor '3/4')."""
    from services.storage.completion import calculate_student_completion as _calc

    return _calc(student_data, all_lessons)
