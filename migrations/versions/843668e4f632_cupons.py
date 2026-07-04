"""cupons de desconto

Revision ID: 843668e4f632
Revises: c5d7f9a1b3e5
Create Date: 2026-06-29 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '843668e4f632'
down_revision = 'c5d7f9a1b3e5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('cupons',
        sa.Column('id',                      sa.Integer(), nullable=False),
        sa.Column('barbearia_id',             sa.Integer(), nullable=False),
        sa.Column('nome',                     sa.String(100), nullable=False),
        sa.Column('codigo',                   sa.String(30),  nullable=False),
        sa.Column('tipo_desconto',            sa.String(20),  nullable=False),
        sa.Column('valor_desconto',           sa.Numeric(10, 2), nullable=False),
        sa.Column('data_expiracao',           sa.Date(), nullable=False),
        sa.Column('quantidade_maxima_usos',   sa.Integer(), nullable=True),
        sa.Column('quantidade_usos',          sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ativo',                    sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('criado_em',                sa.DateTime(), nullable=True),
        sa.Column('atualizado_em',            sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['barbearia_id'], ['barbearias.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('barbearia_id', 'codigo', name='uq_cupom_barbearia_codigo'),
    )
    op.create_index('ix_cupons_barbearia_id', 'cupons', ['barbearia_id'])

    op.add_column('agendamentos', sa.Column('cupom_id', sa.Integer(), nullable=True))
    op.add_column('agendamentos', sa.Column('valor_desconto', sa.Numeric(10, 2), nullable=False, server_default='0'))
    op.create_foreign_key('fk_agendamentos_cupom_id', 'agendamentos', 'cupons', ['cupom_id'], ['id'])


def downgrade():
    op.drop_constraint('fk_agendamentos_cupom_id', 'agendamentos', type_='foreignkey')
    op.drop_column('agendamentos', 'valor_desconto')
    op.drop_column('agendamentos', 'cupom_id')
    op.drop_index('ix_cupons_barbearia_id', table_name='cupons')
    op.drop_table('cupons')
