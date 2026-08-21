"""Helper auth guru — dipakai lintas blueprint (student_management, content_editor)."""

import os
from flask import request

from services import repositories
from services.token_service import validate_token


def teacher_from_cookie():
    """Cek cepat is_teacher tanpa query user_id (dipakai student_management.py,
    yang endpoint-nya tidak butuh atribusi user_id)."""
    token = request.cookies.get("student_token", "")
    if not token:
        return None
    info = validate_token(token)
    if not info or not info.get("is_teacher"):
        return None
    return info


def teacher_user_from_cookie(db):
    """Resolve objek User (role='teacher') dari cookie, atau None.
    Dipakai endpoint yang butuh user_id sungguhan (mis. content_editor)."""
    token = request.cookies.get("student_token", "")
    if not token:
        return None
    user = repositories.get_user_by_token(db, token)
    if not user or user.role != "teacher":
        return None
    return user


def check_origin() -> bool:
    allowed = os.environ.get("ORIGIN", "").strip()
    if not allowed or allowed == "*":
        return True
    origin = request.headers.get("Origin", "")
    if not origin:
        return True
    return origin in {allowed, allowed.rstrip("/")}
