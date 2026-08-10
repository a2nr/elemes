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
  # Ensure we are in the script directory so podman-compose finds the yaml file
  cd "$SCRIPT_DIR" || exit
  if [ "$VERBOSE" -eq 1 ]; then
    podman-compose -p "$PROJECT_NAME" --env-file "$PARENT_DIR/.env" "$@"
  else
    podman-compose -p "$PROJECT_NAME" --env-file "$PARENT_DIR/.env" "$@" >/dev/null 2>&1
  fi
}

# Variant of run_compose that NEVER suppresses output. Wajib dipakai oleh helper
# yang stdout/stderr-nya harus sampai ke pemanggil (output exec, config, ps).
run_compose_out() {
  # Ensure we are in the script directory so podman-compose finds the yaml file
  cd "$SCRIPT_DIR" || exit
  podman-compose -p "$PROJECT_NAME" --env-file "$PARENT_DIR/.env" "$@"
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

# First-run/health DB: tunggu PostgreSQL, migrasi schema (idempotent), lalu
# bootstrap akun guru otomatis bila TEACHER_TOKEN di .env tidak kosong.
db_init() {
  set -a
  source "$PARENT_DIR/.env" 2>/dev/null
  set +a
  local attempts=30 i fresh_schema=0

  # 1) Tunggu PostgreSQL siap (maks ~60 detik)
  for i in $(seq 1 "$attempts"); do
    if podman exec lms-dev_postgres_1 pg_isready \
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
  if [ "$(podman exec lms-dev_postgres_1 psql -U "${POSTGRES_USER:-elemes}" -d "${POSTGRES_DB:-elemes}" \
    -tAc "SELECT to_regclass('public.users') IS NULL")" = "t" ]; then
    fresh_schema=1
  fi

  # 2) Migrasi schema (idempotent)
  echo "🗄️  Migrasi database (alembic upgrade head)..."
  podman exec -w /app -e PYTHONPATH=services lms-dev_elemes_1 \
    python -m alembic upgrade head || {
    echo "⚠️  Migrasi database gagal. Jalankan ./elemes.sh dbupgrade untuk inspeksi."
    return 1
  }

  # 3) Bootstrap guru otomatis hanya bila TEACHER_TOKEN di .env tidak kosong
  #    (untuk prompt interaktif: gunakan ./elemes.sh teacher)
  if [ -n "$TEACHER_TOKEN" ]; then
    echo "👤 Bootstrap akun guru otomatis (dari TEACHER_TOKEN)..."
    printf '%s\n' "$TEACHER_TOKEN" | podman exec -i -w /app -e PYTHONPATH=/app \
      lms-dev_elemes_1 python scripts/bootstrap_teacher.py "${TEACHER_NAME:-Guru LMS}" || {
      echo "⚠️  Bootstrap guru gagal. Periksa TEACHER_TOKEN/TEACHER_NAME di .env, atau jalankan ./elemes.sh teacher."
    }
  fi

  # 4) First-run: restart backend sekali agar startup sync lesson registry
  #    berjalan setelah schema jadi (kalau tidak, tabel lessons kosong).
  if [ "$fresh_schema" -eq 1 ]; then
    echo "🔄 First-run terdeteksi; restart backend agar lesson registry ter-sync..."
    podman restart lms-dev_elemes_1 >/dev/null 2>&1
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
  podman image prune -f
  echo "🏗️  Membangun ulang container dari awal (no-cache)..."
  run_compose build --no-cache
  ;;&
runbuild)
  echo "🏗️  Membangun container..."
  run_compose build
  ;;&
runbuild | runclearbuild)
  echo "🚀 Menjalankan container di background..."
  run_compose up --force-recreate -d
  echo "✅ Elemes berhasil dijalankan!"
  db_init
  ;;
run)
  echo "🚀 Menjalankan container..."
  run_compose up -d
  echo "✅ Elemes berhasil dijalankan!"
  db_init
  ;;
exportall)
  echo "📦 === Mengekspor Semua Image (Pre-Compiled Bundle) ==="
  TAR_FILE="lms-c-precompiled.tar"
  cd "$SCRIPT_DIR" || exit

  echo "🏗️  1. Mem-build Backend Elemes..."
  podman build -t lms-c-backend:latest -f Dockerfile .

  echo "🏗️  2. Mem-build Frontend Elemes (SvelteKit)..."
  podman build -t lms-c-frontend:latest -f frontend/Dockerfile frontend/

  echo "🏗️  3. Mem-build Velxio Simulator..."
  podman build -t lms-c-velxio:latest -f velxio/Dockerfile.standalone --build-arg ENABLE_ESP32=${ENABLE_ESP32:-0} velxio/

  echo ""
  echo "🔍 Memverifikasi image yang berhasil di-build..."
  podman images | grep -E "lms-c-(backend|frontend|velxio)"
  echo ""

  echo "💾 Menyatukan semua image menjadi 1 file tar: $TAR_FILE..."
  podman save lms-c-backend:latest lms-c-frontend:latest lms-c-velxio:latest >"$TAR_FILE"

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
    echo "   ⚠️  Pastikan podman-compose.yml menggunakan image:"
    echo "      - lms-c-backend:latest (untuk service elemes)"
    echo "      - lms-c-frontend:latest (untuk service elemes-frontend)"
    echo "      - lms-c-velxio:latest (untuk service velxio)"
  else
    echo "❌ Export gagal."
  fi
  ;;
importall)
  echo "📦 === Mengimpor Semua Image (Pre-Compiled Bundle) ==="
  TAR_FILE="lms-c-precompiled.tar"

  if [ ! -f "$TAR_FILE" ]; then
    echo "❌ File $TAR_FILE tidak ditemukan!"
    echo "   Pastikan file sudah ada di direktori ini."
    exit 1
  fi

  echo "💾 Mengimpor image dari file $TAR_FILE..."
  podman load -i "$TAR_FILE"

  echo ""
  echo "🔍 Memverifikasi image yang berhasil di-load..."
  podman images | grep -E "lms-c-(backend|frontend|velxio)"
  echo ""

  echo "✅ Selesai! Image berhasil diimpor."
  echo "   Sekarang jalankan: ./elemes.sh run"
  ;;
verify)
  echo "🔍 === Memverifikasi Image Container ==="
  echo ""

  echo "📋 Image yang tersedia:"
  podman images | grep -E "lms-c-(backend|frontend|velxio)" || echo "   ⚠️  Tidak ada image lms-c yang ditemukan"
  echo ""

  echo "📋 Container yang sedang berjalan:"
  podman ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}" | grep -E "lms-dev" || echo "   ⚠️  Tidak ada container yang berjalan"
  echo ""

  echo "🔍 Memeriksa CMD tiap container..."
  for container in "lms-dev_elemes_1" "lms-dev_elemes-frontend_1" "lms-dev_velxio_1" "lms-dev_postgres_1"; do
    if podman ps --format "{{.Names}}" | grep -q "$container"; then
      CMD=$(podman inspect "$container" --format '{{.Config.Cmd}}' 2>/dev/null)
      ENTRYPOINT=$(podman inspect "$container" --format '{{.Config.Entrypoint}}' 2>/dev/null)
      IMAGE=$(podman inspect "$container" --format '{{.Image}}' 2>/dev/null)
      echo "  ✅ $container"
      echo "     Image: $IMAGE"
      echo "     Entrypoint: $ENTRYPOINT"
      echo "     Cmd: $CMD"
      echo ""
    else
      echo "  ⚠️  $container tidak ditemukan"
      echo ""
    fi
  done
  ;;
dbupgrade)
  echo "🗄️  Menjalankan migrasi database (alembic upgrade head)..."
  podman exec -w /app -e PYTHONPATH=services lms-dev_elemes_1 python -m alembic upgrade head
  ;;
dbstatus)
  echo "🗄️  Versi schema database (alembic current & heads):"
  podman exec -w /app -e PYTHONPATH=services lms-dev_elemes_1 python -m alembic current
  podman exec -w /app -e PYTHONPATH=services lms-dev_elemes_1 python -m alembic heads
  ;;
teacher)
  echo "👤 === Manajemen Akun Guru (upsert satu akun canonical) ==="
  if ! podman ps --format '{{.Names}}' | grep -q '^lms-dev_elemes_1$'; then
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
  printf '%s\n' "$TOKEN_INPUT" | podman exec -i -w /app -e PYTHONPATH=/app \
    lms-dev_elemes_1 python scripts/bootstrap_teacher.py "$NAME"
  ;;
dbbackup)
  echo "💾 Membackup database PostgreSQL → backups/"
  set -a; source "$PARENT_DIR/.env" 2>/dev/null; set +a
  mkdir -p "$PARENT_DIR/backups"
  OUT="$PARENT_DIR/backups/elemes_$(date +%Y%m%d_%H%M%S).sql"
  # --clean --if-exists: dump berisi DROP ... IF EXISTS supaya restore
  # ke DB yang sudah berisi data TIDAK bentrok (fix: dbrestore sebelumnya
  # gagal diam-diam karena CREATE TABLE/COPY kena duplicate key).
  podman exec lms-dev_postgres_1 pg_dump \
    -U "${POSTGRES_USER:-elemes}" -d "${POSTGRES_DB:-elemes}" \
    --clean --if-exists > "$OUT"
  echo "✅ Backup selesai: $OUT"
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
  podman exec lms-dev_postgres_1 psql \
    -U "${POSTGRES_USER:-elemes}" -d "${POSTGRES_DB:-elemes}" \
    -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" >/dev/null
  podman exec -i lms-dev_postgres_1 psql \
    -U "${POSTGRES_USER:-elemes}" -d "${POSTGRES_DB:-elemes}" < "$LATEST"
  echo "✅ Restore selesai. Bila daftar lesson kosong, jalankan ./elemes.sh run."
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
  echo "  ./elemes.sh loadtest       # Menjalankan utilitas simulasi Load Test (Locust)"
  ;;
esac

# Catat & tampilkan waktu eksekusi terakhir (setelah semua selesai)
{
  echo "command: $RUN_CMD"
  echo "time: $RUN_TIME"
} > "$LAST_RUN_FILE"
echo ""
echo "🕒 Selesai dijalankan: $RUN_TIME  (perintah: $RUN_CMD)"
