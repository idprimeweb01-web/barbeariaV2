"""integridade_producao_bloco21

Revision ID: 0fc98933f5eb
Revises: 2070465e5fe1
Create Date: 2026-07-04 17:47:11.829406

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0fc98933f5eb'
down_revision = '2070465e5fe1'
branch_labels = None
depends_on = None


def upgrade():
    # ── metodo_pagamento: backfill + NOT NULL ─────────────────────────────────
    op.execute("UPDATE agendamentos SET metodo_pagamento = 'local' WHERE metodo_pagamento IS NULL")
    with op.batch_alter_table('agendamentos', schema=None) as batch_op:
        batch_op.alter_column(
            'metodo_pagamento',
            existing_type=sa.String(length=20),
            nullable=False,
            server_default='local',
        )

    # ── agendamentos: CHECK constraints ───────────────────────────────────────
    with op.batch_alter_table('agendamentos', schema=None) as batch_op:
        batch_op.create_check_constraint(
            'ck_agendamentos_status_valido',
            "status IN ('agendado','concluido','cancelado','em_atendimento',"
            "'aguardando_comprovante','aguardando_aprovacao','aguardando_pagamento',"
            "'nao_realizado','aguardando_transferencia')",
        )
        batch_op.create_check_constraint(
            'ck_agendamentos_valor_total_positivo', 'valor_total >= 0',
        )
        batch_op.create_check_constraint(
            'ck_agendamentos_valor_desconto_positivo', 'valor_desconto >= 0',
        )

    # ── cliente_plano.solicitacao_id (rastreabilidade + trava anti-dupla-aprovação) ──
    with op.batch_alter_table('cliente_plano', schema=None) as batch_op:
        batch_op.add_column(sa.Column('solicitacao_id', sa.Integer(), nullable=True))
        batch_op.create_unique_constraint('uq_cliente_plano_solicitacao_id', ['solicitacao_id'])
        batch_op.create_foreign_key(
            'fk_cliente_plano_solicitacao_id',
            'cliente_plano_solicitacao', ['solicitacao_id'], ['id'],
        )

    # ── cliente_plano_uso: 1 uso por (assinatura, serviço, dia) ───────────────
    with op.batch_alter_table('cliente_plano_uso', schema=None) as batch_op:
        batch_op.create_unique_constraint(
            'uq_plano_uso_dia', ['cliente_plano_id', 'servico_id', 'data_uso'],
        )

    # ── cupons: CHECK constraints ──────────────────────────────────────────────
    with op.batch_alter_table('cupons', schema=None) as batch_op:
        batch_op.create_check_constraint(
            'ck_cupons_valor_desconto_positivo', 'valor_desconto >= 0',
        )
        batch_op.create_check_constraint(
            'ck_cupons_quantidade_usos_positivo', 'quantidade_usos >= 0',
        )
        batch_op.create_check_constraint(
            'ck_cupons_tipo_desconto_valido', "tipo_desconto IN ('percentual','valor_fixo')",
        )
        batch_op.create_check_constraint(
            'ck_cupons_percentual_max_100', "tipo_desconto != 'percentual' OR valor_desconto <= 100",
        )

    # ── barbeiros: comissao_percentual entre 0 e 100 ──────────────────────────
    with op.batch_alter_table('barbeiros', schema=None) as batch_op:
        batch_op.create_check_constraint(
            'ck_barbeiros_comissao_percentual_range',
            'comissao_percentual >= 0 AND comissao_percentual <= 100',
        )

    # ── produtos: estoque não-negativo ────────────────────────────────────────
    with op.batch_alter_table('produtos', schema=None) as batch_op:
        batch_op.create_check_constraint(
            'ck_produtos_quantidade_estoque_positivo', 'quantidade_estoque >= 0',
        )
        batch_op.create_check_constraint(
            'ck_produtos_quantidade_reservada_positivo', 'quantidade_reservada >= 0',
        )

    # ── Índices únicos parciais (SQLAlchemy não expressa partial index portável) ──
    op.execute(
        "CREATE UNIQUE INDEX uq_ag_barbeiro_slot ON agendamentos (barbeiro_id, data_hora) "
        "WHERE status NOT IN ('cancelado')"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_usuario_email_staff ON usuarios (email) "
        "WHERE perfil IN ('gestor','barbeiro','super_admin')"
    )


def downgrade():
    op.execute('DROP INDEX IF EXISTS uq_usuario_email_staff')
    op.execute('DROP INDEX IF EXISTS uq_ag_barbeiro_slot')

    with op.batch_alter_table('produtos', schema=None) as batch_op:
        batch_op.drop_constraint('ck_produtos_quantidade_reservada_positivo', type_='check')
        batch_op.drop_constraint('ck_produtos_quantidade_estoque_positivo', type_='check')

    with op.batch_alter_table('barbeiros', schema=None) as batch_op:
        batch_op.drop_constraint('ck_barbeiros_comissao_percentual_range', type_='check')

    with op.batch_alter_table('cupons', schema=None) as batch_op:
        batch_op.drop_constraint('ck_cupons_percentual_max_100', type_='check')
        batch_op.drop_constraint('ck_cupons_tipo_desconto_valido', type_='check')
        batch_op.drop_constraint('ck_cupons_quantidade_usos_positivo', type_='check')
        batch_op.drop_constraint('ck_cupons_valor_desconto_positivo', type_='check')

    with op.batch_alter_table('cliente_plano_uso', schema=None) as batch_op:
        batch_op.drop_constraint('uq_plano_uso_dia', type_='unique')

    with op.batch_alter_table('cliente_plano', schema=None) as batch_op:
        batch_op.drop_constraint('fk_cliente_plano_solicitacao_id', type_='foreignkey')
        batch_op.drop_constraint('uq_cliente_plano_solicitacao_id', type_='unique')
        batch_op.drop_column('solicitacao_id')

    with op.batch_alter_table('agendamentos', schema=None) as batch_op:
        batch_op.drop_constraint('ck_agendamentos_valor_desconto_positivo', type_='check')
        batch_op.drop_constraint('ck_agendamentos_valor_total_positivo', type_='check')
        batch_op.drop_constraint('ck_agendamentos_status_valido', type_='check')
        batch_op.alter_column(
            'metodo_pagamento',
            existing_type=sa.String(length=20),
            nullable=True,
            server_default=None,
        )
