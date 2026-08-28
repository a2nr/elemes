"""Unit test untuk composite score (pure, tanpa DB).

Ditandai `unit` supaya fixture autouse _isolate_database melewatinya —
tidak butuh PostgreSQL hidup.
"""

import pytest

from services.evaluation import compute_composite

pytestmark = pytest.mark.unit

EX_W = 70.0
QZ_W = 30.0
DONE = 75.0


def test_exercise_quiz_3of4_both_pass():
    r = compute_composite(
        exercise_passed=True,
        quiz_earned=3,
        quiz_total=4,
        has_exercise=True,
        has_quiz=True,
        exercise_weight=EX_W,
        quiz_weight=QZ_W,
        done_min_percent=DONE,
    )
    assert r.composite_percent == pytest.approx(92.5)
    assert r.is_done is True


def test_exercise_passed_quiz_not_attempted():
    # Exercise contributes its full weight (70); quiz term contributes 0
    # (not attempted) → composite = 70.0, which is < 75 threshold → not done.
    r = compute_composite(
        exercise_passed=True,
        quiz_earned=None,
        quiz_total=None,
        has_exercise=True,
        has_quiz=True,
        exercise_weight=EX_W,
        quiz_weight=QZ_W,
        done_min_percent=DONE,
    )
    assert r.composite_percent == 70.0
    assert r.is_done is False


def test_quiz_attempted_exercise_not_passed():
    # Exercise term contributes 0 (not passed); quiz contributes its full
    # weight (30) → composite = 30.0, < 75 threshold → not done.
    r = compute_composite(
        exercise_passed=False,
        quiz_earned=4,
        quiz_total=4,
        has_exercise=True,
        has_quiz=True,
        exercise_weight=EX_W,
        quiz_weight=QZ_W,
        done_min_percent=DONE,
    )
    assert r.composite_percent == 30.0
    assert r.is_done is False


def test_exercise_only_passed():
    r = compute_composite(
        exercise_passed=True,
        quiz_earned=None,
        quiz_total=None,
        has_exercise=True,
        has_quiz=False,
        exercise_weight=EX_W,
        quiz_weight=QZ_W,
        done_min_percent=DONE,
    )
    assert r.composite_percent == 100.0
    assert r.is_done is True


def test_exercise_only_not_passed():
    r = compute_composite(
        exercise_passed=False,
        quiz_earned=None,
        quiz_total=None,
        has_exercise=True,
        has_quiz=False,
        exercise_weight=EX_W,
        quiz_weight=QZ_W,
        done_min_percent=DONE,
    )
    assert r.composite_percent == 0.0
    assert r.is_done is False


def test_quiz_only_3of4():
    r = compute_composite(
        exercise_passed=None,
        quiz_earned=3,
        quiz_total=4,
        has_exercise=False,
        has_quiz=True,
        exercise_weight=EX_W,
        quiz_weight=QZ_W,
        done_min_percent=DONE,
    )
    assert r.composite_percent == 75.0
    assert r.is_done is True


def test_quiz_only_1of4():
    r = compute_composite(
        exercise_passed=None,
        quiz_earned=1,
        quiz_total=4,
        has_exercise=False,
        has_quiz=True,
        exercise_weight=EX_W,
        quiz_weight=QZ_W,
        done_min_percent=DONE,
    )
    assert r.composite_percent == 25.0
    assert r.is_done is False


def test_reading_only():
    r = compute_composite(
        exercise_passed=None,
        quiz_earned=None,
        quiz_total=None,
        has_exercise=False,
        has_quiz=False,
        exercise_weight=EX_W,
        quiz_weight=QZ_W,
        done_min_percent=DONE,
    )
    assert r.composite_percent == 100.0
    assert r.is_done is True


def test_exercise_pass_quiz_0of4_below_threshold():
    r = compute_composite(
        exercise_passed=True,
        quiz_earned=0,
        quiz_total=4,
        has_exercise=True,
        has_quiz=True,
        exercise_weight=EX_W,
        quiz_weight=QZ_W,
        done_min_percent=DONE,
    )
    assert r.composite_percent == 70.0
    assert r.is_done is False
