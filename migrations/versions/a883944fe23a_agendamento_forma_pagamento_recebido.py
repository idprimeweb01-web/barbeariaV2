"""agendamento forma pagamento recebido

Revision ID: a883944fe23a
Revises: d867ae554942
Create Date: 2026-07-12 19:50:16.371533

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a883944fe23a'
down_revision = 'd867ae554942'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('agendamentos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('forma_pagamento_recebido', sa.String(length=20), nullable=True))
        batch_op.create_check_constraint(
            'ck_agendamentos_forma_pagamento_recebido_valida',
            "forma_pagamento_recebido IN ('dinheiro', 'cartao', 'pix')",
        )

    # Backfill: agendamentos ja pagos via PIX (pago online, sem passar pelo
    # recebimento manual do barbeiro) tem forma conhecida — os pagos "no
    # local" antes desta coluna existir ficam NULL (forma desconhecida
    # retroativamente, não é possível inferir).
    op.execute(
        "UPDATE agendamentos SET forma_pagamento_recebido = 'pix' "
        "WHERE metodo_pagamento = 'pix' AND status_pagamento = 'pago'"
    )


def downgrade():
    with op.batch_alter_table('agendamentos', schema=None) as batch_op:
        batch_op.drop_constraint('ck_agendamentos_forma_pagamento_recebido_valida', type_='check')
        batch_op.drop_column('forma_pagamento_recebido')
