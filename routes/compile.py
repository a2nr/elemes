"""
Code compilation route.
"""

from flask import Blueprint, request, jsonify

from compiler import compiler_factory

compile_bp = Blueprint('compile', __name__)


@compile_bp.route('/compile', methods=['POST'])
def compile_code():
    """Compile and run code submitted by the user."""
    try:
        code = None
        language = None

        if request.content_type and 'application/json' in request.content_type:
            try:
                json_data = request.get_json(force=True)
                if json_data:
                    code = json_data.get('code', '')
                    language = json_data.get('language', '')
            except Exception:
                pass

        if not code:
            code = request.form.get('code', '')
            language = request.form.get('language', '')

        if not code:
            return jsonify({'success': False, 'output': '', 'error': 'No code provided'})

        compiler = compiler_factory.get_compiler(language)
        result = compiler.compile_and_run(code)
        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'output': '', 'error': f'An error occurred: {e}'})
