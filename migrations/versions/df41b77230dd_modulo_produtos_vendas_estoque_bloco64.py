"""modulo_produtos_vendas_estoque_bloco64

Revision ID: df41b77230dd
Revises: a75fb199332d
Create Date: 2026-07-06 20:13:27.758242

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'df41b77230dd'
down_revision = 'a75fb199332d'
branch_labels = None
depends_on = None


def upgrade():
    # ── categoria_produto ─────────────────────────────────────────────────────
    op.create_table(
        'categoria_produto',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('barbearia_id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=80), nullable=False),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint('id', name='pk_categoria_produto'),
        sa.ForeignKeyConstraint(['barbearia_id'], ['barbearias.id'], name='fk_categoria_produto_barbearia_id'),
        sa.UniqueConstraint('barbearia_id', 'nome', name='uq_categoria_produto_barbearia_nome'),
    )
    op.create_index('ix_categoria_produto_barbearia_id', 'categoria_produto', ['barbearia_id'])

    # ── venda (antes de produtos/movimentacao_estoque, que referenciam ela) ───
    op.create_table(
        'venda',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('barbearia_id', sa.Integer(), nullable=False),
        sa.Column('cliente_id', sa.Integer(), nullable=True),
        sa.Column('cliente_nome_livre', sa.String(length=100), nullable=True),
        sa.Column('barbeiro_id', sa.Integer(), nullable=True),
        sa.Column('usuario_registro_id', sa.Integer(), nullable=False),
        sa.Column('metodo_pagamento', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='concluida'),
        sa.Column('valor_total', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id', name='pk_venda'),
        sa.ForeignKeyConstraint(['barbearia_id'], ['barbearias.id'], name='fk_venda_barbearia_id'),
        sa.ForeignKeyConstraint(['cliente_id'], ['clientes.id'], name='fk_venda_cliente_id'),
        sa.ForeignKeyConstraint(['barbeiro_id'], ['barbeiros.id'], name='fk_venda_barbeiro_id'),
        sa.ForeignKeyConstraint(['usuario_registro_id'], ['usuarios.id'], name='fk_venda_usuario_registro_id'),
        sa.CheckConstraint('valor_total >= 0', name='ck_venda_valor_total_positivo'),
        sa.CheckConstraint("status IN ('concluida','cancelada')", name='ck_venda_status_valido'),
        sa.CheckConstraint("metodo_pagamento IN ('pix','dinheiro','cartao')", name='ck_venda_metodo_pagamento_valido'),
    )
    op.create_index('ix_venda_barbearia_id', 'venda', ['barbearia_id'])

    # ── venda_item ──────────────────────────────────────────────────────────
    op.create_table(
        'venda_item',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('venda_id', sa.Integer(), nullable=False),
        sa.Column('produto_id', sa.Integer(), nullable=False),
        sa.Column('quantidade', sa.Integer(), nullable=False),
        sa.Column('preco_unitario', sa.Numeric(10, 2), nullable=False),
        sa.Column('custo_unitario_snapshot', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('comissao_valor', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id', name='pk_venda_item'),
        sa.ForeignKeyConstraint(['venda_id'], ['venda.id'], name='fk_venda_item_venda_id'),
        sa.ForeignKeyConstraint(['produto_id'], ['produtos.id'], name='fk_venda_item_produto_id'),
        sa.CheckConstraint('quantidade > 0', name='ck_venda_item_quantidade_positiva'),
    )
    op.create_index('ix_venda_item_venda_id', 'venda_item', ['venda_id'])

    # ── produtos: novas colunas (todas nullable/default seguro p/ dados existentes) ──
    with op.batch_alter_table('produtos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('categoria_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('marca', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('custo_unitario', sa.Numeric(10, 2), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('codigo_barras', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('estoque_minimo', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('foto_url', sa.String(length=300), nullable=True))
        batch_op.create_foreign_key('fk_produtos_categoria_id', 'categoria_produto', ['categoria_id'], ['id'])
        batch_op.create_check_constraint('ck_produtos_custo_unitario_positivo', 'custo_unitario >= 0')
        batch_op.create_check_constraint('ck_produtos_estoque_minimo_positivo', 'estoque_minimo >= 0')
    op.create_index('ix_produtos_categoria_id', 'produtos', ['categoria_id'])

    # ── movimentacao_estoque ──────────────────────────────────────────────────
    op.create_table(
        'movimentacao_estoque',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('barbearia_id', sa.Integer(), nullable=False),
        sa.Column('produto_id', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=20), nullable=False),
        sa.Column('quantidade', sa.Integer(), nullable=False),
        sa.Column('quantidade_apos', sa.Integer(), nullable=False),
        sa.Column('motivo', sa.String(length=200), nullable=True),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('referencia_venda_id', sa.Integer(), nullable=True),
        sa.Column('referencia_atendimento_id', sa.Integer(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id', name='pk_movimentacao_estoque'),
        sa.ForeignKeyConstraint(['barbearia_id'], ['barbearias.id'], name='fk_movimentacao_estoque_barbearia_id'),
        sa.ForeignKeyConstraint(['produto_id'], ['produtos.id'], name='fk_movimentacao_estoque_produto_id'),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], name='fk_movimentacao_estoque_usuario_id'),
        sa.ForeignKeyConstraint(['referencia_venda_id'], ['venda.id'], name='fk_movimentacao_estoque_referencia_venda_id'),
        sa.ForeignKeyConstraint(['referencia_atendimento_id'], ['atendimentos.id'], name='fk_movimentacao_estoque_referencia_atendimento_id'),
        sa.CheckConstraint('quantidade > 0', name='ck_movimentacao_estoque_quantidade_positiva'),
        sa.CheckConstraint(
            "tipo IN ('entrada','saida_venda','saida_uso','ajuste')",
            name='ck_movimentacao_estoque_tipo_valido',
        ),
    )
    op.create_index('ix_movimentacao_estoque_barbearia_id', 'movimentacao_estoque', ['barbearia_id'])
    op.create_index('ix_movimentacao_estoque_produto_id', 'movimentacao_estoque', ['produto_id'])

    # ── feature_metadata: ativo_por_padrao (Script 18) ────────────────────────
    with op.batch_alter_table('feature_metadata', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ativo_por_padrao', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('feature_metadata', schema=None) as batch_op:
        batch_op.drop_column('ativo_por_padrao')

    op.drop_index('ix_movimentacao_estoque_produto_id', table_name='movimentacao_estoque')
    op.drop_index('ix_movimentacao_estoque_barbearia_id', table_name='movimentacao_estoque')
    op.drop_table('movimentacao_estoque')

    op.drop_index('ix_produtos_categoria_id', table_name='produtos')
    with op.batch_alter_table('produtos', schema=None) as batch_op:
        batch_op.drop_constraint('ck_produtos_estoque_minimo_positivo', type_='check')
        batch_op.drop_constraint('ck_produtos_custo_unitario_positivo', type_='check')
        batch_op.drop_constraint('fk_produtos_categoria_id', type_='foreignkey')
        batch_op.drop_column('foto_url')
        batch_op.drop_column('estoque_minimo')
        batch_op.drop_column('codigo_barras')
        batch_op.drop_column('custo_unitario')
        batch_op.drop_column('marca')
        batch_op.drop_column('categoria_id')

    op.drop_index('ix_venda_item_venda_id', table_name='venda_item')
    op.drop_table('venda_item')

    op.drop_index('ix_venda_barbearia_id', table_name='venda')
    op.drop_table('venda')

    op.drop_index('ix_categoria_produto_barbearia_id', table_name='categoria_produto')
    op.drop_table('categoria_produto')
