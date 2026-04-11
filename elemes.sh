#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"
EXAMPLES_DIR="$SCRIPT_DIR/examples"
PROJECT_NAME="$(basename "$PARENT_DIR")"

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
    cp -n "$EXAMPLES_DIR/content/"*.md "$PARENT_DIR/content/"
    echo "📁 [Buat] Folder content/  ($(ls "$PARENT_DIR/content/"*.md 2>/dev/null | wc -l) materi contoh ditambahkan)"
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

  # tokens
  if [ -f "$PARENT_DIR/tokens_siswa.csv" ]; then
    echo "✅ [Skip] tokens_siswa.csv sudah ada"
  else
    cp "$EXAMPLES_DIR/tokens_siswa.csv" "$PARENT_DIR/tokens_siswa.csv"
    echo "👥 [Buat] tokens_siswa.csv  (edit untuk menambah data siswa asli)"
  fi

  echo ""
  echo "🎯 Selesai! Langkah selanjutnya yang direkomendasikan:"
  echo "  👉 1. Edit file ../.env sesuai dengan kebutuhan environment-mu"
  echo "  👉 2. Edit ../content/home.md untuk menyusun daftar materi"
  echo "  👉 3. Edit ../tokens_siswa.csv untuk mendaftarkan akun siswa"
  echo "  🚀 4. Jalankan:  ./elemes.sh runbuild"
  echo ""
  ;;
stop | run | runbuild | runclearbuild)
  echo "🛑 Menghentikan container yang sedang berjalan..."
  podman-compose -p "$PROJECT_NAME" --env-file ../.env down
  ;;&
stop) 
  echo "✅ Container berhasil dihentikan."
  ;;
runclearbuild)
  echo "🧹 Membersihkan container dan image (prune)..."
  podman image prune -f
  echo "🏗️  Membangun ulang container dari awal (no-cache)..."
  podman-compose -p "$PROJECT_NAME" --env-file ../.env build --no-cache
  ;;&
runbuild)
  echo "🏗️  Membangun container..."
  podman-compose -p "$PROJECT_NAME" --env-file ../.env build
  ;;&
runbuild | runclearbuild)
  echo "🚀 Menjalankan container di background..."
  podman-compose -p "$PROJECT_NAME" --env-file ../.env up --force-recreate -d
  echo "✅ Elemes berhasil dijalankan!"
  ;;
run)
  echo "🚀 Menjalankan container..."
  podman-compose -p "$PROJECT_NAME" --env-file ../.env up -d
  echo "✅ Elemes berhasil dijalankan!"
  ;;
generatetoken)
  echo "🔄 Melakukan sinkronisasi tokens_siswa.csv dari materi yang ada..."
  python3 "$SCRIPT_DIR/generate_tokens.py"
  ;;
loadtest)
  echo "📊 === Elemes Load Testing ==="
  cd "$SCRIPT_DIR/load-test" || exit

  if [ ! -d "env" ]; then
    echo "⚙️  Membuat Python Virtual Environment (env/)..."
    python3 -m venv env
  fi

  echo "⚙️  Mengaktifkan environment & menginstall requirements..."
  source env/bin/activate
  pip install -r requirements.txt > /dev/null 2>&1

  echo "⚙️  Mempersiapkan Test Data & menginjeksi akun Bot..."
  python3 content_parser.py --num-tokens 50

  echo ""
  echo "🚀 Memulai Locust Test Suite..."
  echo "👉 Buka http://localhost:8089 di browser web milikmu."
  echo "👉 Masukkan URL backend Elemes sebagai Host (contoh: http://localhost:5000)"
  echo "👉 Tekan CTRL+C di terminal ini untuk menghentikan test."
  echo ""
  
  locust -f locustfile.py
  ;;
*)
  echo "💡 Cara Penggunaan elemes.sh:"
  echo "  ./elemes.sh init           # Inisialisasi konfigurasi, folder, & data tokens"
  echo "  ./elemes.sh run            # Menjalankan container LMS yang sudah ada"
  echo "  ./elemes.sh runbuild       # Build image lalu jalankan container"
  echo "  ./elemes.sh runclearbuild  # Bersihkan cache, Re-build total, lalu jalankan"
  echo "  ./elemes.sh stop           # Menghentikan container yang sedang berjalan"
  echo "  ./elemes.sh generatetoken  # Sinkronisasi kolom tokens CSV sesuai file markdown"
  echo "  ./elemes.sh loadtest       # Menjalankan utilitas simulasi Load Test (Locust)"
  ;;
esac
