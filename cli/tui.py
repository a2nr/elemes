"""
Modern Interactive Terminal User Interface (TUI) for Elemes LMS.
Multi-OS compatible (Linux, macOS, Windows) using Rich & native key reader.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from rich.align import Align
from rich.box import ROUNDED, SIMPLE
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .commands import (
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
    list_backups,
)
from .config import (
    ENV_FILE,
    PARENT_DIR,
    PROJECT_NAME,
    env_val,
    generate_ts_config,
    is_verbose,
    read_env,
    record_last_run,
    toggle_verbose,
)
from .runner import run_container_cmd

console = Console()


# ─── Cross-Platform Key Reader ───────────────────────────────────────────────

def read_key() -> str:
    """
    Read a single keypress or arrow key cross-platform.
    Returns: 'UP', 'DOWN', 'LEFT', 'RIGHT', 'ENTER', 'ESC', or character string.
    """
    if sys.platform == "win32":
        try:
            import msvcrt

            ch = msvcrt.getch()
            if ch in (b"\x00", b"\xe0"):
                ch2 = msvcrt.getch()
                if ch2 == b"H":
                    return "UP"
                elif ch2 == b"P":
                    return "DOWN"
                elif ch2 == b"K":
                    return "LEFT"
                elif ch2 == b"M":
                    return "RIGHT"
                return ""
            if ch in (b"\r", b"\n"):
                return "ENTER"
            if ch == b"\x1b":
                return "ESC"
            if ch == b"\x03":  # Ctrl+C
                raise KeyboardInterrupt()
            return ch.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    # POSIX (Linux, macOS)
    if not sys.stdin.isatty():
        try:
            line = sys.stdin.readline()
            return line.strip().lower()
        except Exception:
            return "q"

    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        raw = os.read(fd, 1)
        if not raw:
            return ""

        if raw == b"\x1b":
            # Check for escape sequences without Python TextIOWrapper buffering
            r, _, _ = select.select([fd], [], [], 0.05)
            if not r:
                return "ESC"
            seq = os.read(fd, 10)
            if seq in (b"[A", b"OA") or seq.endswith(b"A"):
                return "UP"
            elif seq in (b"[B", b"OB") or seq.endswith(b"B"):
                return "DOWN"
            elif seq in (b"[C", b"OC") or seq.endswith(b"C"):
                return "RIGHT"
            elif seq in (b"[D", b"OD") or seq.endswith(b"D"):
                return "LEFT"
            return "ESC"
        elif raw in (b"\r", b"\n"):
            return "ENTER"
        elif raw == b"\x03":  # Ctrl+C
            raise KeyboardInterrupt()
        elif raw == b"\x04":  # Ctrl+D
            return "q"

        return raw.decode("utf-8", errors="ignore")
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def flush_input() -> None:
    """Flush any pending unread characters in stdin to avoid keystroke bleed-through."""
    try:
        if sys.platform == "win32":
            import msvcrt
            while msvcrt.kbhit():
                msvcrt.getch()
        else:
            if sys.stdin.isatty():
                import termios
                termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
    except Exception:
        pass


# ─── Live Service Status ─────────────────────────────────────────────────────

def get_services_status() -> Dict[str, str]:
    """Inspect status of core containers for the dashboard."""
    status_map: Dict[str, str] = {
        "postgres": "stopped",
        "elemes": "stopped",
        "elemes-frontend": "stopped",
        "compiler-worker": "stopped",
        "flowchart": "stopped",
        "velxio": "stopped",
    }

    try:
        ret, out, _ = run_container_cmd(
            [
                "ps",
                "-a",
                "--filter",
                f"label=io.podman.compose.project={PROJECT_NAME}",
                "--format",
                "{{.Names}}|{{.Status}}|{{.Labels}}",
            ],
            capture_stdout=True,
        )
        if ret == 0 and out.strip():
            import re

            for line in out.strip().splitlines():
                parts = line.split("|")
                if len(parts) >= 3:
                    cstatus = parts[1].lower()
                    clabels = parts[2]
                    m = re.search(r"com\.docker\.compose\.service[:=]([a-zA-Z0-9_.-]+)", clabels)
                    if m:
                        svc = m.group(1)
                        if "up" in cstatus:
                            status_map[svc] = "healthy" if "healthy" in cstatus else "running"
                        elif "exit" in cstatus:
                            status_map[svc] = "stopped"
                        else:
                            status_map[svc] = cstatus
    except Exception:
        pass

    return status_map


# ─── UI Components ───────────────────────────────────────────────────────────

def render_header(services_status: Optional[Dict[str, str]] = None) -> None:
    """Render the stylish top hero banner and live status bar."""
    title_text = Text()
    title_text.append("⚡ ELEMES LMS ORCHESTRATOR ⚡\n", style="bold cyan")
    title_text.append("Modern Multi-OS Management Suite for Elemes LMS", style="dim white")

    banner = Panel(
        Align.center(title_text),
        box=ROUNDED,
        border_style="cyan",
        padding=(0, 2),
    )
    console.print(banner)

    # Status Bar
    env_exists = ENV_FILE.is_file()
    env_badge = "[bold green]OK (.env)[/bold green]" if env_exists else "[bold red]Missing (.env)[/bold red]"
    velxio_mode = env_val("VELXIO_MODE", "local")
    verbose_badge = "[bold green]ON[/bold green]" if is_verbose() else "[dim white]OFF[/dim white]"

    info_text = (
        f"  [bold]Proyek:[/bold] [cyan]{PROJECT_NAME}[/cyan]  │  "
        f"[bold]Env:[/bold] {env_badge}  │  "
        f"[bold]Velxio Mode:[/bold] [yellow]{velxio_mode}[/yellow]  │  "
        f"[bold]Verbose:[/bold] {verbose_badge} [dim]([t] toggle)[/dim]  │  "
        f"[bold]OS:[/bold] [magenta]{sys.platform}[/magenta]"
    )
    console.print(info_text)

    # Mini Service Grid
    if services_status:
        grid = Table(box=SIMPLE, show_header=False, padding=(0, 1), collapse_padding=True)
        grid.add_column(style="dim")
        for _ in range(6):
            grid.add_column()

        def badge(name: str, key: str) -> str:
            st = services_status.get(key, "stopped")
            if st in ("running", "healthy"):
                return f"[bold green]●[/bold green] [white]{name}[/white]"
            else:
                return f"[bold red]✖[/bold red] [dim]{name}[/dim]"

        grid.add_row(
            "Layanan:",
            badge("postgres", "postgres"),
            badge("backend", "elemes"),
            badge("frontend", "elemes-frontend"),
            badge("worker", "compiler-worker"),
            badge("flowchart", "flowchart"),
            badge("velxio", "velxio"),
        )
        console.print(grid)

    console.print("─" * console.width, style="dim")


def run_action_screen(title: str, func: Callable[[], int], command_label: str) -> None:
    """Display an action execution view, stream output, and show summary."""
    console.clear()
    console.print(
        Panel(
            f"[bold yellow]🚀 Menjalankan:[/bold yellow] [bold white]{title}[/bold white]\n"
            f"[dim]Perintah: {command_label}[/dim]",
            box=ROUNDED,
            border_style="yellow",
        )
    )
    console.print()

    start_time = time.time()
    try:
        ret = func()
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Dibatalkan oleh pengguna.[/yellow]")
        ret = 130
    except Exception as e:
        console.print(f"\n[red]❌ Terjadi kesalahan: {e}[/red]")
        ret = 1

    duration = time.time() - start_time
    record_last_run(command_label)

    console.print()
    if ret == 0:
        summary_panel = Panel(
            f"[bold green]✅ Selesai dengan sukses![/bold green] (Durasi: {duration:.2f} detik)",
            border_style="green",
            box=ROUNDED,
        )
    else:
        summary_panel = Panel(
            f"[bold red]❌ Perintah gagal dengan exit code: {ret}[/bold red] (Durasi: {duration:.2f} detik)",
            border_style="red",
            box=ROUNDED,
        )
    console.print(summary_panel)

    flush_input()
    console.print("\n[dim]Tekan [ENTER] atau [b] untuk kembali ke menu...[/dim]", end="")
    try:
        while True:
            k = read_key()
            if k in ("ENTER", "ESC", "q", "Q", "b", "B", " "):
                break
    except KeyboardInterrupt:
        pass
    flush_input()


# ─── Interactive Backup Selector ─────────────────────────────────────────────

def interactive_restore_screen() -> int:
    """Show list of backups and allow selecting which one to restore."""
    backups = list_backups()
    if not backups:
        console.clear()
        console.print(
            Panel(
                "[bold red]❌ Tidak ada file backup ditemukan di backups/elemes_*.sql[/bold red]",
                border_style="red",
                box=ROUNDED,
            )
        )
        console.print("\nTekan [ENTER] untuk kembali...")
        read_key()
        return 1

    current_idx = 0
    while True:
        console.clear()
        render_header()
        console.print(
            Panel(
                "[bold cyan]♻️  Pilih File Backup untuk Restore[/bold cyan]\n"
                "[dim]Gunakan panah [UP/DOWN] lalu [ENTER], atau ketik nomor backup. [b] kembali.[/dim]",
                box=ROUNDED,
                border_style="cyan",
            )
        )

        table = Table(box=ROUNDED, expand=True)
        table.add_column("No", justify="right", style="cyan", width=4)
        table.add_column("File Backup", style="bold white")
        table.add_column("Ukuran", justify="right", style="yellow", width=10)
        table.add_column("Waktu Dibuat", justify="center", style="dim", width=22)

        for i, b in enumerate(backups):
            size_kb = b.stat().st_size / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB"
            mtime = datetime.fromtimestamp(b.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")

            prefix = "▶ " if i == current_idx else "  "
            name_text = f"{prefix}{b.name}"
            if i == current_idx:
                row_style = "bold cyan on grey23"
            else:
                row_style = ""

            table.add_row(
                str(i + 1),
                name_text,
                size_str,
                mtime,
                style=row_style,
            )

        console.print(table)
        console.print("\n[dim]Pilihan: [ENTER] Restore file terpilih  │  [b/ESC] Batal & Kembali[/dim]")

        k = read_key()
        if k in ("UP", "k"):
            current_idx = (current_idx - 1) % len(backups)
        elif k in ("DOWN", "j"):
            current_idx = (current_idx + 1) % len(backups)
        elif k in ("b", "B", "ESC", "q"):
            return 0
        elif k.isdigit():
            idx = int(k) - 1
            if 0 <= idx < len(backups):
                target = backups[idx]
                run_action_screen(
                    f"Restore Backup {target.name}",
                    lambda: cmd_dbrestore(backup_path=target, verbose=is_verbose()),
                    f"dbrestore {target.name}",
                )
                return 0
        elif k == "ENTER":
            target = backups[current_idx]
            run_action_screen(
                f"Restore Backup {target.name}",
                lambda: cmd_dbrestore(backup_path=target, verbose=is_verbose()),
                f"dbrestore {target.name}",
            )
            return 0


# ─── Generic Interactive Menu Selector ───────────────────────────────────────

class MenuItem:
    def __init__(
        self,
        key: str,
        label: str,
        desc: str,
        action: Optional[Callable[[], Any]] = None,
        is_submenu: bool = False,
    ):
        self.key = key
        self.label = label
        self.desc = desc
        self.action = action
        self.is_submenu = is_submenu


def run_menu(
    title: str,
    items: List[MenuItem],
    is_main_menu: bool = False,
) -> None:
    """Run an interactive arrow-key and numbered menu."""
    selected_idx = 0

    while True:
        services_status = get_services_status() if is_main_menu else None
        console.clear()
        render_header(services_status)

        menu_panel_title = f"[bold cyan]{title}[/bold cyan]"
        console.print(
            Panel(
                f"{menu_panel_title}\n"
                f"[dim]Navigasi: [↑/↓] Panah, [ENTER] Pilih, [1-{len(items)}] Tombol Angka, "
                f"[{'q: Keluar' if is_main_menu else 'b: Kembali'}][/dim]",
                box=ROUNDED,
                border_style="cyan",
            )
        )

        # Menu List
        max_label_len = max(len(it.label) for it in items) if items else 30
        max_label_len = max(max_label_len, 32)

        for idx, item in enumerate(items):
            is_selected = idx == selected_idx
            item_text = Text()
            if is_selected:
                item_text.append("  ▶ ", style="bold cyan")
                item_text.append(f"[{item.key}]  ", style="bold yellow on grey23")
                item_text.append(f"{item.label:<{max_label_len + 2}}", style="bold white on grey23")
            else:
                item_text.append("    ", style="dim")
                item_text.append(f"[{item.key}]  ", style="bold yellow")
                item_text.append(f"{item.label}", style="white")
            console.print(item_text)

        console.print()

        # Focused Menu Item Description Panel
        if items:
            active_item = items[selected_idx]
            desc_text = active_item.desc or "Tidak ada deskripsi."
            if active_item.is_submenu:
                action_hint = "Tekan [ENTER] atau nomor menu untuk membuka submenu"
            elif active_item.key.lower() == "t":
                action_hint = "Tekan [ENTER] atau [t] untuk toggle"
            elif active_item.key.lower() == "q":
                action_hint = "Tekan [ENTER] atau [q] untuk keluar"
            elif active_item.key.lower() == "b":
                action_hint = "Tekan [ENTER] atau [b] untuk kembali"
            else:
                action_hint = "Tekan [ENTER] untuk mengeksekusi"

            desc_panel = Panel(
                f" [white]{desc_text}[/white]",
                title=f"[bold cyan]ℹ️  Deskripsi: [white]{active_item.label}[/white][/bold cyan]",
                title_align="left",
                subtitle=f"[dim]{action_hint}[/dim]",
                subtitle_align="right",
                box=ROUNDED,
                border_style="blue",
                padding=(0, 1),
            )
            console.print(desc_panel)

        try:
            k = read_key()
        except KeyboardInterrupt:
            if is_main_menu:
                console.print("\nSampai jumpa! 👋")
                sys.exit(0)
            else:
                return

        if k in ("UP", "k"):
            selected_idx = (selected_idx - 1) % len(items)
        elif k in ("DOWN", "j"):
            selected_idx = (selected_idx + 1) % len(items)
        elif k in ("t", "T"):
            # If an item specifically has key 't', execute it; otherwise toggle verbose mode
            has_t_item = False
            for idx, item in enumerate(items):
                if item.key.lower() == "t":
                    selected_idx = idx
                    if item.action:
                        item.action()
                    has_t_item = True
                    break
            if not has_t_item:
                toggle_verbose()
        elif k in ("q", "Q") and is_main_menu:
            console.print("\nSampai jumpa! 👋")
            sys.exit(0)
        elif k in ("b", "B", "ESC", "q", "Q") and not is_main_menu:
            return
        elif k == "ENTER":
            chosen = items[selected_idx]
            if chosen.key.lower() == "b" or (not is_main_menu and chosen.action is None):
                return
            elif chosen.key.lower() == "q" and is_main_menu:
                console.print("\nSampai jumpa! 👋")
                sys.exit(0)
            elif chosen.action:
                chosen.action()
                if not chosen.is_submenu and not is_main_menu:
                    # After running an action in submenu, stay in submenu
                    pass
        else:
            # Check for direct key match
            for idx, item in enumerate(items):
                if k.lower() == item.key.lower():
                    selected_idx = idx
                    if item.key.lower() == "b" and not is_main_menu:
                        return
                    elif item.key.lower() == "q" and is_main_menu:
                        console.print("\nSampai jumpa! 👋")
                        sys.exit(0)
                    elif item.action:
                        item.action()
                    elif not is_main_menu and item.action is None:
                        return
                    break


# ─── Menu Definitions ────────────────────────────────────────────────────────

def menu_server_lifecycle() -> None:
    items = [
        MenuItem(
            "1",
            "Run (Start)",
            "Menjalankan container yang sudah ada (up -d)",
            lambda: run_action_screen("Start LMS Containers", lambda: cmd_run(verbose=is_verbose()), "run"),
        ),
        MenuItem(
            "2",
            "Run + Build",
            "Build container image lalu jalankan",
            lambda: run_action_screen("Build and Run Containers", lambda: cmd_runbuild(verbose=is_verbose()), "runbuild"),
        ),
        MenuItem(
            "3",
            "Run + Clean Rebuild",
            "Prune cache, rebuild total no-cache & jalankan",
            lambda: run_action_screen(
                "Clean Rebuild and Run", lambda: cmd_runclearbuild(verbose=is_verbose()), "runclearbuild"
            ),
        ),
        MenuItem(
            "4",
            "Stop Containers",
            "Hentikan semua container yang sedang berjalan",
            lambda: run_action_screen("Stop Containers", lambda: cmd_stop(verbose=is_verbose()), "stop"),
        ),
        MenuItem(
            "5",
            "Stop + Clean (Prune)",
            "Hentikan container & bersihkan stopped containers serta image tak terpakai",
            lambda: run_action_screen("Stop and Clean", lambda: cmd_stopclean(verbose=is_verbose()), "stopclean"),
        ),
        MenuItem(
            "6",
            "Verify Images & Containers",
            "Verifikasi status container, image tag, dan STALE status",
            lambda: run_action_screen("Verify Containers", lambda: cmd_verify(verbose=is_verbose()), "verify"),
        ),
        MenuItem(
            "t",
            "Toggle Verbose Mode",
            "Ubah mode log detail (ON / OFF)",
            lambda: (toggle_verbose(), None)[1],
        ),
        MenuItem("b", "Kembali", "Kembali ke menu utama", None),
    ]
    run_menu("🚀 Server & Container Lifecycle", items)


def menu_database_users() -> None:
    items = [
        MenuItem(
            "1",
            "Migrasi Database (Upgrade)",
            "Jalankan alembic upgrade head",
            lambda: run_action_screen("Database Migration", lambda: cmd_dbupgrade(verbose=is_verbose()), "dbupgrade"),
        ),
        MenuItem(
            "2",
            "Status Versi Schema",
            "Cek alembic current & heads",
            lambda: run_action_screen("Database Version Status", lambda: cmd_dbstatus(verbose=is_verbose()), "dbstatus"),
        ),
        MenuItem(
            "3",
            "Setup / Update Akun Guru",
            "Prompt nama & token guru untuk upsert satu akun",
            lambda: run_action_screen("Setup Akun Guru", lambda: cmd_teacher(interactive=True, verbose=is_verbose()), "teacher"),
        ),
        MenuItem(
            "4",
            "Backup Database",
            "Dump PostgreSQL ke backups/elemes_<timestamp>.sql",
            lambda: run_action_screen(
                "Backup Database", lambda: cmd_dbbackup(verbose=is_verbose()), "dbbackup"
            ),
        ),
        MenuItem(
            "5",
            "Restore Database (Pilih File)",
            "Pilih file backup dari daftar untuk di-restore",
            interactive_restore_screen,
        ),
        MenuItem("b", "Kembali", "Kembali ke menu utama", None),
    ]
    run_menu("🗄️ Database & User Management", items)


def menu_test_suite() -> None:
    items = [
        MenuItem(
            "1",
            "Unit Test",
            "Unit test cepat tanpa database (pytest -m unit)",
            lambda: run_action_screen("Unit Test Suite", lambda: cmd_test_unit(verbose=is_verbose()), "test-unit"),
        ),
        MenuItem(
            "2",
            "Integration Test",
            "Integration test (memerlukan PostgreSQL)",
            lambda: run_action_screen(
                "Integration Test Suite", lambda: cmd_test_integration(verbose=is_verbose()), "test-integration"
            ),
        ),
        MenuItem(
            "3",
            "Full Test Suite",
            "Jalankan semua test suite (CI gate)",
            lambda: run_action_screen("Full Test Suite", lambda: cmd_test_all(verbose=is_verbose()), "test-all"),
        ),
        MenuItem(
            "4",
            "Smoke Test Post-Deploy",
            "Unit test + subset tes sub-home pasca deploy",
            lambda: run_action_screen("Smoke Test", lambda: cmd_test_smoke(verbose=is_verbose()), "test-smoke"),
        ),
        MenuItem(
            "5",
            "Compiler Worker Test",
            "Jalankan compiler worker test suite",
            lambda: run_action_screen(
                "Compiler Worker Tests", lambda: cmd_test_worker(verbose=is_verbose()), "test-worker"
            ),
        ),
        MenuItem(
            "6",
            "Validasi Dokumentasi",
            "Cek broken link & frontmatter materi di docs/",
            lambda: run_action_screen(
                "Docs Validation", lambda: cmd_docs_validate(verbose=is_verbose()), "docs-validate"
            ),
        ),
        MenuItem("b", "Kembali", "Kembali ke menu utama", None),
    ]
    run_menu("🧪 Test Suite & Quality Checks", items)


def menu_velxio() -> None:
    items = [
        MenuItem(
            "1",
            "Run Velxio Standalone",
            "Jalankan simulator Velxio di background",
            lambda: run_action_screen("Run Velxio Standalone", lambda: cmd_velxio_run(verbose=is_verbose()), "velxio-run"),
        ),
        MenuItem(
            "2",
            "Build & Run Velxio",
            "Build image lalu jalankan Velxio standalone",
            lambda: run_action_screen(
                "Build & Run Velxio", lambda: cmd_velxio_runbuild(verbose=is_verbose()), "velxio-runbuild"
            ),
        ),
        MenuItem(
            "3",
            "Stop Velxio Standalone",
            "Hentikan simulator Velxio standalone",
            lambda: run_action_screen("Stop Velxio", lambda: cmd_velxio_stop(verbose=is_verbose()), "velxio-stop"),
        ),
        MenuItem(
            "4",
            "Status & Health Check",
            "Cek mode (local/remote) dan health check endpoint",
            lambda: run_action_screen("Velxio Status", cmd_velxio_status, "velxio-status"),
        ),
        MenuItem(
            "5",
            "Frontend Vitest",
            "Jalankan unit test frontend modul Velxio",
            lambda: run_action_screen("Velxio Frontend Vitest", lambda: cmd_velxio_test(), "velxio-test"),
        ),
        MenuItem("b", "Kembali", "Kembali ke menu utama", None),
    ]
    run_menu("📡 Velxio Simulator Standalone", items)


def menu_deploy_export() -> None:
    items = [
        MenuItem(
            "1",
            "Export Precompiled Bundle (TAR)",
            "Build backend, frontend, velxio -> lms-precompiled.tar",
            lambda: run_action_screen(
                "Export Precompiled Bundle", lambda: cmd_exportall(verbose=is_verbose()), "exportall"
            ),
        ),
        MenuItem(
            "2",
            "Import Precompiled Bundle",
            "Load image dari lms-precompiled.tar untuk deployment VPS",
            lambda: run_action_screen(
                "Import Precompiled Bundle", lambda: cmd_importall(verbose=is_verbose()), "importall"
            ),
        ),
        MenuItem("b", "Kembali", "Kembali ke menu utama", None),
    ]
    run_menu("📦 Deploy & Precompiled Bundles", items)


def menu_setup_env() -> None:
    def show_env_info() -> int:
        env = read_env()
        table = Table(title="Variabel Environment (.env)", box=ROUNDED)
        table.add_column("Kunci (Key)", style="bold cyan")
        table.add_column("Nilai (Value)", style="white")

        sensitive_keys = {"PASSWORD", "SECRET", "TOKEN", "KEY"}
        for k, v in sorted(env.items()):
            is_sensitive = any(s in k.upper() for s in sensitive_keys)
            display_val = "••••••••" if is_sensitive and v else v
            table.add_row(k, display_val)

        console.print(table)
        return 0

    items = [
        MenuItem(
            "1",
            "Inisialisasi Proyek (Quick Start)",
            "Buat folder .env, content, assets, state dari template",
            lambda: run_action_screen("Quick Start Init", lambda: cmd_init(verbose=is_verbose()), "init"),
        ),
        MenuItem(
            "2",
            "Generate Config Tailscale Serve",
            "Generate config/lms-tail.json sesuai VELXIO_MODE",
            lambda: run_action_screen(
                "Generate Tailscale Config",
                lambda: (generate_ts_config(), print("✅ lms-tail.json berhasil di-generate."), 0)[2],
                "ts-config",
            ),
        ),
        MenuItem(
            "3",
            "Inspeksi Konfigurasi .env",
            "Tampilkan konfigurasi aktif dengan masking data sensitif",
            lambda: run_action_screen("Inspeksi .env", show_env_info, "env-info"),
        ),
        MenuItem(
            "t",
            "Toggle Verbose Mode",
            "Aktifkan / nonaktifkan mode log detail (verbose)",
            lambda: (toggle_verbose(), None)[1],
        ),
        MenuItem("b", "Kembali", "Kembali ke menu utama", None),
    ]
    run_menu("⚙️ Setup & Environment", items)


# ─── Main TUI Entrypoint ─────────────────────────────────────────────────────

def launch_tui() -> None:
    """Launch the modern interactive TUI dashboard and menu."""
    main_items = [
        MenuItem(
            "1",
            "Server & Containers",
            "Start, stop, build, dan verifikasi kontainer LMS",
            menu_server_lifecycle,
            is_submenu=True,
        ),
        MenuItem(
            "2",
            "Database & Users",
            "Migrasi alembic, akun guru, backup & restore database",
            menu_database_users,
            is_submenu=True,
        ),
        MenuItem(
            "3",
            "Test Suite & Quality",
            "Unit test, integration test, smoke test, compiler test",
            menu_test_suite,
            is_submenu=True,
        ),
        MenuItem(
            "4",
            "Velxio Simulator",
            "Kontrol simulator modular Velxio standalone",
            menu_velxio,
            is_submenu=True,
        ),
        MenuItem(
            "5",
            "Export & Deploy",
            "Build & pack bundle image TAR siap upload ke VPS",
            menu_deploy_export,
            is_submenu=True,
        ),
        MenuItem(
            "6",
            "Setup & Environment",
            "Inisialisasi template folder, Tailscale serve, inspeksi .env",
            menu_setup_env,
            is_submenu=True,
        ),
        MenuItem(
            "v",
            "Quick Verify",
            "Cek cepat image status & kontainer yang berjalan",
            lambda: run_action_screen("Quick Verify", lambda: cmd_verify(verbose=is_verbose()), "verify"),
        ),
        MenuItem(
            "t",
            "Toggle Verbose Mode",
            "Ubah mode log detail (ON / OFF)",
            lambda: (toggle_verbose(), None)[1],
        ),
        MenuItem("q", "Keluar", "Tutup aplikasi Elemes TUI", None),
    ]

    try:
        run_menu("Menu Utama Elemes LMS", main_items, is_main_menu=True)
    except KeyboardInterrupt:
        console.print("\nSampai jumpa! 👋")
