"""
Student progress tracking and reporting JSON API routes.
"""

import csv
import io
import logging

from flask import Blueprint, request, jsonify, Response

from services.token_service import (
    validate_token,
    update_student_progress,
    get_all_students_progress,
)
from services.lesson_service import get_lessons_with_learning_objectives

progress_bp = Blueprint('progress', __name__)


@progress_bp.route('/track-progress', methods=['POST'])
def track_progress():
    """Track student progress for a lesson."""
    try:
        data = request.get_json()
        token = data.get('token', '').strip()
        lesson_name = data.get('lesson_name', '').strip()
        status = data.get('status', 'completed').strip()

        logging.info(f"Received track-progress request: token={token}, lesson_name={lesson_name}, status={status}")

        if not token or not lesson_name:
            return jsonify({'success': False, 'message': 'Token and lesson name are required'})

        student_info = validate_token(token)
        if not student_info:
            return jsonify({'success': False, 'message': 'Invalid token'})

        updated = update_student_progress(token, lesson_name, status)
        if updated:
            logging.info(f"Progress updated successfully for token {token}, lesson {lesson_name}")
            return jsonify({'success': True, 'message': 'Progress updated successfully'})
        else:
            logging.warning(f"Failed to update progress for token {token}, lesson {lesson_name}")
            return jsonify({'success': False, 'message': 'Failed to update progress'})

    except Exception as e:
        logging.error(f"Error in track-progress: {e}")
        return jsonify({'success': False, 'message': f'Error tracking progress: {e}'})


@progress_bp.route('/reset-progress', methods=['POST'])
def reset_progress():
    """Reset student progress for a lesson (Teacher only)."""
    try:
        data = request.get_json()
        teacher_token = data.get('teacher_token', '').strip()
        student_token = data.get('student_token', '').strip()
        lesson_name = data.get('lesson_name', '').strip()

        if not teacher_token or not student_token or not lesson_name:
            return jsonify({'success': False, 'message': 'All fields are required'}), 400

        # Validate teacher token
        teacher_info = validate_token(teacher_token)
        if not teacher_info or not teacher_info.get('is_teacher'):
            return jsonify({'success': False, 'message': 'Unauthorized (Teacher only)'}), 401

        # Perform reset (set to not_started)
        updated = update_student_progress(student_token, lesson_name, 'not_started')
        if updated:
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

    return jsonify({
        'students': all_students_progress,
        'lessons': [{'filename': l['filename'], 'title': l['title']} for l in ordered_lessons],
    })


@progress_bp.route('/progress-report/export-csv')
def export_progress_csv():
    """Export the progress report as CSV."""
    token = request.args.get('token', '').strip()
    if not token:
        token = request.cookies.get('student_token', '').strip()

    if not token:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    student_info = validate_token(token)
    if not student_info or not student_info.get('is_teacher'):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    all_students_progress, _ordered_lessons = get_all_students_progress(
        get_lessons_with_learning_objectives,
    )

    output = io.StringIO()
    if all_students_progress:
        fieldnames = list(all_students_progress[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(all_students_progress)

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment; filename=progress_report.csv"},
    )
