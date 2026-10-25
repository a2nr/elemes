"""
Test Fitur D — optimasi kecepatan load gambar asset.

Arsitektur: original disimpan apa adanya; optimasi terjadi saat serving
(resize + WebP on-the-fly, cache di `CACHE_DIR`).

Batas keras yang diuji di sini: cache WAJIB di luar `ASSETS_DIR` supaya
export bundle tetap lossless (hanya original yang ter-zip).
"""

import base64
import io
import os
import pathlib
import zipfile

import pytest

from config import ASSETS_DIR, CACHE_DIR

TEST_ASSETS = pathlib.Path(ASSETS_DIR)
TEST_CACHE = pathlib.Path(CACHE_DIR)

DB_REQUIRED = os.environ.get("DATABASE_URL", "").strip()


# ── Helpers ────────────────────────────────────────────────────────

def _make_png(width: int = 800, height: int = 600) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), (30, 120, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _make_gif(animated: bool = False) -> bytes:
    from PIL import Image

    frames = []
    for color in [(255, 0, 0), (0, 255, 0)]:
        frames.append(Image.new("RGB", (10, 10), color))
    buf = io.BytesIO()
    if animated:
        frames[0].save(
            buf, format="GIF", save_all=True, append_images=frames[1:], duration=100, loop=0
        )
    else:
        frames[0].save(buf, format="GIF")
    return buf.getvalue()


def _write(rel_path: str, raw: bytes) -> pathlib.Path:
    target = TEST_ASSETS / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return target


# ── Unit: lokasi cache & varian ────────────────────────────────────

def test_cache_dir_is_outside_assets_dir():
    """Cache WAJIB sibling, bukan di dalam ASSETS_DIR.

    Kalau cache di dalam ASSETS_DIR, `export_bundle` (os.walk tanpa filter)
    akan ikut men-zip file turunan → bundel ter-import ulang berisi duplikat.
    """
    assets_abs = os.path.abspath(ASSETS_DIR)
    cache_abs = os.path.abspath(CACHE_DIR)
    assert cache_abs != assets_abs
    assert not cache_abs.startswith(assets_abs + os.sep)
    assert os.path.basename(cache_abs) == "assets-cache"


def test_variant_generated_and_reused_from_cache():
    raw = _make_png()
    path = _write("big.png", raw)

    from services import image_cache

    first = image_cache.get_variant(str(path), "big.png")
    assert first is not None
    data, key = first
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP"

    cache_files = list(TEST_CACHE.glob("*.webp"))
    assert len(cache_files) == 1
    assert cache_files[0].read_bytes() == data
    mtime_before = cache_files[0].stat().st_mtime_ns

    # Kunjungan kedua: HARUS pakai cache (tidak regenerate).
    second = image_cache.get_variant(str(path), "big.png")
    assert second is not None
    assert second[1] == key
    assert second[0] == data
    assert cache_files[0].stat().st_mtime_ns == mtime_before
    assert len(list(TEST_CACHE.glob("*.webp"))) == 1


def test_variant_invalidated_when_source_replaced():
    path = _write("swap.png", _make_png(400, 300))

    from services import image_cache

    first = image_cache.get_variant(str(path), "swap.png")
    assert first is not None

    # File asli diganti → mtime berubah → key baru.
    path.write_bytes(_make_png(410, 310))
    second = image_cache.get_variant(str(path), "swap.png")
    assert second is not None
    assert second[1] != first[1]


def test_svg_is_not_converted():
    path = _write("icon.svg", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>")

    from services import image_cache

    assert image_cache.get_variant(str(path), "icon.svg") is None


def test_animated_gif_is_not_converted():
    path = _write("anim.gif", _make_gif(animated=True))

    from services import image_cache

    assert image_cache.get_variant(str(path), "anim.gif") is None


def test_corrupt_image_returns_none_for_original_fallback():
    path = _write("broken.png", b"not-a-real-png")

    from services import image_cache

    assert image_cache.get_variant(str(path), "broken.png") is None


def test_variant_respects_width_parameter():
    from PIL import Image

    path = _write("wide.png", _make_png(1200, 800))

    from services import image_cache

    variant = image_cache.get_variant(str(path), "wide.png", width=300)
    assert variant is not None
    with Image.open(io.BytesIO(variant[0])) as im:
        assert im.width == 300
        assert im.height == 200


def test_variant_respects_max_dimension():
    from PIL import Image

    path = _write("huge.png", _make_png(3000, 2000))

    from services import image_cache

    variant = image_cache.get_variant(str(path), "huge.png")
    assert variant is not None
    with Image.open(io.BytesIO(variant[0])) as im:
        assert max(im.size) == 1600  # ASSET_VARIANT_MAX_DIM default


# ── Route: /assets/<path> (publik, tanpa DB) ───────────────────────

def test_asset_route_serves_webp_variant(client):
    _write("foto.png", _make_png())
    resp = client.get("/assets/foto.png")
    assert resp.status_code == 200
    assert resp.mimetype == "image/webp"
    assert resp.data[:4] == b"RIFF" and resp.data[8:12] == b"WEBP"
    assert resp.headers.get("ETag")
    assert "public" in resp.headers.get("Cache-Control", "")
    assert resp.headers.get("X-Asset-Variant") == "webp"


def test_asset_route_second_request_hits_cache(client):
    _write("foto2.png", _make_png())
    first = client.get("/assets/foto2.png")
    cache_files = list(TEST_CACHE.glob("*.webp"))
    assert len(cache_files) == 1
    mtime_before = cache_files[0].stat().st_mtime_ns

    second = client.get("/assets/foto2.png")
    assert second.status_code == 200
    assert second.headers.get("ETag") == first.headers.get("ETag")
    assert cache_files[0].stat().st_mtime_ns == mtime_before
    assert len(list(TEST_CACHE.glob("*.webp"))) == 1


def test_asset_route_etag_returns_304(client):
    _write("foto3.png", _make_png())
    first = client.get("/assets/foto3.png")
    etag = first.headers.get("ETag")
    assert etag
    resp = client.get("/assets/foto3.png", headers={"If-None-Match": etag})
    assert resp.status_code == 304


def test_asset_route_orig_param_serves_original(client):
    raw = _make_png()
    _write("orig.png", raw)
    resp = client.get("/assets/orig.png?orig=1")
    assert resp.status_code == 200
    assert resp.data == raw
    assert resp.mimetype == "image/png"
    assert resp.headers.get("X-Asset-Variant") == "original"


def test_asset_route_width_param(client):
    _write("w.png", _make_png(1200, 800))
    resp = client.get("/assets/w.png?w=400")
    assert resp.status_code == 200
    from PIL import Image

    with Image.open(io.BytesIO(resp.data)) as im:
        assert im.width == 400


def test_asset_route_svg_passthrough_with_csp(client):
    raw = b"<svg xmlns='http://www.w3.org/2000/svg'><script>x</script></svg>"
    _write("icon.svg", raw)
    resp = client.get("/assets/icon.svg")
    assert resp.status_code == 200
    assert resp.data == raw
    assert resp.mimetype == "image/svg+xml"
    assert "sandbox" in resp.headers.get("Content-Security-Policy", "")


def test_asset_route_corrupt_file_falls_back_to_original(client):
    raw = b"not-a-real-png"
    _write("bad.png", raw)
    resp = client.get("/assets/bad.png")
    assert resp.status_code == 200
    assert resp.data == raw
    assert resp.headers.get("X-Asset-Variant") == "original"


def test_asset_route_missing_file_404(client):
    resp = client.get("/assets/tidak-ada.png")
    assert resp.status_code == 404


def test_asset_route_rejects_path_traversal(client):
    resp = client.get("/assets/../../etc/passwd")
    assert resp.status_code in (400, 404)


def test_asset_route_static_gif_converted(client):
    _write("statis.gif", _make_gif(animated=False))
    resp = client.get("/assets/statis.gif")
    assert resp.status_code == 200
    assert resp.mimetype == "image/webp"


# ── Integrasi: export bundle tetap lossless ───────────────────────

@pytest.mark.skipif(not DB_REQUIRED, reason="butuh DATABASE_URL (PostgreSQL nyata)")
@pytest.mark.integration
def test_export_bundle_contains_only_originals_after_serving(client):
    """Acceptance test wajib: cache terisi → export tetap hanya original."""
    from services import repositories as repo
    from services.database import SessionLocal
    from services.tests.conftest import TEACHER_TOKEN

    db = SessionLocal()
    try:
        teacher = repo.create_user(db, display_name="Pak Guru", role="teacher")
        repo.create_access_token(db, user_id=teacher.id, raw_token=TEACHER_TOKEN)
        db.commit()
    finally:
        db.close()

    raw = _make_png()
    _write("bundle.png", raw)

    client.set_cookie("student_token", TEACHER_TOKEN)

    # 1. Request gambar → varian WebP dibuat & di-cache.
    resp = client.get("/assets/bundle.png")
    assert resp.status_code == 200
    assert resp.mimetype == "image/webp"
    assert list(TEST_CACHE.glob("*.webp")), "cache varian harus terisi"

    # 2. Export bundle → zip harus berisi ORIGINAL saja.
    export = client.get("/content/export")
    assert export.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(export.data)).namelist()

    assert "assets/bundle.png" in names
    assert not any(n.endswith(".webp") for n in names), (
        f"file turunan WebP ikut ter-zip: {[n for n in names if n.endswith('.webp')]}"
    )
    # Tidak ada folder cache di dalam assets.
    assert not any(n.startswith("assets-cache") for n in names)
    assert not any("assets-cache" in n for n in names)


@pytest.mark.skipif(not DB_REQUIRED, reason="butuh DATABASE_URL (PostgreSQL nyata)")
@pytest.mark.integration
def test_assets_tree_does_not_expose_cache_folder(client):
    """getTree('assets') tidak boleh menampilkan folder cache."""
    from services import repositories as repo
    from services.database import SessionLocal
    from services.tests.conftest import TEACHER_TOKEN

    db = SessionLocal()
    try:
        teacher = repo.create_user(db, display_name="Pak Guru", role="teacher")
        repo.create_access_token(db, user_id=teacher.id, raw_token=TEACHER_TOKEN)
        db.commit()
    finally:
        db.close()

    _write("terlihat.png", _make_png())
    client.set_cookie("student_token", TEACHER_TOKEN)

    # Pastikan cache benar-benar terisi (di luar ASSETS_DIR).
    client.get("/assets/terlihat.png")
    assert list(TEST_CACHE.glob("*.webp"))

    resp = client.get("/content/tree?root=assets")
    assert resp.status_code == 200
    tree = resp.get_json()["tree"]
    names = [n.get("name") for n in tree]
    assert "terlihat.png" in names
    assert "assets-cache" not in names
