#!/usr/bin/env python3
"""E2E: upload asset asli (../mr-edu/assets/ilustrasi_beban.jpeg) via UI.

Verifikasi fix "Backend tidak tersedia" (502) saat upload:
 1. Upload file yang ASLINYA gagal (710 KB, body JSON-base64 ~947 KB) via UI.
 2. POST /api/content/assets/upload → 200, entri di tree, download bytes-cocok.
 3. Jalur 413: body > 8M → 413 + pesan ukuran (bukan 502).
 4. Cleanup probe (entri asli ilustrasi_beban.jpeg DIPERTAHANKAN).

Keamanan data user:
 - Bila file dengan nama sama SUDAH ada di server:
     • identik dengan source  → delete via API lalu re-upload via UI (bukti fix,
       nama persis sama; file identik jadi tak ada data yang hilang);
     • berbeda  → upload dengan nama probe (timestamp), entri asli tidak disentuh.

Run: /home/a2nr/lms-dev/venv/bin/python scripts/verify_asset_upload.py
"""
import base64
import json
import os
import random
import shutil
import sys
import time
import urllib.request

BASE = "https://sinau-c-dev.manakin-gentoo.ts.net"
TOKEN = "141214"
SRC = "/home/a2nr/mr-edu/assets/ilustrasi_beban.jpeg"
ORIGINAL_NAME = "ilustrasi_beban.jpeg"

from playwright.sync_api import sync_playwright


def login(page) -> None:
    """Login flow via POST /api/login (paling andal, tak kena race auth.init)."""
    page.goto(BASE + "/login", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)
    st = page.evaluate("""(token) => fetch('/api/login', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({token})
    }).then(x => x.status)""", TOKEN)
    assert st == 200, f"login gagal (status {st}) — cek token di DB"


def wait_editor_ready(page) -> None:
    """Tunggu tree sidebar ter-render (tab Materi/Assets) — bukan networkidle
    (sering tak tercapai: long-poll/keep-alive, container baru warm-up)."""
    page.goto(BASE + "/teacher/content", wait_until="domcontentloaded", timeout=90000)
    page.locator('button.tree-tab', has_text='Assets').first.wait_for(state="visible", timeout=45000)


def fetch_tree(page):
    return page.evaluate("""() => fetch('/api/content/tree?root=assets',
        {credentials:'include'}).then(x => x.json())""")


def find_asset(nodes: list, name: str):
    """Cari node file bernama `name` di list tree (rekursif masuk children)."""
    for n in nodes:
        is_file = (n.get("type") == "file") or (n.get("is_dir") is False)
        if is_file and n.get("name") == name:
            return n
        if n.get("children"):
            r = find_asset(n["children"], name)
            if r:
                return r
    return None


def list_files(nodes: list, prefix: str = "") -> list[str]:
    """Semua path file di tree (rekursif)."""
    out = []
    for n in nodes:
        p = f"{prefix}/{n['name']}" if prefix else n["name"]
        if (n.get("type") == "file") or (n.get("is_dir") is False):
            out.append(p)
        if n.get("children"):
            out.extend(list_files(n["children"], p))
    return out


def delete_entry(page, path: str) -> None:
    page.evaluate("""(a) => fetch(`/api/content/tree/entry?root=assets&path=${encodeURIComponent(a)}&force=true`,
        {method:'DELETE', credentials:'include'})""", path)


def upload_via_ui(page, local_file: str) -> None:
    """Upload via UI: tab Assets → ⬆️ → file chooser → prompt folder ''.
    Tombol ⬆️ hanya render saat tab Assets aktif ({#if} di +page.svelte)."""
    page.locator('button.tree-tab', has_text='Assets').first.click()
    page.locator('button[title="Upload gambar"]').first.wait_for(state="visible", timeout=15000)
    # Dialog handler HARUS didaftarkan sebelum click (skill pitfall):
    #   prompt "Folder tujuan" → accept("") = root assets
    #   confirm "Salin path ke clipboard?" → dismiss
    page.on("dialog", lambda d: d.accept("") if "Folder tujuan" in (d.message or "") else d.dismiss())
    with page.expect_file_chooser(timeout=10000) as fc:
        page.locator('button[title="Upload gambar"]').first.click()
    fc.value.set_files(local_file)
    page.wait_for_timeout(8000)  # upload base64 ~950 KB + refresh tree


def test_413_path(page) -> None:
    """Body > 8M (file 8 MiB) harus 413 + pesan ukuran, bukan 502."""
    b64 = base64.b64encode(random.Random(1).randbytes(8 * 1024 * 1024)).decode()
    res = page.evaluate("""(b64) => fetch('/api/content/assets/upload', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({filename:'huge.png', folder:'', content_base64:b64})
    }).then(async x => ({status: x.status, body: await x.json()}))""", b64)
    assert res["status"] == 413, f"413 path: dapat {res['status']}: {res['body']}"
    assert "terlalu besar" in res["body"].get("message", "").lower(), \
        f"413 path: pesan salah: {res['body']}"
    print(f"413 path: status={res['status']}, message='{res['body']['message']}' ✓")


def main() -> None:
    if not os.path.isfile(SRC):
        sys.exit(f"File sumber tidak ada: {SRC}")
    with open(SRC, "rb") as f:
        src_raw = f.read()
    print(f"source: {SRC} ({len(src_raw)} bytes, body ~{len(src_raw) * 4 // 3 // 1024} KB)")

    errors: list[str] = []
    api_events: list[tuple[str, int, str]] = []
    upload_name = ORIGINAL_NAME
    local_file = SRC
    deleted_existing = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            ignore_https_errors=True,
            service_workers="block",
            viewport={"width": 1280, "height": 800},
        )
        ctx.add_cookies([
            {"name": "student_token", "value": TOKEN,
             "domain": "sinau-c-dev.manakin-gentoo.ts.net", "path": "/",
             "http_only": True, "same_site": "Lax"}
        ])
        ctx.add_init_script(
            "localStorage.setItem('student_token','141214');"
            "localStorage.setItem('student_last_active','" + str(int(time.time() * 1000)) + "');"
        )
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.on("response", lambda r: api_events.append(
            (r.request.method, r.status, r.url)) if "/api/" in r.url else None)

        login(page)
        wait_editor_ready(page)

        # ── 0) Cek state awal: entri dengan nama sama sudah ada? ──
        existing = find_asset(fetch_tree(page).get("tree", []), ORIGINAL_NAME)
        if existing:
            req = urllib.request.Request(f"{BASE}/assets/{existing['path']}")
            with urllib.request.urlopen(req) as resp:
                existing_raw = resp.read()
            if existing_raw == src_raw:
                # Identik → delete + re-upload (bukti fix, nama persis sama)
                print(f"entri sama (identik) sudah ada di server — delete + re-upload {ORIGINAL_NAME}")
                delete_entry(page, existing["path"])
                page.wait_for_timeout(1000)
                deleted_existing = True
            else:
                # Berbeda → jangan timpa; pakai nama probe
                upload_name = f"beban_probe_{int(time.time())}.jpeg"
                local_file = f"/tmp/{upload_name}"
                shutil.copy(SRC, local_file)
                print(f"entri berbeda sudah ada di server — upload sebagai {upload_name} (asli tak disentuh)")

        # ── 1) Upload via UI ──
        upload_via_ui(page, local_file)
        upload_evt = [(m, s, u) for m, s, u in api_events if "assets/upload" in u]
        print("upload events:", upload_evt)
        assert upload_evt and upload_evt[-1][1] == 200, \
            f"upload tidak sukses: {upload_evt or 'tidak ada POST assets/upload'}"

        # ── 2) Tree memuat entri; download bytes-cocok ──
        node = find_asset(fetch_tree(page).get("tree", []), upload_name)
        assert node, f"entri {upload_name} tidak ada di tree assets"
        print(f"tree: entri {upload_name} ada ✓")
        with urllib.request.urlopen(f"{BASE}/assets/{node['path']}") as resp:
            data = resp.read()
            assert resp.status == 200 and data == src_raw, \
                f"download mismatch: {resp.status}, {len(data)} vs {len(src_raw)} bytes"
        print(f"download /assets/{node['path']}: 200, {len(data)} bytes cocok ✓")

        # ── 3) Jalur 413 (body > 8M) ──
        test_413_path(page)

        # ── 4) Cleanup: semua probe beban_probe_* (artefak kita), entri asli tetap ──
        stale = [p_ for p_ in list_files(fetch_tree(page).get("tree", [])) if p_.startswith("beban_probe")]
        for s in stale:
            delete_entry(page, s)
        page.wait_for_timeout(1000)
        final_files = list_files(fetch_tree(page).get("tree", []))
        left = [f for f in final_files if f.startswith("beban_probe")]
        assert not left, f"cleanup gagal — probe tersisa: {left}"
        print(f"cleanup {len(stale)} probe ✓; entri akhir: {len(final_files)} file")
        if upload_name == ORIGINAL_NAME:
            assert ORIGINAL_NAME in final_files, "entri asli hilang setelah cleanup!"
            print(f"entri asli {ORIGINAL_NAME} tersimpan di server ✓")

        errs = [e for e in errors if "favicon" not in e.lower()]
        if errs:
            print("PAGE ERRORS:")
            for e in errs[:10]:
                print("  ", e)
            sys.exit(1)
        print("pageerrors: bersih ✓")
        browser.close()

    print(f"\nSUCCESS: upload {upload_name} ({len(src_raw)} B, body ~{len(src_raw) * 4 // 3 // 1024} KB) "
          f"lolos proxy tanpa 502; 413 path jelas; data user utuh.")


if __name__ == "__main__":
    main()
