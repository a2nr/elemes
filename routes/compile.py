"""
Code compilation route.
"""

import os
import time
import uuid
import requests
from flask import Blueprint, request, jsonify
from flask_limiter import RateLimitExceeded

from services.token_service import validate_token
from extensions import limiter

compile_bp = Blueprint('compile', __name__)

COMPILER_WORKER_URL = os.environ.get('COMPILER_WORKER_URL', 'http://127.0.0.1:8080/execute')
VELXIO_COMPILER_URL = os.environ.get('VELXIO_COMPILER_URL', 'http://127.0.0.1:80/api/compile/')
ANON_QUEUE_DIR = "/tmp/elemes_anon_queue"

# Ensure queue directory exists
os.makedirs(ANON_QUEUE_DIR, exist_ok=True)

def is_logged_in():
    """Check if the request has a valid student token (JSON, Form, or Cookie)."""
    token = None
    if request.is_json:
        try:
            token = request.get_json(force=True).get('token', '')
        except Exception:
            pass
    if not token:
        token = request.form.get('token', '')
    if not token:
        token = request.cookies.get('student_token', '')
    
    token = str(token).strip()
    return bool(token and validate_token(token))

def acquire_anon_slot():
    """Try to acquire a slot in the anonymous compilation queue."""
    try:
        # Cleanup stale files (> 60s)
        now = time.time()
        for f in os.listdir(ANON_QUEUE_DIR):
            fpath = os.path.join(ANON_QUEUE_DIR, f)
            try:
                if now - os.path.getmtime(fpath) > 60:
                    os.remove(fpath)
            except (OSError, IOError):
                pass
        
        # Check capacity
        if len(os.listdir(ANON_QUEUE_DIR)) >= 20:
            return None
        
        slot_id = str(uuid.uuid4())
        fpath = os.path.join(ANON_QUEUE_DIR, slot_id)
        with open(fpath, 'w') as f:
            f.write(str(now))
        return fpath
    except Exception:
        return None

def release_anon_slot(fpath):
    """Release an acquired anonymous slot."""
    if fpath and os.path.exists(fpath):
        try:
            os.remove(fpath)
        except (OSError, IOError):
            pass

@compile_bp.errorhandler(RateLimitExceeded)
def handle_rate_limit_exceeded(e):
    """Handle rate limit errors with a custom message."""
    return jsonify({
        'success': False, 
        'output': '', 
        'error': 'tunggu beberapa saat untuk kompilasi kembali, atau lakukan request token ke guru'
    }), 429

@compile_bp.route('/compile', methods=['POST'])
@limiter.limit("1 per 2 minutes", exempt_when=is_logged_in)
def compile_code():
    """Forward code compilation to the worker service."""
    try:
        code = None
        language = None
        token = None
        stdin = ""

        if request.content_type and 'application/json' in request.content_type:
            try:
                json_data = request.get_json(force=True)
                if json_data:
                    code = json_data.get('code', '')
                    language = json_data.get('language', '')
                    token = json_data.get('token', '').strip()
                    stdin = json_data.get('stdin', '') or ''
            except Exception:
                pass

        if not code:
            code = request.form.get('code', '')
            language = request.form.get('language', '')
            token = request.form.get('token', '').strip()
            stdin = request.form.get('stdin', '') or ''

        # Authorization logic:
        # 1. If token is provided, it MUST be valid.
        # 2. If no token, it is anonymous access (subject to rate limits & queue).
        user_is_logged_in = False
        if token:
            if not validate_token(token):
                return jsonify({'success': False, 'output': '', 'error': 'Unauthorized: Invalid token'})
            user_is_logged_in = True

        # Queue logic for anonymous users
        slot_fpath = None
        if not user_is_logged_in:
            slot_fpath = acquire_anon_slot()
            if not slot_fpath:
                return jsonify({
                    'success': False, 
                    'output': '', 
                    'error': 'tunggu beberapa saat untuk kompilasi kembali, atau lakukan request token ke guru'
                })

        try:
            if not code:
                return jsonify({'success': False, 'output': '', 'error': 'No code provided'})

            # Forward to worker
            response = requests.post(
                COMPILER_WORKER_URL,
                json={'code': code, 'language': language, 'stdin': stdin},
                timeout=15
            )
            return jsonify(response.json())
        finally:
            if slot_fpath:
                release_anon_slot(slot_fpath)

    except requests.exceptions.RequestException as re:
        return jsonify({'success': False, 'output': '', 'error': f'Compiler service unavailable: {re}'})
    except Exception as e:
        return jsonify({'success': False, 'output': '', 'error': f'An error occurred: {e}'})

def _hex_to_binary(hex_content):
    """Parse Intel HEX string into raw binary bytes."""
    binary = bytearray()
    for line in hex_content.strip().split('\n'):
        line = line.strip()
        if not line or not line.startswith(':'):
            continue
        byte_count = int(line[1:3], 16)
        record_type = int(line[7:9], 16)
        if record_type == 0:  # Data record
            data = bytes.fromhex(line[9:9 + byte_count * 2])
            binary.extend(data)
        elif record_type == 1:  # EOF
            break
    return bytes(binary)

@compile_bp.route('/velxio-compile', methods=['POST'])
@compile_bp.route('/velxio-compile/', methods=['POST'])
@limiter.limit("1 per 2 minutes", exempt_when=is_logged_in)
def velxio_compile():
    """Proxy Velxio compilation requests to the Velxio service."""
    slot_fpath = None
    try:
        # Check authorization from cookie if not in JSON
        token = request.cookies.get('student_token')
        user_is_logged_in = bool(token and validate_token(token))

        if not user_is_logged_in:
            slot_fpath = acquire_anon_slot()
            if not slot_fpath:
                return jsonify({
                    'success': False, 
                    'output': '', 
                    'error': 'tunggu beberapa saat untuk kompilasi kembali, atau lakukan request token ke guru'
                })

        # Forward the request to Velxio
        response = requests.post(
            VELXIO_COMPILER_URL,
            json=request.get_json(silent=True) or {},
            timeout=30
        )
        result = response.json()
        # If Velxio only returned hex_content (AVR/Arduino), convert to binary
        if result.get('success') and result.get('hex_content') and not result.get('binary_content'):
            try:
                binary = _hex_to_binary(result['hex_content'])
                import base64
                result['binary_content'] = base64.b64encode(binary).decode('ascii')
                result['binary_type'] = 'bin'
            except Exception as e:
                # Non-fatal: hex_content still available for BLE path
                print(f'hex_to_binary conversion failed: {e}')
        return jsonify(result)

    except requests.exceptions.RequestException as re:
        return jsonify({'success': False, 'output': '', 'error': f'Velxio service unavailable: {re}'})
    except Exception as e:
        return jsonify({'success': False, 'output': '', 'error': f'An error occurred: {e}'})
    finally:
        if slot_fpath:
            release_anon_slot(slot_fpath)
