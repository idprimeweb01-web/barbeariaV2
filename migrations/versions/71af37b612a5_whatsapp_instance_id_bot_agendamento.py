"""whatsapp_instance_id (bot de agendamento)

Revision ID: 71af37b612a5
Revises: f0f4326e5da4
Create Date: 2026-07-19 10:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '71af37b612a5'
down_revision = 'f0f4326e5da4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('barbearias', sa.Column('whatsapp_instance_id', sa.String(100), nullable=True))
    op.create_unique_constraint('uq_barbearias_whatsapp_instance_id', 'barbearias', ['whatsapp_instance_id'])


def downgrade():
    op.drop_constraint('uq_barbearias_whatsapp_instance_id', 'barbearias', type_='unique')
    op.drop_column('barbearias', 'whatsapp_instance_id')
