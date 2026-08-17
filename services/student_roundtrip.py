"""
Round-trip CSV siswa — format tunggal export/import:

    student_id;token;nama_siswa;<lesson_slug...>

Prinsip keamanan:
- Export SELALU mengosongkan kolom `token` (tidak ada recovery token).
- Token mentah hanya dibaca saat import; `raw_token` adalah field internal
  dengan repr=False dan tidak pernah muncul di error, preview, response, atau log.
- Parser murni (tanpa database); validasi DB ada di repositories.

Format status progress mengikuti kontrak legacy (lihat progress_status.py):
belum mulai = kosong / not_started; selesai = completed; skor = "<earned>/<total>".
"""

import csv
import io
import uuid
from dataclasses import dataclass, field

from services.progress_status import ParsedProgress, format_progress_status, parse_progress_status

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

    active = set(active_lesson_slugs)
    delimiter = _detect_import_delimiter(text)
    try:
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
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

    lesson_columns: list[str] = []
    for col in fieldnames:
        if col in REQUIRED_COLUMNS:
            continue
        if col not in active:
            errors.append(f"Kolom lesson tidak dikenal atau tidak aktif: {col!r}")
            continue
        lesson_columns.append(col)

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
        line = reader.line_num  # nomor baris fisik di file (akurat walau ada baris kosong)

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
        for slug in lesson_columns:
            value = record.get(slug) or ""
            v = value.strip()
            if v in ("", "not_started"):
                continue
            try:
                state, earned, total = parse_progress_status(v)
            except ValueError:
                errors.append(f"Baris {line}, kolom {slug}: status tidak dikenal: {v!r}")
                continue
            if state == "completed":
                progress[slug] = ParsedProgress(state="completed")
            elif state == "scored":
                progress[slug] = ParsedProgress(state="scored", score_earned=earned, score_total=total)

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
) -> bytes:
    """Serialize row export → CSV UTF-8 BOM, delimiter ';', token selalu kosong.

    - Header: student_id;token;nama_siswa;<lesson_slugs...> sesuai urutan.
    - Status ditulis dengan kontrak legacy (kosong/completed/<earned>/<total>).
    - `completed_count`, role, hash token, dan metadata internal tidak diekspor.
    """
    fieldnames = ["student_id", "token", "nama_siswa", *lesson_slugs]
    out = io.StringIO()
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
        for slug in lesson_slugs:
            record[slug] = format_progress_status(row.progress.get(slug))
        writer.writerow(record)
    return out.getvalue().encode("utf-8-sig")
