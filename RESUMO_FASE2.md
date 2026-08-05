# RESUMO_FASE2.md — Correções pós-validação (2026-08-02/04)

Resumo operacional da FASE 2: correção dos 6 achados de comportamento
listados em `PLANO_DE_ACAO.md` (C1, C2, A1, M1, M2, M3), um bloco por vez,
cada um com commit próprio e teste de regressão dedicado.

## Commits, em ordem

| # | Commit | O que faz |
|---|---|---|
| 1 | `303a18b` | C2 — trava `rejeitar_compra` contra corrida com `aprovar_compra` |
| 2 | `e1606b1` | C1 — honra valor congelado na aprovação de compra em vez de recalcular |
| 3 | `d931b04` | A1 — limite de uso de cupom por cliente, além do global |
| 4 | `eeded14` | M2 — 409 amigável no double-booking do agendamento manual |
| 5 | `52f2887` | M1 — cancelamento futuro estorna crédito de plano consumido |
| 6 | `e74f501` | M3 — documenta (sem mudar comportamento) que e-mail duplicado é checagem global intencional |

Nenhum push feito ainda — todos os 6 commits estão só locais, seguindo o
mesmo padrão do resto da sessão (o dono decide quando publicar).

---

## Migrations a rodar em produção, nesta ordem

Só 2 migrations nesta fase, ambas aditivas e testadas localmente
(upgrade→downgrade→upgrade, sem downtime, sem dado a migrar/backfill):

1. **`38b77ccd508f`** (bloco C1) — adiciona `cupom_uso.honrado_fora_limite`
   (Boolean, `NOT NULL DEFAULT false`, backfill automático via
   `server_default`).
2. **`3e3f4bfe0d8b`** (bloco A1) — adiciona `cupons.limite_uso_por_cliente`
   (Integer, nullable) + `CHECK` (`IS NULL OR > 0`).

Comando padrão: `flask db upgrade` (a cadeia do Alembic já garante essa
ordem via `down_revision`, não precisa especificar revisão a revisão).

**Nota técnica que vale saber antes de rodar:** o autogenerate do Alembic
propôs, nas duas vezes, dropar `uq_ag_barbeiro_slot` e `uq_usuario_email_staff`
por engano (falso-positivo de drift já documentado em DT-008 — são índices
criados via SQL raw, invisíveis ao autogenerate baseado em models). Os dois
arquivos de migration finais **não** tocam nesses índices — já removi
manualmente e testei que sobrevivem ao ciclo up/down/up. Só citando pra você
não estranhar se comparar com o que o Alembic sugeriu originalmente.

---

## Variáveis de ambiente novas

**Nenhuma.** Esta fase não introduziu configuração nova.

---

## O que testar manualmente antes de liberar

1. **Compras — corrida aprovar×rejeitar (C2):** na tela de Compras do
   gestor (`/gestor/compras-produto`), com um pedido pendente, tentar
   aprovar e rejeitar quase ao mesmo tempo em duas abas — só uma deve
   vencer, a outra deve mostrar "Este pedido já foi processado."
2. **Compras — valor congelado (C1):** criar um pedido com cupom, mudar o
   preço do produto ou desativar o cupom antes de aprovar, confirmar que a
   venda registrada bate com o valor que apareceria no comprovante PIX
   gerado no pedido original (não com o preço/desconto novo).
3. **Cupom — limite por cliente (A1):** criar um cupom no painel
   (`/gestor/cupons`) com "Limite de Uso por Cliente" = 1, usar com um
   cliente, confirmar que o mesmo cliente toma erro na 2ª tentativa e que
   outro cliente ainda consegue usar.
4. **Agendamento manual — 409 amigável (M2):** criar dois agendamentos
   manuais pro mesmo horário/barbeiro quase ao mesmo tempo (duas abas) —
   confirmar que aparece uma mensagem amigável ("horário acabou de ser
   reservado"), não um erro genérico de servidor.
5. **Cancelamento — estorno de plano (M1):** cliente com plano ativo agenda
   um serviço coberto, cancela dentro do prazo — confirmar visualmente
   (tela do cliente ou do gestor, uso mensal do plano) que o crédito volta.
   **Atenção a este ponto:** a exceção manual do gestor
   (`sem_estorno_plano: true`) está implementada só no backend — **não
   existe checkbox na tela de cancelamento do gestor** (`gestor/agenda.html`)
   pra acionar isso ainda. Se você quiser usar essa exceção manual pelo
   painel (não só via API direta), isso precisa de um bloco de UI à parte —
   não fazia parte do pedido original desta fase, não constrooi
   proativamente.
6. **M3:** nenhum teste necessário — comportamento não mudou, só foi
   documentado.

---

## O que NÃO foi tocado nesta fase (lembrete)

- **B1** (preview de cupom aceita valor do cliente sem recálculo) — baixo
  risco, nenhuma ação pedida, continua como estava.
- **Débito de testes** de `LACUNAS_TESTE.md` (autenticação do bot,
  token de comprovante, cupom multi-item, etc.) — fora do escopo desta
  fase, que cobriu só os achados de comportamento confirmados no
  `PLANO_DE_ACAO.md`.
- **DT-007** (credencial Cloudinary vazada) e **DT-010** (sequestro de
  conta via telefone) — dívidas técnicas antigas, não fazem parte deste
  plano, continuam pendentes de ação do dono.
