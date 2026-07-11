"""PDV/Caixa diario, VIP leveling (historico + meses_consecutivos), reset de senha estendido

Revision ID: 66426d1efe99
Revises: 41e540337305
Create Date: 2026-07-11 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '66426d1efe99'
down_revision = '41e540337305'
branch_labels = None
depends_on = None


def upgrade():
    # ── VIP: histórico + progressão mensal ──────────────────────────────────
    op.add_column('cliente_vip', sa.Column(
        'meses_consecutivos', sa.Integer(), nullable=False, server_default=sa.text('0'),
    ))

    op.create_table('cliente_vip_historico',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('barbearia_id', sa.Integer(), nullable=False),
        sa.Column('cliente_id', sa.Integer(), nullable=False),
        sa.Column('evento_tipo', sa.String(50), nullable=False),
        sa.Column('nivel_anterior', sa.Integer()),
        sa.Column('nivel_novo', sa.Integer()),
        sa.Column('descricao', sa.Text()),
        sa.Column('criado_em', sa.DateTime()),
        sa.ForeignKeyConstraint(['barbearia_id'], ['barbearias.id'], name='fk_cliente_vip_historico_barbearia_id'),
        sa.ForeignKeyConstraint(['cliente_id'], ['clientes.id'], name='fk_cliente_vip_historico_cliente_id'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_cliente_vip_historico_barbearia_id', 'cliente_vip_historico', ['barbearia_id'])
    op.create_index('ix_cliente_vip_historico_cliente_id', 'cliente_vip_historico', ['cliente_id'])
    op.create_index('ix_cliente_vip_historico_criado_em', 'cliente_vip_historico', ['criado_em'])

    # ── PDV: caixa diária do barbeiro ────────────────────────────────────────
    op.create_table('barbeiro_caixa',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('barbearia_id', sa.Integer(), nullable=False),
        sa.Column('barbeiro_id', sa.Integer(), nullable=False),
        sa.Column('aberto_em', sa.DateTime(), nullable=False),
        sa.Column('fechado_em', sa.DateTime(), nullable=True),
        sa.Column('total', sa.Numeric(10, 2), nullable=False, server_default=sa.text('0')),
        sa.Column('data', sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(['barbearia_id'], ['barbearias.id'], name='fk_barbeiro_caixa_barbearia_id'),
        sa.ForeignKeyConstraint(['barbeiro_id'], ['barbeiros.id'], name='fk_barbeiro_caixa_barbeiro_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('barbeiro_id', 'data', name='uq_barbeiro_caixa_data'),
        sa.CheckConstraint('total >= 0', name='ck_barbeiro_caixa_total_positivo'),
    )
    op.create_index('ix_barbeiro_caixa_barbearia_id', 'barbeiro_caixa', ['barbearia_id'])
    op.create_index('ix_barbeiro_caixa_barbeiro_id', 'barbeiro_caixa', ['barbeiro_id'])

    op.create_table('item_caixa',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('barbearia_id', sa.Integer(), nullable=False),
        sa.Column('caixa_id', sa.Integer(), nullable=False),
        sa.Column('produto_id', sa.Integer(), nullable=False),
        sa.Column('quantidade', sa.Integer(), nullable=False, server_default=sa.text('1')),
        sa.Column('preco', sa.Numeric(10, 2), nullable=False),
        sa.Column('desconto_percentual', sa.Numeric(5, 2), nullable=False, server_default=sa.text('0')),
        sa.Column('forma_pagamento', sa.String(20), nullable=False),
        sa.Column('agendamento_id', sa.Integer(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['barbearia_id'], ['barbearias.id'], name='fk_item_caixa_barbearia_id'),
        sa.ForeignKeyConstraint(['caixa_id'], ['barbeiro_caixa.id'], name='fk_item_caixa_caixa_id'),
        sa.ForeignKeyConstraint(['produto_id'], ['produtos.id'], name='fk_item_caixa_produto_id'),
        sa.ForeignKeyConstraint(['agendamento_id'], ['agendamentos.id'], name='fk_item_caixa_agendamento_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('quantidade > 0', name='ck_item_caixa_quantidade_positiva'),
        sa.CheckConstraint('preco >= 0', name='ck_item_caixa_preco_positivo'),
        sa.CheckConstraint(
            'desconto_percentual >= 0 AND desconto_percentual <= 100',
            name='ck_item_caixa_desconto_range',
        ),
        sa.CheckConstraint(
            "forma_pagamento IN ('pix','dinheiro','cartao')",
            name='ck_item_caixa_forma_pagamento_valida',
        ),
    )
    op.create_index('ix_item_caixa_barbearia_id', 'item_caixa', ['barbearia_id'])
    op.create_index('ix_item_caixa_caixa_id', 'item_caixa', ['caixa_id'])
    op.create_index('ix_item_caixa_produto_id', 'item_caixa', ['produto_id'])

    # ── Reset de senha estendido (token/código/expiração) ────────────────────
    op.add_column('solicitacoes_senha', sa.Column('token', sa.String(256), nullable=False))
    op.add_column('solicitacoes_senha', sa.Column('codigo_novo', sa.String(20), nullable=False))
    op.add_column('solicitacoes_senha', sa.Column(
        'tentativas', sa.Integer(), nullable=False, server_default=sa.text('0'),
    ))
    op.add_column('solicitacoes_senha', sa.Column('expira_em', sa.DateTime(), nullable=False))
    op.add_column('solicitacoes_senha', sa.Column('confirmado_em', sa.DateTime(), nullable=True))
    op.create_unique_constraint('uq_solicitacoes_senha_token', 'solicitacoes_senha', ['token'])
    op.create_index('ix_solicitacoes_senha_usuario_id', 'solicitacoes_senha', ['usuario_id'])
    op.create_index('ix_solicitacoes_senha_expira_em', 'solicitacoes_senha', ['expira_em'])


def downgrade():
    op.drop_index('ix_solicitacoes_senha_expira_em', table_name='solicitacoes_senha')
    op.drop_index('ix_solicitacoes_senha_usuario_id', table_name='solicitacoes_senha')
    op.drop_constraint('uq_solicitacoes_senha_token', 'solicitacoes_senha', type_='unique')
    op.drop_column('solicitacoes_senha', 'confirmado_em')
    op.drop_column('solicitacoes_senha', 'expira_em')
    op.drop_column('solicitacoes_senha', 'tentativas')
    op.drop_column('solicitacoes_senha', 'codigo_novo')
    op.drop_column('solicitacoes_senha', 'token')

    op.drop_index('ix_item_caixa_produto_id', table_name='item_caixa')
    op.drop_index('ix_item_caixa_caixa_id', table_name='item_caixa')
    op.drop_index('ix_item_caixa_barbearia_id', table_name='item_caixa')
    op.drop_table('item_caixa')

    op.drop_index('ix_barbeiro_caixa_barbeiro_id', table_name='barbeiro_caixa')
    op.drop_index('ix_barbeiro_caixa_barbearia_id', table_name='barbeiro_caixa')
    op.drop_table('barbeiro_caixa')

    op.drop_index('ix_cliente_vip_historico_criado_em', table_name='cliente_vip_historico')
    op.drop_index('ix_cliente_vip_historico_cliente_id', table_name='cliente_vip_historico')
    op.drop_index('ix_cliente_vip_historico_barbearia_id', table_name='cliente_vip_historico')
    op.drop_table('cliente_vip_historico')

    op.drop_column('cliente_vip', 'meses_consecutivos')
