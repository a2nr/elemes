#!/usr/bin/env bash
# Elemes LMS Orchestrator - Portable Unix Wrapper (Linux / macOS)
# Default virtualenv selalu berada di parent folder (../venv) agar elemes/ tetap bersih

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

# Tentukan direktori virtualenv di parent
if [ -d "$PARENT_DIR/.venv" ]; then
  VENV_DIR="$PARENT_DIR/.venv"
else
  VENV_DIR="$PARENT_DIR/venv"
fi
VENV_PYTHON="$VENV_DIR/bin/python"

# 1. Buat virtualenv di parent jika belum ada
if [ ! -x "$VENV_PYTHON" ] && [ "${ELEMES_NO_VENV:-0}" != "1" ]; then
  echo "📦 Menyiapkan virtualenv di $(basename "$VENV_DIR")/ (parent folder agar elemes tetap bersih)..."
  python3 -m venv "$VENV_DIR" || {
    echo "⚠️ Gagal membuat virtualenv dengan python3 -m venv."
  }
fi

# 2. Pastikan dependensi rich terpasang di venv
if [ -x "$VENV_PYTHON" ]; then
  if ! "$VENV_PYTHON" -c "import rich" >/dev/null 2>&1; then
    echo "📦 Memasang dependensi CLI (rich) ke $(basename "$VENV_DIR")..."
    if [ -f "$SCRIPT_DIR/requirements-cli.txt" ]; then
      "$VENV_PYTHON" -m pip install -q -r "$SCRIPT_DIR/requirements-cli.txt" || true
    else
      "$VENV_PYTHON" -m pip install -q "rich>=13.0.0" || true
    fi
  fi
  exec "$VENV_PYTHON" "$SCRIPT_DIR/elemes.py" "$@"
else
  exec python3 "$SCRIPT_DIR/elemes.py" "$@"
fi
