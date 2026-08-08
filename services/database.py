"""
Database layer — engine & session SQLAlchemy.

- Engine dibuat hanya bila DATABASE_URL tersedia (agar aplikasi tetap bisa
  berjalan dengan STORAGE_BACKEND=csv / dev tanpa PostgreSQL).
- Skema TIDAK dibuat via create_all di produksi — memakai Alembic
  (elemes.sh db upgrade).
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

engine = None
SessionLocal = None

if DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

Base = declarative_base()


def get_db():
    """Dependency generator: session per request, commit/rollback di pemakai."""
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL belum diset — storage PostgreSQL tidak aktif")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
