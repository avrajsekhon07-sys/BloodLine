"""Baseline: the BloodLine 1.0 schema.

This revision creates every table from the models as they stood at 1.0 using
`create_all(checkfirst=True)`, so it is safe on an empty database and does
nothing harmful on one that `app.seed` already created (then prefer
`alembic stamp head`).

Before the next model change, replace it with an explicit baseline:
    rm alembic/versions/0001_baseline.py
    alembic revision --autogenerate -m "baseline"      # against an EMPTY database
Every later change should be its own `alembic revision --autogenerate` migration.

Revision ID: 0001
Revises:
"""
from alembic import op

from app.database import Base
from app import models  # noqa: F401

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade():
    Base.metadata.drop_all(bind=op.get_bind())
