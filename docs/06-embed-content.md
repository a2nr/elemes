# Fitur Embed Konten di Materi Markdown & Slide

**Tanggal:** 2026-07-19
**Status:** Implementasi selesai
**Lokasi kode:** Backend `services/lesson_service.py` + Frontend (CSS only)

---

## 1. Latar Belakang

Elemes memerlukan fitur agar author materi dapat menyisipkan konten *embedded* (iframe dari platform luar) langsung dari markdown — baik di tubuh materi maupun di dalam slide presentasi. Contoh penggunaan: video YouTube, desain Canva, Google Docs, Figma, widget Scratch, dll.

### Infrastruktur yang Sudah Ada

Elemes **sudah punya** pipeline markdown→embed untuk `circuit` dan `flowchart`:
- **Backend** (`services/lesson_service.py`): regex fence ```circuit``` → `<div class="*-embed" data-*>`, lalu `md.markdown()` render jadi HTML.
- **Frontend** (`src/lib/actions/render*Embeds.ts`): `IntersectionObserver` ganti div → `<iframe>` lazy load.
- **Slide** sudah diparse di `lesson_service.py`, dan di dalam loop slide embed circuit/flowchart sudah diproses — jadi embed otomatis berlaku di materi **dan** slide.

**Kesimpulan feasibility:** ✅ Sangat feasible — infrastruktur sudah ada, tinggal diperluas polanya.

---

## 2. Evolusi Pendekatan

### Opsi Awal (Ditolak): URL-only fence + whitelist domain

Pendekatan pertama: user tulis URL di fence ```embed```, backend bikin div, frontend pasang iframe.

````markdown
```embed,100%,400px
https://www.youtube.com/embed/VIDEO_ID
```
````

**Masalah ditemukan saat testing:**
1. **Canva menolak di-iframe** — "canva.com refused to connect". Canva set `X-Frame-Options: DENY` untuk URL design biasa; butuh URL khusus `?embed` untuk mengizinkan iframe.
2. **Embed di slide stuck "Memuat..."** — karena iframe ditolak, `onload` tidak fire, loading text tidak dihapus.
3. **Perlu transform per-platform** — Canva butuh `?embed`, Google Docs butuh `/preview`, Figma butuh format khusus. Hardcode per-platform tidak fleksibel.

### Pendekatan Final (Dipilih): Raw HTML embed code + bleach sanitizer

Alih-alih URL, user **paste embed HTML code** siap pakai dari platform (Share → Embed):

````markdown
```embed
<div style="position: relative; width: 100%; padding-top: 56.25%;">
  <iframe loading="lazy" src="https://www.canva.com/design/.../view?embed" allowfullscreen></iframe>
</div>
<a href="https://www.canva.com/..." target="_blank" rel="noopener">Judul</a> by Author
```
````

**Kelebihan:**
- User kontrol penuh (aspect ratio, style, link credit) — embed code dari platform resmi sudah optimize.
- Support Canva, YouTube, Google Docs, Figma, Scratch, dll sekaligus — tanpa hardcode transform per-platform.
- Lebih fleksibel: author bisa kustomisasi wrapper, caption, dll.

**Konsekuensi keamanan:** Raw HTML = potensi XSS. Wajib **sanitize** sebelum render. Tanpa sanitize, author bisa sisipkan `<script>`, `onclick`, `onerror`, dll.

---

## 3. Desain Teknis

### Keamanan — Dual Layer

1. **`bleach` library** (Python standar industri):
   - Whitelist tag: `div`, `iframe`, `a`, `span`, `p`, `br`, `img`.
   - Whitelist attribute per tag: `iframe[src|style|loading|allowfullscreen|allow|title]`, `a[href|target|rel|style]`, dll.
   - Whitelist CSS property: `position`, `width`, `height`, `padding`, `margin`, `border-radius`, `box-shadow`, dll (via `CSSSanitizer` + `tinycss2`).
   - Strip: `<script>`, `onclick`, `onerror`, `javascript:` URL, dan semua tag/attr/style berbahaya.

2. **Domain blacklist** (`EMBED_BLOCKED_HOSTS`):
   - Cek `iframe[src]` setelah sanitasi: wajib `https://`, hostname tidak boleh di blacklist.
   - Default blokir: `localhost`, `127.0.0.1`, `0.0.0.0`, `metadata.google.internal`, `169.254.169.254` (cegah SSRF / metadata leak).
   - Subdomain ikut diblokir (mis. `sub.localhost`).

### Resiliensi — Graceful Degradation

Import `CSSSanitizer` di-bungkus `try/except ImportError`. Kalau `tinycss2` tidak terinstall di environment, aplikasi **tidak crash** — fallback ke `bleach.clean()` tanpa CSS sanitizer (tags/attrs tetap di-sanitize, hanya style CSS tidak difilter). Di production, `tinycss2` wajib ada di `requirements.txt` untuk keamanan penuh.

### Alur Pipeline

```
Markdown (```embed\nRAW HTML\n```)
  ↓
_process_embed_embeds() — regex match fence
  ↓
_sanitize_embed_html() — bleach.clean() + iframe src blacklist check
  ↓
HTML bersih (iframe jadi) → md.markdown() → lesson_content / slides_html
  ↓
Frontend: langsung render via {@html} — tidak perlu action khusus
```

Backend memanggil `_process_embed_embeds()` di 4 titik agar berlaku di semua konten:
1. Loop slide (slide carousel)
2. `lesson_content` (tubuh materi)
3. `exercise_content` (latihan)
4. `lesson_info` (info pelajaran)

Frontend tidak butuh action baru — HTML sudah berisi iframe jadi dari backend. Action `renderEmbedEmbeds.ts` dari pendekatan URL-only lama sudah dihapus.

---

## 4. Implementasi

### File yang Dimodifikasi/Dibuat

| File | Aksi | Detail |
|------|------|--------|
| `services/lesson_service.py` | EDIT | Tambah `import bleach`, `EMBED_ALLOWED_TAGS/ATTRS/STYLES`, fungsi `_sanitize_embed_html()` + `_process_embed_embeds()` (ganti URL-only lama). 4 call sites tetap dipanggil. |
| `services/tests/test_lesson_service_embed.py` | CREATE | 9 pytest: Canva HTML, YouTube HTML, strips `<script>`, strips `onclick`, blocked domain, non-https iframe, empty, unchanged, dangerous style. |
| `services/requirements.txt` | EDIT | Tambah `bleach>=6.0.0`, `tinycss2>=1.2.0`. |
| `frontend/src/app.css` | EDIT | Hapus `.generic-embed*` (tidak dipakai lagi), simpan `.embed-error`. |
| `frontend/src/routes/lesson/[slug]/+page.svelte` | EDIT | Hapus import + call `renderEmbedEmbeds` (tidak perlu lagi). |
| `frontend/src/lib/actions/renderEmbedEmbeds.ts` | DELETE | Pendekatan URL-only dihapus. |
| `examples/content/dasar/test_slides.md` | EDIT | Contoh Canva (raw HTML, di dalam slide) + YouTube (raw HTML, di body materi). |

### Verifikasi

- ✅ `pytest tests/ -v` — 9/9 passed.
- ✅ `npm run build` — sukses tanpa error.
- ✅ Manual test: Canva embed (dengan `?embed` URL) load di slide; YouTube embed load di body.

---

## 5. Cara Pakai

### Untuk Author Materi

1. Buka platform (Canva, YouTube, Google Docs, dll) → klik **Share** / **Bagikan** → **Embed**.
2. Copy kode HTML yang diberikan (biasanya berisi `<iframe>` + optional wrapper `<div>` + `<a>` credit).
3. Paste di markdown materi di dalam fence ```embed```:

````markdown
```embed
<div style="position: relative; width: 100%; padding-top: 56.25%;">
  <iframe loading="lazy" src="https://www.canva.com/design/.../view?embed" allowfullscreen></iframe>
</div>
```
````

4. Embed otomatis muncul di materi. Kalau diletakkan di dalam blok `---slide-start---` / `---slide-end---`, embed muncul di slide carousel.

### Catatan Platform

| Platform | Cara dapat embed code |
|----------|---------------------|
| Canva | Share → Embed → Copy. URL sudah include `?embed`. |
| YouTube | Share → Embed → Copy. URL pakai `youtube.com/embed/VIDEO_ID`. |
| Google Docs | File → Share → Publish to web → Embed → Copy. URL pakai `/preview`. |
| Figma | Share → Get embed code → Copy. URL pakai `figma.com/embed?...`. |

### Pesan Error

- **"Konten embed ditolak: iframe harus https."** — URL iframe pakai `http://`, ganti ke `https://`.
- **"Konten embed ditolak: domain iframe diblokir."** — Domain iframe ada di blacklist (internal/metadata endpoint).
- **"Konten embed kosong."** — Fence ```embed``` tidak berisi apa-apa.

---

## 6. Pertanyaan Umum

**Kenapa pakai raw HTML, bukan URL saja?**
Karena setiap platform punya format embed berbeda (Canva butuh `?embed`, Google Docs butuh `/preview`, Figma butuh `embed_host`). Dengan raw HTML, author paste kode siap pakai dari platform — lebih fleksibel dan tidak perlu hardcode transform per-platform di backend.

**Apakah aman?**
Ya. HTML di-sanitize pakai `bleach` (whitelist tag/attr/style) + cek domain iframe di blacklist. `<script>`, event handler (`onclick`), `javascript:` URL, dan domain berbahaya semua ditolak.

**Bisa dipakai di slide?**
Ya. Embed di dalam `---slide-start---` / `---slide-end---` otomatis diproses — backend panggil `_process_embed_embeds()` di loop slide.

**Kenapa `.generic-embed*` CSS dihapus?**
Itu CSS dari pendekatan URL-only lama (frontend bikin div + lazy iframe). Sekarang iframe sudah jadi dari backend, tidak butuh wrapper CSS khusus. `.embed-error` tetap dipertahankan untuk pesan error.

---

## 7. Riwayat Dokumen

Dokumen ini mengonsolidasi 4 file plan awal yang sudah superseded:
- `possibility-study-embed.md` — studi feasibility awal (opsi A/B/C).
- `plan-embed-implementation.md` — plan implementasi Opsi A (URL + whitelist).
- `plan-fix-embed-stuck.md` — diagnosis "stuck loading" (sempat dikira race condition, ternyata Canva block).
- `plan-embed-rawhtml.md` — plan final pendekatan raw HTML + bleach.

Konsolidasi dilakukan agar pembaca masa depan tidak perlu membaca 4 file perjalanan; cukup 1 dokumen koheren yang menceritakan konteks, keputusan, dan hasil akhir.
