"""migra status legado aguardando_pagamento para aguardando_aprovacao (CONS-02)

Revision ID: a1b2c3d4e5f6
Revises: 71af37b612a5
Create Date: 2026-07-20 00:00:00.000000

'aguardando_pagamento' era o status do fluxo antigo (um passo só) de PIX,
antes de ele ser dividido em 'aguardando_comprovante' (cliente ainda não
enviou comprovante) -> 'aguardando_aprovacao' (comprovante enviado,
esperando o gestor aprovar). Nenhuma rota do sistema cria mais
agendamentos com esse status (só é referenciado defensivamente, para
permitir que registros antigos ainda sejam aprovados) — o valor continua
listado em StatusAgendamento.TODOS/_STATUS_APROVAVEL de propósito, então
esta migration não mexe no CHECK constraint, só nos dados.

Mapeamento escolhido: 'aguardando_pagamento' -> 'aguardando_aprovacao'
(o estado equivalente mais próximo no fluxo atual de 2 passos — o
agendamento está com pagamento pendente de confirmação pelo gestor).
"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '71af37b612a5'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text(
            "UPDATE agendamentos SET status = 'aguardando_aprovacao' "
            "WHERE status = 'aguardando_pagamento'"
        )
    )


def downgrade():
    # Migration de dados só — não há como distinguir, depois do upgrade,
    # quais linhas de 'aguardando_aprovacao' eram originalmente
    # 'aguardando_pagamento'. Downgrade é intencionalmente um no-op.
    pass
