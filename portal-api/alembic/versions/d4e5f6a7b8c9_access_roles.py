"""access_role, person_access_role (feingranulare Admin-Rechte)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""
import sqlalchemy as sa
from alembic import op

revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "access_role",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("permissions", sa.JSON, nullable=False),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "person_access_role",
        sa.Column("person_id", sa.Integer, sa.ForeignKey("person.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("access_role_id", sa.Integer, sa.ForeignKey("access_role.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("person_access_role")
    op.drop_table("access_role")
