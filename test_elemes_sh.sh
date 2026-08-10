#!/usr/bin/env bash
# Regression test untuk resolusi PROJECT_NAME dinamis di elemes.sh.
#
# Memastikan elemes.sh TIDAK pernah menulis nama container hard-coded
# (mis. lms-dev_* / lms-sinau-c_*): semua operasi di-resolve lewat
# podman-compose (exec/restart/config) dan label filter project+service,
# apa pun nama direktori parent / PROJECT_NAME-nya.
#
# Berjalan dengan fake `podman`/`podman-compose` di workspace temp sehingga
# tidak menyentuh container asli sama sekali.

set -euo pipefail

TESTROOT=$(mktemp -d)
trap 'rm -rf "$TESTROOT"' EXIT

# PARENT_DIR memakai NAMA DINAMIS (bukan "lms-dev") -> PROJECT_NAME ikut dinamis.
# elemes.sh menghitung PROJECT_NAME dari basename PARENT_DIR, jadi script
# ditaruh di sub-direktori <PARENT_DIR>/elemes.
PARENT_DIR=$(mktemp -d "$TESTROOT/my-deploy.XXXX")
WORKSPACE="$PARENT_DIR/elemes"
PROJECT_NAME=$(basename "$PARENT_DIR")
FAKEBIN="$TESTROOT/fakebin"
mkdir -p "$WORKSPACE" "$FAKEBIN"
touch "$PARENT_DIR/.env" # PARENT_DIR/.env (dibaca run_compose & db_init)

cp "$(dirname "$0")/elemes.sh" "$WORKSPACE/elemes.sh"
export FAKE_PROJECT="$PROJECT_NAME"

# --- Fake podman-compose: catat semua panggilan, jawab config/exec/restart ----
cat > "$FAKEBIN/podman-compose" <<'EOF'
#!/usr/bin/env bash
LOG="$(dirname "$0")/calls.log"
echo "podman-compose $*" >> "$LOG"
ARGS=" $* "
if [[ "$ARGS" == *" config --services "* ]]; then
  printf 'elemes-ts\npostgres\nelemes\ncompiler-worker\nelemes-frontend\nvelxio\nflowchart\n'
elif [[ "$ARGS" == *" config "* ]]; then
  cat <<'YAML'
services:
  compiler-worker:
    image: lms-compiler-worker:latest
  elemes:
    image: lms-backend:latest
  elemes-frontend:
    image: lms-frontend:latest
  elemes-ts:
    image: docker.io/tailscale/tailscale:latest
  flowchart:
    image: lms-flowchart:latest
  postgres:
    image: postgres:18-alpine
  velxio:
    image: lms-velxio:latest
YAML
elif [[ "$ARGS" == *" exec "* ]]; then
  # psql -tAc dipakai db_init untuk deteksi schema kosong -> jawab "t"
  if [[ "$ARGS" == *" -tAc "* ]]; then
    echo "t"
  else
    echo "fake-exec:$*"
  fi
elif [[ "$ARGS" == *" restart "* ]]; then
  echo "fake-restart:$*"
fi
exit 0
EOF

# --- Fake podman: catat panggilan, jawab ps/images/inspect --------------------
cat > "$FAKEBIN/podman" <<'EOF'
#!/usr/bin/env bash
LOG="$(dirname "$0")/calls.log"
echo "podman $*" >> "$LOG"
ARGS=" $* "
if [[ "$ARGS" == *" ps "* ]]; then
  if [[ "$ARGS" == *"{{.ID}}"* ]]; then
    echo "cid111"
  else
    echo "${FAKE_PROJECT}_elemes-ts_1|docker.io/tailscale/tailscale:latest|abc123|Up|map[com.docker.compose.project:$FAKE_PROJECT com.docker.compose.service:elemes-ts io.podman.compose.project:$FAKE_PROJECT]"
    echo "${FAKE_PROJECT}_postgres_1|postgres:18-alpine|def456|Up (healthy)|map[com.docker.compose.project:$FAKE_PROJECT com.docker.compose.service:postgres io.podman.compose.project:$FAKE_PROJECT]"
    echo "${FAKE_PROJECT}_elemes_1|localhost/lms-backend:latest|old123|Up|map[com.docker.compose.project:$FAKE_PROJECT com.docker.compose.service:elemes io.podman.compose.project:$FAKE_PROJECT]"
    echo "${FAKE_PROJECT}_compiler-worker_1|localhost/lms-compiler-worker:latest|jkl012|Up|map[com.docker.compose.project:$FAKE_PROJECT com.docker.compose.service:compiler-worker io.podman.compose.project:$FAKE_PROJECT]"
    echo "${FAKE_PROJECT}_elemes-frontend_1|localhost/lms-frontend:latest|mno345|Up|map[com.docker.compose.project:$FAKE_PROJECT com.docker.compose.service:elemes-frontend io.podman.compose.project:$FAKE_PROJECT]"
    echo "${FAKE_PROJECT}_velxio_1|localhost/lms-velxio:latest|pqr678|Up|map[com.docker.compose.project:$FAKE_PROJECT com.docker.compose.service:velxio io.podman.compose.project:$FAKE_PROJECT]"
    echo "${FAKE_PROJECT}_flowchart_1|localhost/lms-flowchart:latest|stu901|Up|map[com.docker.compose.project:$FAKE_PROJECT com.docker.compose.service:flowchart io.podman.compose.project:$FAKE_PROJECT]"
  fi
elif [[ "$ARGS" == *" images "* ]]; then
  case "$ARGS" in
    *"lms-backend:latest"*) echo "new456" ;; # != old123 (ImageID container) -> STALE
    *"lms-frontend:latest"*) echo "mno345" ;;
    *"lms-velxio:latest"*) echo "pqr678" ;;
    *"lms-compiler-worker:latest"*) echo "jkl012" ;;
    *"lms-flowchart:latest"*) echo "stu901" ;;
    *"postgres:18-alpine"*) echo "def456" ;;
    *"tailscale/tailscale:latest"*) echo "abc123" ;;
    *) echo "deadbeef" ;;
  esac
elif [[ "$ARGS" == *" inspect "* ]]; then
  echo '["/bin/sh","-c","gunicorn --config gunicorn.conf.py app:create_app()"]'
  echo '["gunicorn"]'
  echo "localhost/lms-backend:latest"
fi
exit 0
EOF

chmod +x "$FAKEBIN/podman" "$FAKEBIN/podman-compose"
export PATH="$FAKEBIN:$PATH"

FAILED=0
fail() { echo "❌ $1"; FAILED=1; }
ok() { echo "✅ $1"; }

# Akumulator semua panggilan (untuk cek global "tidak ada nama hard-coded")
ACCUM="$FAKEBIN/calls.all.log"
: > "$ACCUM"

# Jalankan perintah elemes.sh: truncate calls.log per-perintah (supaya asersi
# per-bagian presisi), lalu kumpulkan ke akumulator untuk cek global.
run_elemes() {
  : > "$FAKEBIN/calls.log"
  local out
  if ! out=$(cd "$WORKSPACE" && bash elemes.sh "$@" 2>&1); then
    return 1
  fi
  cat "$FAKEBIN/calls.log" >> "$ACCUM" 2>/dev/null || true
  printf '%s' "$out"
}

# ===== 1) verify: resolusi via label + service, tanpa nama container hard-coded
if ! OUT=$(run_elemes verify); then
  fail "verify tidak berjalan"
  echo "$OUT"
else
  echo "$OUT" | grep -q "${PROJECT_NAME}_elemes_1" \
    && ok "verify menampilkan container ${PROJECT_NAME}_elemes_1" \
    || fail "verify tidak menampilkan container ${PROJECT_NAME}_elemes_1"
  echo "$OUT" | grep -q "flowchart" \
    && ok "verify menampilkan service flowchart" \
    || fail "verify tidak menampilkan service flowchart"
  echo "$OUT" | grep -q "STALE" \
    && ok "verify mendeteksi image STALE (elemes)" \
    || fail "verify tidak mendeteksi image STALE"
  echo "$OUT" | grep -q "lms-dev" \
    && fail "verify masih menyebut 'lms-dev'" || true
fi

# ===== 2) run: down/up + db_init memakai compose_exec / compose_restart ======
if ! OUT=$(run_elemes run); then
  fail "run tidak berjalan"
  echo "$OUT"
else
  grep -q "exec -T postgres pg_isready" "$FAKEBIN/calls.log" \
    && ok "db_init memakai compose_exec postgres (pg_isready)" \
    || fail "db_init tidak memakai compose_exec postgres (pg_isready)"
  grep -q "exec -T postgres psql" "$FAKEBIN/calls.log" \
    && ok "db_init memakai compose_exec postgres (psql -tAc)" \
    || fail "db_init tidak memakai compose_exec postgres (psql -tAc)"
  grep -q "exec -T -w /app -e PYTHONPATH=services elemes python -m alembic upgrade head" "$FAKEBIN/calls.log" \
    && ok "db_init memakai compose_exec elemes (alembic)" \
    || fail "db_init tidak memakai compose_exec elemes (alembic)"
  grep -q "restart elemes" "$FAKEBIN/calls.log" \
    && ok "first-run memakai compose_restart elemes" \
    || fail "first-run tidak memakai compose_restart elemes"
fi

# ===== 3) dbbackup: dump lewat compose_exec postgres (bukan lms-dev_postgres_1)
if ! OUT=$(run_elemes dbbackup); then
  fail "dbbackup tidak berjalan"
  echo "$OUT"
else
  DUMP=$(ls "$PARENT_DIR"/backups/elemes_*.sql 2>/dev/null | head -1 || true)
  if [ -n "$DUMP" ] && [ -s "$DUMP" ]; then
    ok "dbbackup menghasilkan file dump"
  else
    fail "dbbackup tidak menghasilkan file dump"
  fi
  grep -q "exec -T postgres pg_dump" "$FAKEBIN/calls.log" \
    && ok "dbbackup memakai compose_exec postgres (pg_dump)" \
    || fail "dbbackup tidak memakai compose_exec postgres (pg_dump)"
fi

# ===== 3b) dbupgrade / dbstatus / dbrestore juga memakai compose_exec =========
if ! OUT=$(run_elemes dbupgrade); then
  fail "dbupgrade tidak berjalan"
else
  grep -q "exec -T -w /app -e PYTHONPATH=services elemes python -m alembic upgrade head" "$FAKEBIN/calls.log" \
    && ok "dbupgrade memakai compose_exec elemes (alembic upgrade)" \
    || fail "dbupgrade tidak memakai compose_exec elemes (alembic upgrade)"
fi

if ! OUT=$(run_elemes dbstatus); then
  fail "dbstatus tidak berjalan"
else
  grep -q "exec -T -w /app -e PYTHONPATH=services elemes python -m alembic current" "$FAKEBIN/calls.log" \
    && ok "dbstatus memakai compose_exec elemes (alembic current)" \
    || fail "dbstatus tidak memakai compose_exec elemes (alembic current)"
fi

# dbrestore butuh file backup (buat dummy supaya tidak bergantung hasil dbbackup)
mkdir -p "$PARENT_DIR/backups"
touch "$PARENT_DIR/backups/elemes_20260101_000000.sql"
if ! OUT=$(run_elemes dbrestore); then
  fail "dbrestore tidak berjalan"
else
  grep -q "exec -T postgres psql.*DROP SCHEMA" "$FAKEBIN/calls.log" \
    && ok "dbrestore memakai compose_exec postgres (psql reset schema)" \
    || fail "dbrestore tidak memakai compose_exec postgres (psql reset schema)"
fi

# ===== 3c) exportall / importall memakai tag lms-* (bukan lms-c-*) ===========
if ! OUT=$(run_elemes exportall); then
  fail "exportall tidak berjalan"
else
  grep -q "build -t lms-backend:latest" "$FAKEBIN/calls.log" \
    && ok "exportall build tag lms-backend:latest" \
    || fail "exportall tidak build tag lms-backend:latest"
  grep -q "build -t lms-frontend:latest" "$FAKEBIN/calls.log" \
    && ok "exportall build tag lms-frontend:latest" \
    || fail "exportall tidak build tag lms-frontend:latest"
  grep -q "build -t lms-velxio:latest" "$FAKEBIN/calls.log" \
    && ok "exportall build tag lms-velxio:latest" \
    || fail "exportall tidak build tag lms-velxio:latest"
  grep -q "save lms-backend:latest lms-frontend:latest lms-velxio:latest" "$FAKEBIN/calls.log" \
    && ok "exportall save 3 image dengan tag lms-*" \
    || fail "exportall tidak save dengan tag lms-*"
  if [ -f "$WORKSPACE/lms-precompiled.tar" ]; then
    ok "exportall membuat file lms-precompiled.tar"
  else
    fail "exportall tidak membuat file lms-precompiled.tar"
  fi
fi

if ! OUT=$(run_elemes importall); then
  fail "importall tidak berjalan"
else
  grep -q "load -i lms-precompiled.tar" "$FAKEBIN/calls.log" \
    && ok "importall load dari lms-precompiled.tar" \
    || fail "importall tidak load dari lms-precompiled.tar"
fi

# ===== 4) Tidak boleh ada container name hard-coded / `podman exec` langsung
if grep -qE "lms-dev_|lms-sinau-c_|lms-c-|podman exec " "$ACCUM"; then
  fail "masih ada panggilan container name hard-coded / tag lama lms-c-:"
  grep -E "lms-dev_|lms-sinau-c_|lms-c-|podman exec " "$ACCUM" || true
else
  ok "tidak ada nama container hard-coded / tag lms-c- di semua panggilan"
fi

# ===== 5) Label filter memakai PROJECT_NAME dinamis
grep -q "label=io.podman.compose.project=$PROJECT_NAME" "$ACCUM" \
  && ok "label filter memakai PROJECT_NAME dinamis ($PROJECT_NAME)" \
  || fail "label filter tidak memakai PROJECT_NAME dinamis"

echo ""
if [ "$FAILED" -eq 0 ]; then
  echo "🎉 Semua regression test lulus (PROJECT_NAME=$PROJECT_NAME)"
else
  echo "💥 Ada test yang gagal"
  exit 1
fi
