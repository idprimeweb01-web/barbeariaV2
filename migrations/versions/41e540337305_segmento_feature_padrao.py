"""segmento feature padrao

Revision ID: 41e540337305
Revises: df41b77230dd
Create Date: 2026-07-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '41e540337305'
down_revision = 'df41b77230dd'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('segmento_feature_padrao',
        sa.Column('id',               sa.Integer(), nullable=False),
        sa.Column('segmento_id',      sa.Integer(), nullable=False),
        sa.Column('feature_id',       sa.Integer(), nullable=False),
        sa.Column('ativo_por_padrao', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('atualizado_em',    sa.DateTime()),
        sa.ForeignKeyConstraint(['segmento_id'], ['segmentos.id']),
        sa.ForeignKeyConstraint(['feature_id'], ['feature_metadata.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('segmento_id', 'feature_id', name='uq_segmento_feature_padrao'),
    )
    op.create_index(
        'ix_segmento_feature_padrao_segmento_id',
        'segmento_feature_padrao', ['segmento_id'],
    )


def downgrade():
    op.drop_index('ix_segmento_feature_padrao_segmento_id', table_name='segmento_feature_padrao')
    op.drop_table('segmento_feature_padrao')
