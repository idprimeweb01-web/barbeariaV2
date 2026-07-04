"""add permite_horario_barbeiro to configuracao_agenda

Revision ID: d1a3e7f9b205
Revises: ca00bd81d3ab
Create Date: 2026-06-29 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'd1a3e7f9b205'
down_revision = 'ca00bd81d3ab'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'configuracao_agenda',
        sa.Column('permite_horario_barbeiro', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column('configuracao_agenda', 'permite_horario_barbeiro')
