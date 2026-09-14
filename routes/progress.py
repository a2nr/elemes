"""
Student progress tracking and reporting JSON API routes.
"""

import csv
import io
import logging

from flask import Blueprint, request, jsonify, Response

from services.token_service import (
    validate_token,
    reset_student_progress,
    get_all_students_progress,
)
from services.lesson_service import (
    get_lessons_with_learning_objectives,
    find_lesson_file,
    find_sub_home_for_lesson,
    get_sub_home_data,
    find_all_sub_home_folders,
)

progress_bp = Blueprint('progress', __name__)


def _masked(token: str) -> str:
    """Awalan token untuk log — jangan pernah log token mentah."""
    return f"{token[:6]}..." if token else "(kosong)"


@progress_bp.route('/reset-progress', methods=['POST'])
def reset_progress():
    """Reset progress siswa via student_id (Teacher only).

    Kontrak keamanan: teacher TIDAK perlu (dan tidak boleh) memegang token
    siswa — cukup id anonim dari payload report.
    """
    try:
        data = request.get_json()
        teacher_token = data.get('teacher_token', '').strip()
        student_id = data.get('student_id', '').strip()
        lesson_name = data.get('lesson_name', '').strip()

        if not teacher_token or not student_id or not lesson_name:
            return jsonify({'success': False, 'message': 'All fields are required'}), 400

        # Validasi teacher token
        teacher_info = validate_token(teacher_token)
        if not teacher_info or not teacher_info.get('is_teacher'):
            return jsonify({'success': False, 'message': 'Unauthorized (Teacher only)'}), 401

        # Perform reset (set to not_started)
        updated = reset_student_progress(student_id, lesson_name)
        if updated:
            logging.info(
                "Progress reset oleh teacher=%s untuk student_id=%s, lesson=%s",
                teacher_info.get('student_name'), _masked(student_id), lesson_name,
            )
            return jsonify({'success': True, 'message': 'Progress reset successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to reset progress'})

    except Exception as e:
        logging.error(f"Error in reset-progress: {e}")
        return jsonify({'success': False, 'message': f'Error resetting progress: {e}'})


@progress_bp.route('/progress-report.json')
def api_progress_report():
    """Return progress report data as JSON."""
    token = request.args.get('token', '').strip()
    if not token:
        token = request.cookies.get('student_token', '').strip()

    if not token:
        logging.warning("Unauthorized access attempt to progress-report.json: No token provided")
        return jsonify({'success': False, 'message': 'Unauthorized: Token is required'}), 401

    student_info = validate_token(token)
    if not student_info:
        logging.warning(f"Unauthorized access attempt to progress-report.json: Invalid token '{token[:6]}...'")
        return jsonify({'success': False, 'message': 'Unauthorized: Invalid token'}), 401

    # Security: Only teacher can see the full progress report
    if not student_info.get('is_teacher'):
        logging.warning(f"Unauthorized access attempt to progress-report.json: Student '{student_info.get('student_name')}' is not a teacher")
        return jsonify({'success': False, 'message': 'Forbidden: Teacher access only'}), 403

    all_students_progress, ordered_lessons = get_all_students_progress(
        get_lessons_with_learning_objectives,
    )

    # Petakan sub-bab dari sub-home.md yang terdaftar
    sub_home_folders = find_all_sub_home_folders()
    sub_bab_map = {}
    for folder in sub_home_folders:
        data = get_sub_home_data(folder)
        if data and data.get('title'):
            sub_bab_map[folder] = data['title']

    def _lesson_to_dict(lesson):
        d = {'filename': lesson['filename'], 'title': lesson['title']}
        file_path = lesson.get('path') or find_lesson_file(lesson['filename'])
        if file_path:
            _sub_home_path, folder_name = find_sub_home_for_lesson(file_path)
            if folder_name and folder_name in sub_bab_map:
                d['sub_bab'] = folder_name
                d['sub_bab_title'] = sub_bab_map[folder_name]
        return d

    resp = jsonify({
        'students': all_students_progress,
        'lessons': [_lesson_to_dict(l) for l in ordered_lessons],
        'sub_bab_list': [
            {'folder': f, 'title': sub_bab_map[f]}
            for f in sub_home_folders if f in sub_bab_map
        ],
    })
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp


@progress_bp.route('/progress-report/export-csv')
def export_progress_csv():
    """Export the progress report as CSV with composite scores."""
    token = request.args.get('token', '').strip()
    if not token:
        token = request.cookies.get('student_token', '').strip()

    if not token:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    student_info = validate_token(token)
    if not student_info or not student_info.get('is_teacher'):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    all_students_progress, ordered_lessons = get_all_students_progress(
        get_lessons_with_learning_objectives,
    )

    lesson_slugs = [l['filename'].replace('.md', '') for l in ordered_lessons]
    fieldnames = ['nama_siswa'] + lesson_slugs + ['completed_count']

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=';')
    writer.writeheader()

    for student in all_students_progress:
        row = {'nama_siswa': student.get('nama_siswa', '')}
        for slug in lesson_slugs:
            composite_val = student.get(f"{slug}_composite")
            if composite_val is not None:
                row[slug] = composite_val
            else:
                legacy = student.get(slug, '')
                if legacy == 'completed':
                    row[slug] = 100
                else:
                    row[slug] = ""
        row['completed_count'] = student.get('completed_count', 0)
        writer.writerow(row)

    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={"Content-Disposition": "attachment; filename=progress_report.csv"},
    )

