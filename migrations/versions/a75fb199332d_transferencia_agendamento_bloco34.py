"""transferencia_agendamento_bloco34

Revision ID: a75fb199332d
Revises: 070b21d15769
Create Date: 2026-07-06 12:31:57.478929

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a75fb199332d'
down_revision = '070b21d15769'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'transferencia_agendamento',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('barbearia_id', sa.Integer(), nullable=False),
        sa.Column('agendamento_id', sa.Integer(), nullable=False),
        sa.Column('barbeiro_origem_id', sa.Integer(), nullable=False),
        sa.Column('barbeiro_destino_id', sa.Integer(), nullable=True),
        sa.Column('motivo', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pendente'),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.Column('concluido_em', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id', name='pk_transferencia_agendamento'),
        sa.ForeignKeyConstraint(['barbearia_id'], ['barbearias.id'], name='fk_transferencia_agendamento_barbearia_id'),
        sa.ForeignKeyConstraint(['agendamento_id'], ['agendamentos.id'], name='fk_transferencia_agendamento_agendamento_id'),
        sa.ForeignKeyConstraint(['barbeiro_origem_id'], ['barbeiros.id'], name='fk_transferencia_agendamento_barbeiro_origem_id'),
        sa.ForeignKeyConstraint(['barbeiro_destino_id'], ['barbeiros.id'], name='fk_transferencia_agendamento_barbeiro_destino_id'),
        sa.CheckConstraint(
            "status IN ('pendente','concluida','reagendada','cancelada')",
            name='ck_transferencia_agendamento_status_valido',
        ),
    )
    op.create_index('ix_transferencia_agendamento_barbearia_id', 'transferencia_agendamento', ['barbearia_id'])
    op.create_index('ix_transferencia_agendamento_agendamento_id', 'transferencia_agendamento', ['agendamento_id'])


def downgrade():
    op.drop_index('ix_transferencia_agendamento_agendamento_id', table_name='transferencia_agendamento')
    op.drop_index('ix_transferencia_agendamento_barbearia_id', table_name='transferencia_agendamento')
    op.drop_table('transferencia_agendamento')
