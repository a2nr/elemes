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


@progress_bp.route('/progress-report.json')
def api_progress_report():
    """Return progress report data as JSON."""
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
