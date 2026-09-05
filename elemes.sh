#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"
EXAMPLES_DIR="$SCRIPT_DIR/examples"
PROJECT_NAME="$(basename "$PARENT_DIR")"

# Siapkan variabel waktu eksekusi (dicetak di akhir)
LAST_RUN_FILE="$SCRIPT_DIR/.last_run"
RUN_TIME="$(date '+%Y-%m-%d %H:%M:%S %Z')"
RUN_CMD="${*:-<kosong>}"

# Check for --verbose flag
VERBOSE=0
for arg in "$@"; do
  if [ "$arg" == "--verbose" ]; then
    VERBOSE=1
    break
  fi
done

# Function to run podman-compose quietly unless verbose
run_compose() {
  if [ "$VERBOSE" -eq 1 ]; then
    run_compose_out "$@"
  else
    run_compose_out "$@" >/dev/null 2>&1
  fi
}

# Baris noise yang dicetak podman-compose ke stderr: banner versi, echo
# perintah "podman exec ...", dan laporan "exit code: N". Difilter agar output
# CLI rapi; pakai --verbose untuk menampilkan semuanya.
NOISE_RE='^(podman-compose version:|\[.*--version.*\]$|using podman version:|podman exec |exit code: )'

# Variant of run_compose that NEVER suppresses output. Wajib dipakai oleh helper
# yang stdout/stderr-nya harus sampai ke pemanggil (output exec, config, ps).
# stdout dibiarkan utuh; stderr hanya difilter dari baris noise podman-compose.
run_compose_out() {
  # Ensure we are in the script directory so podman-compose finds the yaml file
  cd "$SCRIPT_DIR" || exit
  if [ "$VERBOSE" -eq 1 ]; then
    podman-compose -p "$PROJECT_NAME" --env-file "$PARENT_DIR/.env" "$@"
  else
    podman-compose -p "$PROJECT_NAME" --env-file "$PARENT_DIR/.env" "$@" \
      2> >(grep -v -E "$NOISE_RE" >&2)
  fi
}

# Jalankan perintah di dalam container service TANPA menyusun nama container.
# Opsi podman-compose exec (-w, -e, -u, ...) WAJIB ditulis SEBELUM nama service:
#   compose_exec elemes python -m alembic upgrade head
#   compose_exec -w /app -e PYTHONPATH=services elemes python -c '...'
# -T menonaktifkan pseudo-TTY (podman-compose exec mengalokasikan TTY secara
# default) sehingga perintah yang di-pipe/redirect berjalan tanpa TTY.
compose_exec() {
  run_compose_out exec -T "$@"
}

# Restart service container berdasarkan nama service.
compose_restart() {
  run_compose_out restart "$@"
}

# Helper untuk membaca nilai konfigurasi dari .env tanpa source
env_val() {
  grep -m1 "^${1}=" "$PARENT_DIR/.env" 2>/dev/null | cut -d= -f2-
}

# ── Velxio standalone compose helpers ────────────────────────
VELXIO_PROJECT="${PROJECT_NAME}-velxio"

run_velxio_compose() {
  cd "$SCRIPT_DIR" || exit
  if [ "$VERBOSE" -eq 1 ]; then
    podman-compose -p "$VELXIO_PROJECT" -f podman-compose.velxio.yml \
      --env-file "$PARENT_DIR/.env" "$@"
  else
    podman-compose -p "$VELXIO_PROJECT" -f podman-compose.velxio.yml \
      --env-file "$PARENT_DIR/.env" "$@" \
      2> >(grep -v -E "$NOISE_RE" >&2)
  fi
}

run_velxio_compose_quiet() {
  if [ "$VERBOSE" -eq 1 ]; then
    run_velxio_compose "$@"
  else
    run_velxio_compose "$@" >/dev/null 2>&1
  fi
}

# Daftar services elemes berdasarkan VELXIO_MODE.
# Return kosong = start all (local mode).
# Return daftar service = start hanya yang terdaftar (remote mode).
elemes_services() {
  local mode
  mode="$(env_val VELXIO_MODE)"
  mode="${mode:-local}"
  if [ "$mode" = "remote" ]; then
    echo "elemes-ts postgres elemes compiler-worker elemes-frontend flowchart"
  fi
}

# Generate lms-tail.json dari template berdasarkan VELXIO_MODE.
# Dipanggil sebelum container start agar Tailscale Serve config up-to-date.
generate_ts_config() {
  local template="$SCRIPT_DIR/config/lms-tail.json.template"
  local output="$SCRIPT_DIR/config/lms-tail.json"

  if [ ! -f "$template" ]; then
    return
  fi

  local mode
  mode="$(env_val VELXIO_MODE)"
  mode="${mode:-local}"

  if [ "$mode" = "remote" ]; then
    local velxio_host
    velxio_host="$(env_val VELXIO_HOST)"
    velxio_host="${velxio_host:-velxio-dev}"
    sed "s|__VELXIO_PROXY_TARGET__|http://${velxio_host}:80/|g" "$template" > "$output"
  else
    sed 's|__VELXIO_PROXY_TARGET__|http://127.0.0.1:80/|g' "$template" > "$output"
  fi
}

# First-run/health DB: tunggu PostgreSQL, migrasi schema (idempotent), lalu
# bootstrap akun guru otomatis bila TEACHER_TOKEN di .env tidak kosong.
db_init() {
  set -a
  source "$PARENT_DIR/.env" 2>/dev/null
  set +a
  local attempts=30 i fresh_schema=0

  # 1) Tunggu PostgreSQL siap (maks ~60 detik)
  for i in $(seq 1 "$attempts"); do
    if compose_exec postgres pg_isready \
      -U "${POSTGRES_USER:-elemes}" -d "${POSTGRES_DB:-elemes}" >/dev/null 2>&1; then
      break
    fi
    sleep 2
    if [ "$i" -eq "$attempts" ]; then
      echo "⚠️  PostgreSQL belum siap; migrasi & bootstrap dilewati. Jalankan ./elemes.sh dbupgrade nanti."
      return 1
    fi
  done

  # Catat apakah schema masih kosong (pertanda first-run / fresh install)
  if [ "$(compose_exec postgres psql -U "${POSTGRES_USER:-elemes}" -d "${POSTGRES_DB:-elemes}" \
    -tAc "SELECT to_regclass('public.users') IS NULL")" = "t" ]; then
    fresh_schema=1
  fi

  # 2) Migrasi schema (idempotent)
  echo "🗄️  Migrasi database (alembic upgrade head)..."
  compose_exec -w /app -e PYTHONPATH=services elemes \
    python -m alembic upgrade head || {
    echo "⚠️  Migrasi database gagal. Jalankan ./elemes.sh dbupgrade untuk inspeksi."
    return 1
  }

  # 3) Bootstrap guru otomatis hanya bila TEACHER_TOKEN di .env tidak kosong
  #    (untuk prompt interaktif: gunakan ./elemes.sh teacher)
  if [ -n "$TEACHER_TOKEN" ]; then
    echo "👤 Bootstrap akun guru otomatis (dari TEACHER_TOKEN)..."
    printf '%s\n' "$TEACHER_TOKEN" | compose_exec -w /app -e PYTHONPATH=/app \
      elemes python scripts/bootstrap_teacher.py "${TEACHER_NAME:-Guru LMS}" || {
      echo "⚠️  Bootstrap guru gagal. Periksa TEACHER_TOKEN/TEACHER_NAME di .env, atau jalankan ./elemes.sh teacher."
    }
  fi

  # 4) First-run: restart backend sekali agar startup sync lesson registry
  #    berjalan setelah schema jadi (kalau tidak, tabel lessons kosong).
  if [ "$fresh_schema" -eq 1 ]; then
    echo "🔄 First-run terdeteksi; restart backend agar lesson registry ter-sync..."
    compose_restart elemes >/dev/null 2>&1
  fi
}

case "$1" in
init)
  echo "✨ === Elemes Quick Start === ✨"
  echo ""

  # .env
  if [ -f "$PARENT_DIR/.env" ]; then
    echo "✅ [Skip] .env sudah ada"
  else
    cp "$EXAMPLES_DIR/../.env.example" "$PARENT_DIR/.env"
    echo "📝 [Buat] .env  (pastikan untuk edit sesuai kebutuhanmu)"
  fi

  # content/
  if [ -d "$PARENT_DIR/content" ] && [ "$(ls -A "$PARENT_DIR/content" 2>/dev/null)" ]; then
    echo "✅ [Skip] Folder content/ sudah ada"
  else
    mkdir -p "$PARENT_DIR/content"
    cp -rn "$EXAMPLES_DIR/content/"* "$PARENT_DIR/content/"
    echo "📁 [Buat] Folder content/  ($(find "$PARENT_DIR/content/" -name "*.md" 2>/dev/null | wc -l) materi contoh ditambahkan)"
  fi

  # assets/
  if [ -d "$PARENT_DIR/assets" ]; then
    echo "✅ [Skip] Folder assets/ sudah ada"
  else
    mkdir -p "$PARENT_DIR/assets"
    echo "📁 [Buat] Folder assets/  (untuk menyimpan file gambar/media)"
  fi

  # state/ (untuk Tailscale tun/state)
  if [ -d "$PARENT_DIR/state" ]; then
    echo "✅ [Skip] Folder state/ sudah ada"
  else
    mkdir -p "$PARENT_DIR/state"
    echo "🔐 [Buat] Folder state/  (untuk Tailscale credentials & state)"
  fi

  # state/velxio/ (untuk Tailscale credentials & state Velxio standalone)
  if [ -d "$PARENT_DIR/state/velxio" ]; then
    echo "✅ [Skip] Folder state/velxio/ sudah ada"
  else
    mkdir -p "$PARENT_DIR/state/velxio"
    echo "🔐 [Buat] Folder state/velxio/  (untuk Tailscale Velxio standalone)"
  fi

  generate_ts_config

  echo ""
  echo "🎯 Selesai! Langkah selanjutnya yang direkomendasikan:"
  echo "  👉 1. Edit file ../.env sesuai dengan kebutuhan environment-mu"
  echo "     (termasuk TEACHER_NAME / TEACHER_TOKEN untuk akun guru)"
  echo "  👉 2. Edit ../content/home.md untuk menyusun daftar materi"
  echo "  👉 3. Jalankan ./elemes.sh teacher untuk membuat/update akun guru"
  echo "  🚀 4. Jalankan:  ./elemes.sh runbuild"
  echo ""
  ;;
stop | run | runbuild | runclearbuild)
  echo "🛑 Menghentikan container yang sedang berjalan..."
  run_compose down
  ;;&
stop)
  echo "✅ Container berhasil dihentikan."
  ;;
runclearbuild)
  echo "🧹 Membersihkan container dan image (prune)..."
  podman image prune -f -a
  echo "🏗️  Membangun ulang container dari awal (no-cache)..."
  run_compose build --no-cache
  ;;&
runbuild)
  echo "🏗️  Membangun container..."
  run_compose build
  ;;&
runbuild | runclearbuild)
  echo "🚀 Menjalankan container di background..."
  generate_ts_config
  SERVICES=$(elemes_services)
  if [ -n "$SERVICES" ]; then
    echo "   ℹ️  VELXIO_MODE=remote → Velxio tidak dijalankan secara lokal"
    run_compose up --force-recreate -d $SERVICES
  else
    run_compose up --force-recreate -d
  fi
  echo "✅ Elemes berhasil dijalankan!"
  db_init
  ;;&
runbuild | runclearbuild)
  # Verifikasi tes sub-home setelah build bersih (runclearbuild) — memakai
  # fake DATABASE_URL kosong agar tes yang butuh PostgreSQL di-skip dan tidak
  # mengubah data produksi. Gagal bila ada tes baru yang rusak.
  if [ "$1" = "runclearbuild" ]; then
    echo "🧪 Verifikasi: unit & API test sub-home..."
    if ! compose_exec -w /app -e PYTHONPATH=services -e DATABASE_URL= \
      elemes python -m pytest -m unit -q; then
      echo "❌ Unit test gagal. Periksa output di atas sebelum deploy."
      exit 1
    fi
    if ! compose_exec -w /app -e PYTHONPATH=services -e DATABASE_URL= \
      elemes python -m pytest services/tests/test_sub_home.py services/tests/test_sub_home_api.py -q; then
      echo "❌ Tes sub-home gagal. Periksa output di atas sebelum deploy."
      exit 1
    fi
    echo "✅ Tes sub-home lulus."
  fi
  ;;
run)
  echo "🚀 Menjalankan container..."
  generate_ts_config
  SERVICES=$(elemes_services)
  if [ -n "$SERVICES" ]; then
    echo "   ℹ️  VELXIO_MODE=remote → Velxio tidak dijalankan secara lokal"
    run_compose up -d $SERVICES
  else
    run_compose up -d
  fi
  echo "✅ Elemes berhasil dijalankan!"
  db_init
  ;;
test-unit)
  echo "🧪 Menjalankan unit test (cepat, no DB)..."
  compose_exec -w /app -e PYTHONPATH=services -e DATABASE_URL= \
    elemes python -m pytest -m unit -v
  ;;
test-integration)
  echo "🧪 Menjalankan integration test (butuh DATABASE_URL)..."
  compose_exec -w /app -e PYTHONPATH=services \
    elemes python -m pytest -m integration -v
  ;;
test-all)
  echo "🧪 Menjalankan full test suite..."
  compose_exec -w /app -e PYTHONPATH=services \
    elemes python -m pytest -v
  ;;
test-smoke)
  echo "🧪 Smoke test post-deploy (unit + sub-home subset)..."
  compose_exec -w /app -e PYTHONPATH=services -e DATABASE_URL= \
    elemes python -m pytest -m unit -v
  compose_exec -w /app -e PYTHONPATH=services -e DATABASE_URL= \
    elemes python -m pytest services/tests/test_sub_home.py services/tests/test_sub_home_api.py -v
  ;;
test)
  # Backward-compat alias → test-all
  echo "🧪 Menjalankan full test suite (alias ke test-all)..."
  compose_exec -w /app -e PYTHONPATH=services \
    elemes python -m pytest -v
  ;;
exportall)
  echo "📦 === Mengekspor Semua Image (Pre-Compiled Bundle) ==="
  TAR_FILE="lms-precompiled.tar"
  cd "$SCRIPT_DIR" || exit

  echo "🏗️  1. Mem-build Backend Elemes..."
  podman build -t lms-backend:latest -f Dockerfile .

  echo "🏗️  2. Mem-build Frontend Elemes (SvelteKit)..."
  podman build -t lms-frontend:latest -f frontend/Dockerfile frontend/

  echo "🏗️  3. Mem-build Velxio Simulator..."
  podman build -t lms-velxio:latest -f velxio/Dockerfile.standalone --build-arg ENABLE_ESP32=${ENABLE_ESP32:-0} velxio/

  echo ""
  echo "🔍 Memverifikasi image yang berhasil di-build..."
  podman images | grep -E "lms-(backend|frontend|velxio)"
  echo ""

  echo "💾 Menyatukan semua image menjadi 1 file tar: $TAR_FILE..."
  podman save lms-backend:latest lms-frontend:latest lms-velxio:latest >"$TAR_FILE"

  if [ $? -eq 0 ]; then
    FILESIZE=$(du -h "$TAR_FILE" | cut -f1)
    echo "✅ Selesai! File '$TAR_FILE' siap di-upload ke VPS."
    echo "   📦 Ukuran file: $FILESIZE"
    echo ""
    echo "   📋 Cara deploy di VPS:"
    echo "   1. Upload file: scp $TAR_FILE user@vps:/path/lms-dev/elemes/"
    echo "   2. Load image:  podman load -i $TAR_FILE"
    echo "   3. Jalankan:    podman-compose up -d"
    echo ""
    echo "   ⚠️  Tag image bundle sudah sama dengan podman-compose.yml:"
    echo "      - lms-backend:latest (untuk service elemes)"
    echo "      - lms-frontend:latest (untuk service elemes-frontend)"
    echo "      - lms-velxio:latest (untuk service velxio)"
    echo "   ℹ️  Service compiler-worker & flowchart TIDAK ikut bundle — di VPS"
    echo "      image-nya di-build otomatis oleh podman-compose dari source (build:);"
    echo "      pastikan folder source ikut ter-upload, atau jalankan: ./elemes.sh runbuild"
  else
    echo "❌ Export gagal."
  fi
  ;;
importall)
  echo "📦 === Mengimpor Semua Image (Pre-Compiled Bundle) ==="
  TAR_FILE="lms-precompiled.tar"

  if [ ! -f "$TAR_FILE" ]; then
    echo "❌ File $TAR_FILE tidak ditemukan!"
    echo "   Pastikan file sudah ada di direktori ini (nama default: lms-precompiled.tar)."
    exit 1
  fi

  echo "💾 Mengimpor image dari file $TAR_FILE..."
  podman load -i "$TAR_FILE"

  echo ""
  echo "🔍 Memverifikasi image yang berhasil di-load..."
  podman images | grep -E "lms-(backend|frontend|velxio)"
  echo ""

  echo "✅ Selesai! Image berhasil diimpor."
  echo "   Sekarang jalankan: ./elemes.sh run"
  ;;
verify)
  echo "🔍 === Memverifikasi Image Container ==="
  echo ""

  # 1) Service -> image tag dari compose config. Resolusi via podman-compose
  #    sehingga TIDAK tergantung nama direktori parent / PROJECT_NAME.
  declare -A SERVICE_IMAGE_TAG
  COMPOSE_CONFIG=$(run_compose_out config 2>/dev/null)
  while IFS= read -r svc; do
    [ -z "$svc" ] && continue
    SERVICE_IMAGE_TAG["$svc"]=$(printf '%s\n' "$COMPOSE_CONFIG" | awk -v s="$svc" '
      $0 ~ "^  " s ":" { in_svc=1; next }
      in_svc && /^  [A-Za-z0-9_.-]+:$/ && $0 !~ "^  " s ":$" { in_svc=0 }
      in_svc && /^    image:/ { sub(/^    image: */, ""); gsub(/[" ]/, "", $0); print; exit }
    ')
  done < <(run_compose_out config --services 2>/dev/null)

  echo "📋 Service yang didefinisikan di podman-compose.yml:"
  for svc in "${!SERVICE_IMAGE_TAG[@]}"; do
    printf "   %s → %s\n" "$svc" "${SERVICE_IMAGE_TAG[$svc]:-<tanpa image:>}"
  done
  echo ""

  # 2) Container milik project ini (ditemukan via label io.podman.compose.project)
  #    + deteksi image STALE: ImageID container != ImageID tag saat ini.
  echo "📋 Container project '$PROJECT_NAME':"
  CONTAINERS=$(podman ps -a \
    --filter "label=io.podman.compose.project=$PROJECT_NAME" \
    --format '{{.Names}}|{{.Image}}|{{.ImageID}}|{{.Status}}|{{.Labels}}' 2>/dev/null)
  if [ -z "$CONTAINERS" ]; then
    echo "   ⚠️  Tidak ada container untuk project '$PROJECT_NAME' (jalankan ./elemes.sh run dulu)"
  else
    while IFS='|' read -r cname cimage cid cstatus clabels; do
      svc=$(printf '%s' "$clabels" | sed -n 's/.*com.docker.compose.service[:=]\([^ ,}]*\).*/\1/p')
      tag="${SERVICE_IMAGE_TAG[$svc]}"
      stale=""
      if [ -n "$tag" ]; then
        tag_iid=$(podman images "$tag" --noheading --format '{{.ID}}' 2>/dev/null | head -1)
        if [ -n "$tag_iid" ] && [ -n "$cid" ] && [ "${cid:0:12}" != "${tag_iid:0:12}" ]; then
          stale=" ⚠️ STALE (container:$cid != image:$tag_iid)"
        fi
      fi
      printf "   • %s\n" "$cname"
      printf "     image: %s  (status: %s)%s\n" "$cimage" "$cstatus" "$stale"
    done <<< "$CONTAINERS"
  fi
  echo ""

  # 3) CMD/Entrypoint tiap service (ditemukan via label project + service)
  echo "🔍 Memeriksa CMD/Entrypoint tiap service..."
  while IFS= read -r svc; do
    [ -z "$svc" ] && continue
    cid=$(podman ps -a \
      --filter "label=io.podman.compose.project=$PROJECT_NAME" \
      --filter "label=com.docker.compose.service=$svc" \
      --format '{{.ID}}' 2>/dev/null | head -1)
    if [ -n "$cid" ]; then
      CMD=$(podman inspect "$cid" --format '{{.Config.Cmd}}' 2>/dev/null)
      ENTRYPOINT=$(podman inspect "$cid" --format '{{.Config.Entrypoint}}' 2>/dev/null)
      IMAGE=$(podman inspect "$cid" --format '{{.Image}}' 2>/dev/null)
      echo "   ✅ $svc ($cid)"
      echo "      Image: $IMAGE"
      echo "      Entrypoint: $ENTRYPOINT"
      echo "      Cmd: $CMD"
    else
      echo "   ⚠️  $svc tidak ditemukan (container belum dibuat)"
    fi
    echo ""
  done < <(run_compose_out config --services 2>/dev/null)
  ;;
dbupgrade)
  echo "🗄️  Menjalankan migrasi database (alembic upgrade head)..."
  compose_exec -w /app -e PYTHONPATH=services elemes python -m alembic upgrade head
  ;;
dbstatus)
  echo "🗄️  Versi schema database (alembic current & heads):"
  compose_exec -w /app -e PYTHONPATH=services elemes python -m alembic current
  compose_exec -w /app -e PYTHONPATH=services elemes python -m alembic heads
  ;;
teacher)
  echo "👤 === Manajemen Akun Guru (upsert satu akun canonical) ==="
  # Cek container service elemes via label filter (bukan nama container hard-coded)
  if ! podman ps \
    --filter "label=io.podman.compose.project=$PROJECT_NAME" \
    --filter "label=com.docker.compose.service=elemes" \
    --format '{{.Names}}' 2>/dev/null | grep -q .; then
    echo "❌ Container backend belum berjalan. Jalankan ./elemes.sh run dulu."
    exit 1
  fi

  # Nama default dari .env (TEACHER_NAME), fallback "Guru LMS"
  DEFAULT_NAME="Guru LMS"
  if [ -f "$PARENT_DIR/.env" ]; then
    set -a; source "$PARENT_DIR/.env" 2>/dev/null; set +a
    if [ -n "$TEACHER_NAME" ]; then
      DEFAULT_NAME="$TEACHER_NAME"
    fi
  fi

  # Prompt nama (Enter = pakai default dari .env)
  printf 'Nama guru [%s]: ' "$DEFAULT_NAME"
  read -r NAME_INPUT
  NAME="${NAME_INPUT:-$DEFAULT_NAME}"
  if [ -z "$NAME" ]; then
    echo "❌ Nama guru tidak boleh kosong."
    exit 1
  fi

  # Prompt token tersembunyi (tidak muncul di process list/history)
  printf 'Token guru: '
  read -r -s TOKEN_INPUT
  echo ""
  if [ -z "$TOKEN_INPUT" ]; then
    echo "❌ Token guru tidak boleh kosong."
    exit 1
  fi

  # Upsert via bootstrap_teacher: buat bila belum ada, UPDATE bila sudah ada
  # (jumlah akun guru selalu tetap satu; token lama di-revoke saat rotasi).
  printf '%s\n' "$TOKEN_INPUT" | compose_exec -w /app -e PYTHONPATH=/app \
    elemes python scripts/bootstrap_teacher.py "$NAME"
  ;;
dbbackup)
  echo "💾 Membackup database PostgreSQL → backups/"
  set -a; source "$PARENT_DIR/.env" 2>/dev/null; set +a
  mkdir -p "$PARENT_DIR/backups"
  OUT="$PARENT_DIR/backups/elemes_$(date +%Y%m%d_%H%M%S).sql"
  # --clean --if-exists: dump berisi DROP ... IF EXISTS supaya restore
  # ke DB yang sudah berisi data TIDAK bentrok (fix: dbrestore sebelumnya
  # gagal diam-diam karena CREATE TABLE/COPY kena duplicate key).
  if compose_exec postgres pg_dump \
    -U "${POSTGRES_USER:-elemes}" -d "${POSTGRES_DB:-elemes}" \
    --clean --if-exists > "$OUT"; then
    echo "✅ Backup selesai: $OUT"
  else
    echo "❌ Backup gagal (lihat error di atas)."
    rm -f "$OUT"
    exit 1
  fi
  ;;
dbrestore)
  set -a; source "$PARENT_DIR/.env" 2>/dev/null; set +a
  LATEST=$(ls -t "$PARENT_DIR"/backups/elemes_*.sql 2>/dev/null | head -1)
  if [ -z "$LATEST" ]; then
    echo "❌ Tidak ada backup di backups/elemes_*.sql"
    exit 1
  fi
  echo "♻️  Restore backup: $LATEST"
  # Reset schema dulu — backup lama (tanpa --clean) tidak berisi DROP,
  # sehingga restore ke DB berisi data bakal bentrok duplicate key.
  compose_exec postgres psql \
    -U "${POSTGRES_USER:-elemes}" -d "${POSTGRES_DB:-elemes}" \
    -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" >/dev/null
  compose_exec postgres psql \
    -U "${POSTGRES_USER:-elemes}" -d "${POSTGRES_DB:-elemes}" < "$LATEST"
  echo "✅ Restore selesai. Bila daftar lesson kosong, jalankan ./elemes.sh run."
  ;;
test-worker)
  echo "🧪 Menjalankan compiler worker test suite..."
  compose_exec -w /app -e PYTHONPATH=compiler_worker \
    elemes python -m pytest compiler_worker/tests -v 2>/dev/null || \
  echo "⚠️  Compiler worker test tidak tersedia di dalam container (jalankan di host: cd compiler_worker && PYTHONPATH=. python -m pytest -v)"
  ;;
docs-validate)
  echo "📄 Validasi dokumentasi (frontmatter + broken link)..."
  compose_exec -w /app -e PYTHONPATH=services \
    elemes python scripts/validate_docs.py
  ;;
velxio-stop | velxio-run | velxio-runbuild)
  echo "🛑 Menghentikan Velxio standalone..."
  run_velxio_compose_quiet down
  ;;&
velxio-stop)
  echo "✅ Velxio standalone dihentikan."
  ;;
velxio-runbuild)
  echo "🏗️  Membangun Velxio standalone image..."
  run_velxio_compose build
  ;;&
velxio-run)
  if ! podman image exists lms-velxio-standalone:latest 2>/dev/null; then
    echo "⚠️  Image 'lms-velxio-standalone:latest' belum dibangun."
    echo "   Jalankan: ./elemes.sh velxio-runbuild"
    exit 1
  fi
  ;;&
velxio-runbuild | velxio-run)
  echo "🚀 Menjalankan Velxio standalone di background..."
  run_velxio_compose up -d
  echo "✅ Velxio standalone berhasil dijalankan!"
  echo ""
  VH="$(env_val VELXIO_HOST)"
  VH="${VH:-velxio-dev}"
  echo "📡 Velxio standalone info:"
  echo "   Tailscale hostname : $VH"
  echo "   Port internal      : 80 (Nginx → FastAPI :8001)"
  echo ""
  echo "💡 Untuk menghubungkan Elemes ke Velxio ini, set di .env mesin Elemes:"
  echo "   VELXIO_MODE=remote"
  echo "   VELXIO_HOST=$VH"
  echo "   VELXIO_COMPILER_URL=http://$VH:80/api/compile/"
  ;;
velxio-status)
  echo "📊 === Status Velxio ==="
  MODE="$(env_val VELXIO_MODE)"
  MODE="${MODE:-local}"
  echo "   Mode: $MODE"

  if [ "$MODE" = "local" ]; then
    echo "   Velxio berjalan dalam compose utama (bundled)"
    if podman ps --filter "label=io.podman.compose.project=$PROJECT_NAME" \
       --filter "label=com.docker.compose.service=velxio" \
       --format '{{.Names}} — {{.Status}}' 2>/dev/null | grep -q .; then
      echo "   ✅ Container:"
      podman ps --filter "label=io.podman.compose.project=$PROJECT_NAME" \
        --filter "label=com.docker.compose.service=velxio" \
        --format '      {{.Names}} — {{.Status}}'
    else
      echo "   ⚠️  Container: not running"
    fi
  else
    echo "   Velxio berjalan terpisah (remote)"
    VURL="$(env_val VELXIO_COMPILER_URL)"
    echo "   VELXIO_COMPILER_URL: ${VURL:-<belum diset>}"
    if podman ps --filter "label=io.podman.compose.project=$VELXIO_PROJECT" \
       --format '{{.Names}}' 2>/dev/null | grep -q .; then
      echo "   ✅ Standalone container (lokal):"
      podman ps --filter "label=io.podman.compose.project=$VELXIO_PROJECT" \
        --format '      {{.Names}} — {{.Status}}'
    else
      echo "   ℹ️  Tidak ada standalone container lokal (Velxio berjalan di mesin remote)"
    fi
    if [ -n "$VURL" ]; then
      HEALTH_URL=$(echo "$VURL" | sed 's|/api/compile.*|/health|')
      echo -n "   🔍 Health check ($HEALTH_URL)... "
      if curl -sf --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
        echo "✅ reachable"
      else
        echo "❌ unreachable"
      fi
    fi
  fi
  ;;
velxio-test)
  echo "🧪 Menjalankan test suite modul Velxio (Frontend Vitest)..."
  if [ -d "$SCRIPT_DIR/velxio/frontend" ]; then
    (cd "$SCRIPT_DIR/velxio/frontend" && npx vitest run "${@:2}")
  else
    echo "❌ Direktori velxio/frontend tidak ditemukan."
    exit 1
  fi
  ;;
*)
  echo "💡 Cara Penggunaan elemes.sh:"
  echo "  ./elemes.sh init           # Inisialisasi konfigurasi, folder, & template .env"
  echo "  ./elemes.sh run            # Menjalankan container LMS yang sudah ada"
  echo "  ./elemes.sh runbuild       # Build image lalu jalankan container"
  echo "  ./elemes.sh runclearbuild  # Bersihkan cache, Re-build total, lalu jalankan"
  echo "  ./elemes.sh stop           # Menghentikan container yang sedang berjalan"
  echo "  ./elemes.sh exportall      # Build & Export semua image LMS (Backend, Frontend, Velxio) jadi satu file tar"
  echo "  ./elemes.sh importall      # Import image dari file tar (untuk deployment di VPS)"
  echo "  ./elemes.sh verify         # Verifikasi image dan konfigurasi container"
  echo "  ./elemes.sh dbupgrade      # Jalankan migrasi schema (alembic upgrade head)"
  echo "  ./elemes.sh dbstatus       # Lihat versi schema database"
  echo "  ./elemes.sh teacher        # Buat/update akun guru (upsert, prompt nama & token)"
  echo "  ./elemes.sh dbbackup       # Backup database → backups/elemes_<ts>.sql"
  echo "  ./elemes.sh dbrestore      # Restore backup terbaru dari backups/"
  echo "  ./elemes.sh test           # Jalankan full test suite (alias ke test-all)"
  echo "  ./elemes.sh test-unit       # Unit test saja (cepat, no DB)"
  echo "  ./elemes.sh test-integration # Integration test (butuh PostgreSQL test DB)"
  echo "  ./elemes.sh test-all       # Full test suite (CI gate)"
  echo "  ./elemes.sh test-smoke     # Smoke test post-deploy (unit + sub-home subset)"
  echo "  ./elemes.sh test-worker    # Compiler worker test suite"
  echo "  ./elemes.sh docs-validate   # Validasi frontmatter & broken link di docs/*.md"
  echo "  ./elemes.sh loadtest       # Menjalankan utilitas simulasi Load Test (Locust)"
  echo ""
  echo "📡 Velxio Modular:"
  echo "  ./elemes.sh velxio-run      # Jalankan Velxio standalone (reuse image)"
  echo "  ./elemes.sh velxio-runbuild # Build lalu jalankan Velxio standalone"
  echo "  ./elemes.sh velxio-stop     # Hentikan Velxio standalone"
  echo "  ./elemes.sh velxio-status   # Cek status & health Velxio (local/remote)"
  echo "  ./elemes.sh velxio-test     # Jalankan test suite modul Velxio (terpisah)"
  ;;
esac

# Catat & tampilkan waktu eksekusi terakhir (setelah semua selesai)
{
  echo "command: $RUN_CMD"
  echo "time: $RUN_TIME"
} > "$LAST_RUN_FILE"
echo ""
echo "🕒 Selesai dijalankan: $RUN_TIME  (perintah: $RUN_CMD)"
