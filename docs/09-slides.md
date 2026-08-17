---
title: Slide Presentasi
order: 9
category: slides
---
# 09. Slide Presentasi Interaktif

Blok `---slide-start---` dan `---slide-end---` di materi markdown membuat carousel presentasi interaktif dengan fullscreen mode.

## Format

```markdown
---slide-start---
## Slide 1: Judul
Konten slide ini mendukung teks, gambar, code fence, dan embed.

```c
int main() {
    printf("Hello, World!\n");
    return 0;
}
```

---slide-end---
```

## Fitur

- **Fullscreen mode** — tombol fullscreen untuk setiap slide
- **Embed support** — Canva, YouTube, Google Docs, Figma di dalam slide
- **Auto-save indicator** — indikator penyimpanan otomatis
- **Progress indicator** — menunjukkan slide ke berapa dari total

## Contoh

Lihat `examples/content/dasar/rangkaian_dasar.md` untuk contoh slide dengan embed Canva dan circuit.

## Catatan

- Slide mendukung semua blok markdown kecuali `---QUIZ_FLASHCARD---` dan `---slide-start---` di dalam slide
- Embed di dalam slide diproses otomatis oleh backend (`_process_embed_embeds()` di loop slide)
- Gambar di slide menggunakan path relatif `/assets/` atau URL absolut