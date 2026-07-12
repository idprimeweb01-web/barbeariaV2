"""webhook n8n

Revision ID: a3ccf28f4117
Revises: 3e79eaee6661
Create Date: 2026-07-11 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a3ccf28f4117'
down_revision = '3e79eaee6661'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('barbearia_webhook_config',
        sa.Column('id',             sa.Integer(), nullable=False),
        sa.Column('barbearia_id',   sa.Integer(), nullable=False),
        sa.Column('webhook_url',    sa.String(500), nullable=True),
        sa.Column('ativo',          sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('eventos_ativos', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('criado_em',      sa.DateTime()),
        sa.Column('atualizado_em',  sa.DateTime()),
        sa.ForeignKeyConstraint(['barbearia_id'], ['barbearias.id'], name='fk_barbearia_webhook_config_barbearia_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('barbearia_id', name='uq_barbearia_webhook_config_barbearia_id'),
    )

    op.create_table('webhook_log',
        sa.Column('id',            sa.Integer(), nullable=False),
        sa.Column('barbearia_id',  sa.Integer(), nullable=False),
        sa.Column('tipo_evento',   sa.String(50), nullable=False),
        sa.Column('payload',       sa.JSON(), nullable=False),
        sa.Column('http_status',   sa.Integer(), nullable=True),
        sa.Column('sucesso',       sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('erro_mensagem', sa.Text(), nullable=True),
        sa.Column('criado_em',     sa.DateTime()),
        sa.ForeignKeyConstraint(['barbearia_id'], ['barbearias.id'], name='fk_webhook_log_barbearia_id'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_webhook_log_barbearia_id', 'webhook_log', ['barbearia_id'])
    op.create_index('ix_webhook_log_criado_em', 'webhook_log', ['criado_em'])


def downgrade():
    op.drop_index('ix_webhook_log_criado_em', table_name='webhook_log')
    op.drop_index('ix_webhook_log_barbearia_id', table_name='webhook_log')
    op.drop_table('webhook_log')
    op.drop_table('barbearia_webhook_config')
