"""
Dokumentasi teknis dan API reference — Docs Viewer endpoints.

Endpoints:
    GET /api/docs            → index semua dokumen (terurut)
    GET /api/docs/<slug>     → rendered HTML + metadata satu dokumen
    GET /api/docs/api-reference → API reference yang mengekstrak docstring route
"""

import re

from flask import Blueprint, current_app, jsonify

from services.docs_service import get_docs_index, get_doc_content

docs_bp = Blueprint("docs_api", __name__)


@docs_bp.route("/docs")
def api_docs_index():
    """List all docs files with metadata, sorted by order."""
    docs = get_docs_index()
    return jsonify({"docs": docs})


@docs_bp.route("/docs/<slug>")
def api_doc_detail(slug):
    """Return rendered HTML + metadata for a single doc by slug."""
    data = get_doc_content(slug)
    if data is None:
        return jsonify({"error": "Dokumen tidak ditemukan"}), 404
    return jsonify(data)


@docs_bp.route("/docs/api-reference")
def api_reference():
    """Generate API reference from route docstrings.

    Scans all registered Flask routes, extracts docstrings, and formats
    them as structured API reference entries.

    Each entry: {method, path, name, auth, doc}

    Uses ``current_app`` (bukan ``create_app()``) agar tidak membuat instance
    app baru / memicu DB sync ulang pada setiap request.
    """
    entries = []

    # Known auth requirements per route (derived from code inspection)
    auth_map = {
        "/login": False,
        "/validate-token": False,
        "/track-progress": False,  # token-based, not session auth
        "/progress-report.json": True,
        "/reset-progress": True,
        "/compile": False,  # token optional (anon allowed)
        "/compile/sessions": False,
        "/compile/sessions/<session_id>": False,
        "/compile/sessions/<session_id>/input": False,
        "/compile/sessions/<session_id>": False,
        "/velxio-compile": False,
        "/quiz-attempts/submit": False,
        "/quiz-attempts/<lesson_name>": False,
        "/students/export-csv": True,
        "/students/import/preview": True,
        "/students/import": True,
        "/students/bulk-delete": True,
        "/api/docs": False,
        "/api/docs/<slug>": False,
        "/api/docs/api-reference": False,
        "/bab/<folder>": False,
        "/lessons": False,
        "/lesson/<path:filename>": False,
        "/get-key-text/<filename>": False,
        "/assets/<path:path>": False,
        "/help": False,
        "/help/asset/<path:filename>": False,
    }

    # Extract from Flask view functions directly
    seen = set()
    for rule in current_app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        path = rule.rule
        if path in seen:
            continue
        seen.add(path)

        methods = sorted(rule.methods - {"HEAD", "OPTIONS"})

        # Try to get the view function's docstring
        view_func = current_app.view_functions.get(rule.endpoint)
        doc = ""
        if view_func:
            doc = (view_func.__doc__ or "").strip()

        auth_req = auth_map.get(path, False)

        entries.append({
            "method": methods,
            "path": path,
            "name": rule.endpoint,
            "auth": auth_req,
            "doc": doc,
        })

    # Sort: methods order then path
    entries.sort(key=lambda e: (e["method"][0] if e["method"] else "", e["path"]))

    return jsonify({"endpoints": entries})
