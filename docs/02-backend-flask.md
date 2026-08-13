# 02. Backend (Flask API)

The backend is built with Flask, providing API endpoints for the SvelteKit frontend to fetch lessons, track progress, manage authentication, and proxy compilation requests.

## Application Factory (`elemes/app.py`)

- `def create_app():`
  Initializes the Flask application, loads configuration from `elemes/config.py` (which reads from `.env`), and registers the following blueprints:
  - `auth_bp` (`routes/auth.py`)
  - `lessons_bp` (`routes/lessons.py`)
  - `compile_bp` (`routes/compile.py`)
  - `progress_bp` (`routes/progress.py`)

## Core API Routes

### Authentication (`routes/auth.py`)
- `def login():` (POST `/login`)
  Receives `token` in JSON payload. Validates via `token_service.validate_token()`. On success, sets the `student_token` cookie. Rate-limited and includes a 1.5s tarpit for failures.
- `def logout():` (POST `/logout`)
  Clears the `student_token` cookie.
- `def validate_token_route():` (POST `/validate-token`)
  Checks if the current `student_token` cookie is valid.

### Lessons (`routes/lessons.py`)
- `def api_lessons():` (GET `/lessons`)
  Returns a list of all lessons and the rendered `home.md` content via `lesson_service.get_ordered_lessons_with_learning_objectives()`.
- `def api_bab(folder):` (GET `/bab/<folder>`)
  Returns parsed `sub-home.md` data for a folder (title, intro HTML, lesson list) via `lesson_service.get_sub_home_data()`. Returns 404 when the folder has no `sub-home.md`.
- `def api_lesson(filename):` (GET `/lesson/<slug>.json`)
  Returns the fully parsed lesson data (content, initial code, circuits, key texts, active tabs) via `lesson_service.render_markdown_content(filepath)`. When the lesson lives in a folder that has a `sub-home.md`, `ordered_lessons` (sidebar) and prev/next navigation are scoped to that folder's lesson list; otherwise it falls back to the global `home.md` list.
- `def get_key_text(filename):` (GET `/get-key-text/<slug>`)
  Returns only the required keywords for a specific lesson without exposing the full content logic.

### Compilation (`routes/compile.py`)
- `def compile_code():` (POST `/compile`)
  Accepts `code` and `language`. Routes execution to the sandboxed worker using the `CompilerFactory`. Incorporates rate-limiting for anonymous users.
- `def velxio_compile():` (POST `/velxio-compile` mapped from `/velxio/api/compile`)
  A proxy endpoint that forwards Arduino compilation requests to the Velxio container, enforcing rate limits for anonymous users.

### Progress Tracking (`routes/progress.py`)
- `def track_progress():` (POST `/track-progress`)
  Accepts `lesson_name` and `status`. Persists progress to PostgreSQL via `token_service.update_student_progress()`.
- `def api_progress_report():` (GET `/progress-report.json`)
  Returns a matrix of all student progress. Requires a teacher token.
- `def export_progress_csv():` (GET `/progress-report/export-csv`)
  Exports progress data as a CSV download. Requires a teacher token.

## Services

### Token Service (`services/token_service.py`)
Facade over the single active storage backend — PostgreSQL, via
`services/storage/postgres_backend.py`. The legacy CSV backend and its helpers
(`initialize_tokens_file`, `_load_tokens_safely`) have been **removed**.
- `def validate_token(token):` Returns `{'student_name', 'is_teacher'}` or `None` for a valid token.
- `def is_teacher_token(token):` Returns `True` if the token belongs to the teacher account.
- `def get_student_progress(token):` Returns a dictionary of lesson progress for a specific token.
- `def update_student_progress(token, lesson_name, status="completed"):` Persists progress to PostgreSQL.
- `def get_teacher_token():` Returns the active teacher token (implemented in `postgres_backend`).
- `def reset_student_progress(student_id, lesson_name):` Resets progress by anonymous `student_id` (never the raw token).

Student tokens are stored **only as an HMAC-SHA256 digest** in the
`access_tokens` table (peppered with `TOKEN_PEPPER` from `.env`) — raw tokens
are never persisted and cannot be recovered or exported.

### Lesson Service (`services/lesson_service.py`)
Parses Markdown files to extract content and configuration.
- `def get_lessons(source_path=None):` Returns lessons listed in the `Available_Lessons` section of `home.md` (or of `source_path` when given, e.g. a `sub-home.md`).
- `def get_ordered_lessons_with_learning_objectives(progress=None, source_path=None):` Returns lessons ordered as they appear in `home.md` (or `source_path`), optionally injected with user progress status.
- `def find_sub_home_for_lesson(file_path):` Returns `(sub_home_path, folder_name)` when the lesson's folder (one level inside `content/`) has a `sub-home.md`, else `(None, None)`.
- `def get_sub_home_data(folder_name):` Parses a folder's `sub-home.md` (title, intro HTML, lesson list) with an mtime-based cache so edits to the file are picked up without restart.
- `def render_markdown_content(file_path):` The core parsing function. Uses regex to extract markers like `---INITIAL_CODE---`, `---VELXIO_CIRCUIT---`, etc. It identifies the `active_tabs` needed for the frontend.
- `def _parse_flashcards(text):` Specifically parses `---QUIZ_FLASHCARD---` blocks into a structured JSON array for the frontend MCQ/Flashcard component.

See `docs/13-content-sub-home.md` for the author-facing guide on writing `sub-home.md`.

## Compiler Framework (`compiler/`)

The compilation logic is abstracted via a factory pattern.

- `class CompilerFactory:` (`compiler/__init__.py`)
  - `def get_compiler(self, language):` Returns the appropriate `BaseCompiler` instance (e.g., `CCompiler` or `PythonCompiler`).
- `class BaseCompiler(ABC):` (`compiler/base_compiler.py`)
  - `def compile(self, code, timeout=10):` Abstract method.
  - `def run(self, file_path, timeout=5):` Abstract method.
- `class CCompiler(BaseCompiler):` and `class PythonCompiler(BaseCompiler):`
  Implementation wrappers that construct payloads and send HTTP requests to the `compiler-worker` container (`http://compiler-worker:8080/execute`).
