"""restaura constraints de integridade perdidas (uq_ag_barbeiro_slot, uq_usuario_email_staff)

Revision ID: 6c106d8fec79
Revises: 087a5b599c06
Create Date: 2026-07-22

Achado em checkup de produção: 10 requisições concorrentes reservando o
MESMO horário do MESMO barbeiro resultavam em até 3 agendamentos criados
(esperado: 1). Investigação mostrou que os dois índices únicos parciais
criados em 0fc98933f5eb (integridade_producao_bloco21) NÃO EXISTEM no
banco atual, apesar do alembic_version mostrar que essa migration já foi
aplicada.

Causa raiz: 3c670a830b06 (dúvidas triagem categoria) usa
batch_alter_table em 'agendamentos' e 'usuarios' pra outras mudanças —
Alembic em modo batch recria a tabela inteira, e o autogenerate daquela
migration DROPOU e tentou RECRIAR esses índices como efeito colateral
(são invisíveis ao ORM, então toda migration seguinte que mexeu nessas
tabelas via batch_alter_table repetiu o drop/recreate). Em algum ponto
dessa cadeia o recreate não colou de fato no banco — resultado: dois
índices de segurança crítica (evitar double-booking e e-mail duplicado
de staff) ausentes silenciosamente há várias migrations.

Esta migration é corretiva e idempotente-por-construção: não depende de
nenhum estado anterior específico, só garante que os dois índices
existem no final, criando cada um só se realmente faltar. Isso corrige
tanto o banco atual (que já rodou a cadeia quebrada) quanto qualquer
deploy futuro que rode a cadeia inteira do zero (onde os drops/creates
anteriores podem ou não ter se cancelado corretamente).

'segmentos_chave_key' (o terceiro nome citado nos comentários de drift
das migrations anteriores) NÃO precisa de correção — Segmento.chave já
tem proteção equivalente via 'ix_segmentos_chave' (unique=True+index=True
no model), só com nome diferente do que o autogenerate esperava.
"""
from alembic import op


revision = '6c106d8fec79'
down_revision = '087a5b599c06'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'agendamentos' AND indexname = 'uq_ag_barbeiro_slot'
            ) THEN
                CREATE UNIQUE INDEX uq_ag_barbeiro_slot ON agendamentos (barbeiro_id, data_hora)
                WHERE status NOT IN ('cancelado');
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'usuarios' AND indexname = 'uq_usuario_email_staff'
            ) THEN
                CREATE UNIQUE INDEX uq_usuario_email_staff ON usuarios (email)
                WHERE perfil IN ('gestor', 'barbeiro', 'super_admin');
            END IF;
        END $$;
    """)


def downgrade():
    op.execute('DROP INDEX IF EXISTS uq_usuario_email_staff')
    op.execute('DROP INDEX IF EXISTS uq_ag_barbeiro_slot')
