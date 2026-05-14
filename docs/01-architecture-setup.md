# 01. Architecture & Setup

## High-Level System Architecture

The Elemes LMS-C project uses a multi-container architecture orchestrated via Podman, with a Tailscale Funnel acting as the public ingress point.

```
Internet (HTTPS :443)
    │
    ▼
Tailscale Funnel (elemes-ts)
    │
    ├── /                   → SvelteKit Frontend (elemes-frontend :3000)
    ├── /assets/            → Flask Backend (elemes :5000)
    ├── /velxio/api/compile → Flask Backend (Rate-limited Proxy :5000)
    ├── /velxio/            → Velxio Arduino Simulator (velxio :80)
    │
    ▼
SvelteKit Frontend (elemes-frontend :3000)
  ├── SSR pages (lesson content embedded in HTML)
  ├── CodeMirror 6 editor (lazy-loaded)
  ├── CircuitJS simulator (iframe, GWT-compiled) — mode "circuit"
  ├── Velxio Arduino simulator (iframe, React) — mode "velxio"
  ├── API proxy: /api/* → Flask
  └── PWA manifest
    │
    ▼  /api/*
Flask API Backend (elemes :5000)
  ├── Code compilation (Proxied to Compiler Worker)
  ├── Arduino Proxy (/velxio-compile → Velxio :80)
  ├── Token authentication (CSV)
  ├── Progress tracking
  └── Lesson content parsing (markdown)
    │
    ▼  HTTP
Compiler Worker (compiler-worker :8080)
  ├── gVisor Sandbox (runsc runtime)
  ├── Gunicorn (4 workers)
  └── Isolation: gcc / python3 execution
    │
Velxio Arduino Simulator (velxio :80)
  ├── React + Vite frontend (editor + simulator canvas)
  ├── FastAPI backend (arduino-cli compile)
  ├── AVR8 / RP2040 CPU emulation (browser)
  └── PostMessage bridge ↔ Elemes (EmbedBridge.ts)
```

## Container Setup

| Container | Image | Port | Fungsi |
|-----------|-------|------|--------|
| `elemes` | Python 3.11 | 5000 | Flask API (auth, lessons, progress, compile-proxy) |
| `compiler-worker` | Python 3.11 + gcc | 8080 | **Sandboxed** execution engine (gVisor) |
| `elemes-frontend` | Node 20 | 3000 | SvelteKit SSR |
| `velxio` | Node + Python + arduino-cli | 80 | Simulator Arduino (React + FastAPI) |
| `elemes-ts` | Tailscale | 443 | HTTPS Funnel + reverse proxy |

## Directory Structure

```
project/
├── .env                  # Konfigurasi environment
├── content/              # Folder materi pelajaran (file .md)
│   ├── home.md           # Halaman utama & daftar pelajaran
│   ├── hello_world.md    # Contoh materi
│   └── ...
├── assets/               # Gambar untuk materi (opsional)
│   └── gambar.png
├── tokens_siswa.csv      # Data token siswa (auto-generated)
├── state/                # State Tailscale (auto-generated)
└── elemes/               # Folder engine LMS (JANGAN DIUBAH)
    ├── elemes.sh          # Script untuk menjalankan LMS
    └── ...
```

## Setup and Execution

The primary entry point for managing the system is the `elemes.sh` script located in the `elemes` folder.

1. **Initialization:**
   ```bash
   cd elemes
   ./elemes.sh init
   ```
   Generates `.env`, `content/`, and `tokens_siswa.csv` from examples. Safe to run multiple times.

2. **Configuration:**
   Edit `../.env` to set branding and Tailscale configuration:
   ```env
   APP_BAR_TITLE=Pemrograman C - SMK Nusantara
   COPYRIGHT_TEXT=SMK Nusantara @ 2025
   PAGE_TITLE_SUFFIX=SMK Nusantara
   CONTENT_DIR=content
   TOKENS_FILE=tokens.csv
   ELEMES_HOST=lms-smk-nusantara
   TS_AUTHKEY=tskey-auth-xxxx
   ```

3. **Running the Application:**
   ```bash
   ./elemes.sh runbuild  # Build images and start containers
   ./elemes.sh run       # Start containers without rebuilding
   ./elemes.sh stop      # Stop all containers
   ```

4. **Managing Users (Tokens):**
   To update columns in the CSV based on available lessons:
   ```bash
   ./elemes.sh generatetoken
   ```
   Then manually edit `tokens_siswa.csv` (using semicolon `;` delimiter) to add student rows. The first data row is always the teacher token.

## Security Overview

The system incorporates several security layers to ensure stability and safety:
1. **Isolated Execution:** User-submitted C and Python code runs inside a `compiler-worker` container protected by a **gVisor (`runsc`) sandbox**, preventing RCE attacks from reaching the host kernel.
2. **Rate Limiting & Tarpitting:**
   - Anonymous users: Limited to **1 compile per 2 minutes** per IP, with a global queue of 20 slots.
   - Login endpoints: Max **50 requests per minute per IP**.
   - Failed logins: Suffer a **1.5-second tarpit delay** to neutralize brute-force attacks.
3. **Cookie Security:** The `student_token` session cookie uses `httponly: true`, `samesite: 'Lax'`, and dynamically sets `secure: true` based on the `COOKIE_SECURE` environment variable.
