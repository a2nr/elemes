"""
Reproduce quiz option-display bug via Playwright.
- Login via UI navbar (token guru 141214)
- Buka /lesson/quiz_test
- Mulai kuis, navigasi bolak-balik antar soal (mcq <-> flashcard)
- Tiap soal mcq: bandingkan jumlah tombol .option-btn di DOM vs
  panjang options dari server quiz_data (cocokkan by question text/prose)
- Log ke /tmp/repro_quiz.log
"""
import sys, json, urllib.request
from pathlib import Path

BASE = "https://sinau-c-dev.manakin-gentoo.ts.net"
TOKEN = "141214"
SLUG = "quiz_test"
LOG = "/tmp/repro_quiz.log"

def log(msg):
    with open(LOG, "a") as f:
        f.write(msg + "\n")
    print(msg)

def norm(t):
    return (t or "").replace("\n", " ").strip()[:50].lower()

def fetch_quiz_data():
    url = f"{BASE}/api/lesson/{SLUG}.json?token={TOKEN}"
    req = urllib.request.Request(url, headers={"User-Agent": "repro"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    return data.get("quiz_data", [])

def main():
    Path(LOG).write_text("")
    try:
        qd = fetch_quiz_data()
        log(f"== server quiz_data: {len(qd)} soal")
    except Exception as e:
        log(f"!! gagal fetch quiz_data: {e}")
        qd = []

    server_by_text = {}
    for q in qd:
        txt = q.get("question") or q.get("front") or ""
        server_by_text[norm(txt)] = len(q.get("options") or [])

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(service_workers="block")
        pg = ctx.new_page()
        pg.on("console", lambda m: log(f"[console.{m.type}] {m.text}"))
        pg.on("pageerror", lambda e: log(f"[pageerror] {e}"))

        log(f"== goto {BASE}/lesson/{SLUG}")
        pg.add_init_script(f"localStorage.setItem('student_token','{TOKEN}');")
        pg.goto(f"{BASE}/lesson/{SLUG}", wait_until="networkidle", timeout=60000)
        pg.wait_for_timeout(2000)
        # reload biar auth.init() jalanin validateToken -> authLoggedIn=true
        pg.reload(wait_until="networkidle")
        pg.wait_for_timeout(2500)

        # Buka modal login: klik dropdown-item "Masuk" lalu submit
        try:
            pg.locator(".dropdown-item", has_text="Masuk").first.click(timeout=8000)
            pg.get_by_placeholder("Masukkan token...").fill(TOKEN)
            pg.get_by_role("button", name="Masuk").click(timeout=8000)
            log("== submit login modal OK")
        except Exception as e:
            log(f"!! gagal modal login: {e}")
            # fallback: cari semua elemen ber-text Masuk
            try:
                els = pg.locator("text=Masuk").all_inner_texts()
                log(f"text=Masuk elements: {els}")
            except: pass
        pg.wait_for_timeout(2000)
        # debug: cek validateToken API dari browser context
        vt = pg.evaluate("""async () => {
            try {
                const r = await fetch('/api/validate-token', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({token:'141214'})});
                return await r.json();
            } catch(e) { return 'ERR:'+e.message; }
        }""")
        log(f"== validateToken from browser: {vt}")

        try:
            pg.get_by_text("Mulai Kuis Sekarang").click(timeout=10000)
            log("== klik Mulai Kuis OK")
        except Exception as e:
            log(f"!! gagal klik Mulai Kuis: {e}")
            buttons = pg.locator("button").all_inner_texts()
            log(f"buttons: {buttons[:20]}")
            b.close()
            return

        pg.wait_for_timeout(1500)
        ndots = pg.locator(".nav-dot").count()
        log(f"== jumlah nav-dot (soal): {ndots}")

        mismatches = 0
        for i in range(ndots):
            pg.locator(".nav-dot").nth(i).click()
            pg.wait_for_timeout(400)
            opt_btns = pg.locator(".option-btn").count()
            flash_ok = pg.locator(".btn-flashcard-ok").count()
            q_prose = pg.locator(".quiz-question-prose").inner_text()[:50].replace("\n", " ")
            expected = server_by_text.get(norm(q_prose))
            tag = "flashcard" if flash_ok > 0 else ("mcq" if opt_btns > 0 else "EMPTY")
            status = "OK"
            if tag == "mcq" and expected is not None and opt_btns != expected:
                status = f"!!! MISMATCH DOM={opt_btns} vs server={expected}"
                mismatches += 1
            elif tag == "mcq" and opt_btns == 0:
                status = "!!! MCQ TANPA OPSI"
                mismatches += 1
            elif tag == "flashcard" and opt_btns > 0:
                status = "!!! FLASHCARD PUNYA OPSI (aneh)"
                mismatches += 1
            elif tag == "EMPTY":
                status = "!!! SOAL KOSONG (no option, no flashcard)"
                mismatches += 1
            log(f"[soal {i}] type={tag} prose={q_prose!r} DOM_opts={opt_btns} server_expected={expected} {status}")

        log(f"== SELESAI. mismatches={mismatches}")
        b.close()

if __name__ == "__main__":
    main()
