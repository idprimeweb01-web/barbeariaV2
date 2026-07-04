"""segmentos e rotulos dinamicos

Revision ID: c5d7f9a1b3e5
Revises: a3f8c2e1d047
Create Date: 2026-06-29 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c5d7f9a1b3e5'
down_revision = 'a3f8c2e1d047'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('segmentos',
        sa.Column('id',    sa.Integer(), nullable=False),
        sa.Column('nome',  sa.String(100), nullable=False),
        sa.Column('chave', sa.String(50),  nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('chave'),
    )
    op.create_index('ix_segmentos_chave', 'segmentos', ['chave'], unique=True)

    op.create_table('segmento_rotulos',
        sa.Column('id',          sa.Integer(), nullable=False),
        sa.Column('segmento_id', sa.Integer(), nullable=False),
        sa.Column('rotulo_tenant',               sa.String(50)),
        sa.Column('rotulo_tenant_plural',         sa.String(50)),
        sa.Column('rotulo_profissional',          sa.String(50)),
        sa.Column('rotulo_profissional_plural',   sa.String(50)),
        sa.Column('rotulo_servico',               sa.String(50)),
        sa.Column('rotulo_servico_plural',        sa.String(50)),
        sa.Column('rotulo_agendamento',           sa.String(50)),
        sa.Column('rotulo_agendamento_plural',    sa.String(50)),
        sa.Column('rotulo_cliente',               sa.String(50)),
        sa.Column('rotulo_cliente_plural',        sa.String(50)),
        sa.Column('rotulo_produto',               sa.String(50)),
        sa.Column('rotulo_produto_plural',        sa.String(50)),
        sa.Column('rotulo_plano',                 sa.String(50)),
        sa.Column('rotulo_plano_plural',          sa.String(50)),
        sa.Column('rotulo_pagamento',             sa.String(50)),
        sa.Column('rotulo_faturamento',           sa.String(50)),
        sa.Column('rotulo_relatorio',             sa.String(50)),
        sa.Column('atualizado_em', sa.DateTime()),
        sa.ForeignKeyConstraint(['segmento_id'], ['segmentos.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('segmento_id'),
    )

    op.add_column('barbearias',
        sa.Column('segmento_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_barbearias_segmento_id',
        'barbearias', 'segmentos',
        ['segmento_id'], ['id'],
    )


def downgrade():
    op.drop_constraint('fk_barbearias_segmento_id', 'barbearias', type_='foreignkey')
    op.drop_column('barbearias', 'segmento_id')
    op.drop_table('segmento_rotulos')
    op.drop_index('ix_segmentos_chave', table_name='segmentos')
    op.drop_table('segmentos')
