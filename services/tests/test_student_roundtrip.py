"""
Unit test parser/formatter round-trip CSV siswa (murni, tanpa database).

Mengunci:
- schema tunggal export/import (BOM, delimiter ';', kolom token kosong);
- validasi all-or-nothing (duplicate UUID/token, status, ukuran, dst.);
- token TIDAK pernah bocor ke error maupun repr row.
"""

from pathlib import Path

import pytest

from services.progress_status import (
    ParsedProgress,
    format_progress_status,
    parse_progress_status,
)
from services.student_roundtrip import (
    MAX_FILE_BYTES,
    MAX_ROWS,
    RoundTripImportError,
    StudentRoundTripRow,
    is_canonical_uuid,
    mask_student_id,
    parse_roundtrip_csv,
    serialize_export_csv,
)

FIXTURES = Path(__file__).parent / "fixtures"

ACTIVE = ["hello_world", "variabel"]

UUID_1 = "7eab651c-5eb1-4eb8-8fd2-17fd77aec6df"
UUID_2 = "22222222-2222-4222-8222-222222222222"


# ── helper format status ───────────────────────────────────────────


def test_parse_progress_status_contract():
    assert parse_progress_status("") == ("not_started", None, None)
    assert parse_progress_status("not_started") == ("not_started", None, None)
    assert parse_progress_status("completed") == ("completed", None, None)
    assert parse_progress_status("3/4") == ("scored", 3, 4)
    assert parse_progress_status("0/10") == ("scored", 0, 10)


def test_parse_progress_status_invalid():
    for bad in ["selesai", "4/2", "abc", "1/0", "-1/5", "2/1/3", "a/b"]:
        with pytest.raises(ValueError):
            parse_progress_status(bad)


def test_format_progress_status_contract():
    assert format_progress_status(None) == ""
    assert format_progress_status(ParsedProgress("completed")) == "completed"
    assert format_progress_status(ParsedProgress("scored", 3, 4)) == "3/4"
    assert format_progress_status(("not_started", None, None)) == "not_started"


# ── serializer export ──────────────────────────────────────────────


def _sample_export_rows():
    return [
        StudentRoundTripRow(
            line=0,
            student_id=UUID_1,
            raw_token="",
            display_name="Nama Siswa 1",
            progress={
                "hello_world": ParsedProgress("completed"),
                "variabel": ParsedProgress("scored", 3, 4),
            },
        ),
        StudentRoundTripRow(
            line=0,
            student_id=None,
            raw_token="",
            display_name="Siswa Baru",
            progress={"variabel": ParsedProgress("completed")},
        ),
    ]


def test_export_serializer_bom_delimiter_and_header():
    data = serialize_export_csv(_sample_export_rows(), ["hello_world", "variabel"])
    text = data.decode("utf-8-sig")
    assert not text.startswith("\ufeff")  # BOM sudah dikonsumsi decode utf-8-sig
    assert data.startswith("\ufeff".encode("utf-8"))  # raw bytes membawa BOM
    lines = text.strip().splitlines()
    assert lines[0] == "student_id;token;nama_siswa;hello_world;variabel"
    assert lines[1].startswith(f"{UUID_1};;Nama Siswa 1;completed;3/4")
    # row 2: UUID kosong, token kosong, hello_world blank → ";;Siswa Baru;;completed"
    assert lines[2] == ";;Siswa Baru;;completed"


def test_export_always_has_empty_token_column():
    data = serialize_export_csv(_sample_export_rows(), ["hello_world"])
    text = data.decode("utf-8-sig")
    for line in text.strip().splitlines()[1:]:
        cols = line.split(";")
        assert cols[1] == ""  # token selalu kosong tanpa pengecualian


def test_export_excludes_internal_fields():
    text = serialize_export_csv(_sample_export_rows(), ["hello_world"]).decode("utf-8-sig")
    assert "completed_count" not in text
    assert "token_hash" not in text
    assert "digest" not in text
    assert "role" not in text
    assert "teacher" not in text


# ── parser: valid ──────────────────────────────────────────────────


def test_parse_valid_fixture():
    content = (FIXTURES / "student_roundtrip_valid.csv").read_bytes()
    rows = parse_roundtrip_csv(content, ACTIVE)
    assert len(rows) == 2

    r1 = rows[0]
    assert r1.student_id == UUID_1
    assert r1.raw_token == "TOKEN_12345678"
    assert r1.display_name == "Nama Siswa 1"
    assert r1.progress["hello_world"].state == "completed"
    assert r1.progress["variabel"] == ParsedProgress("scored", 3, 4)

    r2 = rows[1]
    assert r2.student_id is None  # UUID kosong = siswa baru
    # not_started tidak disimpan → sparse; variabel completed dipertahankan
    assert "hello_world" not in r2.progress
    assert r2.progress["variabel"].state == "completed"


def test_parse_subset_of_lesson_columns():
    content = (
        "student_id;token;nama_siswa;hello_world\n"
        ";TOKEN_12345678;Siswa Baru;completed\n"
    )
    rows = parse_roundtrip_csv(content, ["hello_world", "variabel"])
    assert len(rows) == 1
    # lesson yang tidak ada kolomnya → not_started (tidak di-progress)
    assert "variabel" not in rows[0].progress


def test_parse_header_only_file_is_valid_empty():
    content = "student_id;token;nama_siswa;hello_world\n"
    rows = parse_roundtrip_csv(content, ACTIVE)
    assert rows == []


def test_parse_ignores_empty_rows():
    content = (
        "student_id;token;nama_siswa;hello_world\n"
        "\n"
        ";TOKEN_12345678;Siswa Baru;completed\n"
        "\n"
    )
    rows = parse_roundtrip_csv(content, ACTIVE)
    assert len(rows) == 1


# ── parser: token ──────────────────────────────────────────────────


def test_parse_rejects_empty_token():
    bad = "student_id;token;nama_siswa;hello_world\n;;Nama;completed\n"
    with pytest.raises(RoundTripImportError) as exc:
        parse_roundtrip_csv(bad, ACTIVE)
    assert any("token wajib diisi" in e for e in exc.value.errors)


def test_parse_rejects_whitespace_and_control_chars_in_token():
    cases = [
        "student_id;token;nama_siswa;hello_world\n; TOKEN_1234;A;completed\n",
        "student_id;token;nama_siswa;hello_world\n;TOKEN_12\n34;A;completed\n",
        "student_id;token;nama_siswa;hello_world\n;abc;A;completed\n",  # < 8 karakter
    ]
    for content in cases:
        with pytest.raises(RoundTripImportError):
            parse_roundtrip_csv(content, ACTIVE)


def test_parse_rejects_token_too_long():
    long_token = "T" * 129
    content = f"student_id;token;nama_siswa;hello_world\n;{long_token};A;completed\n"
    with pytest.raises(RoundTripImportError) as exc:
        parse_roundtrip_csv(content, ACTIVE)
    assert any("128" in e for e in exc.value.errors)


def test_parse_rejects_duplicate_token_in_file():
    content = (
        "student_id;token;nama_siswa;hello_world\n"
        f";TOKEN_12345678;A;completed\n"
        f";TOKEN_12345678;B;completed\n"
    )
    with pytest.raises(RoundTripImportError) as exc:
        parse_roundtrip_csv(content, ACTIVE)
    assert any("duplikat" in e.lower() for e in exc.value.errors)


# ── parser: token kosong untuk baris existing (hasil export) ───────


def test_parse_accepts_existing_student_id_with_empty_token():
    # Baris hasil export: student_id terisi + token kosong → diterima
    # (siswa existing dipulihkan/di-update; token lama dipertahankan).
    content = (
        "student_id;token;nama_siswa;hello_world\n"
        f"{UUID_1};;Nama Siswa Lama;completed\n"
    )
    rows = parse_roundtrip_csv(content, ACTIVE)
    assert len(rows) == 1
    r = rows[0]
    assert r.student_id == UUID_1
    assert r.raw_token == ""
    assert r.display_name == "Nama Siswa Lama"
    assert r.progress["hello_world"].state == "completed"


def test_parse_accepts_export_snapshot_with_empty_tokens():
    # CSV aktual berisi dua baris student_id + token kosong (hasil export
    # PostgreSQL) dapat diparse murni; token kosong tidak dianggap duplikat.
    content = (
        "student_id;token;nama_siswa;hello_world\n"
        f"{UUID_1};;Nama Siswa Lama;completed\n"
        f"{UUID_2};;Siswa Kedua;not_started\n"
    )
    rows = parse_roundtrip_csv(content, ACTIVE)
    assert len(rows) == 2
    assert [r.student_id for r in rows] == [UUID_1, UUID_2]
    assert all(r.raw_token == "" for r in rows)
    assert "hello_world" in rows[0].progress
    assert "hello_world" not in rows[1].progress  # not_started → sparse


def test_parse_accepts_whitespace_only_token_with_student_id():
    # Token whitespace-only pada baris existing diperlakukan sebagai token
    # kosong yang sah.
    content = (
        "student_id;token;nama_siswa;hello_world\n"
        f"{UUID_1};   ;Nama Siswa Lama;completed\n"
    )
    rows = parse_roundtrip_csv(content, ACTIVE)
    assert len(rows) == 1
    assert rows[0].raw_token == ""


def test_parse_rejects_whitespace_around_nonempty_token_even_with_student_id():
    # Spasi di sekitar token non-kosong tetap ditolak walau student_id terisi.
    secret = "TOKEN_RAHASIA_UNIK_001"
    content = (
        "student_id;token;nama_siswa;hello_world\n"
        f"{UUID_1}; {secret};Nama Siswa Lama;completed\n"
    )
    with pytest.raises(RoundTripImportError) as exc:
        parse_roundtrip_csv(content, ACTIVE)
    assert any("spasi" in e for e in exc.value.errors)
    assert secret not in str(exc.value)  # token tidak bocor ke pesan error


def test_parse_existing_row_with_empty_token_never_leaks_repr():
    row = parse_roundtrip_csv(
        f"student_id;token;nama_siswa;hello_world\n{UUID_1};;Nama;completed\n",
        ACTIVE,
    )[0]
    assert row.raw_token == ""
    assert "token" not in repr(row).lower() or "raw_token" not in repr(row)


# ── parser: student_id / UUID ──────────────────────────────────────


def test_is_canonical_uuid():
    assert is_canonical_uuid(UUID_1)
    assert not is_canonical_uuid("")
    assert not is_canonical_uuid("bukan-uuid")
    assert not is_canonical_uuid(UUID_1.upper())  # huruf besar tidak canonical


def test_parse_rejects_invalid_and_duplicate_uuid():
    bad_uuid = "student_id;token;nama_siswa;hello_world\nNOT_A_UUID;TOKEN_12345678;A;completed\n"
    with pytest.raises(RoundTripImportError) as exc:
        parse_roundtrip_csv(bad_uuid, ACTIVE)
    assert any("UUID tidak valid" in e for e in exc.value.errors)

    dup = (
        "student_id;token;nama_siswa;hello_world\n"
        f"{UUID_1};TOKEN_12345678;A;completed\n"
        f"{UUID_1};TOKEN_87654321;B;completed\n"
    )
    with pytest.raises(RoundTripImportError) as exc:
        parse_roundtrip_csv(dup, ACTIVE)
    assert any("UUID duplikat" in e for e in exc.value.errors)


def test_parse_invalid_uuid_with_empty_token_reports_only_uuid_error():
    # UUID invalid + token kosong: error token "untuk siswa baru" TIDAK boleh
    # muncul (baris ini jelas bukan siswa baru — error UUID-nya sudah cukup).
    content = "student_id;token;nama_siswa;hello_world\nNOT_A_UUID;;A;completed\n"
    with pytest.raises(RoundTripImportError) as exc:
        parse_roundtrip_csv(content, ACTIVE)
    assert any("UUID tidak valid" in e for e in exc.value.errors)
    assert not any("token wajib diisi" in e for e in exc.value.errors)


# ── parser: header & format file ───────────────────────────────────


def test_parse_rejects_missing_required_column():
    content = "token;nama_siswa;hello_world\nTOKEN_12345678;A;completed\n"
    with pytest.raises(RoundTripImportError) as exc:
        parse_roundtrip_csv(content, ACTIVE)
    assert any("student_id" in e for e in exc.value.errors)


def test_parse_rejects_duplicate_header():
    content = "student_id;token;token;nama_siswa;hello_world\n;;T;A;completed\n"
    with pytest.raises(RoundTripImportError) as exc:
        parse_roundtrip_csv(content, ACTIVE)
    assert any("Header duplikat" in e for e in exc.value.errors)


def test_parse_rejects_unknown_lesson_column():
    content = "student_id;token;nama_siswa;hello_world;tidak_ada\n;TOKEN_12345678;A;completed;completed\n"
    with pytest.raises(RoundTripImportError) as exc:
        parse_roundtrip_csv(content, ACTIVE)
    assert any("tidak_ada" in e for e in exc.value.errors)


def test_parse_rejects_inactive_lesson_column():
    # lesson tidak ada di daftar aktif → ditolak (bukan diam-diam di-ignore)
    content = "student_id;token;nama_siswa;hello_world\n;TOKEN_12345678;A;completed\n"
    with pytest.raises(RoundTripImportError):
        parse_roundtrip_csv(content, ["variabel"])


def test_parse_rejects_unsupported_tab_delimiter():
    # Delimiter tab tidak didukung; seluruh header menjadi satu field pada
    # semua kandidat → error delimiter yang jelas, BUKAN seluruh header
    # ditampilkan sebagai satu unknown lesson.
    content = "student_id\ttoken\tnama_siswa\thello_world\n\tTOKEN_12345678\tA\tcompleted\n"
    with pytest.raises(RoundTripImportError) as exc:
        parse_roundtrip_csv(content, ACTIVE)
    joined = "; ".join(exc.value.errors)
    assert "titik koma (;)" in joined or "koma (,)" in joined
    assert "Kolom lesson tidak dikenal" not in joined


# ── parser: delimiter koma (`,`) ───────────────────────────────────


def test_parse_accepts_comma_delimiter_for_new_student():
    # Reproduksi file lampiran pengguna: header koma + row siswa baru.
    content = (
        "student_id,token,nama_siswa,hello_world,variabel\r\n"
        ",LocustBot48,Locust Bot 48,completed,\r\n"
    )
    rows = parse_roundtrip_csv(content, ACTIVE)
    assert len(rows) == 1
    assert rows[0].student_id is None
    assert rows[0].raw_token == "LocustBot48"
    assert rows[0].display_name == "Locust Bot 48"
    assert rows[0].progress["hello_world"].state == "completed"


def test_parse_accepts_comma_delimiter_with_bom():
    content = (
        "\ufeffstudent_id,token,nama_siswa,hello_world\r\n"
        ",TOKEN_12345678,Siswa Baru,completed\r\n"
    )
    rows = parse_roundtrip_csv(content, ACTIVE)
    assert len(rows) == 1
    assert rows[0].raw_token == "TOKEN_12345678"
    assert rows[0].display_name == "Siswa Baru"


def test_parse_accepts_comma_delimiter_existing_student_empty_token():
    # Baris hasil export (student_id terisi + token kosong) juga valid
    # dengan delimiter koma.
    content = (
        "student_id,token,nama_siswa,hello_world\r\n"
        f"{UUID_1},,Nama Siswa Lama,completed\r\n"
    )
    rows = parse_roundtrip_csv(content, ACTIVE)
    assert len(rows) == 1
    assert rows[0].student_id == UUID_1
    assert rows[0].raw_token == ""


def test_parse_comma_csv_rejects_duplicate_header():
    content = "student_id,token,token,nama_siswa,hello_world\n,,T,A,completed\n"
    with pytest.raises(RoundTripImportError) as exc:
        parse_roundtrip_csv(content, ACTIVE)
    assert any("Header duplikat" in e for e in exc.value.errors)


def test_parse_comma_csv_rejects_unknown_lesson_column():
    content = "student_id,token,nama_siswa,hello_world,tidak_ada\n,TOKEN_12345678,A,completed,completed\n"
    with pytest.raises(RoundTripImportError) as exc:
        parse_roundtrip_csv(content, ACTIVE)
    assert any("tidak_ada" in e for e in exc.value.errors)


def test_parse_comma_csv_errors_never_contain_token_value():
    secret = "TOKEN_RAHASIA_UNIK_001"
    content = (
        "student_id,token,nama_siswa,hello_world\n"
        f",{secret},A,completed\n"
        f",{secret},B,completed\n"  # duplikat → error yang menyebut token
    )
    with pytest.raises(RoundTripImportError) as exc:
        parse_roundtrip_csv(content, ACTIVE)
    assert secret not in str(exc.value)
    for error in exc.value.errors:
        assert secret not in error


# ── parser: quoted field (delimiter di dalam nilai, bukan di-split naif) ──


def test_parse_quoted_comma_in_name_comma_csv():
    # Koma di dalam quoted field harus tetap satu nilai, bukan split manual.
    content = (
        "student_id,token,nama_siswa,hello_world\r\n"
        ',TOKEN_12345678,"Doe, Budi",completed\r\n'
    )
    rows = parse_roundtrip_csv(content, ACTIVE)
    assert len(rows) == 1
    assert rows[0].display_name == "Doe, Budi"


def test_parse_quoted_semicolon_in_name_semicolon_csv():
    # Titik koma di dalam quoted field harus tetap satu nilai pada
    # delimiter canonical.
    content = (
        "student_id;token;nama_siswa;hello_world\r\n"
        ';TOKEN_12345678;"Budi; Santoso";completed\r\n'
    )
    rows = parse_roundtrip_csv(content, ACTIVE)
    assert len(rows) == 1
    assert rows[0].display_name == "Budi; Santoso"


def test_parse_mixed_delimiter_reports_schema_errors_not_whole_header():
    # Header campuran ; dan , terpecah menjadi beberapa field tapi tidak
    # memenuhi schema pada delimiter manapun → error kolom wajib yang
    # jelas, dan seluruh raw header TIDAK tampil sebagai satu unknown
    # lesson (yang menyesatkan).
    content = "student_id;token,nama_siswa;hello_world\n;TOKEN_12345678,A,completed\n"
    with pytest.raises(RoundTripImportError) as exc:
        parse_roundtrip_csv(content, ACTIVE)
    joined = "; ".join(exc.value.errors)
    assert "Kolom wajib hilang" in joined
    assert "student_id;token,nama_siswa;hello_world" not in joined


def test_parse_rejects_csv_layer_error():
    # Field melebihi batas field csv (131072) → csv.Error saat parsing
    content = (
        "student_id;token;nama_siswa;hello_world\n"
        ";TOKEN_12345678;" + "x" * 200000 + ";completed\n"
    )
    with pytest.raises(RoundTripImportError):
        parse_roundtrip_csv(content, ACTIVE)


def test_parse_rejects_empty_file():
    with pytest.raises(RoundTripImportError) as exc:
        parse_roundtrip_csv("", ACTIVE)
    assert any("kosong" in e or "header" in e.lower() for e in exc.value.errors)


def test_parse_rejects_invalid_progress_status():
    content = "student_id;token;nama_siswa;hello_world;variabel\n;TOKEN_12345678;A;selesai;4/2\n"
    with pytest.raises(RoundTripImportError) as exc:
        parse_roundtrip_csv(content, ACTIVE)
    joined = "; ".join(exc.value.errors)
    assert "selesai" in joined
    assert "4/2" in joined


def test_parse_rejects_name_too_long():
    name = "N" * 256
    content = f"student_id;token;nama_siswa;hello_world\n;TOKEN_12345678;{name};completed\n"
    with pytest.raises(RoundTripImportError) as exc:
        parse_roundtrip_csv(content, ACTIVE)
    assert any("255" in e for e in exc.value.errors)


def test_parse_rejects_too_many_rows():
    header = "student_id;token;nama_siswa;hello_world\n"
    body = "".join(f";TOKEN_{i:08d};Siswa {i};completed\n" for i in range(MAX_ROWS + 1))
    with pytest.raises(RoundTripImportError) as exc:
        parse_roundtrip_csv(header + body, ACTIVE)
    assert any(f"batas {MAX_ROWS}" in e for e in exc.value.errors)


def test_parse_rejects_file_too_big():
    big = b"a" * (MAX_FILE_BYTES + 1)
    with pytest.raises(RoundTripImportError) as exc:
        parse_roundtrip_csv(big, ACTIVE)
    assert any("5 MiB" in e for e in exc.value.errors)


# ── keamanan: token tidak bocor ────────────────────────────────────


def test_errors_never_contain_token_value():
    secret = "TOKEN_RAHASIA_UNIK_001"
    content = (
        "student_id;token;nama_siswa;hello_world\n"
        f";{secret};A;completed\n"
        f";{secret};B;completed\n"  # duplikat → error yang menyebut token
    )
    with pytest.raises(RoundTripImportError) as exc:
        parse_roundtrip_csv(content, ACTIVE)
    assert secret not in str(exc.value)
    for error in exc.value.errors:
        assert secret not in error


def test_row_repr_never_contains_token():
    row = StudentRoundTripRow(
        line=2,
        student_id=UUID_1,
        raw_token="TOKEN_RAHASIA_UNIK_001",
        display_name="Budi",
        progress={},
    )
    assert "TOKEN_RAHASIA_UNIK_001" not in repr(row)


def test_mask_student_id():
    assert mask_student_id(UUID_1) == "7eab651c…"
    assert mask_student_id(None) == ""
    assert mask_student_id("") == ""
