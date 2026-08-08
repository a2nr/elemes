"""Helper murni bersama — perhitungan jumlah lesson selesai.

Kontrak: status yang dihitung "selesai" = bukan '' dan bukan 'not_started'
(termasuk skor legacy '3/4'). Dipakai kedua storage backend agar tidak divergen.
"""


def calculate_student_completion(student_data, all_lessons) -> int:
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
