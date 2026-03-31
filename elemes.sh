#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

case "$1" in
stop | run | runbuild)
  echo "Stop Container..."
  podman-compose --env-file ../.env down
  ;;&
runbuild)
  echo "Build and Run Container..."
  podman-compose --env-file ../.env up --build --force-recreate -d
  ;;&
run)
  echo "Run Container..."
  podman-compose --env-file ../.env up -d
  ;;&
generatetoken)
  echo "Generating tokens_siswa.csv from content..."
  python3 "$SCRIPT_DIR/generate_tokens.py"
  ;;&
*)
  echo "elemes.sh ( run | runbuild | stop | generatetoken )"
  ;;
esac
