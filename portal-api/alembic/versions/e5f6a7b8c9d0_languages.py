"""Mehrsprachigkeit: survey_version.languages, question/dimension.translations, person.language

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""
import sqlalchemy as sa
from alembic import op

revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("survey_version", sa.Column("languages", sa.JSON, nullable=True))
    op.add_column("question", sa.Column("translations", sa.JSON, nullable=True))
    op.add_column("dimension", sa.Column("translations", sa.JSON, nullable=True))
    op.add_column("person", sa.Column("language", sa.String(8), nullable=True))


def downgrade() -> None:
    op.drop_column("person", "language")
    op.drop_column("dimension", "translations")
    op.drop_column("question", "translations")
    op.drop_column("survey_version", "languages")
