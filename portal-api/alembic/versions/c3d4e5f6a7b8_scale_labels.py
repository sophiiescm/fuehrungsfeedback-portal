"""scale_labels (Beschriftung je Skalenstufe)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""
import sqlalchemy as sa
from alembic import op

revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("question", sa.Column("scale_labels", sa.JSON, nullable=True))


def downgrade() -> None:
    op.drop_column("question", "scale_labels")
