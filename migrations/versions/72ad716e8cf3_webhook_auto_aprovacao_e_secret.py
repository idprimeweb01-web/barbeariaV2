"""webhook auto aprovacao e secret

Revision ID: 72ad716e8cf3
Revises: e906dfc4e380
Create Date: 2026-07-18 15:49:19.384356

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '72ad716e8cf3'
down_revision = 'e906dfc4e380'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'barbearia_webhook_config',
        sa.Column('permite_auto_aprovacao', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'barbearia_webhook_config',
        sa.Column('webhook_secret', sa.String(length=64), nullable=True),
    )


def downgrade():
    op.drop_column('barbearia_webhook_config', 'webhook_secret')
    op.drop_column('barbearia_webhook_config', 'permite_auto_aprovacao')
