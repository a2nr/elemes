"""
Parsing/format status progress — kontrak legacy tunggal yang dipakai UI, export,
import, dan storage backend PostgreSQL:

- belum mulai : kosong ("") atau "not_started"
- selesai     : "completed"
- skor        : "<earned>/<total>", misalnya "3/4"

Helper ini dipakai oleh importer round-trip (student_roundtrip) DAN storage
backend agar format status tidak divergen antar komponen.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedProgress:
    """Status progress hasil parse (hanya state non-not_started yang dipertahankan)."""

    state: str  # 'completed' | 'scored'
    score_earned: int | None = None
    score_total: int | None = None


def parse_progress_status(value: str) -> tuple[str, int | None, int | None]:
    """Parse status legacy → (state, score_earned, score_total).

    - "" / "not_started"      → ("not_started", None, None)
    - "completed"             → ("completed", None, None)
    - "<earned>/<total>"      → ("scored", earned, total) bila total > 0 dan
                                0 <= earned <= total
    - selain itu              → raise ValueError (status tidak dikenal)
    """
    v = (value or "").strip()
    if v in ("", "not_started"):
        return ("not_started", None, None)
    if v == "completed":
        return ("completed", None, None)
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
    - scored          → "<earned>/<total>"
    - completed       → "completed"
    - not_started     → "not_started"
    """
    if progress is None:
        return ""
    if isinstance(progress, tuple):
        state, earned, total = progress
    else:
        state = progress.state
        earned = getattr(progress, "score_earned", None)
        total = getattr(progress, "score_total", None)
    if state == "scored":
        return f"{earned}/{total}"
    return state
