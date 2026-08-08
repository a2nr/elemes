# 10. Flowchart Interaktif

Blok `` ```flowchart `` di materi markdown membuat flowchart interaktif dengan evaluasi frontend.

## Format

```markdown
```flowchart
start → [Kondisi A?] → ya → [Aksi 1] → end
                ↓ tidak
            [Aksi 2] → end
```
```

## Fitur

- **Node & edge** — node dengan label, edge dengan arah
- **Obstacle-aware orthogonal routing** — routing edge menghindari obstacle
- **Readonly mode** — flowchart hanya bisa dilihat, tidak diedit
- **Evaluasi frontend** — evaluasi struktur flowchart (JSON) di sisi klien

## Evaluasi

Flowchart dievaluasi oleh frontend:
1. Parse JSON flowchart data
2. Verifikasi struktur: node ada, edge valid, tidak ada siklus (jika tidak diizinkan)
3. Render visual dengan routing orthogonal

## Contoh

Lihat `examples/content/flowchart.md` untuk contoh flowchart dengan evaluasi.