"""Compiler worker — hybrid endpoint server.

Keeps the legacy /execute batch endpoint AND adds interactive PTY session
endpoints powered by SessionManager.
"""
import os
import re
import signal
import subprocess
import tempfile
import uuid
from flask import Flask, jsonify, request
from session_manager import (
    SessionManager,
    SessionCapacityError,
    SessionNotFoundError,
    SessionNotRunningError,
    SessionValidationError,
)

# ------------------------------------------------------------------
# Legacy batch endpoints (backward compatible)
# ------------------------------------------------------------------

def _kill_proc_group(proc):
    """Terminate a process group: SIGTERM → sleep → SIGKILL."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, OSError):
        try:
            proc.terminate()
        except Exception:
            pass
    try:
        proc.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            try:
                proc.kill()
            except Exception:
                pass
        try:
            proc.wait(timeout=1.0)
        except Exception:
            pass


def run_c_code(code, stdin="", timeout=5):
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = os.path.join(tmpdir, "program.c")
        exe_path = os.path.join(tmpdir, "program")

        with open(source_path, "w") as f:
            f.write(code)

        # Compile
        try:
            compile_res = subprocess.run(
                ["gcc", source_path, "-o", exe_path],
                capture_output=True, text=True, timeout=10,
            )
            if compile_res.returncode != 0:
                return {
                    "success": False,
                    "output": compile_res.stdout,
                    "error": compile_res.stderr,
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": "Compilation timed out",
            }

        # Run
        try:
            run_res = subprocess.run(
                [exe_path],
                input=stdin,
                capture_output=True, text=True, timeout=timeout,
            )
            return {
                "success": True,
                "output": run_res.stdout,
                "error": run_res.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": "Program execution timed out",
            }
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}


def run_python_code(code, stdin="", timeout=5):
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
        tmp.write(code.encode("utf-8"))
        tmp_path = tmp.name

    try:
        run_res = subprocess.run(
            ["python3", tmp_path],
            input=stdin,
            capture_output=True, text=True, timeout=timeout,
        )
        return {
            "success": True,
            "output": run_res.stdout,
            "error": run_res.stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": "Program execution timed out",
        }
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ------------------------------------------------------------------
# App factory + session manager singleton
# ------------------------------------------------------------------

_session_mgr = None
_app = None


def get_session_mgr():
    global _session_mgr
    if _session_mgr is None:
        _session_mgr = SessionManager()
    return _session_mgr


def create_app():
    """Create the Flask application with both legacy and session routes."""
    app = Flask(__name__)
    register_routes(app)
    return app


def register_routes(app):
    @app.route("/health", methods=["GET"])
    def health():
        try:
            stats = get_session_mgr().stats()
            return jsonify(stats)
        except Exception as e:
            return jsonify({"error": str(e), "status": "degraded"}), 500

    @app.route("/execute", methods=["POST"])
    def execute():
        data = request.json
        code = data.get("code", "")
        language = data.get("language", "").lower()
        stdin_input = data.get("stdin", "") or ""

        if language == "c":
            return jsonify(run_c_code(code, stdin_input))
        elif language == "python":
            return jsonify(run_python_code(code, stdin_input))
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "output": "",
                        "error": f"Unsupported language: {language}",
                    }
                ),
                400,
            )

    # ------------------------------------------------------------------
    # Interactive session endpoints (Tasks 4)
    # ------------------------------------------------------------------

    _SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{20,}$")

    def _parse_session_id(sid_str):
        """Validate and return opaque session ID string, or None."""
        if sid_str and _SESSION_ID_RE.match(sid_str):
            return sid_str
        return None

    @app.route("/sessions", methods=["POST"])
    def create_session():
        mgr = get_session_mgr()
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"success": False, "error": "invalid JSON body"}), 400

        language = body.get("language", "").lower()
        files = body.get("files", [])
        active_file = body.get("active_file")
        stdin_input = body.get("stdin", "") or ""

        try:
            session = mgr.create(language, files, active_file, stdin_input)
            result = mgr.get_delta(session.session_id, cursor=0)
            return jsonify(result), 202
        except SessionCapacityError as e:
            return jsonify({"success": False, "error": str(e)}), 429
        except SessionValidationError as e:
            return jsonify({"success": False, "error": str(e)}), 400
        except Exception as e:  # noqa: BLE001
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/sessions/<session_id>", methods=["GET"])
    def get_session(session_id):
        """Get delta output from a session using optional cursor query param."""
        mgr = get_session_mgr()
        try:
            cursor_param = request.args.get("cursor", "0")
            cursor = max(0, int(cursor_param))
        except (TypeError, ValueError):
            cursor = 0
        try:
            result = mgr.get_delta(session_id, cursor=cursor)
            return jsonify(result)
        except SessionNotFoundError as e:
            return jsonify({"success": False, "error": str(e)}), 404
        except Exception as e:  # noqa: BLE001
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/sessions/<session_id>/input", methods=["POST"])
    def send_session_input(session_id):
        mgr = get_session_mgr()
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"success": False, "error": "invalid JSON body"}), 400

        text = body.get("text", "")
        if not isinstance(text, str):
            return jsonify({"success": False, "error": "input must be a string"}), 400

        try:
            mgr.write_input(session_id, text)
            # Return latest status after writing input
            result = mgr.get_delta(session_id, cursor=0)
            return jsonify(result)
        except SessionNotFoundError as e:
            return jsonify({"success": False, "error": str(e)}), 404
        except SessionNotRunningError as e:
            return jsonify({"success": False, "error": str(e)}), 409
        except Exception as e:  # noqa: BLE001
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/sessions/<session_id>", methods=["DELETE"])
    def stop_session(session_id):
        mgr = get_session_mgr()
        try:
            summary = mgr.stop(session_id)
            result = mgr.get_delta(session_id, cursor=0)
            return jsonify(result)
        except SessionNotFoundError as e:
            return jsonify({"success": False, "error": str(e)}), 404
        except Exception as e:  # noqa: BLE001
            return jsonify({"success": False, "error": str(e)}), 500


# Module-level app reference used by gunicorn
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
