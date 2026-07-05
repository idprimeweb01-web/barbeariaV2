"""indices_performance_bloco52

Revision ID: 070b21d15769
Revises: 0fc98933f5eb
Create Date: 2026-07-05 17:04:07.795257

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '070b21d15769'
down_revision = '0fc98933f5eb'
branch_labels = None
depends_on = None


def upgrade():
    # ── CRÍTICOS: auditoria_log (full scan em toda consulta de auditoria) ────
    op.create_index('ix_auditoria_log_barbearia_id', 'auditoria_log', ['barbearia_id'])
    op.create_index('ix_auditoria_log_usuario_id', 'auditoria_log', ['usuario_id'])

    # ── ALTOS ──────────────────────────────────────────────────────────────
    op.create_index('ix_clientes_usuario_id', 'clientes', ['usuario_id'])
    op.create_index('ix_barbeiros_usuario_id', 'barbeiros', ['usuario_id'])
    op.create_index('ix_cliente_plano_uso_servico_id', 'cliente_plano_uso', ['servico_id'])
    op.create_index('ix_agendamento_servicos_cliente_plano_id', 'agendamento_servicos', ['cliente_plano_id'])
    op.create_index('ix_agendamentos_cupom_id', 'agendamentos', ['cupom_id'])

    # ── MÉDIOS ─────────────────────────────────────────────────────────────
    op.create_index('ix_barbeiro_servicos_servico_id', 'barbeiro_servicos', ['servico_id'])
    op.create_index('ix_planos_barbeiro_id', 'planos', ['barbeiro_id'])
    op.create_index('ix_cliente_plano_plano_id', 'cliente_plano', ['plano_id'])
    op.create_index('ix_cliente_plano_solicitacao_cliente_id', 'cliente_plano_solicitacao', ['cliente_id'])
    op.create_index('ix_atendimentos_cliente_id', 'atendimentos', ['cliente_id'])
    op.create_index('ix_plano_servicos_servico_id', 'plano_servicos', ['servico_id'])


def downgrade():
    op.drop_index('ix_plano_servicos_servico_id', table_name='plano_servicos')
    op.drop_index('ix_atendimentos_cliente_id', table_name='atendimentos')
    op.drop_index('ix_cliente_plano_solicitacao_cliente_id', table_name='cliente_plano_solicitacao')
    op.drop_index('ix_cliente_plano_plano_id', table_name='cliente_plano')
    op.drop_index('ix_planos_barbeiro_id', table_name='planos')
    op.drop_index('ix_barbeiro_servicos_servico_id', table_name='barbeiro_servicos')

    op.drop_index('ix_agendamentos_cupom_id', table_name='agendamentos')
    op.drop_index('ix_agendamento_servicos_cliente_plano_id', table_name='agendamento_servicos')
    op.drop_index('ix_cliente_plano_uso_servico_id', table_name='cliente_plano_uso')
    op.drop_index('ix_barbeiros_usuario_id', table_name='barbeiros')
    op.drop_index('ix_clientes_usuario_id', table_name='clientes')

    op.drop_index('ix_auditoria_log_usuario_id', table_name='auditoria_log')
    op.drop_index('ix_auditoria_log_barbearia_id', table_name='auditoria_log')
