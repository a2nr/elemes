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
- `def api_lesson(filename):` (GET `/lesson/<slug>.json`)
  Returns the fully parsed lesson data (content, initial code, circuits, key texts, active tabs) via `lesson_service.render_markdown_content(filepath)`.
- `def get_key_text(filename):` (GET `/get-key-text/<slug>`)
  Returns only the required keywords for a specific lesson without exposing the full content logic.

### Compilation (`routes/compile.py`)
- `def compile_code():` (POST `/compile`)
  Accepts `code` and `language`. Routes execution to the sandboxed worker using the `CompilerFactory`. Incorporates rate-limiting for anonymous users.
- `def velxio_compile():` (POST `/velxio-compile` mapped from `/velxio/api/compile`)
  A proxy endpoint that forwards Arduino compilation requests to the Velxio container, enforcing rate limits for anonymous users.

### Progress Tracking (`routes/progress.py`)
- `def track_progress():` (POST `/track-progress`)
  Accepts `lesson_name` and `status`. Updates the CSV file via `token_service.update_student_progress()`.
- `def api_progress_report():` (GET `/progress-report.json`)
  Returns a matrix of all student progress. Requires a teacher token.
- `def export_progress_csv():` (GET `/progress-report/export-csv`)
  Exports progress data as a CSV download. Requires a teacher token.

## Services

### Token Service (`services/token_service.py`)
Manages reads and writes to the `tokens_siswa.csv` file.
- `def _load_tokens_safely() -> Tuple[Dict[str, dict], List[str]]:` Reads CSV data safely.
- `def validate_token(token):` Returns `True` if the token exists.
- `def is_teacher_token(token):` Returns `True` if the token belongs to the first row (the teacher).
- `def get_student_progress(token):` Returns a dictionary of lesson progress for a specific token.
- `def update_student_progress(token, lesson_name, status="completed"):` Writes progress back to the CSV.

### Lesson Service (`services/lesson_service.py`)
Parses Markdown files to extract content and configuration.
- `def get_ordered_lessons_with_learning_objectives(progress=None):` Returns lessons ordered as they appear in `home.md`, optionally injected with user progress status.
- `def render_markdown_content(file_path):` The core parsing function. Uses regex to extract markers like `---INITIAL_CODE---`, `---VELXIO_CIRCUIT---`, etc. It identifies the `active_tabs` needed for the frontend.
- `def _parse_flashcards(text):` Specifically parses `---QUIZ_FLASHCARD---` blocks into a structured JSON array for the frontend MCQ/Flashcard component.

## Compiler Framework (`compiler/`)

The compilation logic is abstracted via a factory pattern.

- `class CompilerFactory:` (`compiler/__init__.py`)
  - `def get_compiler(self, language):` Returns the appropriate `BaseCompiler` instance (e.g., `CCompiler` or `PythonCompiler`).
- `class BaseCompiler(ABC):` (`compiler/base_compiler.py`)
  - `def compile(self, code, timeout=10):` Abstract method.
  - `def run(self, file_path, timeout=5):` Abstract method.
- `class CCompiler(BaseCompiler):` and `class PythonCompiler(BaseCompiler):`
  Implementation wrappers that construct payloads and send HTTP requests to the `compiler-worker` container (`http://compiler-worker:8080/execute`).
