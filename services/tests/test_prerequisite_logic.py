"""Unit test logika prasyarat: status skor & ambang minimum global.

Kontrak yang diuji (perilaku BARU setelah deprecasi `min: N%` per-lesson):
- Status `scored` (mis. "3/4") memenuhi prasyarat untuk skor berapa pun.
- `completed` selalu memenuhi.
- Status tidak dikenal (non-empty, bukan "not_started") juga memenuhi — ambang
  per-lesson diabaikan; satu-satunya ambang adalah LESSON_DONE_MIN_PERCENT
  (global, di config.py).
- `not_started` / progress kosong / status kosong → belum terpenuhi.
- `_parse_prerequisite_bullet` SELALU mengembalikan min_percent=None (suffix
  `min: N%` tetap dibuang dari teks demi kompatibilitas mundur, tapi tidak
  lagi diekstrak).
"""

import pytest

pytestmark = pytest.mark.unit

from services.lesson_service import (
    _parse_prerequisite_bullet,
    get_missing_prerequisites,
    is_prerequisite_met,
)


# ---------------------------------------------------------------------------
# _parse_prerequisite_bullet
# ---------------------------------------------------------------------------

def test_parse_bullet_link_without_threshold():
    assert _parse_prerequisite_bullet("- [Kuis](lesson/quiz.md)") == ("quiz", None)


def test_parse_bullet_link_with_percent_threshold():
    # min_percent SELALU None sekarang (diabaikan).
    assert _parse_prerequisite_bullet("- [Kuis](lesson/quiz.md) min: 75%") == ("quiz", None)


def test_parse_bullet_link_without_colon():
    assert _parse_prerequisite_bullet("- [Kuis](lesson/quiz.md) min 50%") == ("quiz", None)


def test_parse_bullet_link_with_minimum_word():
    assert _parse_prerequisite_bullet("- [Kuis](lesson/quiz.md) minimum: 80%") == ("quiz", None)


def test_parse_bullet_link_with_comma_decimal():
    assert _parse_prerequisite_bullet("- [Kuis](lesson/quiz.md) min: 62,5%") == ("quiz", None)


def test_parse_bullet_plain_text_with_threshold():
    assert _parse_prerequisite_bullet("- Kuis min 75%") == ("Kuis", None)


def test_parse_bullet_plain_text_without_threshold():
    assert _parse_prerequisite_bullet("- Dasar") == ("Dasar", None)


def test_parse_bullet_trailing_comma_before_threshold():
    assert _parse_prerequisite_bullet("- [Kuis](lesson/quiz.md), min: 75%") == ("quiz", None)


@pytest.mark.parametrize("bullet", ["- Tidak ada", "- None", "-", ""])
def test_parse_bullet_skip_values(bullet):
    assert _parse_prerequisite_bullet(bullet) is None


def test_parse_bullet_path_with_folder():
    assert _parse_prerequisite_bullet("- [Dasar](lesson/dasar.md)") == ("dasar", None)


# ---------------------------------------------------------------------------
# is_prerequisite_met
# ---------------------------------------------------------------------------

def test_met_no_progress():
    assert is_prerequisite_met(None, "dasar") is False
    assert is_prerequisite_met({}, "dasar") is False


def test_met_not_started():
    assert is_prerequisite_met({"dasar": ""}, "dasar") is False
    assert is_prerequisite_met({"dasar": "not_started"}, "dasar") is False


def test_met_completed():
    assert is_prerequisite_met({"dasar": "completed"}, "dasar") is True


def test_met_any_score_satisfies():
    assert is_prerequisite_met({"quiz": "3/4"}, "quiz") is True
    assert is_prerequisite_met({"quiz": "0/4"}, "quiz") is True
    assert is_prerequisite_met({"quiz": "4/4"}, "quiz") is True


def test_met_unknown_status():
    # Status tidak dikenal, asal non-empty & bukan "not_started", dianggap done.
    assert is_prerequisite_met({"dasar": "xyz"}, "dasar") is True


def test_met_missing_slug():
    assert is_prerequisite_met({"lain": "completed"}, "dasar") is False


def test_met_spec_dict_without_threshold():
    assert is_prerequisite_met({"quiz": "2/4"}, {"slug": "quiz", "min_percent": None}) is True


def test_met_threshold_ignored():
    # Ambang per-lesson (min_percent) diabaikan: status non-empty
    # non-not_started memenuhi meski skor di bawah ambang.
    spec_low = {"slug": "quiz", "min_percent": 75.0}
    assert is_prerequisite_met({"quiz": "2/4"}, spec_low) is True
    spec_high = {"slug": "quiz", "min_percent": 90.0}
    assert is_prerequisite_met({"quiz": "completed"}, spec_high) is True
    spec_zero = {"slug": "quiz", "min_percent": 75.0}
    assert is_prerequisite_met({"quiz": "0/0"}, spec_zero) is True


# ---------------------------------------------------------------------------
# get_missing_prerequisites
# ---------------------------------------------------------------------------

def test_missing_returns_only_unmet_in_order():
    progress = {"a": "completed", "b": "3/4", "c": ""}
    specs = [{"slug": "a"}, {"slug": "b"}, {"slug": "c"}]
    assert get_missing_prerequisites(progress, specs) == ["c"]


def test_missing_accepts_plain_slugs():
    progress = {"b": "0/4"}
    assert get_missing_prerequisites(progress, ["a", "b"]) == ["a"]


def test_missing_threshold():
    # Ambang diabaikan: "2/4" non-empty non-not_started => terpenuhi => [].
    progress = {"q": "2/4"}
    assert get_missing_prerequisites(progress, [{"slug": "q", "min_percent": 75.0}]) == []
    progress2 = {"q": "3/4"}
    assert get_missing_prerequisites(progress2, [{"slug": "q", "min_percent": 75.0}]) == []


def test_missing_empty_and_none():
    assert get_missing_prerequisites({}, []) == []
    assert get_missing_prerequisites(None, [{"slug": "a"}]) == ["a"]
