"""
Container runner and command execution abstraction for Elemes CLI.
Multi-OS compatible (Linux, macOS, Windows).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import IO, Any, Dict, List, Optional, Tuple, Union

from .config import (
    ENV_FILE,
    NOISE_RE,
    PROJECT_NAME,
    SCRIPT_DIR,
    is_verbose,
)


def detect_compose_command() -> List[str]:
    """
    Detect the appropriate compose command on the host.
    Checks podman-compose, podman compose, docker compose, docker-compose.
    Allows override via LMS_COMPOSE_CMD.
    """
    override = os.environ.get("LMS_COMPOSE_CMD")
    if override:
        return override.split()

    # 1. Prefer podman-compose (standard for Elemes)
    if shutil.which("podman-compose"):
        return ["podman-compose"]

    # 2. Check podman compose sub-command
    if shutil.which("podman"):
        try:
            res = subprocess.run(
                ["podman", "compose", "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if res.returncode == 0:
                return ["podman", "compose"]
        except Exception:
            pass

    # 3. Check docker compose / docker-compose
    if shutil.which("docker"):
        try:
            res = subprocess.run(
                ["docker", "compose", "version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if res.returncode == 0:
                return ["docker", "compose"]
        except Exception:
            pass

    if shutil.which("docker-compose"):
        return ["docker-compose"]

    # Default fallback
    return ["podman-compose"]


def detect_container_command() -> str:
    """
    Detect container runtime executable ('podman' or 'docker').
    Allows override via LMS_CONTAINER_CMD.
    """
    override = os.environ.get("LMS_CONTAINER_CMD")
    if override:
        return override

    if shutil.which("podman"):
        return "podman"
    if shutil.which("docker"):
        return "docker"
    return "podman"


def _filter_stderr_stream(
    stderr_pipe: IO[str], verbose: bool, captured_lines: Optional[List[str]] = None
) -> None:
    """Read lines from stderr_pipe, filter noise lines, and output remainder."""
    try:
        for line in iter(stderr_pipe.readline, ""):
            if not line:
                break
            if captured_lines is not None:
                captured_lines.append(line)
            if verbose or is_verbose() or not NOISE_RE.search(line):
                sys.stderr.write(line)
                sys.stderr.flush()
    except Exception:
        pass


def execute_process(
    cmd: List[str],
    cwd: Optional[Path] = None,
    env: Optional[Dict[str, str]] = None,
    verbose: bool = False,
    capture_stdout: bool = False,
    quiet: bool = False,
    stdin_file: Optional[IO[Any]] = None,
    stdin_data: Optional[str] = None,
    stdout_file: Optional[IO[Any]] = None,
) -> Tuple[int, str, str]:
    """
    Execute a subprocess with streaming, noise filtering, and cross-platform I/O.
    Returns (returncode, stdout_str, stderr_str).
    """
    run_cwd = cwd or SCRIPT_DIR
    run_env = dict(os.environ)
    if env:
        run_env.update(env)

    if quiet:
        # Suppress output on success; emit error output if failed
        try:
            stdin_src = stdin_file if stdin_file else (subprocess.PIPE if stdin_data else None)
            proc = subprocess.run(
                cmd,
                cwd=str(run_cwd),
                env=run_env,
                stdin=stdin_src,
                input=stdin_data.encode("utf-8") if stdin_data else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if proc.returncode != 0:
                if proc.stderr:
                    sys.stderr.write(proc.stderr)
                elif proc.stdout:
                    sys.stdout.write(proc.stdout)
            return proc.returncode, proc.stdout, proc.stderr
        except Exception as e:
            return 1, "", str(e)

    if verbose or is_verbose():
        sys.stderr.write(f"⚙️  [VERBOSE] Executing: {' '.join(cmd)}\n")
        sys.stderr.flush()

    # Redirect to binary file directly (e.g. pg_dump)
    if stdout_file:
        proc = None
        try:
            stdin_src = stdin_file if stdin_file else (subprocess.PIPE if stdin_data else None)
            proc = subprocess.Popen(
                cmd,
                cwd=str(run_cwd),
                env=run_env,
                stdin=stdin_src,
                stdout=stdout_file,
                stderr=subprocess.PIPE,
                text=True,
            )
            captured_stderr: List[str] = []
            stderr_thread = threading.Thread(
                target=_filter_stderr_stream,
                args=(proc.stderr, verbose, captured_stderr),
            )
            stderr_thread.daemon = True
            stderr_thread.start()

            if stdin_data and proc.stdin:
                proc.stdin.write(stdin_data)
                proc.stdin.close()

            proc.wait()
            stderr_thread.join()
            return proc.returncode, "", "".join(captured_stderr)
        except Exception as e:
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            return 1, "", str(e)

    # Capturing or streaming output
    stdout_lines: List[str] = []
    stderr_lines: List[str] = []
    proc = None

    try:
        stdin_pipe = stdin_file if stdin_file else (subprocess.PIPE if stdin_data else subprocess.DEVNULL)
        proc = subprocess.Popen(
            cmd,
            cwd=str(run_cwd),
            env=run_env,
            stdin=stdin_pipe,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        if stdin_data and proc.stdin:
            try:
                proc.stdin.write(stdin_data)
                proc.stdin.close()
            except Exception:
                pass

        def read_stdout() -> None:
            if not proc.stdout:
                return
            for line in iter(proc.stdout.readline, ""):
                if not line:
                    break
                stdout_lines.append(line)
                if not capture_stdout:
                    sys.stdout.write(line)
                    sys.stdout.flush()

        stdout_thread = threading.Thread(target=read_stdout)
        stdout_thread.daemon = True
        stdout_thread.start()

        stderr_thread = threading.Thread(
            target=_filter_stderr_stream,
            args=(proc.stderr, verbose, stderr_lines),
        )
        stderr_thread.daemon = True
        stderr_thread.start()

        proc.wait()
        stdout_thread.join()
        stderr_thread.join()

        return proc.returncode, "".join(stdout_lines), "".join(stderr_lines)

    except Exception as e:
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        if verbose:
            sys.stderr.write(f"Process execution error: {e}\n")
        return 1, "", str(e)


def run_compose_out(
    args: List[str],
    verbose: bool = False,
    capture_stdout: bool = False,
    quiet: bool = False,
    stdin_data: Optional[str] = None,
    stdin_file: Optional[IO[Any]] = None,
    stdout_file: Optional[IO[Any]] = None,
    extra_env: Optional[Dict[str, str]] = None,
) -> Tuple[int, str, str]:
    """
    Run podman-compose with PROJECT_NAME and --env-file without suppressing output.
    Filters noise from stderr unless verbose.
    """
    compose_cmd = detect_compose_command()
    full_cmd = [
        *compose_cmd,
        "-p",
        PROJECT_NAME,
        "--env-file",
        str(ENV_FILE),
        *args,
    ]
    return execute_process(
        full_cmd,
        cwd=SCRIPT_DIR,
        env=extra_env,
        verbose=verbose,
        capture_stdout=capture_stdout,
        quiet=quiet,
        stdin_data=stdin_data,
        stdin_file=stdin_file,
        stdout_file=stdout_file,
    )


def run_compose(args: List[str], verbose: bool = False) -> int:
    """Run podman-compose quietly unless verbose."""
    if verbose or is_verbose():
        ret, _, _ = run_compose_out(args, verbose=True)
        return ret
    compose_cmd = detect_compose_command()
    full_cmd = [
        *compose_cmd,
        "-p",
        PROJECT_NAME,
        "--env-file",
        str(ENV_FILE),
        *args,
    ]
    ret, _, _ = execute_process(full_cmd, cwd=SCRIPT_DIR, quiet=True)
    return ret


def compose_exec(
    service_and_args: List[str],
    verbose: bool = False,
    capture_stdout: bool = False,
    quiet: bool = False,
    stdin_data: Optional[str] = None,
    stdin_file: Optional[IO[Any]] = None,
    stdout_file: Optional[IO[Any]] = None,
    extra_env: Optional[Dict[str, str]] = None,
) -> Tuple[int, str, str]:
    """
    Execute a command inside a service container via podman-compose exec -T.
    Matches bash compose_exec: run_compose_out exec -T "$@"
    """
    args = ["exec", "-T", *service_and_args]
    return run_compose_out(
        args,
        verbose=verbose or is_verbose(),
        capture_stdout=capture_stdout,
        quiet=quiet,
        stdin_data=stdin_data,
        stdin_file=stdin_file,
        stdout_file=stdout_file,
        extra_env=extra_env,
    )


def compose_restart(service: str, verbose: bool = False) -> int:
    """Restart service container using service name."""
    is_v = verbose or is_verbose()
    args = ["restart", service]
    ret, _, _ = run_compose_out(args, verbose=is_v, capture_stdout=not is_v)
    return ret


def run_velxio_compose(
    args: List[str],
    verbose: bool = False,
    quiet: bool = False,
    capture_stdout: bool = False,
) -> Tuple[int, str, str]:
    """Run compose for Velxio standalone project."""
    compose_cmd = detect_compose_command()
    velxio_project = f"{PROJECT_NAME}-velxio"
    full_cmd = [
        *compose_cmd,
        "-p",
        velxio_project,
        "-f",
        "podman-compose.velxio.yml",
        "--env-file",
        str(ENV_FILE),
        *args,
    ]
    return execute_process(
        full_cmd,
        cwd=SCRIPT_DIR,
        verbose=verbose or is_verbose(),
        quiet=quiet,
        capture_stdout=capture_stdout,
    )


def run_container_cmd(
    args: List[str],
    verbose: bool = False,
    capture_stdout: bool = False,
    quiet: bool = False,
    cwd: Optional[Path] = None,
    stdin_file: Optional[IO[Any]] = None,
    stdout_file: Optional[IO[Any]] = None,
) -> Tuple[int, str, str]:
    """
    Run direct container runtime command ('podman' or 'docker').
    """
    runtime = detect_container_command()
    full_cmd = [runtime, *args]
    return execute_process(
        full_cmd,
        cwd=cwd or SCRIPT_DIR,
        verbose=verbose or is_verbose(),
        capture_stdout=capture_stdout,
        quiet=quiet,
        stdin_file=stdin_file,
        stdout_file=stdout_file,
    )
