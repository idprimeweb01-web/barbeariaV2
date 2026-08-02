"""cupom_limite_uso_por_cliente

Revision ID: 3e3f4bfe0d8b
Revises: 38b77ccd508f
Create Date: 2026-08-02 14:31:48.338154

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3e3f4bfe0d8b'
down_revision = '38b77ccd508f'
branch_labels = None
depends_on = None


def upgrade():
    # NOTA: o autogenerate também propôs dropar 'uq_ag_barbeiro_slot' e
    # 'uq_usuario_email_staff' — mesmo falso-positivo de drift documentado em
    # DT-008 (índices via SQL raw, invisíveis ao autogenerate). Removido
    # manualmente. O CheckConstraint também não é detectado automaticamente
    # (padrão já conhecido do projeto) — adicionado à mão abaixo.
    op.add_column(
        'cupons',
        sa.Column('limite_uso_por_cliente', sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        'ck_cupons_limite_uso_por_cliente_positivo',
        'cupons',
        'limite_uso_por_cliente IS NULL OR limite_uso_por_cliente > 0',
    )


def downgrade():
    op.drop_constraint('ck_cupons_limite_uso_por_cliente_positivo', 'cupons', type_='check')
    op.drop_column('cupons', 'limite_uso_por_cliente')
