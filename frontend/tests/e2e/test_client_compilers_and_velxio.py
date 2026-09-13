"""
E2E Playwright verification test for:
1. Client-side compilers (PicoC for C, MicroPython WASM for Python)
2. Velxio Arduino Simulator (ensures no COEP / ERR_BLOCKED_BY_RESPONSE)
3. Flowchart editor iframe
4. Playground execution modes

Usage:
  /home/a2nr/lms-dev/venv/bin/python elemes/frontend/tests/e2e/test_client_compilers_and_velxio.py
"""

import time
from playwright.sync_api import sync_playwright

def test_all():
    print("=== STARTING LMS E2E INTEGRATION TEST ===", flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        console_logs = []
        page_errors = []
        req_failures = []

        page.on('console', lambda msg: console_logs.append(f"[{msg.type.upper()}] {msg.text}"))
        page.on('pageerror', lambda err: page_errors.append(str(err)))
        page.on('requestfailed', lambda req: req_failures.append(f"{req.method} {req.url} -> {req.failure}"))

        # -------------------------------------------------------------
        # 1. TEST HELLO WORLD (C & Python Web Workers)
        # -------------------------------------------------------------
        print("\n[1/3] Testing /lesson/hello_world.md (Client-side C & Python)...", flush=True)
        page.goto("https://sinau-c-dev.manakin-gentoo.ts.net/lesson/hello_world.md", wait_until='networkidle')
        time.sleep(2)

        # Click Python
        py_tab = page.get_by_role("button", name="Python", exact=True)
        if py_tab.is_visible():
            py_tab.click()
            time.sleep(1)
            page.get_by_role("button", name="▶ Run").click()
            time.sleep(2)
            out = page.locator(".tab-panel:not(.tab-hidden)").inner_text()
            assert "Halo Dunia" in out, f"Python output mismatch: {out}"
            print("  ✅ Python MicroPython WASM execution succeeded!", flush=True)

        # Click C
        c_tab = page.get_by_role("button", name="C", exact=True)
        if c_tab.is_visible():
            c_tab.click()
            time.sleep(1)
            page.get_by_role("button", name="▶ Run").click()
            time.sleep(2)
            out = page.locator(".tab-panel:not(.tab-hidden)").inner_text()
            assert "Halo Dunia" in out, f"C output mismatch: {out}"
            print("  ✅ C PicoC execution succeeded!", flush=True)

        # -------------------------------------------------------------
        # 2. TEST ARDUINO / VELXIO LESSON
        # -------------------------------------------------------------
        print("\n[2/3] Testing /lesson/led_blink_arduino.md (Velxio Simulator Iframe)...", flush=True)
        page.goto("https://sinau-c-dev.manakin-gentoo.ts.net/lesson/led_blink_arduino.md", wait_until='networkidle')
        time.sleep(2)

        arduino_tab = page.get_by_role("button", name="Arduino")
        assert arduino_tab.is_visible(), "Arduino tab button missing!"
        arduino_tab.click()
        time.sleep(4)

        velxio_iframe = page.locator("iframe.velxio-iframe")
        assert velxio_iframe.is_visible(), "Velxio iframe is not visible!"
        frame = page.frame_locator("iframe.velxio-iframe").first
        root_count = frame.locator("#root").count()
        assert root_count > 0, "Velxio #root React mount container missing inside iframe!"
        print("  ✅ Velxio Arduino simulator loaded and visible inside lesson iframe!", flush=True)

        # -------------------------------------------------------------
        # 3. TEST PLAYGROUND
        # -------------------------------------------------------------
        print("\n[3/3] Testing /playground (Flowchart & Velxio)...", flush=True)
        page.goto("https://sinau-c-dev.manakin-gentoo.ts.net/playground", wait_until='networkidle')
        time.sleep(2)

        pg_fc = page.locator("button:has-text('Flowchart')")
        if pg_fc.is_visible():
            pg_fc.click()
            time.sleep(3)
            assert page.locator("iframe.flowchart-iframe").first.is_visible(), "Playground Flowchart iframe not visible!"
            print("  ✅ Flowchart loaded in Playground!", flush=True)

        # Error check
        blocked_reqs = [r for r in req_failures if "BLOCKED" in r]
        print(f"\nBlocked requests: {len(blocked_reqs)}")
        print(f"Page errors: {len(page_errors)}")
        assert len(blocked_reqs) == 0, f"Blocked requests detected: {blocked_reqs}"
        assert len(page_errors) == 0, f"Page errors detected: {page_errors}"

        print("\n🎉 ALL E2E TESTS PASSED!", flush=True)
        browser.close()

if __name__ == '__main__':
    test_all()
