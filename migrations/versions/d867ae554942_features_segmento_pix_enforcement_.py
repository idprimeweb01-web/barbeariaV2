"""features_segmento_pix_enforcement_dividas

Revision ID: d867ae554942
Revises: a3ccf28f4117
Create Date: 2026-07-12 14:40:20.101190

Nota: o autogenerate também acusou a remoção de 'uq_ag_barbeiro_slot'
(agendamentos), 'segmentos_chave_key' (segmentos) e 'uq_usuario_email_staff'
(usuarios) — falso-positivo já conhecido do projeto (autogenerate não
introspecta bem índices únicos parciais/expressões). Removido do upgrade/
downgrade abaixo; nenhum dos três é tocado por esta migration.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd867ae554942'
down_revision = 'a3ccf28f4117'
branch_labels = None
depends_on = None

_FEATURES_REMOVIDAS = ('relatorios_avancados', 'agendamento_login', 'fila_espera')


def upgrade():
    # ── Schema: status_pagamento ────────────────────────────────────────────
    with op.batch_alter_table('agendamentos', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'status_pagamento', sa.String(length=20), nullable=False,
            server_default='pendente',
        ))
        batch_op.create_check_constraint(
            'ck_agendamentos_status_pagamento_valido',
            "status_pagamento IN ('pendente', 'pago')",
        )

    # Backfill: agendamentos existentes pagos via PIX já foram recebidos —
    # os demais (local/presencial) entram como 'pendente' via server_default acima.
    op.execute(
        "UPDATE agendamentos SET status_pagamento = 'pago' WHERE metodo_pagamento = 'pix'"
    )

    # ── Dados: remove as 3 features decorativas do catálogo ─────────────────
    # Ordem: filhos (feature_barbearia, segmento_feature_padrao) antes do pai
    # (feature_metadata), por causa das FKs sem ON DELETE CASCADE.
    placeholders = ", ".join(f"'{nome}'" for nome in _FEATURES_REMOVIDAS)
    op.execute(f"""
        DELETE FROM feature_barbearia
        WHERE feature_id IN (SELECT id FROM feature_metadata WHERE nome IN ({placeholders}))
    """)
    op.execute(f"""
        DELETE FROM segmento_feature_padrao
        WHERE feature_id IN (SELECT id FROM feature_metadata WHERE nome IN ({placeholders}))
    """)
    op.execute(f"DELETE FROM feature_metadata WHERE nome IN ({placeholders})")


def downgrade():
    # Não recria as 3 features removidas (dado de catálogo, não de schema —
    # se precisar reverter, rodar seed_feature_metadata() com o código antigo).
    with op.batch_alter_table('agendamentos', schema=None) as batch_op:
        batch_op.drop_constraint('ck_agendamentos_status_pagamento_valido', type_='check')
        batch_op.drop_column('status_pagamento')
