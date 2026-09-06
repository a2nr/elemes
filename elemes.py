#!/usr/bin/env python3
"""
Elemes LMS Management Suite (Cross-Platform CLI & Interactive TUI)
Multi-OS compatible: Linux, macOS, Windows.
Default virtualenv: PARENT_DIR / "venv" (keeps elemes/ directory clean).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
PARENT_DIR = SCRIPT_DIR.parent
REQUIREMENTS_CLI = SCRIPT_DIR / "requirements-cli.txt"


def ensure_parent_venv() -> None:
    """
    Ensure the orchestrator runs inside the parent virtualenv (../venv).
    Keeps the elemes/ directory completely clean while ensuring dependencies.
    """
    if os.environ.get("ELEMES_NO_VENV") == "1":
        return

    # Check for existing venv in parent directory
    venv_dir = PARENT_DIR / ".venv" if (PARENT_DIR / ".venv").is_dir() else PARENT_DIR / "venv"
    if sys.platform == "win32":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    # 1. Check if we are already running inside that virtualenv
    try:
        is_in_venv = venv_python.is_file() and (
            Path(sys.executable).resolve() == venv_python.resolve()
        )
    except Exception:
        is_in_venv = False

    if is_in_venv:
        # We are inside the parent venv. Ensure rich is installed.
        try:
            import rich  # noqa: F401
        except ImportError:
            print(f"📦 Memasang dependensi CLI ({REQUIREMENTS_CLI.name}) ke {venv_dir.name}...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-r", str(REQUIREMENTS_CLI)],
                check=False,
            )
        return

    # 2. Not running in parent venv: Create if missing
    if not venv_python.is_file():
        print(f"📦 Menyiapkan virtualenv di {venv_dir.name}/ (parent folder agar elemes tetap bersih)...")
        try:
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        except Exception as e:
            print(f"⚠️ Gagal membuat virtualenv: {e}")
            return

    # 3. Ensure rich is installed in the target venv
    res = subprocess.run(
        [str(venv_python), "-c", "import rich"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if res.returncode != 0 and REQUIREMENTS_CLI.is_file():
        print(f"📦 Memasang dependensi CLI (rich) ke {venv_dir.name}...")
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", "-q", "-r", str(REQUIREMENTS_CLI)],
            check=False,
        )

    # 4. Re-execute the script using the parent virtualenv's Python
    try:
        os.execv(str(venv_python), [str(venv_python), *sys.argv])
    except Exception as e:
        print(f"⚠️ Gagal beralih ke virtualenv {venv_python}: {e}")


# Run bootstrap before importing any CLI/TUI modules
ensure_parent_venv()

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cli.commands import (
    cmd_dbbackup,
    cmd_dbrestore,
    cmd_dbstatus,
    cmd_dbupgrade,
    cmd_docs_validate,
    cmd_exportall,
    cmd_importall,
    cmd_init,
    cmd_run,
    cmd_runbuild,
    cmd_runclearbuild,
    cmd_stop,
    cmd_stopclean,
    cmd_teacher,
    cmd_test_all,
    cmd_test_integration,
    cmd_test_smoke,
    cmd_test_unit,
    cmd_test_worker,
    cmd_velxio_run,
    cmd_velxio_runbuild,
    cmd_velxio_status,
    cmd_velxio_stop,
    cmd_velxio_test,
    cmd_verify,
)
from cli.config import is_verbose, record_last_run, set_verbose
from cli.tui import launch_tui


def print_help() -> None:
    help_text = """💡 Cara Penggunaan elemes:
  ./elemes.sh [perintah]     (Linux/macOS)
  elemes.bat [perintah]      (Windows CMD)
  .\\elemes.ps1 [perintah]     (Windows PowerShell)
  python elemes.py [perintah]

🖥️  TUI Mode:
  ./elemes.sh                # Buka Interactive Modern TUI Menu
  ./elemes.sh menu           # Buka Interactive Modern TUI Menu

🚀 Server & Container:
  init                       # Inisialisasi konfigurasi, folder, & template .env
  run                        # Menjalankan container LMS yang sudah ada
  runbuild                   # Build image lalu jalankan container
  runclearbuild              # Bersihkan cache, Re-build total, lalu jalankan
  stop                       # Menghentikan container yang sedang berjalan
  stopclean                  # Hentikan container lalu bersihkan stopped container & image tak terpakai
  verify                     # Verifikasi image dan konfigurasi container

🗄️ Database & Users:
  dbupgrade                  # Jalankan migrasi schema (alembic upgrade head)
  dbstatus                   # Lihat versi schema database
  teacher                    # Buat/update akun guru (upsert, prompt nama & token)
  dbbackup                   # Backup database → backups/elemes_<ts>.sql
  dbrestore                  # Restore backup terbaru dari backups/

🧪 Testing & Quality:
  test                       # Jalankan full test suite (alias ke test-all)
  test-unit                  # Unit test saja (cepat, no DB)
  test-integration           # Integration test (butuh PostgreSQL test DB)
  test-all                   # Full test suite (CI gate)
  test-smoke                 # Smoke test post-deploy (unit + sub-home subset)
  test-worker                # Compiler worker test suite
  docs-validate              # Validasi frontmatter & broken link di docs/*.md

📦 Deployment & Bundle:
  exportall                  # Build & Export semua image LMS jadi satu file tar
  importall                  # Import image dari file tar (untuk deployment di VPS)

📡 Velxio Modular:
  velxio-run                 # Jalankan Velxio standalone (reuse image)
  velxio-runbuild            # Build lalu jalankan Velxio standalone
  velxio-stop                # Hentikan Velxio standalone
  velxio-status              # Cek status & health Velxio (local/remote)
  velxio-test                # Jalankan test suite modul Velxio (terpisah)
"""
    print(help_text)


def main() -> int:
    raw_args = sys.argv[1:]
    verbose = False
    args: list[str] = []

    for a in raw_args:
        if a in ("--verbose", "-v"):
            verbose = True
            set_verbose(True)
        else:
            args.append(a)

    # If no subcommand is provided or 'menu' / '--menu', launch interactive TUI
    if not args or args[0] in ("menu", "--menu", "-m"):
        launch_tui()
        return 0

    command = args[0].lower()
    run_cmd = " ".join(raw_args)
    ret = 0

    if command in ("help", "--help", "-h"):
        print_help()
        return 0
    elif command == "init":
        ret = cmd_init(verbose=verbose)
    elif command == "run":
        ret = cmd_run(verbose=verbose)
    elif command == "runbuild":
        ret = cmd_runbuild(verbose=verbose)
    elif command == "runclearbuild":
        ret = cmd_runclearbuild(verbose=verbose)
    elif command == "stop":
        ret = cmd_stop(verbose=verbose or is_verbose())
    elif command in ("stopclean", "stop-clean"):
        ret = cmd_stopclean(verbose=verbose or is_verbose())
    elif command == "verify":
        ret = cmd_verify(verbose=verbose)
    elif command == "dbupgrade":
        ret = cmd_dbupgrade(verbose=verbose)
    elif command == "dbstatus":
        ret = cmd_dbstatus(verbose=verbose)
    elif command == "teacher":
        ret = cmd_teacher(interactive=True, verbose=verbose)
    elif command == "dbbackup":
        ret = cmd_dbbackup(verbose=verbose)
    elif command == "dbrestore":
        ret = cmd_dbrestore(verbose=verbose)
    elif command in ("test", "test-all"):
        ret = cmd_test_all(verbose=verbose)
    elif command == "test-unit":
        ret = cmd_test_unit(verbose=verbose)
    elif command == "test-integration":
        ret = cmd_test_integration(verbose=verbose)
    elif command == "test-smoke":
        ret = cmd_test_smoke(verbose=verbose)
    elif command == "test-worker":
        ret = cmd_test_worker(verbose=verbose)
    elif command == "docs-validate":
        ret = cmd_docs_validate(verbose=verbose)
    elif command == "exportall":
        ret = cmd_exportall(verbose=verbose)
    elif command == "importall":
        ret = cmd_importall(verbose=verbose)
    elif command == "velxio-run":
        ret = cmd_velxio_run(verbose=verbose)
    elif command == "velxio-runbuild":
        ret = cmd_velxio_runbuild(verbose=verbose)
    elif command == "velxio-stop":
        ret = cmd_velxio_stop(verbose=verbose)
    elif command == "velxio-status":
        ret = cmd_velxio_status()
    elif command == "velxio-test":
        ret = cmd_velxio_test(extra_args=args[1:])
    elif command == "loadtest":
        print("💡 Menjalankan simulasi load test...")
        print("   Periksa direktori load-test/ untuk skrip Locust:")
        print("   cd load-test && ./start_locust_workers.sh")
        ret = 0
    else:
        print(f"⚠️ Perintah tidak dikenal: {command}\n")
        print_help()
        return 1

    run_time = record_last_run(run_cmd)
    print()
    print(f"🕒 Selesai dijalankan: {run_time}  (perintah: {run_cmd})")
    return ret


if __name__ == "__main__":
    sys.exit(main())
