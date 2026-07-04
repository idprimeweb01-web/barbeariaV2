"""extend agendamento status to varchar30

Revision ID: a3f8c2e1d047
Revises: 992b53c7662d
Create Date: 2026-06-29 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a3f8c2e1d047'
down_revision = '992b53c7662d'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('agendamentos', 'status',
        existing_type=sa.String(20),
        type_=sa.String(30),
        existing_nullable=True)


def downgrade():
    op.alter_column('agendamentos', 'status',
        existing_type=sa.String(30),
        type_=sa.String(20),
        existing_nullable=True)
