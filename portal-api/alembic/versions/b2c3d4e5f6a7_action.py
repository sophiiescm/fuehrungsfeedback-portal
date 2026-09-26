"""action (Massnahmen)

Revision ID: b2c3d4e5f6a7
Revises: a1f0c2d3e4b5
"""
import sqlalchemy as sa
from alembic import op

revision = 'b2c3d4e5f6a7'
down_revision = 'a1f0c2d3e4b5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "action",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("leader_person_id", sa.Integer, sa.ForeignKey("person.id"), nullable=False, index=True),
        sa.Column("round_id", sa.Integer, sa.ForeignKey("round.id"), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("topic", sa.String(200), nullable=True),
        sa.Column("status", sa.Enum("geplant", "in_arbeit", "erledigt", name="action_status_enum"), nullable=False),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("visible_to_team", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("action")
    sa.Enum(name="action_status_enum").drop(op.get_bind(), checkfirst=True)
