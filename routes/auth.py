"""
Authentication routes: login, logout, validate-token.
"""

import os
import time
from flask import Blueprint, request, jsonify

from extensions import limiter
from services.token_service import validate_token

auth_bp = Blueprint('auth', __name__)

# Security Configuration
COOKIE_SECURE = os.environ.get('COOKIE_SECURE', 'false').lower() == 'true'



@auth_bp.route('/login', methods=['POST'])
@limiter.limit("50 per minute")
def login():
    """Handle student login with token."""
    try:
        data = request.get_json(silent=True, force=True) or {}
        token = (data.get('token') or '').strip()

        if not token:
            return jsonify({'success': False, 'message': 'Token is required'})

        student_info = validate_token(token)
        if student_info:
            response = jsonify({
                'success': True,
                'student_name': student_info['student_name'],
                'is_teacher': student_info.get('is_teacher', False),
                'message': 'Login successful',
            })
            response.set_cookie(
                'student_token', token,
                httponly=True, secure=COOKIE_SECURE, samesite='Lax', max_age=86400,
            )
            return response
        else:
            return jsonify({'success': False, 'message': 'Invalid token'})

    except Exception as e:
        return jsonify({'success': False, 'message': 'Error processing login'})


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Handle student logout."""
    try:
        response = jsonify({'success': True, 'message': 'Logout successful'})
        response.set_cookie('student_token', '', expires=0)
        return response
    except Exception as e:
        return jsonify({'success': False, 'message': 'Error processing logout'})


@auth_bp.route('/validate-token', methods=['POST'])
def validate_token_route():
    """Validate a token without logging in."""
    try:
        data = request.get_json(silent=True, force=True) or {}
        token = (data.get('token') or '').strip()

        if not token:
            token = (request.cookies.get('student_token') or '').strip()

        if not token:
            return jsonify({'success': False, 'message': 'Token is required'})

        student_info = validate_token(token)
        if student_info:
            return jsonify({
                'success': True,
                'student_name': student_info['student_name'],
                'is_teacher': student_info.get('is_teacher', False),
            })
        else:
            return jsonify({'success': False, 'message': 'Invalid token'})

    except Exception as e:
        return jsonify({'success': False, 'message': 'Error validating token'})
