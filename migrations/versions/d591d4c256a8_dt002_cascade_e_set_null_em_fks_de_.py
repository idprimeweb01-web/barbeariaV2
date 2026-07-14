"""dt002 cascade e set null em fks de historico

DT-002: FKs sem ON DELETE fazem qualquer deleção de Agendamento/Usuario
levantar ForeignKeyViolation quando já existem filhos/registros de log
apontando pra eles (confirmado 3x em limpeza de dados de teste). Duas
categorias de fix, nunca por bulk .query.delete() e sim CASCADE/SET NULL
no próprio banco, robusto independente de como a deleção é feita:

  - agendamento_servicos.agendamento_id, agendamento_solicitacao_pix.agendamento_id
    -> ON DELETE CASCADE (são detalhe do agendamento, não fazem sentido órfãos).
  - auditoria_log.usuario_id, tokens_revogados.usuario_id
    -> ON DELETE SET NULL (preserva o histórico/log; só o vínculo com o
       usuário apagado é que some — ambas as colunas já eram nullable).

Revision ID: d591d4c256a8
Revises: a883944fe23a
Create Date: 2026-07-13 21:05:46.801103

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd591d4c256a8'
down_revision = 'a883944fe23a'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('agendamento_servicos_agendamento_id_fkey', 'agendamento_servicos', type_='foreignkey')
    op.create_foreign_key(
        'agendamento_servicos_agendamento_id_fkey', 'agendamento_servicos',
        'agendamentos', ['agendamento_id'], ['id'], ondelete='CASCADE',
    )

    op.drop_constraint('agendamento_solicitacao_pix_agendamento_id_fkey', 'agendamento_solicitacao_pix', type_='foreignkey')
    op.create_foreign_key(
        'agendamento_solicitacao_pix_agendamento_id_fkey', 'agendamento_solicitacao_pix',
        'agendamentos', ['agendamento_id'], ['id'], ondelete='CASCADE',
    )

    op.drop_constraint('auditoria_log_usuario_id_fkey', 'auditoria_log', type_='foreignkey')
    op.create_foreign_key(
        'auditoria_log_usuario_id_fkey', 'auditoria_log',
        'usuarios', ['usuario_id'], ['id'], ondelete='SET NULL',
    )

    op.drop_constraint('tokens_revogados_usuario_id_fkey', 'tokens_revogados', type_='foreignkey')
    op.create_foreign_key(
        'tokens_revogados_usuario_id_fkey', 'tokens_revogados',
        'usuarios', ['usuario_id'], ['id'], ondelete='SET NULL',
    )


def downgrade():
    op.drop_constraint('tokens_revogados_usuario_id_fkey', 'tokens_revogados', type_='foreignkey')
    op.create_foreign_key(
        'tokens_revogados_usuario_id_fkey', 'tokens_revogados',
        'usuarios', ['usuario_id'], ['id'],
    )

    op.drop_constraint('auditoria_log_usuario_id_fkey', 'auditoria_log', type_='foreignkey')
    op.create_foreign_key(
        'auditoria_log_usuario_id_fkey', 'auditoria_log',
        'usuarios', ['usuario_id'], ['id'],
    )

    op.drop_constraint('agendamento_solicitacao_pix_agendamento_id_fkey', 'agendamento_solicitacao_pix', type_='foreignkey')
    op.create_foreign_key(
        'agendamento_solicitacao_pix_agendamento_id_fkey', 'agendamento_solicitacao_pix',
        'agendamentos', ['agendamento_id'], ['id'],
    )

    op.drop_constraint('agendamento_servicos_agendamento_id_fkey', 'agendamento_servicos', type_='foreignkey')
    op.create_foreign_key(
        'agendamento_servicos_agendamento_id_fkey', 'agendamento_servicos',
        'agendamentos', ['agendamento_id'], ['id'],
    )
