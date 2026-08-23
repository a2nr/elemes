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
    """Known limitation: fail-open bila header Origin tidak ada.

    Request tanpa header Origin dianggap sah (return True). Ini pola lama yang
    sudah dipakai sebelum ini (student_management.py) dan bukan regresi.
    Risiko diflaskan oleh cookie student_token yang SameSite=Lax di routes/auth.py
    — browser modern tidak mengirim cookie ini pada request state-changing
    (POST/PATCH/DELETE) cross-site.

    Namun karena content_editor blueprint kini memiliki akses tulis/hapus langsung
    ke filesystem (bukan hanya baca data siswa), kebijakan fail-open ini menjadi
    lebih berisiko. Jika Origin header tidak ada, request dianggap berasal dari
    klien same-origin (seperti curl, internal service call, atau browser yang
    menyederhanakan header). Jika Origin ada, wajib match terhadap ORIGIN env.
    """
    allowed = os.environ.get("ORIGIN", "").strip()
    if not allowed or allowed == "*":
        return True
    origin = request.headers.get("Origin", "")
    if not origin:
        return True  # fail-open: rasa tidak adanya header Origin
    return origin in {allowed, allowed.rstrip("/")}
