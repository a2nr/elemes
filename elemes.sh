#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"
EXAMPLES_DIR="$SCRIPT_DIR/examples"
PROJECT_NAME="$(basename "$PARENT_DIR")"

case "$1" in
init)
  echo "=== Elemes Quick Start ==="
  echo ""

  # .env
  if [ -f "$PARENT_DIR/.env" ]; then
    echo "[skip] .env sudah ada"
  else
    cp "$EXAMPLES_DIR/../.env.example" "$PARENT_DIR/.env"
    echo "[buat] .env  (edit sesuai kebutuhan)"
  fi

  # content/
  if [ -d "$PARENT_DIR/content" ] && [ "$(ls -A "$PARENT_DIR/content" 2>/dev/null)" ]; then
    echo "[skip] content/ sudah ada"
  else
    mkdir -p "$PARENT_DIR/content"
    cp -n "$EXAMPLES_DIR/content/"*.md "$PARENT_DIR/content/"
    echo "[buat] content/  ($(ls "$PARENT_DIR/content/"*.md 2>/dev/null | wc -l) materi)"
  fi

  # assets/
  mkdir -p "$PARENT_DIR/assets"

  # tokens
  if [ -f "$PARENT_DIR/tokens_siswa.csv" ]; then
    echo "[skip] tokens_siswa.csv sudah ada"
  else
    cp "$EXAMPLES_DIR/tokens_siswa.csv" "$PARENT_DIR/tokens_siswa.csv"
    echo "[buat] tokens_siswa.csv  (edit untuk tambah siswa)"
  fi

  echo ""
  echo "Selesai! Langkah selanjutnya:"
  echo "  1. Edit ../.env sesuai kebutuhan"
  echo "  2. Edit ../content/home.md untuk daftar materi"
  echo "  3. Edit ../tokens_siswa.csv untuk data siswa"
  echo "  4. Jalankan:  ./elemes.sh runbuild"
  ;;
stop | run | runbuild | runclearbuild)
  echo "Stop Container..."
  podman-compose -p "$PROJECT_NAME" --env-file ../.env down
  ;;&
stop) ;;
runclearbuild)
  echo "Cleanup dangling images..."
  podman image prune -f
  echo "Build Container (no cache)..."
  podman-compose -p "$PROJECT_NAME" --env-file ../.env build --no-cache
  ;;&
runbuild)
  echo "Build Container..."
  podman-compose -p "$PROJECT_NAME" --env-file ../.env build
  ;;&
runbuild | runclearbuild)
  echo "Run Container..."
  podman-compose -p "$PROJECT_NAME" --env-file ../.env up --force-recreate -d
  ;;
run)
  echo "Run Container..."
  podman-compose -p "$PROJECT_NAME" --env-file ../.env up -d
  ;;
generatetoken)
  echo "Generating tokens_siswa.csv from content..."
  python3 "$SCRIPT_DIR/generate_tokens.py"
  ;;
*)
  echo "elemes.sh ( init | run | runbuild | runclearbuild | stop | generatetoken )"
  ;;
esac
