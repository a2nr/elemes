"""
Cache varian ringan (WebP) untuk asset gambar raster.

Arsitektur (Fitur D — optimasi kecepatan load gambar):

- **Upload menyimpan file original apa adanya.** Tidak ada konversi saat
  upload — original tetap utuh di storage dan bisa diakses kapan saja.
- **Optimasi terjadi saat serving.** Saat browser meminta `/assets/<path>`,
  server mengirim versi ringan: resize (maks dimensi) + encode WebP, yang
  di-generate on-the-fly lalu di-cache di disk.
- **Semua asset lama otomatis ikut teroptimasi** — tanpa migrasi, tanpa
  tooling konversi, tanpa menyentuh konten markdown (path referensi tidak
  berubah).

Batas keras: cache WAJIB berada di luar `ASSETS_DIR` (lihat `config.CACHE_DIR`).
`export_bundle` men-zip seluruh isi `ASSETS_DIR` tanpa filter — kalau cache
berada di dalam, file turunan ikut ter-zip lalu ter-import ulang sebagai asset
biasa. Dengan cache di luar, export tetap 100% lossless.

Invalidasi: berdasarkan `mtime` + `size` file original. File diganti →
mtime berubah → key cache berubah → entry lama menjadi yatim (dibiarkan,
dibersihkan lazy).
"""

from __future__ import annotations

import hashlib
import io
import logging
import os

from config import (
    ASSET_VARIANT_MAX_DIM,
    ASSET_VARIANT_QUALITY,
    CACHE_DIR,
)

logger = logging.getLogger(__name__)

# Ekstensi gambar raster yang boleh di-generate varian WebP-nya.
RASTER_EXTS = frozenset({'.png', '.jpg', '.jpeg', '.webp', '.gif'})

# Ekstensi yang selalu di-serve apa adanya (vektor / format khusus).
PASSTHROUGH_EXTS = frozenset({'.svg'})


def is_raster(rel_path: str) -> bool:
    """True bila path adalah gambar raster yang boleh di-generate variannya."""
    return os.path.splitext(rel_path.lower())[1] in RASTER_EXTS


def is_passthrough(rel_path: str) -> bool:
    """True bila file harus selalu di-serve original (mis. SVG)."""
    return os.path.splitext(rel_path.lower())[1] in PASSTHROUGH_EXTS


def cache_key(rel_path: str, mtime_ns: int, size: int, width: int | None) -> str:
    """Kunci cache deterministik: path + mtime + ukuran + lebar varian.

    mtime membuat cache otomatis invalidasi saat file asli diganti.
    """
    raw = f'{rel_path}|{mtime_ns}|{size}|{width or 0}'.encode('utf-8')
    return hashlib.sha1(raw).hexdigest()


def _cache_file_for(key: str) -> str:
    return os.path.join(CACHE_DIR, f'{key}.webp')


def _build_webp(abs_path: str, width: int | None) -> bytes | None:
    """Buka original, resize (bila perlu), encode WebP.

    Return None bila file tidak bisa diproses (corrupt, format tak didukung,
    GIF animasi, dsb) — pemanggil lalu fallback serve original.
    """
    try:
        from PIL import Image, ImageOps
    except ImportError:  # pragma: no cover - Pillow adalah dependency wajib
        logger.warning("Pillow tidak tersedia — varian WebP dilewati")
        return None

    try:
        with Image.open(abs_path) as im:
            # GIF/WebP animasi: konversi WebP animasi kompleks & berisiko —
            # biarkan apa adanya (pass-through).
            if getattr(im, 'is_animated', False):
                return None

            # Hormati orientasi EXIF (foto HP) sebelum resize.
            try:
                im = ImageOps.exif_transpose(im)
            except Exception:  # pragma: no cover - EXIF rusak tidak fatal
                pass

            if im.mode not in ('RGB', 'RGBA'):
                im = im.convert('RGBA' if 'transparency' in im.info else 'RGB')

            target = width or ASSET_VARIANT_MAX_DIM
            longest = max(im.size)
            if longest > target:
                scale = target / longest
                new_size = (
                    max(1, round(im.width * scale)),
                    max(1, round(im.height * scale)),
                )
                im = im.resize(new_size, Image.LANCZOS)

            buf = io.BytesIO()
            im.save(buf, format='WEBP', quality=ASSET_VARIANT_QUALITY, method=4)
            return buf.getvalue()
    except Exception as exc:
        logger.warning("Gagal membuat varian WebP untuk %s: %r", abs_path, exc)
        return None


def get_variant(
    abs_path: str,
    rel_path: str,
    width: int | None = None,
) -> tuple[bytes, str] | None:
    """Ambil (atau buat) varian WebP untuk asset gambar raster.

    Return `(bytes, etag)` bila varian berhasil dibuat/diambil,
    atau `None` bila file tidak boleh/berhasil di-variant-kan
    (SVG, GIF animasi, file korrupt, Pillow gagal) — pemanggil harus
    fallback ke original.
    """
    if not is_raster(rel_path):
        return None

    try:
        st = os.stat(abs_path)
    except OSError:
        return None

    key = cache_key(rel_path, st.st_mtime_ns, st.st_size, width)
    cache_file = _cache_file_for(key)

    try:
        with open(cache_file, 'rb') as fh:
            data = fh.read()
        if data:
            return data, key
    except FileNotFoundError:
        pass
    except OSError as exc:  # pragma: no cover - I/O error tak terduga
        logger.warning("Gagal baca cache %s: %r", cache_file, exc)

    data = _build_webp(abs_path, width)
    if not data:
        return None

    # Tulis atomik supaya request paralel tidak membaca file setengah jadi.
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp_file = f'{cache_file}.{os.getpid()}.tmp'
        with open(tmp_file, 'wb') as fh:
            fh.write(data)
        os.replace(tmp_file, cache_file)
    except OSError as exc:  # pragma: no cover - mis. cache dir tidak writable
        logger.warning("Gagal menyimpan cache %s: %r", cache_file, exc)

    return data, key
