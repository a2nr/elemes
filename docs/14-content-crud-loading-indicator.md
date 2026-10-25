# 14 — Indikator Loading untuk CRUD /teacher/content, Upload Asset & Export

## Latar Belakang

Halaman editor konten (`frontend/src/routes/teacher/content/+page.svelte`) memiliki
beberapa operasi yang bisa memakan waktu (upload base64, export zip, CRUD tree),
tetapi tidak memberikan umpan balik visual apa pun selama operasi berjalan.
Akibatnya guru tidak tahu apakah aksi sedang diproses, dan tombol bisa diklik ganda
(resiko file/folder duplikat atau request ganda).

## Temuan Audit (kondisi saat ini)

| Operasi | Handler | Kondisi saat ini |
|---|---|---|
| Upload asset | `handleUpload()` → `uploadAsset()` | ❌ Tanpa indikator. Upload base64 bisa lama untuk file besar. |
| Export bundle | `handleExport()` → `exportBundle()` | ⚠️ Tombol hanya `disabled={importExportBusy}`, tidak ada spinner/teks "sedang menyiapkan". |
| Import bundle | `handleImportFile()` | ⚠️ `importProgress` ($state) di-update via `onProgress` tapi **tidak pernah dirender** — CSS `.ie-progress` sudah ada namun tak terpakai (dead code). |
| Buat folder | `handleCreateFolder()` → `createFolder()` | ❌ Tanpa busy state; bisa double-submit. |
| Buat file | `handleCreateFile()` → `createFile()` | ❌ Tanpa busy state. |
| Rename | `handleRename()` → `renameEntry()` | ❌ Tanpa busy state. |
| Delete (biasa & force) | `handleDelete()` → `deleteEntry()` | ❌ Tanpa busy state. |
| Save / Publish | `mgr.handleSave()` / `handlePublish()` | ✅ Sudah ada (`⏳` + disabled) — jadikan pola referensi. |

Referensi pola spinner yang sudah ada di kodebase: `.progress-spinner` di
`DeployTab.svelte` / `DeployFAB.svelte`, dan pola `busy` di dialog dialog
(`AddStudentDialog`, `BulkDeleteStudentsDialog`, `StudentImportDialog`).

## Rencana Implementasi

### Fase 1 — Infrastruktur state busy (inti)

File: `frontend/src/routes/teacher/content/+page.svelte`

1. Tambahkan state lokal:

   ```ts
   let treeBusy = $state<string | null>(null); // label operasi, mis. 'Membuat folder…'
   ```

2. Helper pembungkus agar semua handler konsisten + mencegah double-submit:

   ```ts
   async function withTreeBusy(label: string, fn: () => Promise<void>) {
     if (treeBusy) return; // guard re-entrancy
     treeBusy = label;
     try { await fn(); }
     finally { treeBusy = null; }
   }
   ```

3. Bungkus handler berikut: `handleCreateFolder`, `handleCreateFile`,
   `handleRename`, `handleDelete` (termasuk jalur force delete),
   `handleUpload`, dan `handleExport`.

### Fase 2 — Indikator di header tree (treeActions)

1. Saat `treeBusy !== null`, tampilkan teks status kecil di tree header
   (regunakan style `.ie-progress` yang sudah ada):

   ```svelte
   {#if treeBusy}<span class="ie-progress">⏳ {treeBusy}</span>{/if}
   ```

2. Semua tombol `tree-action-btn` (📄 📁 ⬆️ 📤 📥) mendapat
   `disabled={treeBusy !== null}`; tombol yang sedang berjalan menampilkan `⏳`.

### Fase 3 — Render progress import (perbaiki dead code)

- Render `importProgress` yang sudah di-update oleh `importBundle.onProgress`:
  `"{importProgress.done}/{importProgress.total} — {importProgress.current}"`.
- Karena import & export sama-sama memakai `importExportBusy`, tampilkan
  `importProgress` bila ada, atau `treeBusy`/label statis ("Menyiapkan zip…")
  untuk export.

### Fase 4 — Feedback tambahan (opsional, prioritas rendah)

1. Toast "Mengunggah {file.name}…" saat upload dimulai (fungsi `showToast`
   sudah tersedia di file ini).
2. Skeleton/dim overlay pada `.tree-panel` saat `loadTrees()` berjalan pasca
   operasi CRUD, agar tidak terlihat "berkedip" tanpa penjelasan.
3. Ganti `window.prompt` folder tujuan upload dengan dialog kecil (terpisah,
   tidak wajib).

### Fase 5 — Verifikasi

1. Build lolos: `npm run build` / `npm run check` di `frontend/`.
2. Uji manual (throttle jaringan "Slow 3G" di DevTools):
   - Upload gambar ±5 MB → tombol ⬆️ jadi ⏳, tombol lain disabled, toast muncul.
   - Export saat tree berisi banyak file → label "Menyiapkan zip…" sampai unduh dimulai.
   - Import zip besar → teks `n/total — path` berjalan.
   - Buat/rename/delete folder & file → status muncul; klik ganda cepat tidak
     menghasilkan request kedua (guard `treeBusy`).
   - Save/Publish tidak berubah perilaku.

## Kriteria Selesai

- [ ] Semua operasi CRUD tree, upload asset, export, dan import menampilkan
      indikator loading saat berjalan.
- [ ] Tombol-tombol terkait disabled selama operasi berjalan (tidak bisa double-submit).
- [ ] `importProgress` benar-benar tampil di UI (dead code terpakai).
- [ ] Tidak ada regresi pada Save/Publish dan preview.

## File yang Diubah

- `frontend/src/routes/teacher/content/+page.svelte` (satu-satunya file wajib —
  state, helper, markup header tree, dan CSS `.ie-progress` sudah tersedia).

Estimasi: kecil–sedang (± 0.5–1 hari termasuk uji manual).
