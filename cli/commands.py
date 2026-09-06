"""
Core command implementations for Elemes CLI.
Multi-OS compatible (Linux, macOS, Windows).
"""

from __future__ import annotations

import getpass
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import (
    ENV_FILE,
    EXAMPLES_DIR,
    PARENT_DIR,
    PROJECT_NAME,
    SCRIPT_DIR,
    elemes_services,
    env_val,
    generate_ts_config,
    is_verbose,
    read_env,
)
from .runner import (
    compose_exec,
    compose_restart,
    detect_compose_command,
    detect_container_command,
    run_compose,
    run_compose_out,
    run_container_cmd,
    run_velxio_compose,
)


def cmd_init(verbose: bool = False) -> int:
    """Initialize configuration, folders, and template .env."""
    print("✨ === Elemes Quick Start === ✨\n")

    # 1. .env
    target_env = PARENT_DIR / ".env"
    example_env = SCRIPT_DIR / ".env.example"
    if not example_env.is_file():
        example_env = EXAMPLES_DIR.parent / ".env.example"

    if target_env.is_file():
        print("✅ [Skip] .env sudah ada")
    else:
        if example_env.is_file():
            shutil.copy2(example_env, target_env)
            print("📝 [Buat] .env  (pastikan untuk edit sesuai kebutuhanmu)")
        else:
            print("⚠️ [Peringatan] .env.example tidak ditemukan")

    # 2. content/
    target_content = PARENT_DIR / "content"
    example_content = EXAMPLES_DIR / "content"
    if target_content.is_dir() and any(target_content.iterdir()):
        print("✅ [Skip] Folder content/ sudah ada")
    else:
        target_content.mkdir(parents=True, exist_ok=True)
        if example_content.is_dir():
            for item in example_content.iterdir():
                dest = target_content / item.name
                if not dest.exists():
                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)
            md_count = len(list(target_content.glob("**/*.md")))
            print(f"📁 [Buat] Folder content/  ({md_count} materi contoh ditambahkan)")
        else:
            print("📁 [Buat] Folder content/")

    # 3. assets/
    target_assets = PARENT_DIR / "assets"
    if target_assets.is_dir():
        print("✅ [Skip] Folder assets/ sudah ada")
    else:
        target_assets.mkdir(parents=True, exist_ok=True)
        print("📁 [Buat] Folder assets/  (untuk menyimpan file gambar/media)")

    # 4. state/
    target_state = PARENT_DIR / "state"
    if target_state.is_dir():
        print("✅ [Skip] Folder state/ sudah ada")
    else:
        target_state.mkdir(parents=True, exist_ok=True)
        print("🔐 [Buat] Folder state/  (untuk Tailscale credentials & state)")

    # 5. state/velxio/
    target_state_velxio = PARENT_DIR / "state" / "velxio"
    if target_state_velxio.is_dir():
        print("✅ [Skip] Folder state/velxio/ sudah ada")
    else:
        target_state_velxio.mkdir(parents=True, exist_ok=True)
        print("🔐 [Buat] Folder state/velxio/  (untuk Tailscale Velxio standalone)")

    generate_ts_config()

    print("\n🎯 Selesai! Langkah selanjutnya yang direkomendasikan:")
    print("  👉 1. Edit file ../.env sesuai dengan kebutuhan environment-mu")
    print("     (termasuk TEACHER_NAME / TEACHER_TOKEN untuk akun guru)")
    print("  👉 2. Edit ../content/home.md untuk menyusun daftar materi")
    print("  👉 3. Jalankan ./elemes.sh teacher untuk membuat/update akun guru")
    print("  🚀 4. Jalankan:  ./elemes.sh runbuild\n")
    return 0


def db_init(verbose: bool = False) -> int:
    """
    First-run & database health: wait for PostgreSQL, migrate schema (idempotent),
    and bootstrap teacher account if TEACHER_TOKEN is set in .env.
    """
    env = read_env()
    user = env.get("POSTGRES_USER", "elemes")
    db = env.get("POSTGRES_DB", "elemes")
    teacher_token = env.get("TEACHER_TOKEN", "")
    teacher_name = env.get("TEACHER_NAME", "Guru LMS")

    attempts = 30
    pg_ready = False
    for i in range(1, attempts + 1):
        ret, _, _ = compose_exec(
            ["postgres", "pg_isready", "-U", user, "-d", db],
            quiet=True,
        )
        if ret == 0:
            pg_ready = True
            break
        time.sleep(2)

    if not pg_ready:
        print("⚠️  PostgreSQL belum siap; migrasi & bootstrap dilewati. Jalankan ./elemes.sh dbupgrade nanti.")
        return 1

    # Check if fresh schema (users table exists?)
    fresh_schema = False
    ret, stdout, _ = compose_exec(
        ["postgres", "psql", "-U", user, "-d", db, "-tAc", "SELECT to_regclass('public.users') IS NULL"],
        capture_stdout=True,
    )
    if stdout.strip() == "t":
        fresh_schema = True

    # Alembic migration
    print("🗄️  Migrasi database (alembic upgrade head)...")
    ret, _, _ = compose_exec(
        ["-w", "/app", "-e", "PYTHONPATH=services", "elemes", "python", "-m", "alembic", "upgrade", "head"],
        verbose=verbose,
    )
    if ret != 0:
        print("⚠️  Migrasi database gagal. Jalankan ./elemes.sh dbupgrade untuk inspeksi.")
        return 1

    # Bootstrap teacher if TEACHER_TOKEN is set
    if teacher_token:
        print("👤 Bootstrap akun guru otomatis (dari TEACHER_TOKEN)...")
        ret, _, _ = compose_exec(
            ["-w", "/app", "-e", "PYTHONPATH=/app", "elemes", "python", "scripts/bootstrap_teacher.py", teacher_name],
            stdin_data=f"{teacher_token}\n",
            verbose=verbose,
        )
        if ret != 0:
            print("⚠️  Bootstrap guru gagal. Periksa TEACHER_TOKEN/TEACHER_NAME di .env, atau jalankan ./elemes.sh teacher.")

    # If fresh schema, restart backend so lesson registry is synchronized
    if fresh_schema:
        print("🔄 First-run terdeteksi; restart backend agar lesson registry ter-sync...")
        compose_restart("elemes", verbose=False)

    return 0


def cmd_run(verbose: bool = False) -> int:
    """Run existing LMS containers."""
    is_v = verbose or is_verbose()
    print("🚀 Menjalankan container...")
    generate_ts_config()
    services = elemes_services()
    if services:
        print("   ℹ️  VELXIO_MODE=remote → Velxio tidak dijalankan secara lokal")
        ret = run_compose(["up", "-d", *services], verbose=is_v)
    else:
        ret = run_compose(["up", "-d"], verbose=is_v)

    if ret != 0:
        print("❌ Gagal menjalankan container.")
        return ret

    print("✅ Elemes berhasil dijalankan!")
    return db_init(verbose=is_v)


def cmd_stop(verbose: bool = False) -> int:
    """Stop running LMS containers."""
    is_v = verbose or is_verbose()
    print("🛑 Menghentikan container yang sedang berjalan...")
    ret = run_compose(["down"], verbose=is_v)
    if ret == 0:
        print("✅ Container berhasil dihentikan.")
    else:
        print("❌ Gagal menghentikan container.")
    return ret


def cmd_stopclean(verbose: bool = False) -> int:
    """Stop running LMS containers and prune stopped containers & unused images."""
    is_v = verbose or is_verbose()
    print("🛑 Menghentikan container yang sedang berjalan...")
    ret = run_compose(["down"], verbose=is_v)
    if ret == 0:
        print("✅ Container berhasil dihentikan.")
    else:
        print("⚠️  Peringatan saat menghentikan container.")

    print("🧹 Membersihkan container yang sudah berhenti (prune)...")
    run_container_cmd(["container", "prune", "-f"], verbose=is_v)

    print("🧹 Membersihkan image yang tidak terpakai (prune)...")
    run_container_cmd(["image", "prune", "-f"], verbose=is_v)

    print("✨ Selesai! Semua container dihentikan dan cache container/image dibersihkan.")
    return 0


def cmd_runbuild(verbose: bool = False) -> int:
    """Build images and start containers."""
    is_v = verbose or is_verbose()
    print("🛑 Menghentikan container yang sedang berjalan...")
    run_compose(["down"], verbose=is_v)
    print("🏗️  Membangun container...")
    ret = run_compose(["build"], verbose=is_v)
    if ret != 0:
        print("❌ Gagal membangun container.")
        return ret

    print("🚀 Menjalankan container di background...")
    generate_ts_config()
    services = elemes_services()
    if services:
        print("   ℹ️  VELXIO_MODE=remote → Velxio tidak dijalankan secara lokal")
        ret = run_compose(["up", "--force-recreate", "-d", *services], verbose=is_v)
    else:
        ret = run_compose(["up", "--force-recreate", "-d"], verbose=is_v)

    if ret != 0:
        print("❌ Gagal menjalankan container.")
        return ret

    print("✅ Elemes berhasil dijalankan!")
    return db_init(verbose=is_v)


def cmd_runclearbuild(verbose: bool = False) -> int:
    """Clean cache (prune), rebuild from scratch, run, and verify tests."""
    is_v = verbose or is_verbose()
    print("🛑 Menghentikan container yang sedang berjalan...")
    run_compose(["down"], verbose=is_v)
    print("🧹 Membersihkan container dan image (prune)...")
    run_container_cmd(["image", "prune", "-f", "-a"], verbose=is_v)
    print("🏗️  Membangun ulang container dari awal (no-cache)...")
    ret = run_compose(["build", "--no-cache"], verbose=is_v)
    if ret != 0:
        print("❌ Gagal membangun ulang container.")
        return ret

    print("🚀 Menjalankan container di background...")
    generate_ts_config()
    services = elemes_services()
    if services:
        print("   ℹ️  VELXIO_MODE=remote → Velxio tidak dijalankan secara lokal")
        ret = run_compose(["up", "--force-recreate", "-d", *services], verbose=is_v)
    else:
        ret = run_compose(["up", "--force-recreate", "-d"], verbose=is_v)

    if ret != 0:
        print("❌ Gagal menjalankan container.")
        return ret

    print("✅ Elemes berhasil dijalankan!")
    ret = db_init(verbose=is_v)
    if ret != 0:
        return ret

    print("🧪 Verifikasi: unit & API test sub-home...")
    ret, _, _ = compose_exec(
        ["-w", "/app", "-e", "PYTHONPATH=services", "-e", "DATABASE_URL=", "elemes", "python", "-m", "pytest", "-m", "unit", "-q"],
        verbose=verbose,
    )
    if ret != 0:
        print("❌ Unit test gagal. Periksa output di atas sebelum deploy.")
        return 1

    ret, _, _ = compose_exec(
        ["-w", "/app", "-e", "PYTHONPATH=services", "-e", "DATABASE_URL=", "elemes", "python", "-m", "pytest", "services/tests/test_sub_home.py", "services/tests/test_sub_home_api.py", "-q"],
        verbose=verbose,
    )
    if ret != 0:
        print("❌ Tes sub-home gagal. Periksa output di atas sebelum deploy.")
        return 1

    print("✅ Tes sub-home lulus.")
    return 0


def cmd_verify(verbose: bool = False) -> int:
    """Verify container images, configuration, STALE status, and entrypoints."""
    is_v = verbose or is_verbose()
    print("🔍 === Memverifikasi Image Container ===\n")
    if is_v:
        print(f"   ℹ️  Engine Compose    : {' '.join(detect_compose_command())}")
        print(f"   ℹ️  Engine Container  : {detect_container_command()}")
        print(f"   ℹ️  Project Name      : {PROJECT_NAME}")
        print(f"   ℹ️  File .env         : {ENV_FILE}\n")

    # 1. Resolve service -> image tag from compose config
    service_image_tag: Dict[str, str] = {}
    _, services_out, _ = run_compose_out(["config", "--services"], capture_stdout=True)
    _, config_out, _ = run_compose_out(["config"], capture_stdout=True)

    services_list = [s.strip() for s in services_out.splitlines() if s.strip()]

    # Parse yaml/text output for service image tag
    for svc in services_list:
        pattern = rf"(?m)^  {re.escape(svc)}:\s*\n(?:    [^\n]+\n)*?    image:\s*([^\s\n\"']+)"
        m = re.search(pattern, config_out)
        if m:
            service_image_tag[svc] = m.group(1).strip().strip('"').strip("'")
        else:
            service_image_tag[svc] = ""

    print("📋 Service yang didefinisikan di podman-compose.yml:")
    for svc in sorted(services_list):
        tag = service_image_tag.get(svc, "")
        print(f"   {svc} → {tag if tag else '<tanpa image:>'}")
    print()

    # 2. Containers belonging to this project (via label io.podman.compose.project)
    print(f"📋 Container project '{PROJECT_NAME}':")
    ret, ps_out, _ = run_container_cmd(
        [
            "ps",
            "-a",
            "--filter",
            f"label=io.podman.compose.project={PROJECT_NAME}",
            "--format",
            "{{.Names}}|{{.Image}}|{{.ImageID}}|{{.Status}}|{{.Labels}}",
        ],
        capture_stdout=True,
    )

    containers_lines = [line.strip() for line in ps_out.splitlines() if line.strip()]
    if not containers_lines:
        print(f"   ⚠️  Tidak ada container untuk project '{PROJECT_NAME}' (jalankan ./elemes.sh run dulu)")
    else:
        for line in containers_lines:
            parts = line.split("|")
            if len(parts) < 5:
                continue
            cname, cimage, cid, cstatus, clabels = parts[0], parts[1], parts[2], parts[3], parts[4]

            # Extract service name from label com.docker.compose.service
            m_svc = re.search(r"com\.docker\.compose\.service[:=]([a-zA-Z0-9_.-]+)", clabels)
            svc = m_svc.group(1) if m_svc else ""
            tag = service_image_tag.get(svc, "")
            stale = ""
            if tag:
                _, img_out, _ = run_container_cmd(
                    ["images", tag, "--noheading", "--format", "{{.ID}}"],
                    capture_stdout=True,
                )
                tag_iid = img_out.strip().splitlines()[0].strip() if img_out.strip() else ""
                if tag_iid and cid and (cid[:12] != tag_iid[:12]):
                    stale = f" ⚠️ STALE (container:{cid} != image:{tag_iid})"

            print(f"   • {cname}")
            print(f"     image: {cimage}  (status: {cstatus}){stale}")
            if is_v:
                print(f"     ID: {cid}  |  labels: {clabels}")
    print()

    # 3. CMD/Entrypoint for each service
    print("🔍 Memeriksa CMD/Entrypoint tiap service...")
    for svc in services_list:
        ret, cid_out, _ = run_container_cmd(
            [
                "ps",
                "-a",
                "--filter",
                f"label=io.podman.compose.project={PROJECT_NAME}",
                "--filter",
                f"label=com.docker.compose.service={svc}",
                "--format",
                "{{.ID}}",
            ],
            capture_stdout=True,
        )
        cid = cid_out.strip().splitlines()[0].strip() if cid_out.strip() else ""
        if cid:
            _, cmd_val, _ = run_container_cmd(["inspect", cid, "--format", "{{.Config.Cmd}}"], capture_stdout=True)
            _, ep_val, _ = run_container_cmd(["inspect", cid, "--format", "{{.Config.Entrypoint}}"], capture_stdout=True)
            _, img_val, _ = run_container_cmd(["inspect", cid, "--format", "{{.Image}}"], capture_stdout=True)
            print(f"   ✅ {svc} ({cid})")
            print(f"      Image: {img_val.strip()}")
            print(f"      Entrypoint: {ep_val.strip()}")
            print(f"      Cmd: {cmd_val.strip()}")
            if is_v:
                _, ports_val, _ = run_container_cmd(["inspect", cid, "--format", "{{.NetworkSettings.Ports}}"], capture_stdout=True)
                if ports_val.strip() and ports_val.strip() != "map[]":
                    print(f"      Ports: {ports_val.strip()}")
        else:
            print(f"   ⚠️  {svc} tidak ditemukan (container belum dibuat)")
        print()

    return 0


def cmd_dbupgrade(verbose: bool = False) -> int:
    """Run database migration (alembic upgrade head)."""
    print("🗄️  Menjalankan migrasi database (alembic upgrade head)...")
    ret, _, _ = compose_exec(
        ["-w", "/app", "-e", "PYTHONPATH=services", "elemes", "python", "-m", "alembic", "upgrade", "head"],
        verbose=verbose,
    )
    return ret


def cmd_dbstatus(verbose: bool = False) -> int:
    """View database schema version (alembic current & heads)."""
    print("🗄️  Versi schema database (alembic current & heads):")
    compose_exec(
        ["-w", "/app", "-e", "PYTHONPATH=services", "elemes", "python", "-m", "alembic", "current"],
        verbose=verbose,
    )
    ret, _, _ = compose_exec(
        ["-w", "/app", "-e", "PYTHONPATH=services", "elemes", "python", "-m", "alembic", "heads"],
        verbose=verbose,
    )
    return ret


def cmd_teacher(interactive: bool = True, name_input: Optional[str] = None, token_input: Optional[str] = None, verbose: bool = False) -> int:
    """Create or update canonical teacher account."""
    print("👤 === Manajemen Akun Guru (upsert satu akun canonical) ===")

    # Check if backend container is running
    ret, names_out, _ = run_container_cmd(
        [
            "ps",
            "--filter",
            f"label=io.podman.compose.project={PROJECT_NAME}",
            "--filter",
            "label=com.docker.compose.service=elemes",
            "--format",
            "{{.Names}}",
        ],
        capture_stdout=True,
    )
    if not names_out.strip():
        print("❌ Container backend belum berjalan. Jalankan ./elemes.sh run dulu.")
        return 1

    default_name = env_val("TEACHER_NAME", "Guru LMS")
    name = name_input or ""
    token = token_input or ""

    if interactive:
        try:
            val = input(f"Nama guru [{default_name}]: ").strip()
            name = val if val else default_name
        except (EOFError, KeyboardInterrupt):
            print("\n❌ Dibatalkan.")
            return 1

        if not name:
            print("❌ Nama guru tidak boleh kosong.")
            return 1

        try:
            token = getpass.getpass("Token guru: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n❌ Dibatalkan.")
            return 1

        if not token:
            print("❌ Token guru tidak boleh kosong.")
            return 1
    else:
        name = name or default_name
        if not token:
            print("❌ Token guru harus diisi.")
            return 1

    ret, _, _ = compose_exec(
        ["-w", "/app", "-e", "PYTHONPATH=/app", "elemes", "python", "scripts/bootstrap_teacher.py", name],
        stdin_data=f"{token}\n",
        verbose=verbose,
    )
    return ret


def cmd_dbbackup(verbose: bool = False) -> int:
    """Backup PostgreSQL database to backups/elemes_<timestamp>.sql."""
    print("💾 Membackup database PostgreSQL → backups/")
    env = read_env()
    user = env.get("POSTGRES_USER", "elemes")
    db = env.get("POSTGRES_DB", "elemes")

    backups_dir = PARENT_DIR / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = backups_dir / f"elemes_{ts}.sql"

    try:
        with open(out_file, "wb") as f:
            ret, _, stderr = compose_exec(
                ["postgres", "pg_dump", "-U", user, "-d", db, "--clean", "--if-exists"],
                stdout_file=f,
                verbose=verbose,
            )

        if ret == 0 and out_file.exists() and out_file.stat().st_size > 0:
            print(f"✅ Backup selesai: {out_file}")
            return 0
        else:
            print("❌ Backup gagal (lihat error di atas).")
            if out_file.exists():
                out_file.unlink(missing_ok=True)
            return 1
    except Exception as e:
        print(f"❌ Backup gagal: {e}")
        if out_file.exists():
            out_file.unlink(missing_ok=True)
        return 1


def list_backups() -> List[Path]:
    """List all database backups sorted newest first."""
    backups_dir = PARENT_DIR / "backups"
    if not backups_dir.is_dir():
        return []
    files = list(backups_dir.glob("elemes_*.sql"))
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def cmd_dbrestore(backup_path: Optional[Path] = None, verbose: bool = False) -> int:
    """Restore database from backup file (defaults to latest)."""
    env = read_env()
    user = env.get("POSTGRES_USER", "elemes")
    db = env.get("POSTGRES_DB", "elemes")

    target_file = backup_path
    if not target_file:
        backups = list_backups()
        if not backups:
            print("❌ Tidak ada backup di backups/elemes_*.sql")
            return 1
        target_file = backups[0]

    if not target_file.is_file():
        print(f"❌ File backup {target_file} tidak ditemukan!")
        return 1

    print(f"♻️  Restore backup: {target_file}")

    # Drop schema public and recreate
    ret, _, _ = compose_exec(
        ["postgres", "psql", "-U", user, "-d", db, "-c", "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"],
        quiet=True,
    )

    try:
        with open(target_file, "rb") as f:
            ret, _, _ = compose_exec(
                ["postgres", "psql", "-U", user, "-d", db],
                stdin_file=f,
                verbose=verbose,
            )
        if ret == 0:
            print("✅ Restore selesai. Bila daftar lesson kosong, jalankan ./elemes.sh run.")
            return 0
        else:
            print("❌ Restore database gagal.")
            return ret
    except Exception as e:
        print(f"❌ Restore gagal: {e}")
        return 1


def cmd_test_unit(verbose: bool = True) -> int:
    """Run unit tests (fast, no DB)."""
    print("🧪 Menjalankan unit test (cepat, no DB)...")
    ret, _, _ = compose_exec(
        ["-w", "/app", "-e", "PYTHONPATH=services", "-e", "DATABASE_URL=", "elemes", "python", "-m", "pytest", "-m", "unit", "-v"],
        verbose=verbose,
    )
    return ret


def cmd_test_integration(verbose: bool = True) -> int:
    """Run integration tests (requires PostgreSQL)."""
    print("🧪 Menjalankan integration test (butuh DATABASE_URL)...")
    ret, _, _ = compose_exec(
        ["-w", "/app", "-e", "PYTHONPATH=services", "elemes", "python", "-m", "pytest", "-m", "integration", "-v"],
        verbose=verbose,
    )
    return ret


def cmd_test_all(verbose: bool = True) -> int:
    """Run full test suite."""
    print("🧪 Menjalankan full test suite...")
    ret, _, _ = compose_exec(
        ["-w", "/app", "-e", "PYTHONPATH=services", "elemes", "python", "-m", "pytest", "-v"],
        verbose=verbose,
    )
    return ret


def cmd_test_smoke(verbose: bool = True) -> int:
    """Post-deploy smoke test (unit + sub-home subset)."""
    print("🧪 Smoke test post-deploy (unit + sub-home subset)...")
    ret1, _, _ = compose_exec(
        ["-w", "/app", "-e", "PYTHONPATH=services", "-e", "DATABASE_URL=", "elemes", "python", "-m", "pytest", "-m", "unit", "-v"],
        verbose=verbose,
    )
    ret2, _, _ = compose_exec(
        ["-w", "/app", "-e", "PYTHONPATH=services", "-e", "DATABASE_URL=", "elemes", "python", "-m", "pytest", "services/tests/test_sub_home.py", "services/tests/test_sub_home_api.py", "-v"],
        verbose=verbose,
    )
    return ret1 or ret2


def cmd_test_worker(verbose: bool = True) -> int:
    """Run compiler worker test suite."""
    print("🧪 Menjalankan compiler worker test suite...")
    ret, _, _ = compose_exec(
        ["-w", "/app", "-e", "PYTHONPATH=compiler_worker", "elemes", "python", "-m", "pytest", "compiler_worker/tests", "-v"],
        verbose=verbose,
    )
    if ret != 0:
        print("⚠️  Compiler worker test tidak tersedia di dalam container (jalankan di host: cd compiler_worker && PYTHONPATH=. python -m pytest -v)")
    return ret


def cmd_docs_validate(verbose: bool = True) -> int:
    """Validate documentation frontmatter and broken links."""
    print("📄 Validasi dokumentasi (frontmatter + broken link)...")
    ret, _, _ = compose_exec(
        ["-w", "/app", "-e", "PYTHONPATH=services", "elemes", "python", "scripts/validate_docs.py"],
        verbose=verbose,
    )
    return ret


def cmd_exportall(verbose: bool = True) -> int:
    """Build and export all images (backend, frontend, velxio) into pre-compiled TAR bundle."""
    print("📦 === Mengekspor Semua Image (Pre-Compiled Bundle) ===")
    tar_file = SCRIPT_DIR / "lms-precompiled.tar"

    print("🏗️  1. Mem-build Backend Elemes...")
    ret = run_container_cmd(["build", "-t", "lms-backend:latest", "-f", "Dockerfile", "."], verbose=verbose)[0]
    if ret != 0:
        print("❌ Build backend gagal.")
        return 1

    print("🏗️  2. Mem-build Frontend Elemes (SvelteKit)...")
    ret = run_container_cmd(["build", "-t", "lms-frontend:latest", "-f", "frontend/Dockerfile", "frontend/"], verbose=verbose)[0]
    if ret != 0:
        print("❌ Build frontend gagal.")
        return 1

    print("🏗️  3. Mem-build Velxio Simulator...")
    enable_esp32 = os.environ.get("ENABLE_ESP32", "0")
    ret = run_container_cmd(
        ["build", "-t", "lms-velxio:latest", "-f", "velxio/Dockerfile.standalone", "--build-arg", f"ENABLE_ESP32={enable_esp32}", "velxio/"],
        verbose=verbose,
    )[0]
    if ret != 0:
        print("❌ Build velxio simulator gagal.")
        return 1

    print("\n🔍 Memverifikasi image yang berhasil di-build...")
    run_container_cmd(["images"], verbose=True)
    print()

    print(f"💾 Menyatukan semua image menjadi 1 file tar: {tar_file.name}...")
    try:
        with open(tar_file, "wb") as f:
            ret = run_container_cmd(["save", "lms-backend:latest", "lms-frontend:latest", "lms-velxio:latest"], stdout_file=f)[0]

        if ret == 0 and tar_file.is_file():
            size_mb = tar_file.stat().st_size / (1024 * 1024)
            size_str = f"{size_mb:.1f}M" if size_mb < 1024 else f"{size_mb/1024:.2f}G"
            print(f"✅ Selesai! File '{tar_file.name}' siap di-upload ke VPS.")
            print(f"   📦 Ukuran file: {size_str}\n")
            print("   📋 Cara deploy di VPS:")
            print(f"   1. Upload file: scp {tar_file.name} user@vps:/path/lms-dev/elemes/")
            print(f"   2. Load image:  podman load -i {tar_file.name}")
            print("   3. Jalankan:    podman-compose up -d\n")
            print("   ⚠️  Tag image bundle sudah sama dengan podman-compose.yml:")
            print("      - lms-backend:latest (untuk service elemes)")
            print("      - lms-frontend:latest (untuk service elemes-frontend)")
            print("      - lms-velxio:latest (untuk service velxio)")
            print("   ℹ️  Service compiler-worker & flowchart TIDAK ikut bundle — di VPS")
            print("      image-nya di-build otomatis oleh podman-compose dari source (build:);")
            print("      pastikan folder source ikut ter-upload, atau jalankan: ./elemes.sh runbuild")
            return 0
        else:
            print("❌ Export gagal.")
            return 1
    except Exception as e:
        print(f"❌ Export gagal: {e}")
        return 1


def cmd_importall(verbose: bool = True) -> int:
    """Import precompiled images from tar file."""
    print("📦 === Mengimpor Semua Image (Pre-Compiled Bundle) ===")
    tar_file = SCRIPT_DIR / "lms-precompiled.tar"
    if not tar_file.is_file():
        print(f"❌ File {tar_file.name} tidak ditemukan!")
        print(f"   Pastikan file sudah ada di direktori ini (nama default: {tar_file.name}).")
        return 1

    print(f"💾 Mengimpor image dari file {tar_file.name}...")
    ret = run_container_cmd(["load", "-i", str(tar_file.name)], verbose=verbose)[0]
    if ret != 0:
        print("❌ Gagal mengimpor image.")
        return 1

    print("\n🔍 Memverifikasi image yang berhasil di-load...")
    run_container_cmd(["images"], verbose=True)
    print()

    print("✅ Selesai! Image berhasil diimpor.")
    print("   Sekarang jalankan: ./elemes.sh run")
    return 0


def cmd_velxio_stop(verbose: bool = False) -> int:
    """Stop Velxio standalone containers."""
    print("🛑 Menghentikan Velxio standalone...")
    ret, _, _ = run_velxio_compose(["down"], quiet=not verbose, verbose=verbose)
    if ret == 0:
        print("✅ Velxio standalone dihentikan.")
    return ret


def cmd_velxio_runbuild(verbose: bool = False) -> int:
    """Build Velxio standalone image and start container."""
    print("🛑 Menghentikan Velxio standalone...")
    run_velxio_compose(["down"], quiet=not verbose, verbose=verbose)
    print("🏗️  Membangun Velxio standalone image...")
    ret, _, _ = run_velxio_compose(["build"], verbose=verbose)
    if ret != 0:
        print("❌ Gagal membangun Velxio standalone.")
        return ret
    return _velxio_start_and_info(verbose=verbose)


def cmd_velxio_run(verbose: bool = False) -> int:
    """Run Velxio standalone container (reuses existing image)."""
    # Check if image exists
    ret, _, _ = run_container_cmd(["image", "exists", "lms-velxio-standalone:latest"], quiet=True)
    if ret != 0:
        print("⚠️  Image 'lms-velxio-standalone:latest' belum dibangun.")
        print("   Jalankan: ./elemes.sh velxio-runbuild")
        return 1

    print("🛑 Menghentikan Velxio standalone...")
    run_velxio_compose(["down"], quiet=not verbose, verbose=verbose)
    return _velxio_start_and_info(verbose=verbose)


def _velxio_start_and_info(verbose: bool = False) -> int:
    print("🚀 Menjalankan Velxio standalone di background...")
    ret, _, _ = run_velxio_compose(["up", "-d"], verbose=verbose)
    if ret != 0:
        print("❌ Gagal menjalankan Velxio standalone.")
        return ret

    print("✅ Velxio standalone berhasil dijalankan!\n")
    vh = env_val("VELXIO_HOST", "velxio-dev")
    print("📡 Velxio standalone info:")
    print(f"   Tailscale hostname : {vh}")
    print("   Port internal      : 80 (Nginx → FastAPI :8001)\n")
    print("💡 Untuk menghubungkan Elemes ke Velxio ini, set di .env mesin Elemes:")
    print("   VELXIO_MODE=remote")
    print(f"   VELXIO_HOST={vh}")
    print(f"   VELXIO_COMPILER_URL=http://{vh}:80/api/compile/")
    return 0


def cmd_velxio_status() -> int:
    """Inspect status & health of Velxio (local or remote mode)."""
    print("📊 === Status Velxio ===")
    mode = env_val("VELXIO_MODE", "local").lower()
    print(f"   Mode: {mode}")

    if mode == "local":
        print("   Velxio berjalan dalam compose utama (bundled)")
        ret, names_out, _ = run_container_cmd(
            [
                "ps",
                "--filter",
                f"label=io.podman.compose.project={PROJECT_NAME}",
                "--filter",
                "label=com.docker.compose.service=velxio",
                "--format",
                "{{.Names}} — {{.Status}}",
            ],
            capture_stdout=True,
        )
        if names_out.strip():
            print("   ✅ Container:")
            for line in names_out.strip().splitlines():
                print(f"      {line}")
        else:
            print("   ⚠️  Container: not running")
    else:
        print("   Velxio berjalan terpisah (remote)")
        vurl = env_val("VELXIO_COMPILER_URL", "")
        print(f"   VELXIO_COMPILER_URL: {vurl if vurl else '<belum diset>'}")
        velxio_project = f"{PROJECT_NAME}-velxio"
        ret, names_out, _ = run_container_cmd(
            [
                "ps",
                "--filter",
                f"label=io.podman.compose.project={velxio_project}",
                "--format",
                "{{.Names}} — {{.Status}}",
            ],
            capture_stdout=True,
        )
        if names_out.strip():
            print("   ✅ Standalone container (lokal):")
            for line in names_out.strip().splitlines():
                print(f"      {line}")
        else:
            print("   ℹ️  Tidak ada standalone container lokal (Velxio berjalan di mesin remote)")

        if vurl:
            health_url = re.sub(r"/api/compile.*", "/health", vurl)
            sys.stdout.write(f"   🔍 Health check ({health_url})... ")
            sys.stdout.flush()
            try:
                req = urllib.request.Request(health_url, headers={"User-Agent": "elemes-cli"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        print("✅ reachable")
                    else:
                        print(f"⚠️ status {resp.status}")
            except Exception:
                print("❌ unreachable")

    return 0


def cmd_velxio_test(extra_args: Optional[List[str]] = None) -> int:
    """Run Velxio frontend test suite (vitest)."""
    print("🧪 Menjalankan test suite modul Velxio (Frontend Vitest)...")
    velxio_frontend = SCRIPT_DIR / "velxio" / "frontend"
    if not velxio_frontend.is_dir():
        print("❌ Direktori velxio/frontend tidak ditemukan.")
        return 1

    npx_bin = shutil.which("npx")
    if not npx_bin:
        print("❌ Executable 'npx' tidak ditemukan.")
        return 1

    cmd = [npx_bin, "vitest", "run", *(extra_args or [])]
    try:
        res = subprocess.run(cmd, cwd=velxio_frontend)
        return res.returncode
    except Exception as e:
        print(f"❌ Gagal menjalankan test: {e}")
        return 1
