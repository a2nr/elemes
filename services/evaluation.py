"""Composite score computation for lesson evaluation.

Logic:
- Exercise is binary (passed/failed). Quiz scored as evalCorrect/evalTotal * 100.
- Composite = exercise_pct * (EXERCISE_WEIGHT/100) + quiz_pct * (QUIZ_WEIGHT/100).
- "Done": composite >= LESSON_DONE_MIN_PERCENT (global env var).
- Implicit AND: if quiz not attempted → quiz term contributes 0 → composite < threshold.
  If exercise not passed → exercise term contributes 0 → composite < threshold.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CompositeResult:
    composite_percent: float
    is_done: bool


def compute_composite(
    *,
    exercise_passed: bool | None,
    quiz_earned: int | None,
    quiz_total: int | None,
    has_exercise: bool,
    has_quiz: bool,
    exercise_weight: float,
    quiz_weight: float,
    done_min_percent: float,
) -> CompositeResult:
    # Reading-only lesson (no exercise, no quiz) — auto-done
    if not has_exercise and not has_quiz:
        return CompositeResult(composite_percent=100.0, is_done=True)
    # Exercise-only lesson
    if has_exercise and not has_quiz:
        pct = 100.0 if exercise_passed is True else 0.0
        return CompositeResult(composite_percent=pct, is_done=exercise_passed is True and pct >= done_min_percent)
    # Quiz-only lesson
    if not has_exercise and has_quiz:
        if quiz_earned is None or not quiz_total:
            return CompositeResult(composite_percent=0.0, is_done=False)
        pct = (quiz_earned / quiz_total) * 100.0
        return CompositeResult(composite_percent=round(pct, 2), is_done=round(pct, 2) >= done_min_percent)
    # Lesson has BOTH exercise AND quiz
    ex_pct = 100.0 if exercise_passed is True else 0.0
    quiz_pct = (quiz_earned / quiz_total) * 100.0 if (quiz_earned is not None and quiz_total) else 0.0
    composite = round(ex_pct * (exercise_weight / 100.0) + quiz_pct * (quiz_weight / 100.0), 2)
    return CompositeResult(composite_percent=composite, is_done=composite >= done_min_percent)
