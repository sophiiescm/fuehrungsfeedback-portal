"""used_assertion (Trusted-App-SSO Replay-Schutz)

Revision ID: a1f0c2d3e4b5
Revises: 28959119f653
"""
import sqlalchemy as sa
from alembic import op

revision = 'a1f0c2d3e4b5'
down_revision = '28959119f653'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "used_assertion",
        sa.Column("jti", sa.String(100), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("used_assertion")
