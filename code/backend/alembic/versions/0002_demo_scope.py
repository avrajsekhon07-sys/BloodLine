"""Additive markers for isolating synthetic demo data.

Revision ID: 0002_demo_scope
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_demo_scope"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # Existing accounts and organisations are explicitly classified as real.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in ("user_accounts", "blood_banks", "hospitals"):
        # 0001_baseline builds tables from live model metadata. On a brand-new
        # database it may already have created the marker columns; deployed
        # databases stamped at 0001 do not have them yet.
        names = {column["name"] for column in inspector.get_columns(table)}
        if "is_demo" not in names:
            op.add_column(table, sa.Column("is_demo", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade():
    # Removing these markers after fixtures exist would make synthetic records
    # indistinguishable from production records. Keep the isolation boundary.
    raise RuntimeError("Demo scope is a security boundary; forward-fix this migration instead of downgrading.")
