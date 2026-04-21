"""
Code compilation route.
"""

import os
import requests
from flask import Blueprint, request, jsonify

from services.token_service import validate_token

compile_bp = Blueprint('compile', __name__)

COMPILER_WORKER_URL = os.environ.get('COMPILER_WORKER_URL', 'http://compiler-worker:8080/execute')

@compile_bp.route('/compile', methods=['POST'])
def compile_code():
    """Forward code compilation to the worker service."""
    try:
        code = None
        language = None
        token = None

        if request.content_type and 'application/json' in request.content_type:
            try:
                json_data = request.get_json(force=True)
                if json_data:
                    code = json_data.get('code', '')
                    language = json_data.get('language', '')
                    token = json_data.get('token', '')
            except Exception:
                pass

        if not code:
            code = request.form.get('code', '')
            language = request.form.get('language', '')
            token = request.form.get('token', '')

        if not token or not validate_token(token):
            return jsonify({'success': False, 'output': '', 'error': 'Unauthorized: Valid token required'})

        if not code:
            return jsonify({'success': False, 'output': '', 'error': 'No code provided'})

        # Forward to worker
        response = requests.post(
            COMPILER_WORKER_URL,
            json={'code': code, 'language': language},
            timeout=15
        )
        return jsonify(response.json())

    except requests.exceptions.RequestException as re:
        return jsonify({'success': False, 'output': '', 'error': f'Compiler service unavailable: {re}'})
    except Exception as e:
        return jsonify({'success': False, 'output': '', 'error': f'An error occurred: {e}'})
