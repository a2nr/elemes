"""
Round-trip CSV siswa — format tunggal export/import:

    # Format kolom lesson: ...
    student_id;token;nama_siswa;<lesson_slug...>

Prinsip keamanan & struktur:
- Baris pertama file export memuat baris legend komentar (# Format kolom lesson...).
- Parser mengabaikan baris komentar di awal file (#) secara backward-compatible.
- Export SELALU mengosongkan kolom `token` (tidak ada recovery token).
- Token mentah hanya dibaca saat import; `raw_token` adalah field internal
  dengan repr=False dan tidak pernah muncul di error, preview, response, atau log.
- Parser murni (tanpa database); validasi DB ada di repositories.

Grammar kolom lesson round-trip:
- Kosong / not_started : tidak diubah (merge semantics).
- RESET (case-insensitive) : reset/hapus progress lesson untuk siswa ybs.
- completed : selesai (reading / single-activity).
- <earned>/<total> : skor kuis legacy (mis. "3/4").
- done:<exercise 1/0/kosong>:<earned>/<total> : status composite exercise + quiz.

Catatan pemakaian spreadsheet (Excel / Google Sheets):
Kolom lesson berisi "<earned>/<total>" atau "done:..." sebaiknya diformat sebagai
**Text** di aplikasi spreadsheet sebelum diedit manual agar delimiter "/" tidak
otomatis dikonversi menjadi tanggal.
"""

import csv
import io
import uuid
from dataclasses import dataclass, field

from services.progress_status import (
    ParsedProgress,
    format_progress_status,
    format_roundtrip_cell,
    parse_progress_status,
    parse_roundtrip_cell,
)

LEGEND_COMMENT_LINE = (
    "# Format kolom lesson: (kosong)=tidak diubah | RESET=reset ke belum-mulai | "
    "completed=selesai | <earned>/<total>=skor kuis | "
    "done:<exercise 1/0/kosong>:<earned>/<total>=composite exercise+kuis"
)

DELIMITER = ";"

# Delimiter export (canonical) — tetap dipakai serializer, tidak berubah.
EXPORT_DELIMITER = ";"
# Delimiter yang diterima saat import. Deteksi berbasis schema (lihat
# _detect_import_delimiter), bukan Sniffer — file pendek dengan banyak sel
# kosong (seperti hasil export spreadsheet) mudah salah terdeteksi Sniffer.
SUPPORTED_IMPORT_DELIMITERS = (";", ",")

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MiB
MAX_ROWS = 1000
MAX_NAME_LENGTH = 255
TOKEN_MIN_LENGTH = 8
TOKEN_MAX_LENGTH = 128

REQUIRED_COLUMNS = ("student_id", "token", "nama_siswa")

# Kontrol karakter yang dilarang dalam token (kontrol + DEL).
_CONTROL_CHARS = set(range(0x00, 0x20)) | {0x7F}


class RoundTripImportError(ValueError):
    """Import gagal total — daftar error hanya menyebut baris/kolom, bukan token."""

    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


@dataclass
class StudentRoundTripRow:
    """Satu baris hasil export/import.

    `raw_token` adalah field internal: repr=False, dan dilarang dicetak/dipantulkan
    ke response, preview, report, maupun log.
    """

    line: int
    student_id: str | None  # None / "" = siswa baru (UUID dibuat server)
    raw_token: str = field(repr=False)
    display_name: str
    progress: dict[str, ParsedProgress]  # {lesson_slug: status non-not_started}


def is_canonical_uuid(value: str) -> bool:
    """UUID canonical: format 8-4-4-4-12 huruf kecil, tanpa variasi lain."""
    try:
        return str(uuid.UUID(value)) == value
    except (ValueError, AttributeError, TypeError):
        return False


def mask_student_id(student_id: str | None) -> str:
    """Masking UUID untuk preview: cukup awalan, identitas tetap terlihat."""
    if not student_id:
        return ""
    return f"{student_id[:8]}…"


def _token_is_valid(token: str) -> bool:
    if not (TOKEN_MIN_LENGTH <= len(token) <= TOKEN_MAX_LENGTH):
        return False
    for ch in token:
        if ord(ch) in _CONTROL_CHARS or ch == "\n" or ch == "\r":
            return False
    return True


def validate_single_student_input(display_name: str, raw_token: str) -> list[str]:
    """Validasi input tambah-1-siswa (dipakai endpoint /students/add).

    Aturan sama dengan validasi baris CSV round-trip (nama & token), supaya
    kedua jalur (CSV & single-add) punya kontrak identik.
    """
    errors: list[str] = []
    name = (display_name or "").strip()
    if not name:
        errors.append("Nama siswa wajib diisi")
    elif len(name) > MAX_NAME_LENGTH:
        errors.append(f"Nama siswa maksimal {MAX_NAME_LENGTH} karakter")
    if not _token_is_valid(raw_token):
        errors.append(f"Token harus {TOKEN_MIN_LENGTH}-{TOKEN_MAX_LENGTH} karakter tanpa karakter kontrol")
    return errors


def _detect_import_delimiter(text: str) -> str:
    """Pilih delimiter import (`;` atau `,`) dari header, berbasis schema.

    Header dibaca dengan `csv.reader` per kandidat delimiter — bukan
    `splitlines()` + `split()` — sehingga quoting CSV dihormati. Kandidat
    valid bila ketiga kolom wajib muncul sebagai kolom individual.

    Jika tidak ada kandidat yang memenuhi schema:
    - header tetap SATU field pada semua kandidat → delimiter tidak
      dikenali (mis. tab-separated) → RoundTripImportError informatif;
    - selain itu (header terpecah tapi kolom salah) → dipilih delimiter
      yang memecah header menjadi field PALING BANYAK, supaya validasi
      missing/duplicate/unknown columns berikutnya paling akurat.
    """
    parsed: list[tuple[str, list[str]]] = []
    for candidate in SUPPORTED_IMPORT_DELIMITERS:
        try:
            header = next(csv.reader(io.StringIO(text), delimiter=candidate), None)
        except csv.Error:
            header = None
        if header:
            parsed.append((candidate, header))

    # Kandidat schema-valid; urutan SUPPORTED_IMPORT_DELIMITERS menjamin
    # delimiter canonical (`;`) menang bila keduanya kebetulan valid.
    for candidate, header in parsed:
        if all(col in header for col in REQUIRED_COLUMNS):
            return candidate

    if parsed and all(len(header) == 1 for _, header in parsed):
        raise RoundTripImportError(
            ["Delimiter CSV tidak dikenali; gunakan titik koma (;) atau koma (,)"]
        )

    if parsed:
        return max(parsed, key=lambda ch: len(ch[1]))[0]
    return EXPORT_DELIMITER


def _row_is_empty(record: dict) -> bool:
    return all(not (v or "").strip() for v in record.values())


def extract_slug_from_header(header: str, active_slugs: set[str] | None = None) -> str:
    """Ekstrak slug lesson canonical dari nama kolom header.

    Mendukung format:
    - Bare slug: "hello_world"
    - Slug + expected format: "hello_world [completed]", "quiz_test [<earned>/4]"
    - Title + (slug) + format: "Hello World (hello_world) [completed]"
    - Title + (slug): "Hello World (hello_world)"
    """
    raw = (header or "").strip()
    if not raw:
        return ""
    if active_slugs and raw in active_slugs:
        return raw

    # 1. Hapus kurung siku [expected format] di akhir bila ada
    base = raw
    if base.endswith("]") and "[" in base:
        base = base[: base.rfind("[")].strip()

    if active_slugs and base in active_slugs:
        return base

    # 2. Bila ada kurung biasa (slug) di akhir: "Title (slug)"
    if base.endswith(")") and "(" in base:
        inside = base[base.rfind("(") + 1 : -1].strip()
        if active_slugs and inside in active_slugs:
            return inside
        if inside:
            return inside

    return base


def parse_roundtrip_csv(
    content: str | bytes,
    active_lesson_slugs: list[str] | set[str],
) -> list[StudentRoundTripRow]:
    """Parse & validasi file round-trip secara murni (tanpa database).

    Mengembalikan daftar row valid, atau raise RoundTripImportError dengan
    seluruh error format (all-or-nothing). Error TIDAK pernah memuat token.
    """
    errors: list[str] = []

    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise RoundTripImportError(["Encoding file harus UTF-8 (dengan atau tanpa BOM)"])
    else:
        text = content
        if text.startswith("\ufeff"):
            text = text.lstrip("\ufeff")

    if len(text.encode("utf-8")) > MAX_FILE_BYTES:
        raise RoundTripImportError([f"File melebihi batas {MAX_FILE_BYTES // (1024 * 1024)} MiB"])

    lines = text.splitlines(keepends=True)
    comment_count = 0
    while comment_count < len(lines) and lines[comment_count].lstrip().startswith("#"):
        comment_count += 1
    cleaned_text = "".join(lines[comment_count:])

    if not cleaned_text.strip():
        raise RoundTripImportError(["File kosong atau header tidak ditemukan"])

    active = set(active_lesson_slugs)
    delimiter = _detect_import_delimiter(cleaned_text)
    try:
        reader = csv.DictReader(io.StringIO(cleaned_text), delimiter=delimiter)
        fieldnames = reader.fieldnames
        if not fieldnames:
            raise RoundTripImportError(["File kosong atau header tidak ditemukan"])
    except csv.Error:
        raise RoundTripImportError(["Format CSV tidak valid (delimiter/quoting rusak)"])

    # ── validasi header ──────────────────────────────────────────────
    missing = [col for col in REQUIRED_COLUMNS if col not in fieldnames]
    if missing:
        errors.append(f"Kolom wajib hilang: {', '.join(missing)}")

    seen_headers: set[str] = set()
    for col in fieldnames:
        if col in seen_headers:
            errors.append(f"Header duplikat: {col!r}")
        seen_headers.add(col)

    header_to_slug: dict[str, str] = {}
    seen_slugs: set[str] = set()
    for col in fieldnames:
        if col in REQUIRED_COLUMNS:
            continue
        slug = extract_slug_from_header(col, active)
        if slug not in active:
            errors.append(f"Kolom lesson tidak dikenal atau tidak aktif: {col!r}")
            continue
        if slug in seen_slugs:
            errors.append(f"Header duplikat untuk lesson: {col!r}")
            continue
        seen_slugs.add(slug)
        header_to_slug[col] = slug

    if errors:
        raise RoundTripImportError(errors)

    # ── validasi row ─────────────────────────────────────────────────
    rows: list[StudentRoundTripRow] = []
    seen_ids: set[str] = set()
    seen_tokens: set[str] = set()
    data_row_count = 0

    try:
        record_iter = iter(reader)
    except csv.Error:
        raise RoundTripImportError(["Format CSV tidak valid (delimiter/quoting rusak)"])

    while True:
        try:
            record = next(record_iter)
        except StopIteration:
            break
        except csv.Error:
            errors.append("Format CSV tidak valid (delimiter/quoting rusak)")
            break

        if _row_is_empty(record):
            continue
        data_row_count += 1
        line = reader.line_num + comment_count  # nomor baris fisik asli di file

        if data_row_count > MAX_ROWS:
            errors.append(f"Jumlah baris melebihi batas {MAX_ROWS}")
            break

        # student_id — diparse DULU karena menentukan aturan token di bawah.
        # Kolom kosong = siswa baru (UUID dibuat server); kolom terisi = baris
        # existing yang hanya boleh di-restore/update (tanpa token baru). Aturan
        # token memakai `is_existing_row` (kolom terisi) supaya baris dengan
        # UUID invalid/duplikat tidak memunculkan pesan "token wajib untuk siswa
        # baru" yang menyesatkan — error UUID-nya sudah cukup.
        sid_raw = (record.get("student_id") or "").strip()
        student_id: str | None = None
        is_existing_row = bool(sid_raw)
        if sid_raw:
            if not is_canonical_uuid(sid_raw):
                errors.append(f"Baris {line}, kolom student_id: UUID tidak valid")
            elif sid_raw in seen_ids:
                errors.append(f"Baris {line}, kolom student_id: UUID duplikat dalam file")
            else:
                seen_ids.add(sid_raw)
                student_id = sid_raw

        # token — aturan bergantung pada identitas baris:
        # - siswa baru (student_id kosong): token WAJIB diisi.
        # - siswa existing (student_id valid terisi): token boleh kosong
        #   (hasil export); token yang diisi tetap divalidasi formatnya, dan
        #   keputusan konflik (token baru untuk siswa existing) ada di repository.
        raw_token = record.get("token") or ""
        token = raw_token.strip()
        is_existing = is_existing_row
        if not token:
            if not is_existing:
                errors.append(
                    f"Baris {line}, kolom token: token wajib diisi untuk siswa baru"
                )
            # token kosong untuk baris existing = sah; sengaja TIDAK dimasukkan
            # ke seen_tokens agar dua baris export tidak dianggap duplikat.
        elif token != raw_token:
            errors.append(f"Baris {line}, kolom token: token tidak boleh memiliki spasi di awal/akhir")
        elif not _token_is_valid(token):
            errors.append(
                f"Baris {line}, kolom token: token harus {TOKEN_MIN_LENGTH}-{TOKEN_MAX_LENGTH} karakter "
                "tanpa karakter kontrol/newline"
            )
        elif token in seen_tokens:
            errors.append(f"Baris {line}, kolom token: token duplikat dalam file")
        else:
            seen_tokens.add(token)

        # nama_siswa
        name = record.get("nama_siswa") or ""
        name_stripped = name.strip()
        if not name_stripped:
            errors.append(f"Baris {line}, kolom nama_siswa: nama wajib diisi")
        elif len(name_stripped) > MAX_NAME_LENGTH:
            errors.append(f"Baris {line}, kolom nama_siswa: nama maksimal {MAX_NAME_LENGTH} karakter")

        # progress per lesson
        progress: dict[str, ParsedProgress] = {}
        for col, slug in header_to_slug.items():
            value = record.get(col) or ""
            try:
                parsed = parse_roundtrip_cell(value)
            except ValueError as exc:
                errors.append(f"Baris {line}, kolom {col}: {exc}")
                continue
            if parsed is not None:
                progress[slug] = parsed

        rows.append(
            StudentRoundTripRow(
                line=line,
                student_id=student_id,
                raw_token=token,
                display_name=name_stripped,
                progress=progress,
            )
        )

    if errors:
        raise RoundTripImportError(errors)
    return rows


def serialize_export_csv(
    rows: list[StudentRoundTripRow],
    lesson_slugs: list[str],
    lesson_headers: dict[str, str] | None = None,
) -> bytes:
    """Serialize row export → CSV UTF-8 BOM, delimiter ';', token selalu kosong.

    - Baris pertama: legend grammar sel progress (# Format kolom lesson...).
    - Header: student_id;token;nama_siswa;<lesson_headers...> sesuai urutan.
    - Status ditulis dengan grammar roundtrip (kosong/completed/<earned>/<total>/done:...).
    - `completed_count`, role, hash token, dan metadata internal tidak diekspor.
    """
    headers_map = lesson_headers or {}
    resolved_columns: list[tuple[str, str]] = []
    for item in lesson_slugs:
        header_label = headers_map.get(item, item)
        canonical_slug = extract_slug_from_header(item)
        resolved_columns.append((canonical_slug, header_label))

    fieldnames = ["student_id", "token", "nama_siswa", *[lbl for _, lbl in resolved_columns]]
    out = io.StringIO()
    out.write(f"{LEGEND_COMMENT_LINE}\n")
    writer = csv.DictWriter(
        out, fieldnames=fieldnames, delimiter=EXPORT_DELIMITER, lineterminator="\n"
    )
    writer.writeheader()
    for row in rows:
        record: dict[str, str] = {
            "student_id": row.student_id or "",
            "token": "",  # selalu kosong — tidak ada export/recovery token
            "nama_siswa": row.display_name,
        }
        for slug, col_name in resolved_columns:
            record[col_name] = format_roundtrip_cell(row.progress.get(slug))
        writer.writerow(record)
    return out.getvalue().encode("utf-8-sig")
