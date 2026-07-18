"""adiciona tema em barbearia_customizacao

Revision ID: e906dfc4e380
Revises: d591d4c256a8
Create Date: 2026-07-17 22:25:56.342940

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e906dfc4e380'
down_revision = 'd591d4c256a8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'barbearia_customizacao',
        sa.Column('tema', sa.String(length=20), nullable=True, server_default='preto'),
    )


def downgrade():
    op.drop_column('barbearia_customizacao', 'tema')
