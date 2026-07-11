"""vip nivel brindes estruturados

Revision ID: 3e79eaee6661
Revises: 66426d1efe99
Create Date: 2026-07-11 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '3e79eaee6661'
down_revision = '66426d1efe99'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('vip_niveis', sa.Column(
        'brindes', sa.JSON(), nullable=False, server_default='[]',
    ))


def downgrade():
    op.drop_column('vip_niveis', 'brindes')
