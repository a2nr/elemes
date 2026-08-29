"""
Parsing/format status progress.

Kontrak legacy (dipakai UI live app, laporan guru, dan endpoint attempt kuis):
- belum mulai : kosong ("") atau "not_started"
- selesai     : "completed"
- skor        : "<earned>/<total>", misalnya "3/4"

Grammar round-trip CSV (dipakai export/import siswa via parse_roundtrip_cell / format_roundtrip_cell):
- belum mulai/diamkan : kosong ("") atau "not_started" -> None (merge semantics)
- reset lesson        : "RESET" (case-insensitive) -> hapus progress lesson utk siswa ybs
- selesai             : "completed"
- skor kuis           : "<earned>/<total>"
- composite           : "done:<ex>:<earned>/<total>" (<ex>: "1" / "0" / "")

Catatan pemakaian spreadsheet (Excel / Google Sheets):
Kolom lesson berisi "<earned>/<total>" atau "done:..." sebaiknya diformat sebagai
**Text** di aplikasi spreadsheet sebelum diedit manual agar format tidak otomatis
dikonversi menjadi tanggal.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedProgress:
    """Status progress hasil parse (hanya state non-not_started yang dipertahankan)."""

    state: str  # 'completed' | 'scored' | 'done' | 'reset'
    score_earned: int | None = None
    score_total: int | None = None
    exercise_passed: bool | None = None
    quiz_earned: int | None = None
    quiz_total: int | None = None


def parse_roundtrip_cell(value: str) -> ParsedProgress | None:
    """Grammar sel round-trip (single source of truth untuk import & export):
    - "" / "not_started"          → None (tidak diubah — merge semantics)
    - "RESET" (case-insensitive)  → ParsedProgress(state="reset")
                                     — hapus progress lesson ini utk siswa ybs
    - "completed"                 → ParsedProgress(state="completed")
    - "<earned>/<total>"          → ParsedProgress(state="scored", score_earned=..., score_total=...)
    - "done:<ex>:<earned>/<total>" → ParsedProgress(state="done", exercise_passed=..., quiz_earned=..., quiz_total=...)
        <ex>: "1"→True, "0"→False, ""→None (lesson tanpa komponen exercise)
        bagian kuis boleh kosong (lesson tanpa komponen quiz); jika diisi,
        validasi sama seperti "scored" (int, int, total>0, 0<=earned<=total)
    - selain itu → raise ValueError
    """
    v = (value or "").strip()
    if v in ("", "not_started"):
        return None
    if v.upper() == "RESET":
        return ParsedProgress(state="reset")
    if v == "completed":
        return ParsedProgress(state="completed")

    if v.startswith("done:"):
        parts = v.split(":")
        if len(parts) != 3:
            raise ValueError(f"format cell done tidak valid: {v!r}")

        ex_raw = parts[1].strip()
        if ex_raw == "":
            exercise_passed = None
        elif ex_raw == "1":
            exercise_passed = True
        elif ex_raw == "0":
            exercise_passed = False
        else:
            raise ValueError(f"komponen exercise tidak valid (harus 1, 0, atau kosong): {ex_raw!r}")

        quiz_raw = parts[2].strip()
        if quiz_raw == "":
            quiz_earned = None
            quiz_total = None
        elif "/" in quiz_raw:
            qparts = quiz_raw.split("/")
            if len(qparts) != 2:
                raise ValueError(f"komponen quiz tidak valid: {quiz_raw!r}")
            try:
                q_earned, q_total = int(qparts[0]), int(qparts[1])
            except ValueError:
                raise ValueError(f"skor quiz bukan angka: {quiz_raw!r}")
            if q_total <= 0 or not (0 <= q_earned <= q_total):
                raise ValueError(f"skor quiz tidak valid ({q_earned}/{q_total}): {quiz_raw!r}")
            quiz_earned, quiz_total = q_earned, q_total
        else:
            raise ValueError(f"format quiz tidak valid: {quiz_raw!r}")

        return ParsedProgress(
            state="done",
            exercise_passed=exercise_passed,
            quiz_earned=quiz_earned,
            quiz_total=quiz_total,
        )

    if "/" in v:
        parts = v.split("/")
        if len(parts) == 2:
            try:
                earned, total = int(parts[0]), int(parts[1])
            except ValueError:
                raise ValueError(f"status progress tidak dikenal: {v!r}")
            if total > 0 and 0 <= earned <= total:
                return ParsedProgress(state="scored", score_earned=earned, score_total=total)
            else:
                raise ValueError(f"skor tidak valid ({earned}/{total}): {v!r}")
        else:
            raise ValueError(f"status progress tidak dikenal: {v!r}")

    raise ValueError(f"status progress tidak dikenal: {v!r}")


def format_roundtrip_cell(parsed: ParsedProgress | None) -> str:
    """Kebalikan dari parse_roundtrip_cell (hanya dipakai EXPORT, tidak pernah
    menghasilkan 'RESET' — itu murni instruksi import).
    state='done' → 'done:<ex>:<earned>/<total>'.
    """
    if parsed is None:
        return ""
    if parsed.state == "completed":
        return "completed"
    if parsed.state == "scored":
        return f"{parsed.score_earned}/{parsed.score_total}"
    if parsed.state == "done":
        ex_str = ""
        if parsed.exercise_passed is True:
            ex_str = "1"
        elif parsed.exercise_passed is False:
            ex_str = "0"

        quiz_str = ""
        if parsed.quiz_earned is not None and parsed.quiz_total is not None:
            quiz_str = f"{parsed.quiz_earned}/{parsed.quiz_total}"

        return f"done:{ex_str}:{quiz_str}"
    if parsed.state in ("not_started", ""):
        return ""
    return parsed.state


def parse_progress_status(value: str) -> tuple[str, int | None, int | None]:
    """Parse status legacy → (state, score_earned, score_total).

    - "" / "not_started"      → ("not_started", None, None)
    - "completed"             → ("completed", None, None)
    - "done"                  → ("done", None, None)
    - "in_progress"           → ("in_progress", None, None)
    - "<earned>/<total>"      → ("scored", earned, total) bila total > 0 dan
                                0 <= earned <= total
    - selain itu              → raise ValueError (status tidak dikenal)
    """
    v = (value or "").strip()
    if v in ("", "not_started"):
        return ("not_started", None, None)
    if v == "completed":
        return ("completed", None, None)
    if v == "done":
        return ("done", None, None)
    if v == "in_progress":
        return ("in_progress", None, None)
    if "/" in v:
        parts = v.split("/")
        if len(parts) == 2:
            try:
                earned, total = int(parts[0]), int(parts[1])
            except ValueError:
                earned = total = None
            if (
                earned is not None
                and total is not None
                and total > 0
                and 0 <= earned <= total
            ):
                return ("scored", earned, total)
    raise ValueError(f"status progress tidak dikenal: {v!r}")


def format_progress_status(progress) -> str:
    """Render status ke string kontrak legacy.

    Menerima None, ParsedProgress, tuple (state, earned, total), atau objek
    dengan atribut state/score_earned/score_total (mis. model StudentProgress).

    - None            → ""
    - done            → persen komposit dibulatkan bila ada, else "done"
    - in_progress     → "" (harus kosong: tidak dihitung prasyarat lengkap)
    - scored          → "<earned>/<total>"
    - completed       → "completed"
    - not_started     → "not_started"
    - lainnya         → state itu sendiri
    """
    if progress is None:
        return ""
    if isinstance(progress, tuple):
        state, earned, total = progress
    else:
        state = progress.state
        earned = getattr(progress, "score_earned", None)
        total = getattr(progress, "score_total", None)
    if state == "in_progress":
        return ""
    if state == "done":
        composite = getattr(progress, "composite_percent", None)
        if composite is not None:
            return f"{round(composite)}"
        return "done"
    if state == "scored":
        return f"{earned}/{total}"
    return state
