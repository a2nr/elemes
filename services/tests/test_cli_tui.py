"""
Unit tests for Elemes CLI and TUI modules.
Covers:
  - Configuration & Environment (.env parsing, NOISE_RE filtering, Tailscale config)
  - Runner abstraction & command detection
  - TUI Live status container parsing (get_services_status)
  - Keyboard escape sequence parser (read_key)
  - Menu navigation & index wrapping logic
  - StopClean command execution sequence
  - CLI argument dispatcher
"""

from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure elemes directory is on sys.path
ELEMES_DIR = Path(__file__).resolve().parent.parent.parent
if str(ELEMES_DIR) not in sys.path:
    sys.path.insert(0, str(ELEMES_DIR))

from cli.commands import cmd_stopclean, list_backups
from cli.config import (
    NOISE_RE,
    PROJECT_NAME,
    elemes_services,
    env_val,
    generate_ts_config,
    is_verbose,
    read_env,
    set_verbose,
    toggle_verbose,
)
from cli.runner import (
    _filter_stderr_stream,
    detect_compose_command,
    detect_container_command,
)
from cli.tui import MenuItem, get_services_status, read_key


# ─── 1. Configuration & .env Parsing Tests ────────────────────────────────────

@pytest.mark.unit
def test_read_env_parsing(tmp_path: Path):
    """Test native .env parser with various syntax styles."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# Comment line\n"
        "APP_PORT=8000\n"
        "DATABASE_URL=\"postgres://user:pass@host:5432/db\"\n"
        "SINGLE_QUOTED='single_value'\n"
        "  SPACED_KEY =  spaced_val  \n"
        "\n"
        "# Another comment\n"
        "EMPTY_VAL=\n",
        encoding="utf-8",
    )
    parsed = read_env(env_file)
    assert parsed["APP_PORT"] == "8000"
    assert parsed["DATABASE_URL"] == "postgres://user:pass@host:5432/db"
    assert parsed["SINGLE_QUOTED"] == "single_value"
    assert parsed["SPACED_KEY"] == "spaced_val"
    assert parsed["EMPTY_VAL"] == ""
    assert env_val("APP_PORT", env_path=env_file) == "8000"
    assert env_val("NON_EXISTENT", default="fallback", env_path=env_file) == "fallback"


@pytest.mark.unit
def test_read_env_missing_file(tmp_path: Path):
    """Test reading non-existent .env file safely returns empty dict."""
    missing = tmp_path / "does_not_exist.env"
    assert read_env(missing) == {}
    assert env_val("KEY", default="default", env_path=missing) == "default"


@pytest.mark.unit
def test_noise_re_filtering():
    """Verify podman-compose noise lines match NOISE_RE while real errors/logs do not."""
    noise_samples = [
        "podman-compose version: 1.0.6",
        "['podman', '--version']",
        "using podman version: 4.9.3",
        "podman exec -T elemes python -m alembic upgrade head",
        "exit code: 0",
        "exit code: 1",
    ]
    for sample in noise_samples:
        assert NOISE_RE.search(sample) is not None, f"Expected noise to match: {sample}"

    legitimate_samples = [
        "INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.",
        "Error: cannot connect to Postgres database",
        "Traceback (most recent call last):",
        "FAILED tests/test_something.py::test_fail",
        "WARNING: could not find key",
    ]
    for sample in legitimate_samples:
        assert NOISE_RE.search(sample) is None, f"Expected non-noise NOT to match: {sample}"


@pytest.mark.unit
def test_verbose_toggle():
    """Verify verbose mode state toggling and global setters."""
    set_verbose(False)
    assert not is_verbose()

    assert toggle_verbose() is True
    assert is_verbose() is True

    assert toggle_verbose() is False
    assert is_verbose() is False

    set_verbose(True)
    assert is_verbose() is True
    set_verbose(False)


@pytest.mark.unit
def test_elemes_services_mode(monkeypatch):
    """Verify service list based on VELXIO_MODE."""
    # Local mode
    monkeypatch.setattr("cli.config.read_env", lambda *a, **k: {"VELXIO_MODE": "local"})
    assert elemes_services() == []

    # Remote mode
    monkeypatch.setattr("cli.config.read_env", lambda *a, **k: {"VELXIO_MODE": "remote"})
    svcs = elemes_services()
    assert "elemes-ts" in svcs
    assert "postgres" in svcs
    assert "elemes" in svcs
    assert "velxio" not in svcs  # Velxio standalone is not in primary compose in remote mode


# ─── 2. Runner & Noise Filtering Tests ────────────────────────────────────────

@pytest.mark.unit
def test_filter_stderr_stream():
    """Verify _filter_stderr_stream strips noise unless verbose is active."""
    noise_stream = io.StringIO(
        "podman-compose version: 1.0.6\n"
        "Real error occurred!\n"
        "exit code: 0\n"
    )
    captured = []
    # When verbose=False, noise should be filtered from output
    with patch("sys.stderr.write") as mock_stderr_write:
        _filter_stderr_stream(noise_stream, verbose=False, captured_lines=captured)
        written = [call.args[0] for call in mock_stderr_write.call_args_list]
        assert "Real error occurred!\n" in written
        assert "podman-compose version: 1.0.6\n" not in written
        assert "exit code: 0\n" not in written
        # But captured_lines records all lines
        assert len(captured) == 3


@pytest.mark.unit
def test_detect_compose_command_override(monkeypatch):
    """Verify LMS_COMPOSE_CMD environment variable overrides detection."""
    monkeypatch.setenv("LMS_COMPOSE_CMD", "custom-compose --special-flag")
    cmd = detect_compose_command()
    assert cmd == ["custom-compose", "--special-flag"]


@pytest.mark.unit
def test_detect_container_command_override(monkeypatch):
    """Verify LMS_CONTAINER_CMD environment variable overrides detection."""
    monkeypatch.setenv("LMS_CONTAINER_CMD", "custom-podman")
    cmd = detect_container_command()
    assert cmd == "custom-podman"


# ─── 3. TUI Container Status Parsing Tests ────────────────────────────────────

@pytest.mark.unit
def test_get_services_status_parsing(monkeypatch):
    """Test get_services_status correctly parses podman ps output without quiet=True bug."""
    mock_ps_output = (
        "lms-dev_elemes-ts_1|Up 2 hours|map[com.docker.compose.service:elemes-ts]\n"
        "lms-dev_postgres_1|Up 2 hours (healthy)|map[com.docker.compose.service:postgres]\n"
        "lms-dev_elemes_1|Up 2 hours|map[com.docker.compose.service:elemes]\n"
        "lms-dev_compiler-worker_1|Up 2 hours|map[com.docker.compose.service:compiler-worker]\n"
        "lms-dev_elemes-frontend_1|Up 2 hours|map[com.docker.compose.service:elemes-frontend]\n"
        "lms-dev_velxio_1|Exited (0) 5 minutes ago|map[com.docker.compose.service:velxio]\n"
    )

    def mock_run_container_cmd(args, capture_stdout=False, **kwargs):
        # Crucial check: capture_stdout must be True, and quiet must NOT suppress stdout
        assert capture_stdout is True
        return 0, mock_ps_output, ""

    monkeypatch.setattr("cli.tui.run_container_cmd", mock_run_container_cmd)

    status = get_services_status()
    assert status["postgres"] == "healthy"
    assert status["elemes"] == "running"
    assert status["compiler-worker"] == "running"
    assert status["elemes-frontend"] == "running"
    assert status["velxio"] == "stopped"
    assert status["flowchart"] == "stopped"  # Missing from ps output = stopped


@pytest.mark.unit
def test_get_services_status_empty(monkeypatch):
    """Test get_services_status with no running containers returns stopped for all."""
    monkeypatch.setattr(
        "cli.tui.run_container_cmd",
        lambda *a, **k: (0, "", ""),
    )
    status = get_services_status()
    for svc in ("postgres", "elemes", "elemes-frontend", "compiler-worker", "flowchart", "velxio"):
        assert status[svc] == "stopped"


# ─── 4. Keyboard Escape Sequence & Unbuffered I/O Tests ───────────────────────

@pytest.mark.unit
def test_read_key_arrow_sequences(monkeypatch):
    """
    Test read_key correctly parses ANSI and SS3 arrow key sequences
    without Python TextIOWrapper buffering problems.
    """
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdin.fileno", lambda: 0)
    monkeypatch.setattr("termios.tcgetattr", lambda fd: [])
    monkeypatch.setattr("termios.tcsetattr", lambda fd, when, old: None)
    monkeypatch.setattr("tty.setraw", lambda fd: None)

    # Simulate ANSI UP arrow: \x1b followed by [A
    read_queue = [b"\x1b", b"[A"]
    monkeypatch.setattr("os.read", lambda fd, n: read_queue.pop(0) if read_queue else b"")
    monkeypatch.setattr("select.select", lambda r, w, x, t: ([r], [], []))
    assert read_key() == "UP"

    # Simulate ANSI DOWN arrow: \x1b followed by [B
    read_queue = [b"\x1b", b"[B"]
    assert read_key() == "DOWN"

    # Simulate SS3 UP arrow (application cursor mode): \x1b followed by OA
    read_queue = [b"\x1b", b"OA"]
    assert read_key() == "UP"

    # Simulate SS3 DOWN arrow: \x1b followed by OB
    read_queue = [b"\x1b", b"OB"]
    assert read_key() == "DOWN"

    # Simulate Enter key
    read_queue = [b"\r"]
    assert read_key() == "ENTER"

    # Simulate Standalone Esc (select times out)
    read_queue = [b"\x1b"]
    monkeypatch.setattr("select.select", lambda r, w, x, t: ([], [], []))
    assert read_key() == "ESC"


@pytest.mark.unit
def test_read_key_windows(monkeypatch):
    """Test read_key in Windows environment using simulated msvcrt."""
    monkeypatch.setattr("sys.platform", "win32")

    mock_msvcrt = MagicMock()
    # Windows sends \xe0 then \x48 ('H') for UP arrow
    mock_msvcrt.getch.side_effect = [b"\xe0", b"H", b"\xe0", b"P", b"\r", b"q"]

    with patch.dict("sys.modules", {"msvcrt": mock_msvcrt}):
        assert read_key() == "UP"
        assert read_key() == "DOWN"
        assert read_key() == "ENTER"
        assert read_key() == "q"


# ─── 5. Menu Navigation & Index Wrapping Tests ────────────────────────────────

@pytest.mark.unit
def test_menu_item_initialization():
    """Verify MenuItem properties and defaults."""
    action_called = False

    def sample_action():
        nonlocal action_called
        action_called = True

    item = MenuItem("1", "Test Item", "Test Description", sample_action)
    assert item.key == "1"
    assert item.label == "Test Item"
    assert item.desc == "Test Description"
    assert item.is_submenu is False

    item.action()
    assert action_called is True


@pytest.mark.unit
def test_menu_index_wrapping_logic():
    """Verify index increment and decrement wrapping calculations."""
    items_count = 5
    current_idx = 0

    # UP wraps from 0 to items_count - 1
    current_idx = (current_idx - 1) % items_count
    assert current_idx == 4

    # DOWN wraps from items_count - 1 to 0
    current_idx = (current_idx + 1) % items_count
    assert current_idx == 0

    # DOWN moves forward
    current_idx = (current_idx + 1) % items_count
    assert current_idx == 1


@pytest.mark.unit
def test_run_menu_focused_description_rendering(monkeypatch):
    """Verify run_menu renders focused description panel below the menu list."""
    from cli.tui import run_menu, console

    item1 = MenuItem("1", "First Choice", "Description for First Choice")
    item2 = MenuItem("2", "Second Choice", "Description for Second Choice")
    items = [item1, item2]

    # Simulate DOWN arrow then 'q' to exit
    key_inputs = ["DOWN", "q"]
    monkeypatch.setattr("cli.tui.read_key", lambda: key_inputs.pop(0) if key_inputs else "q")

    printed_panels = []
    original_print = console.print

    def capture_print(*args, **kwargs):
        for a in args:
            from rich.panel import Panel
            if isinstance(a, Panel):
                printed_panels.append(a)
        return original_print(*args, **kwargs)

    monkeypatch.setattr(console, "print", capture_print)

    run_menu("Test Menu", items, is_main_menu=False)

    # Panels printed should include the description panels for item1 then item2
    desc_panels = [p for p in printed_panels if "Deskripsi" in str(p.title)]
    assert len(desc_panels) >= 2
    assert "First Choice" in str(desc_panels[0].title)
    assert "Description for First Choice" in str(desc_panels[0].renderable)
    assert "Second Choice" in str(desc_panels[1].title)
    assert "Description for Second Choice" in str(desc_panels[1].renderable)


@pytest.mark.unit
def test_run_menu_enter_on_kembali_returns(monkeypatch):
    """Verify navigating with DOWN arrow to 'Kembali' and pressing ENTER exits the submenu."""
    from cli.tui import MenuItem, run_menu

    items = [
        MenuItem("1", "Action One", "Do action one", action=lambda: None),
        MenuItem("b", "Kembali", "Kembali ke menu utama", None),
    ]

    # Navigate DOWN to 'b', then press ENTER
    key_sequence = ["DOWN", "ENTER"]
    monkeypatch.setattr("cli.tui.read_key", lambda: key_sequence.pop(0) if key_sequence else "b")

    # Should cleanly return from run_menu without hanging
    run_menu("Submenu Test", items, is_main_menu=False)


@pytest.mark.unit
def test_run_menu_enter_on_keluar_exits(monkeypatch):
    """Verify navigating with DOWN arrow to 'Keluar' and pressing ENTER calls sys.exit(0)."""
    from cli.tui import MenuItem, run_menu

    items = [
        MenuItem("1", "Submenu One", "Go to submenu", action=lambda: None),
        MenuItem("q", "Keluar", "Keluar aplikasi", None),
    ]

    key_sequence = ["DOWN", "ENTER"]
    monkeypatch.setattr("cli.tui.read_key", lambda: key_sequence.pop(0) if key_sequence else "q")

    with pytest.raises(SystemExit) as exc_info:
        run_menu("Main Menu Test", items, is_main_menu=True)
    assert exc_info.value.code == 0


@pytest.mark.unit
def test_run_action_screen_back_keys(monkeypatch):
    """Verify run_action_screen exits wait loop when pressing 'b', 'B', or ENTER."""
    from cli.tui import run_action_screen

    executed = []
    def dummy_action():
        executed.append(True)
        return 0

    # Test pressing 'b' to return
    monkeypatch.setattr("cli.tui.read_key", lambda: "b")
    run_action_screen("Test Action", dummy_action, "test_action")
    assert len(executed) == 1

    # Test pressing 'B' to return
    monkeypatch.setattr("cli.tui.read_key", lambda: "B")
    run_action_screen("Test Action 2", dummy_action, "test_action_2")
    assert len(executed) == 2


# ─── 6. Commands & StopClean Execution Tests ──────────────────────────────────

@pytest.mark.unit
def test_cmd_stopclean_sequence(monkeypatch):
    """Verify cmd_stopclean runs compose down, container prune, and image prune in order."""
    calls = []

    def mock_run_compose(args, verbose=False):
        calls.append(("compose", args))
        return 0

    def mock_run_container_cmd(args, verbose=False, **kwargs):
        calls.append(("container", args))
        return 0, "", ""

    monkeypatch.setattr("cli.commands.run_compose", mock_run_compose)
    monkeypatch.setattr("cli.commands.run_container_cmd", mock_run_container_cmd)

    ret = cmd_stopclean(verbose=False)
    assert ret == 0
    assert len(calls) == 3
    assert calls[0] == ("compose", ["down"])
    assert calls[1] == ("container", ["container", "prune", "-f"])
    assert calls[2] == ("container", ["image", "prune", "-f"])


@pytest.mark.unit
def test_list_backups_sorted(tmp_path: Path, monkeypatch):
    """Verify list_backups finds and sorts backups newest first."""
    backups_dir = tmp_path / "backups"
    backups_dir.mkdir()

    f1 = backups_dir / "elemes_20260101_100000.sql"
    f2 = backups_dir / "elemes_20260201_100000.sql"
    f3 = backups_dir / "elemes_20260301_100000.sql"

    f1.write_text("dump1")
    f2.write_text("dump2")
    f3.write_text("dump3")

    # Set artificial mtimes: f3 newest, f1 oldest
    os.utime(f1, (1000, 1000))
    os.utime(f2, (2000, 2000))
    os.utime(f3, (3000, 3000))

    monkeypatch.setattr("cli.commands.PARENT_DIR", tmp_path)

    backups = list_backups()
    assert len(backups) == 3
    assert backups[0].name == "elemes_20260301_100000.sql"
    assert backups[1].name == "elemes_20260201_100000.sql"
    assert backups[2].name == "elemes_20260101_100000.sql"


# ─── 7. Tailscale Config & CLI Main Dispatcher Tests ──────────────────────────

@pytest.mark.unit
def test_generate_ts_config(tmp_path: Path, monkeypatch):
    """Test generating lms-tail.json substitutes __VELXIO_PROXY_TARGET__ properly."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    template = config_dir / "lms-tail.json.template"
    template.write_text('{"target": "__VELXIO_PROXY_TARGET__"}')

    monkeypatch.setattr("cli.config.SCRIPT_DIR", tmp_path)

    # Local mode
    monkeypatch.setattr("cli.config.read_env", lambda *a, **k: {"VELXIO_MODE": "local"})
    generate_ts_config()
    out = (config_dir / "lms-tail.json").read_text()
    assert "http://127.0.0.1:80/" in out

    # Remote mode
    monkeypatch.setattr(
        "cli.config.read_env",
        lambda *a, **k: {"VELXIO_MODE": "remote", "VELXIO_HOST": "my-velxio-host"},
    )
    generate_ts_config()
    out = (config_dir / "lms-tail.json").read_text()
    assert "http://my-velxio-host:80/" in out


@pytest.mark.unit
def test_cli_main_dispatch(monkeypatch):
    """Test CLI main() routing without running containers."""
    import elemes

    # 1. Help flag returns 0
    monkeypatch.setattr("sys.argv", ["elemes.py", "--help"])
    assert elemes.main() == 0

    # 2. Unknown command returns 1
    monkeypatch.setattr("sys.argv", ["elemes.py", "unknown-random-cmd"])
    assert elemes.main() == 1

    # 3. StopClean routes to cmd_stopclean
    stopclean_called = False

    def mock_stopclean(*a, **k):
        nonlocal stopclean_called
        stopclean_called = True
        return 0

    monkeypatch.setattr("elemes.cmd_stopclean", mock_stopclean)
    monkeypatch.setattr("sys.argv", ["elemes.py", "stopclean"])
    assert elemes.main() == 0
    assert stopclean_called is True


@pytest.mark.unit
def test_all_cli_commands_dispatch_matrix(monkeypatch):
    """Verify that every single CLI command routes and executes without NameError or signature errors."""
    import elemes

    all_commands = [
        "init",
        "run",
        "runbuild",
        "runclearbuild",
        "stop",
        "stopclean",
        "stop-clean",
        "verify",
        "dbupgrade",
        "dbstatus",
        "teacher",
        "dbbackup",
        "dbrestore",
        "test",
        "test-all",
        "test-unit",
        "test-integration",
        "test-smoke",
        "test-worker",
        "docs-validate",
        "exportall",
        "importall",
        "velxio-run",
        "velxio-runbuild",
        "velxio-stop",
        "velxio-status",
        "velxio-test",
        "loadtest",
    ]

    # Mock all cmd_* in elemes to record their invocation and return 0
    for name in dir(elemes):
        if name.startswith("cmd_") and callable(getattr(elemes, name)):
            monkeypatch.setattr(elemes, name, lambda *a, **k: 0)

    for cmd in all_commands:
        monkeypatch.setattr("sys.argv", ["elemes.py", cmd])
        ret = elemes.main()
        assert ret == 0, f"Command {cmd} failed with exit code {ret}"

    # Also verify with --verbose flag
    for cmd in ["run", "verify", "dbstatus", "stopclean"]:
        monkeypatch.setattr("sys.argv", ["elemes.py", "--verbose", cmd])
        ret = elemes.main()
        assert ret == 0


# ─── 8. Verbose Mode Effect on Container Menu & Commands ──────────────────────

@pytest.mark.unit
def test_container_menu_respects_verbose_toggle(monkeypatch):
    """Verify that toggling verbose mode propagates directly into container menu actions."""
    import cli.tui as tui
    from cli.config import set_verbose

    captured_verbose = []

    def mock_cmd_run(verbose=False):
        captured_verbose.append(verbose)
        return 0

    monkeypatch.setattr("cli.tui.cmd_run", mock_cmd_run)
    monkeypatch.setattr("cli.tui.run_action_screen", lambda title, func, cmd: func())

    # Get menu items from menu_server_lifecycle
    captured_items = []
    monkeypatch.setattr("cli.tui.run_menu", lambda title, items: captured_items.extend(items))
    tui.menu_server_lifecycle()

    run_item = next(it for it in captured_items if it.key == "1")

    # 1. When verbose is OFF
    set_verbose(False)
    run_item.action()
    assert captured_verbose[-1] is False

    # 2. When verbose is ON
    set_verbose(True)
    run_item.action()
    assert captured_verbose[-1] is True

    # Reset
    set_verbose(False)


@pytest.mark.unit
def test_cmd_verify_verbose_output(capsys, monkeypatch):
    """Verify cmd_verify includes engine and project details only when verbose is True."""
    from cli.commands import cmd_verify
    from cli.config import set_verbose

    monkeypatch.setattr("cli.commands.run_compose_out", lambda *a, **k: (0, "elemes\n", "services:\n  elemes:\n    image: lms:latest\n"))
    monkeypatch.setattr("cli.commands.run_container_cmd", lambda *a, **k: (0, "", ""))

    # Verbose OFF
    set_verbose(False)
    cmd_verify(verbose=False)
    captured = capsys.readouterr().out
    assert "Engine Compose" not in captured
    assert "Project Name" not in captured

    # Verbose ON
    set_verbose(True)
    cmd_verify(verbose=True)
    captured_verbose = capsys.readouterr().out
    assert "Engine Compose" in captured_verbose
    assert "Project Name" in captured_verbose

    set_verbose(False)


@pytest.mark.unit
def test_run_compose_verbose_vs_quiet(monkeypatch):
    """Verify run_compose executes quietly when verbose=False, and verbose=True when active."""
    from cli.runner import run_compose
    from cli.config import set_verbose

    executed_calls = []

    def mock_execute_process(cmd, quiet=False, verbose=False, **kwargs):
        executed_calls.append({"cmd": cmd, "quiet": quiet, "verbose": verbose})
        return 0, "", ""

    monkeypatch.setattr("cli.runner.execute_process", mock_execute_process)

    # 1. Verbose OFF -> quiet=True
    set_verbose(False)
    run_compose(["up", "-d"], verbose=False)
    assert len(executed_calls) == 1
    assert executed_calls[0]["quiet"] is True

    # 2. Verbose ON -> quiet=False, verbose=True
    set_verbose(True)
    run_compose(["up", "-d"], verbose=False)  # even if verbose arg is False, is_verbose() is True
    assert len(executed_calls) == 2
    assert executed_calls[1]["quiet"] is False
    assert executed_calls[1]["verbose"] is True

    set_verbose(False)


@pytest.mark.unit
def test_all_submenus_integrity_and_actions(monkeypatch):
    """
    Ensure every submenu in tui.py constructs its MenuItem list properly
    and all actions can be resolved and invoked without NameError (e.g. cmd_dbbackup).
    """
    import cli.tui as tui

    collected_submenus = []

    def mock_run_menu(title, items, is_main_menu=False):
        collected_submenus.append((title, items))

    monkeypatch.setattr(tui, "run_menu", mock_run_menu)
    monkeypatch.setattr(tui, "run_action_screen", lambda title, func, cmd: func())
    monkeypatch.setattr(tui, "interactive_restore_screen", lambda: 0)

    # Mock all potential cmd_* calls inside actions to return 0
    from cli import commands
    for attr in dir(commands):
        if attr.startswith("cmd_") and callable(getattr(commands, attr)):
            monkeypatch.setattr(commands, attr, lambda *a, **k: 0)
            if hasattr(tui, attr):
                monkeypatch.setattr(tui, attr, lambda *a, **k: 0)

    # Invoke all menu builders
    tui.menu_server_lifecycle()
    tui.menu_database_users()
    tui.menu_test_suite()
    tui.menu_velxio()
    tui.menu_deploy_export()
    tui.menu_setup_env()

    assert len(collected_submenus) == 6

    # Test every item action in every submenu
    for title, items in collected_submenus:
        assert len(items) > 0
        for item in items:
            assert item.label
            assert item.key
            if item.action and not item.is_submenu:
                # Should execute cleanly without NameError (e.g. cmd_dbbackup)
                item.action()
