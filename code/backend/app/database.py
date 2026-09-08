"""
Database connection setup.

Defaults to a local SQLite file so the W5/MST prototype runs with zero
external dependencies. For staging/production, set the DATABASE_URL env
var to a PostgreSQL DSN, e.g.:

    export DATABASE_URL="postgresql+psycopg2://user:pass@localhost:5432/bloodline"

The SQLAlchemy models in models.py use only cross-dialect-safe types, so
no code changes are required to switch from SQLite to PostgreSQL.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bloodline.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
