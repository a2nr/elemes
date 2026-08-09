#!/usr/bin/env python3
"""
C Programming Learning Management System
Application factory — assembles blueprints and startup tasks.
Flask serves as a JSON API consumed by the SvelteKit frontend.
"""

import logging

from flask import Flask
from flask_cors import CORS

from extensions import limiter
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
    import os
    allowed_origin = os.environ.get('ORIGIN', '*')
    CORS(app, resources={r"/*": {"origins": allowed_origin}})

    # Initialize extensions
    limiter.init_app(app)

    # ── Blueprints ────────────────────────────────────────────────────
    from routes.auth import auth_bp
    from routes.compile import compile_bp
    from routes.lessons import lessons_bp
    from routes.progress import progress_bp
    from routes.help import help_bp
    from routes.student_management import student_management_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(compile_bp)
    app.register_blueprint(lessons_bp)
    app.register_blueprint(progress_bp)
    app.register_blueprint(help_bp)
    app.register_blueprint(student_management_bp)

    # ── Startup tasks ─────────────────────────────────────────────────
    initialize_tokens_file(get_lesson_names())
    # Sync metadata lesson ke PostgreSQL (auto-skip bila DB belum aktif).
    # Idempotent; kegagalan hanya di-log — tidak mematikan app.
    from services.lesson_registry import maybe_sync_on_startup

    maybe_sync_on_startup()

    return app


# Gunicorn entry: gunicorn "app:create_app()"
# Dev entry: python app.py
if __name__ == '__main__':
    import os
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    application = create_app()
    application.run(host='0.0.0.0', port=5000, debug=debug_mode)
