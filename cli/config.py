"""
Configuration and environment management for Elemes CLI.
Multi-OS compatible using pathlib.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Core directory paths resolved portably across Linux, macOS, Windows
CLI_DIR = Path(__file__).resolve().parent
SCRIPT_DIR = CLI_DIR.parent
PARENT_DIR = SCRIPT_DIR.parent
PROJECT_NAME = PARENT_DIR.name

EXAMPLES_DIR = SCRIPT_DIR / "examples"
ENV_FILE = PARENT_DIR / ".env"
LAST_RUN_FILE = SCRIPT_DIR / ".last_run"

# Regex for filtering noisy stderr lines from podman-compose
NOISE_RE = re.compile(
    r"^(podman-compose version:|\[.*--version.*\]$|using podman version:|podman exec |exit code: )"
)


def read_env(env_path: Optional[Path] = None) -> Dict[str, str]:
    """
    Parse .env file without shell sourcing, preserving values cleanly.
    Compatible with Windows and Unix newlines.
    """
    path = env_path or ENV_FILE
    env_vars: Dict[str, str] = {}
    if not path.is_file():
        return env_vars

    try:
        content = path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                # Remove enclosing matching quotes if present
                if (val.startswith('"') and val.endswith('"')) or (
                    val.startswith("'") and val.endswith("'")
                ):
                    val = val[1:-1]
                env_vars[key] = val
    except Exception:
        pass
    return env_vars


def env_val(key: str, default: str = "", env_path: Optional[Path] = None) -> str:
    """Read a single configuration value from .env."""
    env = read_env(env_path)
    return env.get(key, default)


def generate_ts_config() -> None:
    """
    Generate lms-tail.json from template based on VELXIO_MODE.
    Prepares Tailscale Serve config before starting containers.
    """
    template_path = SCRIPT_DIR / "config" / "lms-tail.json.template"
    output_path = SCRIPT_DIR / "config" / "lms-tail.json"

    if not template_path.is_file():
        return

    mode = env_val("VELXIO_MODE", "local").lower()
    if mode == "remote":
        velxio_host = env_val("VELXIO_HOST", "velxio-dev")
        target = f"http://{velxio_host}:80/"
    else:
        target = "http://127.0.0.1:80/"

    try:
        content = template_path.read_text(encoding="utf-8")
        new_content = content.replace("__VELXIO_PROXY_TARGET__", target)
        output_path.write_text(new_content, encoding="utf-8")
    except Exception as e:
        print(f"⚠️  Gagal membuat {output_path.name}: {e}")


def elemes_services() -> List[str]:
    """
    List of elemes services to start based on VELXIO_MODE.
    Empty list = start all services (local mode).
    Non-empty = start only listed services (remote mode).
    """
    mode = env_val("VELXIO_MODE", "local").lower()
    if mode == "remote":
        return [
            "elemes-ts",
            "postgres",
            "elemes",
            "compiler-worker",
            "elemes-frontend",
            "flowchart",
        ]
    return []


def get_run_timestamp() -> str:
    """Format current time like date '+%Y-%m-%d %H:%M:%S %Z'."""
    now = datetime.now().astimezone()
    # Format: 2026-09-06 05:30:00 WIB
    return now.strftime("%Y-%m-%d %H:%M:%S %Z")


def record_last_run(command_str: str) -> str:
    """Record execution command and time into .last_run."""
    run_time = get_run_timestamp()
    try:
        LAST_RUN_FILE.write_text(
            f"command: {command_str}\ntime: {run_time}\n",
            encoding="utf-8",
        )
    except Exception:
        pass
    return run_time


# Verbose mode state
_VERBOSE: bool = False


def is_verbose() -> bool:
    """Return whether verbose mode is currently active."""
    return _VERBOSE


def set_verbose(val: bool) -> None:
    """Set verbose mode globally."""
    global _VERBOSE
    _VERBOSE = val


def toggle_verbose() -> bool:
    """Toggle verbose mode and return new state."""
    global _VERBOSE
    _VERBOSE = not _VERBOSE
    return _VERBOSE
