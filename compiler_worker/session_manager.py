"""Interactive session manager for the compiler worker (Playground A1, Tasks 1-3).

Manages interactive PTY sessions for Python and C programs:
- Bounded output buffer with byte cursors (delta reads, no repetition).
- Per-session tempdir, validated multi-file uploads.
- PTY lifecycle: pty.openpty() + termios ECHO off + reader thread (select/os.read,
  incremental UTF-8 decoder) + parent-side watchdog (idle / max runtime / output
  overflow) — no preexec_fn (multi-threaded app).
- C compile queue: threading.BoundedSemaphore(MAX_COMPILES), status queued →
  compiling → running, gcc without shell.
- One daemon sweeper thread for retention cleanup + watchdog kills.
"""

import codecs
import os
import pty
import re
import secrets
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import termios
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass, field


# --------------------------------------------------------------------------
# Errors (mapped to HTTP codes in app.py)
# --------------------------------------------------------------------------

class SessionError(Exception):
    """Base class for session manager errors."""


class SessionCapacityError(SessionError):
    """Registry full — HTTP 429."""


class SessionValidationError(SessionError):
    """Invalid request payload — HTTP 400."""


class SessionNotFoundError(SessionError):
    """Unknown session id — HTTP 404."""


class SessionNotRunningError(SessionError):
    """Input written to a session that is not running — HTTP 409."""


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

def _env_int(name, default):
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


TERMINAL_STATUSES = frozenset({"exited", "error", "stopped"})

# Explicit, validated status transitions.
_ALLOWED_TRANSITIONS = {
    "queued": {"compiling", "running", "error", "stopped"},
    "compiling": {"running", "error", "exited", "stopped"},
    "running": {"exited", "error", "stopped"},
    "exited": set(),
    "error": set(),
    "stopped": set(),
}


# --------------------------------------------------------------------------
# Session model
# --------------------------------------------------------------------------

@dataclass
class InteractiveSession:
    session_id: str
    language: str
    status: str
    created_at: float
    last_activity_at: float
    output_base_cursor: int = 0
    output_next_cursor: int = 0
    output_chunks: deque = field(default_factory=deque)
    process: subprocess.Popen | None = None
    master_fd: int | None = None
    exit_code: int | None = None
    error: str | None = None
    # --- extra bookkeeping ------------------------------------------------
    tempdir: str | None = None
    started_at: float = 0.0
    last_output_at: float = 0.0
    input_pending: str = ""
    truncated: bool = False
    reader_thread: threading.Thread | None = None

    def _set_status(self, new_status):
        old = self.status
        if new_status == old:
            return
        if new_status not in _ALLOWED_TRANSITIONS.get(old, set()):
            raise SessionError(
                f"invalid status transition: {old} -> {new_status}"
            )
        self.status = new_status


# --------------------------------------------------------------------------
# Manager
# --------------------------------------------------------------------------

class SessionManager:
    def __init__(
        self,
        *,
        max_sessions=None,
        max_compiles=None,
        queue_timeout=None,
        idle_timeout=None,
        max_runtime=None,
        terminal_retention=None,
        output_limit_bytes=None,
        max_files=None,
        max_source_bytes=None,
        sweeper_interval=1.0,
        autostart_sweeper=True,
    ):
        self.max_sessions = max_sessions or _env_int("INTERACTIVE_MAX_SESSIONS", 50)
        self.max_compiles = max_compiles or _env_int("INTERACTIVE_MAX_COMPILES", 2)
        self.queue_timeout = queue_timeout or _env_int("INTERACTIVE_QUEUE_TIMEOUT_SECONDS", 20)
        self.idle_timeout = idle_timeout or _env_int("INTERACTIVE_IDLE_TIMEOUT_SECONDS", 30)
        self.max_runtime = max_runtime or _env_int("INTERACTIVE_MAX_RUNTIME_SECONDS", 60)
        self.terminal_retention = terminal_retention or _env_int(
            "INTERACTIVE_TERMINAL_RETENTION_SECONDS", 15
        )
        self.output_limit_bytes = output_limit_bytes or _env_int(
            "INTERACTIVE_OUTPUT_LIMIT_BYTES", 262144
        )
        self.max_files = max_files or _env_int("INTERACTIVE_MAX_FILES", 20)
        self.max_source_bytes = max_source_bytes or _env_int(
            "INTERACTIVE_MAX_SOURCE_BYTES", 262144
        )
        self.sweeper_interval = sweeper_interval

        self._lock = threading.RLock()
        self._sessions = {}
        self._compile_semaphore = threading.BoundedSemaphore(self.max_compiles)
        self._compiling_count = 0
        self._sweeper_stop = threading.Event()
        self._sweeper = None
        if autostart_sweeper:
            self._start_sweeper()

    # ------------------------------------------------------------------
    # Sweeper daemon thread
    # ------------------------------------------------------------------

    def _start_sweeper(self):
        self._sweeper = threading.Thread(
            target=self._sweeper_loop,
            name="session-sweeper",
            daemon=True,
        )
        self._sweeper.start()

    def _sweeper_loop(self):
        while not self._sweeper_stop.wait(self.sweeper_interval):
            try:
                self.cleanup_expired()
            except Exception:  # noqa: BLE001 — sweeper must never die
                pass

    def shutdown(self):
        """Stop sweeper, kill all child processes, remove tempdirs."""
        self._sweeper_stop.set()
        if self._sweeper is not None and self._sweeper.is_alive():
            self._sweeper.join(timeout=2)
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for s in sessions:
            if s.process is not None and s.process.poll() is None:
                self._kill_proc(s.process)
            self._cleanup_tempdir(s)

    # ------------------------------------------------------------------
    # Output buffer (bounded, byte cursors)
    # ------------------------------------------------------------------

    def _append_output(self, session, text):
        """Append decoded text; evict oldest chunks past the byte limit."""
        if not text:
            return
        data = text if isinstance(text, str) else text.decode("utf-8", "replace")
        encoded_len = len(data.encode("utf-8"))
        limit = self.output_limit_bytes
        if encoded_len > limit:
            # Single chunk larger than the whole buffer: keep its head.
            data = data[:limit]
            encoded_len = limit
            with self._lock:
                session.output_chunks.clear()
                session.output_base_cursor = session.output_next_cursor
                session.truncated = True
        with self._lock:
            while (
                session.output_chunks
                and (session.output_next_cursor - session.output_base_cursor)
                + encoded_len
                > limit
            ):
                old = session.output_chunks.popleft()
                session.output_base_cursor += len(old.encode("utf-8"))
                session.truncated = True
            session.output_chunks.append(data)
            session.output_next_cursor += encoded_len

    def _slice_from_cursor(self, chunks, base, next_cursor, cursor):
        """Return (text, missed_data) for byte cursor relative to chunk stream."""
        if cursor < base:
            return "".join(chunks), True
        if cursor >= next_cursor:
            return "", False
        buf = []
        offset = base
        missed = False
        for c in chunks:
            clen = len(c.encode("utf-8"))
            if offset + clen <= cursor:
                offset += clen
                continue
            if offset == cursor:
                buf.append(c)
            else:
                # Cursor points mid-chunk (pathological): reslice from byte offset.
                raw = c.encode("utf-8")[cursor - offset :]
                buf.append(raw.decode("utf-8", errors="replace"))
                missed = True
            offset += clen
        return "".join(buf), missed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self, language, files, active_file=None, stdin=""):
        """Validate, register, and launch a new interactive session."""
        if language not in ("python", "c"):
            raise SessionValidationError(f"unsupported language: {language!r}")
        files = self._validate_files(language, files)
        with self._lock:
            if len(self._sessions) >= self.max_sessions:
                raise SessionCapacityError(
                    f"session capacity reached: {self.max_sessions} active sessions"
                )
            now = time.time()
            session = InteractiveSession(
                session_id=secrets.token_urlsafe(32),
                language=language,
                status="queued",
                created_at=now,
                last_activity_at=now,
            )
            session.started_at = now
            session.input_pending = stdin if isinstance(stdin, str) else ""
            self._sessions[session.session_id] = session
        try:
            if language == "python":
                self._launch_python(session, files, active_file)
            else:
                self._launch_c(session, files)
        except SessionValidationError:
            with self._lock:
                self._sessions.pop(session.session_id, None)
                self._cleanup_tempdir(session)
            raise
        except Exception as e:  # noqa: BLE001 — surface as error session
            with self._lock:
                session.status = "error"
                session.error = str(e)
                session.last_activity_at = time.time()
        return session

    def get_delta(self, session_id, cursor=0):
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionNotFoundError(f"unknown session: {session_id}")
            chunks = list(session.output_chunks)
            base = session.output_base_cursor
            next_cursor = session.output_next_cursor
            buffer_truncated = session.truncated
            status = session.status
            language = session.language
            exit_code = session.exit_code
            error = session.error
        try:
            cursor = max(0, int(cursor))
        except (TypeError, ValueError):
            cursor = 0
        text, missed = self._slice_from_cursor(chunks, base, next_cursor, cursor)
        return {
            "session_id": session_id,
            "language": language,
            "status": status,
            "output": text,
            "cursor": next_cursor,
            "base_cursor": base,
            "truncated": missed,
            "buffer_truncated": buffer_truncated,
            "running": status == "running",
            "exit_code": exit_code,
            "error": error,
        }

    def write_input(self, session_id, text):
        if not isinstance(text, str):
            raise SessionValidationError("input must be a string")
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionNotFoundError(f"unknown session: {session_id}")
            if session.status != "running" or session.master_fd is None:
                raise SessionNotRunningError(
                    f"session {session_id} is not running (status={session.status})"
                )
            fd = session.master_fd
        if not text:
            return True
        # input()/scanf() butuh Enter (newline) untuk submit — tambahkan bila belum ada
        normalized = text if text.endswith("\n") else text + "\n"
        ok = self._write_all(fd, normalized)
        if not ok:
            with self._lock:
                session.status = "stopped"
                session.error = "broken pipe while writing input"
                session.last_activity_at = time.time()
            raise SessionNotRunningError("session terminated while writing input")
        with self._lock:
            session.last_activity_at = time.time()
        return True

    def stop(self, session_id):
        """Stop a session; idempotent."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionNotFoundError(f"unknown session: {session_id}")
            if session.status == "stopped":
                return self._summary(session)
            if session.status in TERMINAL_STATUSES:
                # Already finished on its own — nothing to kill.
                return self._summary(session)
            proc = session.process
            session.status = "stopped"
            session.last_activity_at = time.time()
        if proc is not None and proc.poll() is None:
            self._kill_proc(proc)
        with self._lock:
            if session.exit_code is None and session.process is not None:
                session.exit_code = session.process.poll()
            return self._summary(session)

    def cleanup_expired(self):
        """Retention cleanup + watchdog kills. Returns number of sessions cleaned."""
        now = time.time()
        to_remove = []
        to_kill = []  # (session, reason)
        with self._lock:
            for sid, s in list(self._sessions.items()):
                if s.status in TERMINAL_STATUSES:
                    if now - s.last_activity_at >= self.terminal_retention:
                        to_remove.append(sid)
                elif s.status == "queued":
                    if now - s.created_at >= self.queue_timeout:
                        s.status = "error"
                        s.error = f"queue timeout after {self.queue_timeout}s"
                        s.last_activity_at = now
                        to_remove.append(sid)
                elif s.status == "running":
                    if now - s.last_activity_at >= self.idle_timeout:
                        to_kill.append((s, "idle timeout"))
                    elif now - s.started_at >= self.max_runtime:
                        to_kill.append((s, "max runtime exceeded"))
                elif s.status == "compiling":
                    if now - s.started_at >= self.max_runtime:
                        to_kill.append((s, "max runtime exceeded"))
        for s, reason in to_kill:
            with self._lock:
                if s.status == "running" or s.status == "compiling":
                    s.status = "stopped"
                    s.error = reason
                    s.last_activity_at = now
            if s.process is not None and s.process.poll() is None:
                self._kill_proc(s.process)
        with self._lock:
            for sid in to_remove:
                s = self._sessions.pop(sid, None)
                if s is not None:
                    self._cleanup_tempdir(s)
        return len(to_remove) + len(to_kill)

    def stats(self):
        with self._lock:
            counts = Counter(s.status for s in self._sessions.values())
            total = len(self._sessions)
        return {
            "active_sessions": total,
            "queued": counts.get("queued", 0),
            "compiling": counts.get("compiling", 0),
            "running": counts.get("running", 0),
            "exited": counts.get("exited", 0),
            "error": counts.get("error", 0),
            "stopped": counts.get("stopped", 0),
            "limits": {
                "max_sessions": self.max_sessions,
                "max_compiles": self.max_compiles,
                "queue_timeout_seconds": self.queue_timeout,
                "idle_timeout_seconds": self.idle_timeout,
                "max_runtime_seconds": self.max_runtime,
                "terminal_retention_seconds": self.terminal_retention,
                "output_limit_bytes": self.output_limit_bytes,
                "max_files": self.max_files,
                "max_source_bytes": self.max_source_bytes,
            },
        }

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    _NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

    @staticmethod
    def _valid_name(name, allowed_exts):
        if not isinstance(name, str) or not name:
            return False
        if "/" in name or "\\" in name:
            return False
        if name in (".", "..") or name.startswith("..") or os.path.isabs(name):
            return False
        if not SessionManager._NAME_RE.match(name):
            return False
        return os.path.splitext(name)[1].lower() in allowed_exts

    def _validate_files(self, language, files):
        allowed_exts = {".py"} if language == "python" else {".c", ".h"}
        if not isinstance(files, list) or not files:
            raise SessionValidationError("files must be a non-empty list")
        if len(files) > self.max_files:
            raise SessionValidationError(
                f"too many files: {len(files)} > {self.max_files}"
            )
        seen = {}
        total_bytes = 0
        normalized = []
        for item in files:
            if not isinstance(item, dict) or "name" not in item or "content" not in item:
                raise SessionValidationError("each file must be {name, content}")
            name = item["name"]
            content = item["content"]
            if not isinstance(content, str):
                raise SessionValidationError(f"content of {name!r} must be a string")
            if not self._valid_name(name, allowed_exts):
                raise SessionValidationError(
                    f"invalid file name {name!r} (basename only, extension "
                    f"{'/'.join(sorted(allowed_exts))})"
                )
            key = name.lower()
            if key in seen:
                raise SessionValidationError(
                    f"duplicate file name (case-insensitive): {name!r} and {seen[key]!r}"
                )
            seen[key] = name
            total_bytes += len(content.encode("utf-8"))
            if total_bytes > self.max_source_bytes:
                raise SessionValidationError(
                    f"total source exceeds {self.max_source_bytes} bytes"
                )
            normalized.append({"name": name, "content": content})
        return normalized

    # ------------------------------------------------------------------
    # Launch: Python
    # ------------------------------------------------------------------

    def _launch_python(self, session, files, active_file):
        tempdir = tempfile.mkdtemp(prefix="elemes-py-")
        session.tempdir = tempdir
        self._write_files(tempdir, files)
        names = [f["name"] for f in files]
        target = active_file if active_file in names else names[0]
        if not target.endswith(".py"):
            raise SessionValidationError(f"active file must be a .py file: {target!r}")
        self._spawn_pty(session, [sys.executable, target], tempdir)

    # ------------------------------------------------------------------
    # Launch: C with compile queue
    # ------------------------------------------------------------------

    def _launch_c(self, session, files):
        tempdir = tempfile.mkdtemp(prefix="elemes-c-")
        session.tempdir = tempdir
        self._write_files(tempdir, files)
        c_files = [f["name"] for f in files if f["name"].endswith(".c")]
        if not c_files:
            raise SessionValidationError("no .c source files to compile")
        acquired = self._compile_semaphore.acquire(timeout=self.queue_timeout)
        if not acquired:
            with self._lock:
                session.status = "error"
                session.error = f"compile queue timeout after {self.queue_timeout}s"
                session.last_activity_at = time.time()
            return
        with self._lock:
            if session.status != "queued":
                # Stopped/errored while waiting in queue.
                self._compile_semaphore.release()
                return
            session.status = "compiling"
            self._compiling_count += 1
        try:
            res = subprocess.run(
                ["gcc", "-std=c11", "-Wall", "-Wextra", "-I", tempdir]
                + c_files
                + ["-o", "program"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=tempdir,
                shell=False,
            )
            if res.stdout:
                self._append_output(session, res.stdout)
            if res.stderr:
                self._append_output(session, res.stderr)
            if res.returncode != 0:
                with self._lock:
                    session.status = "error"
                    session.error = "compilation failed"
                    session.exit_code = res.returncode
                    session.last_activity_at = time.time()
                return
        except subprocess.TimeoutExpired:
            with self._lock:
                session.status = "error"
                session.error = "compilation timed out"
                session.last_activity_at = time.time()
            return
        finally:
            with self._lock:
                self._compiling_count -= 1
            self._compile_semaphore.release()
        self._spawn_pty(session, [os.path.join(tempdir, "program")], tempdir)

    # ------------------------------------------------------------------
    # PTY lifecycle
    # ------------------------------------------------------------------

    @staticmethod
    def _write_files(tempdir, files):
        for f in files:
            path = os.path.join(tempdir, f["name"])
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(f["content"])

    def _spawn_pty(self, session, argv, cwd):
        """Spawn argv on a PTY (no shell, no preexec_fn), then start reader."""
        with self._lock:
            if session.status in TERMINAL_STATUSES or session.status == "stopped":
                return None
            master_fd, slave_fd = pty.openpty()
            try:
                attrs = termios.tcgetattr(slave_fd)
                attrs[3] &= ~termios.ECHO
                termios.tcsetattr(slave_fd, termios.TCSANOW, attrs)
                proc = subprocess.Popen(
                    argv,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    cwd=cwd,
                    start_new_session=True,
                    shell=False,
                    close_fds=True,
                )
                os.close(slave_fd)
            except Exception:
                os.close(master_fd)
                try:
                    os.close(slave_fd)
                except OSError:
                    pass
                raise
            session.process = proc
            session.master_fd = master_fd
            session.status = "running"
            session.started_at = time.time()
            session.last_output_at = time.time()
            session.last_activity_at = time.time()
            pending = session.input_pending
            session.input_pending = ""
        if pending:
            self._write_all(master_fd, pending)
        thread = threading.Thread(
            target=self._reader_loop,
            args=(session,),
            name=f"reader-{session.session_id[:8]}",
            daemon=True,
        )
        session.reader_thread = thread
        thread.start()
        return session

    def _reader_loop(self, session):
        """select + os.read on the PTY master; incremental UTF-8 decoding."""
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        fd = session.master_fd
        overflow = False
        try:
            while True:
                try:
                    ready, _, _ = select.select([fd], [], [], 0.5)
                except (OSError, ValueError):
                    break
                if ready:
                    try:
                        data = os.read(fd, 4096)
                    except OSError:
                        break
                    if not data:
                        break
                    text = decoder.decode(data)
                    if text:
                        self._append_output(session, text)
                        with self._lock:
                            session.last_output_at = time.time()
                            session.last_activity_at = time.time()
                            overflow = self._output_overflowed(session)
                        if overflow:
                            break
                else:
                    proc = session.process
                    if proc is not None and proc.poll() is not None:
                        # Child exited: drain any residual buffered output.
                        self._drain(session, fd, decoder)
                        break
        finally:
            with self._lock:
                if overflow:
                    session.status = "stopped"
                    session.error = "output limit exceeded"
                elif session.status not in TERMINAL_STATUSES:
                    session.status = "exited"
                if session.process is not None:
                    session.exit_code = session.process.poll()
                session.last_activity_at = time.time()
                self._close_master_fd(session)
            if overflow:
                proc = session.process
                if proc is not None and proc.poll() is None:
                    self._kill_proc(proc)

    def _drain(self, session, fd, decoder):
        deadline = time.time() + 0.5
        while time.time() < deadline:
            try:
                ready, _, _ = select.select([fd], [], [], 0.1)
            except (OSError, ValueError):
                return
            if not ready:
                return
            try:
                data = os.read(fd, 4096)
            except OSError:
                return
            if not data:
                return
            text = decoder.decode(data)
            if text:
                self._append_output(session, text)

    def _output_overflowed(self, session):
        return (
            session.output_next_cursor - session.output_base_cursor
            >= self.output_limit_bytes
        )

    def _close_master_fd(self, session):
        fd = session.master_fd
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
            session.master_fd = None

    @staticmethod
    def _write_all(fd, text):
        view = memoryview(text.encode("utf-8"))
        while view:
            try:
                written = os.write(fd, view)
            except OSError:
                return False
            if written <= 0:
                return False
            view = view[written:]
        return True

    @staticmethod
    def _kill_proc(proc):
        """SIGTERM the process group, escalate to SIGKILL after 1s."""
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            try:
                proc.terminate()
            except Exception:  # noqa: BLE001
                pass
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, OSError):
                try:
                    proc.kill()
                except Exception:  # noqa: BLE001
                    pass
            try:
                proc.wait(timeout=1.0)
            except Exception:  # noqa: BLE001
                pass

    def _cleanup_tempdir(self, session):
        if session.tempdir:
            shutil.rmtree(session.tempdir, ignore_errors=True)
            session.tempdir = None

    @staticmethod
    def _summary(session):
        return {
            "session_id": session.session_id,
            "language": session.language,
            "status": session.status,
            "exit_code": session.exit_code,
            "error": session.error,
            "created_at": session.created_at,
            "last_activity_at": session.last_activity_at,
        }
