"""Metadata model: nama tabel, constraint, relasi — tanpa butuh DB hidup."""

from sqlalchemy import ForeignKeyConstraint

from services import models as _models  # noqa: F401  (mendaftarkan metadata)
from services.database import Base


def _table(name):
    return Base.metadata.tables[name]


def _fks(table):
    return [c for c in table.constraints if isinstance(c, ForeignKeyConstraint)]


def _fk_to(table, column_name):
    for fk in _fks(table):
        if column_name in fk.column_keys:
            return fk
    return None


def test_users_table_shape():
    cols = _table("users").columns
    assert {"id", "display_name", "role", "is_active"}.issubset(cols.keys())
    assert cols["role"].type.length == 10
    assert _table("users").primary_key.columns.keys() == ["id"]


def test_users_role_check_constraint():
    checks = [c.name for c in _table("users").constraints if c.name == "ck_users_role"]
    assert checks


def test_access_tokens_hash_unique_and_indexed():
    table = _table("access_tokens")
    assert any(c.name == "uq_access_tokens_token_hash" for c in table.constraints)
    assert {"ix_access_tokens_token_hash", "ix_access_tokens_user_id"}.issubset(
        {i.name for i in table.indexes}
    )
    fk = _fk_to(table, "user_id")
    assert fk is not None
    assert fk.ondelete == "CASCADE"


def test_lessons_slug_unique():
    table = _table("lessons")
    assert any(c.name == "uq_lessons_slug" for c in table.constraints)


def test_student_progress_unique_and_state_check():
    table = _table("student_progress")
    assert any(c.name == "uq_student_progress_user_lesson" for c in table.constraints)
    assert any(c.name == "ck_student_progress_state" for c in table.constraints)
    cols = table.columns
    assert cols["state"].default.arg == "not_started"
    assert cols["score_earned"].nullable
    assert cols["score_total"].nullable


def test_cascade_delete_user_removes_tokens_and_progress():
    tokens_fk = _fk_to(_table("access_tokens"), "user_id")
    progress_fk = _fk_to(_table("student_progress"), "user_id")
    assert tokens_fk is not None and tokens_fk.ondelete == "CASCADE"
    assert progress_fk is not None and progress_fk.ondelete == "CASCADE"
