#!/usr/bin/env python3
"""
C Programming Learning Management System
Application factory — assembles blueprints and startup tasks.
Flask serves as a JSON API consumed by the SvelteKit frontend.
"""

import logging

from flask import Flask
from flask_cors import CORS

from services.lesson_service import get_lesson_names
from services.token_service import initialize_tokens_file

# Configure logging once at module level
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)


def create_app():
    """Application factory."""
    app = Flask(__name__)

    # Allow cross-origin requests from the SvelteKit frontend
    CORS(app)

    # ── Blueprints ────────────────────────────────────────────────────
    from routes.auth import auth_bp
    from routes.compile import compile_bp
    from routes.lessons import lessons_bp
    from routes.progress import progress_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(compile_bp)
    app.register_blueprint(lessons_bp)
    app.register_blueprint(progress_bp)

    # ── Startup tasks ─────────────────────────────────────────────────
    initialize_tokens_file(get_lesson_names())

    return app


# Gunicorn entry: gunicorn "app:create_app()"
# Dev entry: python app.py
if __name__ == '__main__':
    import os
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    application = create_app()
    application.run(host='0.0.0.0', port=5000, debug=debug_mode)
