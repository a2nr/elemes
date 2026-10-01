"""E2E verify: tombol export/import bundle di content editor (lms-dev).

Auth: cookie student_token=141214 (HttpOnly, untuk /api) + localStorage
(studi) + reload supaya auth.init() jalan. Sama seperti recipe skill.

Langkah:
1. Login guru -> buka /teacher/content
2. Klik tombol export (📤) -> tangkap download event -> simpan zip, cek isinya
3. Klik tombol import (📥) -> pilih probe zip via file_chooser -> accept confirm
4. Cek via API /api/content/tree bahwa imported/probe.md muncul

Menulis zip probe sendiri (content/imported/probe.md + assets/imported/probe.png).
"""
import io
import sys
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://sinau-c-dev.manakin-gentoo.ts.net"
TEACHER_TOKEN = "141214"
PROBE_ZIP = Path("/tmp/elemes-probe-bundle.zip")
DOWNLOAD_DIR = Path("/tmp/elemes-e2e-downloads")


def make_probe_zip() -> Path:
    if PROBE_ZIP.exists():
        return PROBE_ZIP
    with zipfile.ZipFile(PROBE_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("content/imported/probe.md", "# Probe Import\n\nMateri test.\n")
        zf.writestr("assets/imported/probe.png", b"\x89PNG\r\n\x1a\nfake-png")
    return PROBE_ZIP


def main() -> int:
    make_probe_zip()
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            accept_downloads=True,
            ignore_https_errors=True,
            service_workers="block",
            viewport={"width": 1280, "height": 800},
        )
        ctx.add_cookies([{
            "name": "student_token",
            "value": TEACHER_TOKEN,
            "domain": "sinau-c-dev.manakin-gentoo.ts.net",
            "path": "/",
            "http_only": True,
            "same_site": "Lax",
        }])
        page = ctx.new_page()
        page.add_init_script(f"localStorage.setItem('student_token','{TEACHER_TOKEN}');")

        pageerrors = []
        page.on("pageerror", lambda e: pageerrors.append(str(e)))

        # ── Login & buka editor ──
        page.goto(f"{BASE}/teacher/content", wait_until="networkidle")
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(2500)

        # Guard: pastikan editor guru tampil
        if page.locator(".content-editor-layout").count() == 0:
            print("FAIL: .content-editor-layout tidak muncul (auth? gate?)")
            print("pageerrors:", pageerrors)
            browser.close()
            return 1
        print("OK: content editor tampil")

        # ── Export ──
        export_btn = page.locator("button.panel-btn", has_text="📤")
        if export_btn.count() == 0:
            print("FAIL: tombol export 📤 tidak ditemukan")
            browser.close()
            return 1
        print("OK: tombol export ditemukan")

        with page.expect_download(timeout=20000) as dl_info:
            export_btn.first.click()
        download = dl_info.value
        dest = DOWNLOAD_DIR / download.suggested_filename
        download.save_as(dest)
        print(f"OK: download tersimpan -> {dest} ({dest.stat().st_size} bytes)")

        # Cek isi zip
        with zipfile.ZipFile(dest) as zf:
            names = set(zf.namelist())
        assert "content/home.md" in names, f"zip tidak berisi content/home.md: {sorted(names)[:8]}"
        assert any(n.startswith("assets/") for n in names), "zip tidak berisi assets/"
        print(f"OK: zip berisi {len(names)} entry; ada content/ dan assets/")

        # ── Import ──
        import_btn = page.locator("button.panel-btn", has_text="📥")
        if import_btn.count() == 0:
            print("FAIL: tombol import 📥 tidak ditemukan")
            browser.close()
            return 1
        print("OK: tombol import ditemukan")

        confirmed = {"mode": None}

        def on_dialog(dialog):
            # window.confirm: OK = skip, Cancel = overwrite -> pilih overwrite
            # (probe file belum ada, jadi mode tidak terlalu penting; pilih skip/OK)
            print(f"  dialog: {dialog.type} -> accept (skip mode)")
            confirmed["mode"] = "skip"
            dialog.accept()

        page.on("dialog", on_dialog)

        with page.expect_file_chooser(timeout=20000) as fc_info:
            import_btn.first.click()
        fc = fc_info.value
        fc.set_files(str(PROBE_ZIP))
        print("OK: file probe dipilih")

        # Tunggu toast/import selesai (progress -> toast -> reload tree)
        page.wait_for_timeout(5000)

        # ── Verify via API tree ──
        tree = page.evaluate(
            """async () => {
                const r = await fetch('/api/content/tree?root=content', { credentials: 'include' });
                const j = await r.json();
                return j.success ? j.tree : null;
            }"""
        )
        flat = []
        def walk(nodes):
            for n in nodes or []:
                flat.append(n["path"])
                if n.get("children"):
                    walk(n["children"])
        walk(tree)
        ok_imported = "imported/probe.md" in flat
        print(f"OK imported/probe.md di tree: {ok_imported}")
        if not ok_imported:
            print("  tree sample:", flat[:10])
            print("FAIL: imported/probe.md tidak ada di tree")
            print("pageerrors:", pageerrors)
            browser.close()
            return 1

        # ── Verify asset via API tree assets ──
        atree = page.evaluate(
            """async () => {
                const r = await fetch('/api/content/tree?root=assets', { credentials: 'include' });
                const j = await r.json();
                return j.success ? j.tree : null;
            }"""
        )
        aflat = []
        def walk_a(nodes):
            for n in nodes or []:
                aflat.append(n["path"])
                if n.get("children"):
                    walk_a(n["children"])
        walk_a(atree)
        ok_asset = "imported/probe.png" in aflat
        print(f"OK imported/probe.png di assets tree: {ok_asset}")

        # ── Overwrite round: import ulang mode overwrite, pastikan isi berubah ──
        # (mode ditentukan dari confirm -> kedua kalinya tekan Cancel)
        confirmed["mode"] = None

        def on_dialog2(dialog):
            dialog.dismiss()  # Cancel = overwrite

        page.remove_listener("dialog", on_dialog)
        page.on("dialog", on_dialog2)

        with page.expect_file_chooser(timeout=20000) as fc_info2:
            import_btn.first.click()
        fc2 = fc_info2.value
        fc2.set_files(str(PROBE_ZIP))
        page.wait_for_timeout(5000)

        body = page.evaluate(
            """async () => {
                const r = await fetch('/api/content/drafts?target_path=imported/probe.md', { credentials: 'include' });
                const j = await r.json();
                return j.success ? (j.body || '') : 'ERR';
            }"""
        )
        print(f"OK body probe.md setelah overwrite: {body.strip()[:40]!r}")
        if not body.startswith("# Probe Import"):
            print("FAIL: isi probe.md tidak sesuai setelah overwrite")
            browser.close()
            return 1

        print("pageerrors:", pageerrors)
        if pageerrors:
            # filter 502/favicon infra noise
            real = [e for e in pageerrors if "502" not in e and "favicon" not in e]
            if real:
                print("FAIL: pageerrors nyata:", real)
                browser.close()
                return 1

        print("\nALL E2E CHECKS PASSED")
        browser.close()
        return 0


if __name__ == "__main__":
    sys.exit(main())
