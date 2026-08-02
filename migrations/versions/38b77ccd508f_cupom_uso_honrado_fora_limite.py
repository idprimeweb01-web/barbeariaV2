"""cupom_uso_honrado_fora_limite

Revision ID: 38b77ccd508f
Revises: 6c106d8fec79
Create Date: 2026-08-02 02:37:09.605526

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '38b77ccd508f'
down_revision = '6c106d8fec79'
branch_labels = None
depends_on = None


def upgrade():
    # NOTA: o autogenerate também propôs dropar 'uq_ag_barbeiro_slot' e
    # 'uq_usuario_email_staff' — falso-positivo de drift já documentado em
    # DT-008 (índices criados via SQL raw, invisíveis ao autogenerate
    # baseado em models). Removido manualmente do diff — esta migration
    # mexe só em cupom_uso.
    op.add_column(
        'cupom_uso',
        sa.Column('honrado_fora_limite', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade():
    op.drop_column('cupom_uso', 'honrado_fora_limite')
