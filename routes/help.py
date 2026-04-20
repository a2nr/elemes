import os
import markdown as md
from flask import Blueprint, jsonify, send_from_directory
from services.lesson_service import MD_EXTENSIONS

help_bp = Blueprint('help_api', __name__)

HELP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'help')

@help_bp.route('/help')
def get_help_content():
    file_path = os.path.join(HELP_DIR, 'TUTORIAL_SISWA.md')
    if not os.path.exists(file_path):
        return jsonify({'error': 'Help content not found'}), 404
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Render markdown to HTML
    html_content = md.markdown(content, extensions=MD_EXTENSIONS)
    
    return jsonify({
        'title': 'Panduan Penggunaan',
        'content': html_content
    })

@help_bp.route('/help/asset/<path:filename>')
def serve_help_asset(filename):
    return send_from_directory(os.path.join(HELP_DIR, 'asset'), filename)
