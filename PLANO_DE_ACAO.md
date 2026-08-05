# PLANO_DE_ACAO.md — Consolidação (coordenador) + status pós-FASE 2

Consolida os 3 relatórios da validação disparada em 2026-08-02, cobrindo os 6
módulos novos entrados nos últimos 35 commits (Dúvidas, Loja/Compras, Bot
WhatsApp, Cupom multi-item, Notificações in-app, Perfil+Comprovante) e a
reconfirmação de 3 achados abertos de `AUDITORIA_PRODUCAO.md` (2026-07-23).

Fontes: `LACUNAS_TESTE.md` (audita-testes), `RELATORIO_IDOR.md` (caca-falhas),
`RELATORIO_REGRAS.md` (caca-bugs, rodadas 1 e 2).

**Regra deste documento (herdada do coordenador): eu não corrijo nada aqui.
Isto é só o plano. Correção volta pro fluxo de um bloco por vez, com
aprovação humana antes de cada um.**

## ⚡ STATUS — FASE 2 concluída em 2026-08-02/04 (6 blocos, 6 commits)

Todos os itens de comportamento (C1, C2, A1, M1, M2, M3) foram corrigidos,
um bloco por vez, cada um com teste de regressão confirmado falhando sem a
correção e passando com ela. Detalhes completos em `RESUMO_FASE2.md`.

| Item | Status | Commit |
|---|---|---|
| C2 — corrida aprovar×rejeitar | ✅ RESOLVIDO | `303a18b` |
| C1 — valor divergente na aprovação | ✅ RESOLVIDO | `e1606b1` |
| A1 — cupom sem limite por cliente | ✅ RESOLVIDO | `d931b04` |
| M2 — double-booking manual sem 409 | ✅ RESOLVIDO | `eeded14` |
| M1 — cancelamento não estorna plano | ✅ RESOLVIDO | `52f2887` |
| M3 — e-mail duplicado global | ✅ DOCUMENTADO (intencional, confirmado) | `e74f501` |
| B1 — preview de cupom sem recálculo | ⏳ ABERTO (baixo risco, nenhuma ação pedida) | — |
| Débito de testes (`LACUNAS_TESTE.md`) | ⏳ ABERTO (fora do escopo da FASE 2) | — |

O restante deste documento é o plano ORIGINAL de 2026-08-02, mantido como
registro histórico do que foi encontrado — as seções abaixo descrevem o
estado de ANTES da correção.

---

## Resumo executivo

- **2 achados CRÍTICOS novos**, ambos no módulo de Loja/Compras — nenhum
  IDOR, nenhuma falha de segurança nova.
- **Nenhuma falha de IDOR/cross-tenant** encontrada em nenhum dos 6 módulos
  novos — inclusive o ponto de maior risco aparente (comprovante via link
  assinado, autenticação do bot WhatsApp) foi confirmado correto.
- **3 achados antigos da auditoria de 07/23 continuam abertos** — nenhum dos
  35 commits recentes mexeu neles.
- **1 achado ALTO** (cupom sem limite por cliente) e **3 MÉDIOS** confirmados/
  reconfirmados.
- A rede de testes automatizados tem buracos grandes nos módulos novos (só
  Dúvidas está bem coberto) — não é um bug em si, mas significa que qualquer
  regressão futura nesses módulos pode passar despercebida.

---

## 🔴 CRÍTICO — corrigir antes de qualquer lançamento com uso real de dinheiro

### C1. Valor da Venda diverge do que o cliente pagou via PIX (Loja/Compras) — ✅ RESOLVIDO (`e1606b1`)
**Onde:** `app/routes/gestor/compras.py:100-113`, `app/utils/vendas.py:70-109`
(`preco_unitario` recalculado na linha 74, `validar_cupom` reexecutado do
zero na linha 99).

**O problema:** `criar_compra` congela preço/desconto/total no momento do
pedido e cobra isso via PIX. `aprovar_compra` **descarta esse valor
congelado** e recalcula tudo do zero com o preço/cupom **atuais** no
momento da aprovação. Se o gestor mudar o preço do produto, ou o cupom
expirar/esgotar/for desativado nesse meio-tempo:
- a `Venda` registrada (e a comissão do barbeiro, calculada em cima dela)
  diverge do que entrou de fato via PIX;
- se o cupom expirou, `aprovar_compra` **falha inteiro** — pedido já pago
  fica travado, sem fallback nem reembolso automatizado.

**Fonte:** `RELATORIO_REGRAS.md` §2.1 (caca-bugs, confirmado por leitura de
código linha a linha).

### C2. Corrida aprovar × rejeitar sem lock simétrico (Loja/Compras) — ✅ RESOLVIDO (`303a18b`)
**Onde:** `app/routes/gestor/compras.py:94` (`aprovar_compra`, usa
`.with_for_update()`) vs. `:141-143` (`rejeitar_compra`, sem lock).

**O problema:** dois requests simultâneos (aprovar + rejeitar) na mesma
solicitação podem ambos passar da checagem de status antes de qualquer
commit. Sequência possível: `rejeitar` lê `status='pendente'` antes do
commit do `aprovar`, fica bloqueado no `UPDATE` esperando o lock liberar,
`aprovar` comita (Venda real criada, estoque baixado, comissão lançada),
e então o `UPDATE` do `rejeitar` roda por cima **sem revalidar nada**,
marcando `status='rejeitada'` e notificando o cliente que o pedido foi
rejeitado — **enquanto a venda real já existe, com estoque debitado e
comissão registrada, nada disso revertido.**

**Fonte:** `RELATORIO_REGRAS.md` §2.2 (caca-bugs; dedução da semântica de
lock do Postgres READ COMMITTED + do UPDATE gerado pelo SQLAlchemy, não
executado em teste de carga real).

---

## 🟠 ALTO

### A1. Cupom sem limite de uso por cliente *(achado #6 da auditoria 07/23 — reconfirmado, nada mudou)* — ✅ RESOLVIDO (`d931b04`)
**Onde:** `app/utils/cupons.py:9-43` (`validar_cupom`), model `Cupom`
(`app/models/__init__.py:755-787`), model `CupomUso` (`:816-829`).

**O problema:** `Cupom` só tem limite **global** de uso
(`quantidade_maxima_usos`). `CupomUso` já guarda `cliente_id` por uso, mas
`validar_cupom()` nunca consulta isso para bloquear o mesmo cliente
reaplicando o cupom indefinidamente. Um cupom "10% na primeira visita" pode
ser reusado pelo mesmo cliente quantas vezes ele quiser.

**Fonte:** `RELATORIO_REGRAS.md`, seção "Rodada 2", achado #6.

---

## 🟡 MÉDIO

### M1. Cancelamento não estorna crédito de plano *(achado #7 — reconfirmado)* — ✅ RESOLVIDO (`52f2887`)
**Onde:** `app/routes/cliente/agendamento.py:138-206`,
`app/routes/gestor/agendamento.py:212-260`,
`app/routes/barbeiro/agendamentos.py:213-255`.

Os 3 endpoints de cancelamento tratam cupom (`decrementar_uso_cupom`) mas
nenhum toca `ClientePlanoUso` — cliente perde a sessão do plano mensal
mesmo cancelando com antecedência. **Decisão do dono (confirmada):**
cancelamento de agendamento FUTURO estorna; gestor pode forçar exceção
manual (`sem_estorno_plano: true`); agendamento no passado (sem status de
"falta" dedicado no sistema) não estorna. Ver `app/utils/planos.py::
estornar_creditos_plano`.

### M2. Double-booking manual do gestor cai em erro genérico *(achado #8 — reconfirmado)* — ✅ RESOLVIDO (`eeded14`)
**Onde:** `app/routes/gestor/agendamento.py:396,460-461` (sem try/except),
comparar com o padrão correto em `app/routes/pub/agendamento.py:310-318`.

Não é falha de integridade — o índice único `uq_ag_barbeiro_slot` no banco
continua impedindo o double-booking real. É só UX pior: dois
gestores/telas criando manualmente o mesmo horário ao mesmo tempo veem
"erro interno do servidor" (500) em vez de "esse horário acabou de ser
ocupado" (409).

### M3. Verificação de e-mail duplicado no perfil do gestor é global, não por tenant — ✅ DOCUMENTADO (`e74f501`, intencional confirmado)
**Onde:** `app/routes/gestor/perfil.py::editar_conta` (achado lateral do
audita-testes, não estava no escopo original de nenhum dos 2 testadores de
falha, mas é relevante o bastante para entrar aqui).

`Usuario.query.filter(Usuario.email == email, ...)` não é escopado por
`barbearia_id` — um gestor da barbearia A tentando trocar seu e-mail para
um e-mail já usado por alguém da barbearia B recebe 409 "já existe uma
conta com este e-mail", o que **confirma a existência de uma conta em
outra barbearia** (enumeração cross-tenant via resposta HTTP). Pode ser
intencional (login parece ser global por e-mail no sistema todo) — não
confirmado como bug, só como comportamento não documentado.

**Fonte:** `LACUNAS_TESTE.md` §6.

---

## 🔵 BAIXO / informativo

### B1. Preview de cupom aceita valor do item vindo do cliente, sem recálculo
**Onde:** `app/routes/cliente/cupons.py:30-34`
(`POST /api/v1/cliente/cupons/validar`).

Hoje inofensivo — é só uma prévia de UI, não encontrado nenhum fluxo de
cobrança real que reaproveite esse valor. **Risco futuro:** se algum dia
essa prévia virar base de cobrança sem revalidação server-side, vira forma
direta de pagar menos, já que o `valor` de cada item é 100% controlado
pelo cliente. Recomendação: nunca usar esse endpoint para nada além de UI.

---

## ✅ Verificado e confirmado CORRETO (não são achados, registrando por completude)

- **Nenhum IDOR/cross-tenant** em Dúvidas, Loja/Compras, Bot WhatsApp,
  Notificações in-app, Perfil do gestor.
- **`_autenticar_bot()`** (bot WhatsApp) é fail-closed — ausência do secret
  no ambiente nega tudo, não abre a rota.
- **Comprovante via link assinado** — token vinculado a tenant/recurso
  corretos, adulteração bloqueada por assinatura HMAC + filtro duplo
  server-side, expira de verdade (10 min).
- **Cookies `Secure`** *(achado #3 da auditoria 07/23)* — **RESOLVIDO**,
  confirmado nos 3 cookies (`bos_at`, `bos_rt`, `session`), condicionado a
  `FLASK_ENV=production` estar setado no ambiente real (ressalva
  operacional, não de código).
- **Bot de WhatsApp** não tem caminho de criação de agendamento separado —
  reaproveita o mesmo endpoint público (`quick_booking`) com todas as
  validações de conflito/horário/lock. Ressalva: sem visibilidade do
  workflow n8n em si.
- **Ordem `notificar()` × `commit_ou_falhar()`** — correta em todos os
  gatilhos novos revisados (dúvidas, compras, webhook/automação n8n).
- **Cupom multi-item (modo nenhum/todos/selecionar)** — lógica correta hoje
  (a suspeita de inversão não se confirmou), mas **zero coberta por teste**
  — ver débito de testes abaixo.

---

## Débito de testes priorizado (rede de proteção — não são bugs confirmados, são pontos cegos)

Lista completa em `LACUNAS_TESTE.md`. Os itens abaixo já foram
**verificados manualmente e confirmados corretos** pelos testadores desta
rodada, mas continuam sem teste automatizado que prove isso permanentemente
(qualquer regressão futura passaria despercebida):

1. **`_autenticar_bot()`** — maior prioridade: é a única barreira de um
   blueprint que expõe telefone+agenda de clientes.
2. **Token de comprovante** (adulterado/expirado), para os 4 tipos —
   só `duvida_msg` tem teste hoje.
3. **Cupom multi-item, os 3 modos** — maior risco de "dar desconto onde não
   devia" do sistema inteiro, zero coberto.
4. **IDOR em `gestor/compras.py`/`cliente/produtos.py`** — verificado
   manualmente correto, sem teste automatizado.
5. **Os 16 endpoints de notificação** (4 blueprints × 4 rotas) — nunca
   chamados diretamente em teste.
6. **CSAT baixo (nota 1-2) em Dúvidas** disparando notificação — caminho
   central da feature, não coberto.
7. **`gestor/perfil.py` completo** — zero testes.
8. **`evolution.py` mockado** — nenhuma infraestrutura de mock HTTP existe
   na suíte hoje.

Itens 4-7 da lista original de `LACUNAS_TESTE.md` ("divergência de valor" e
"corrida aprovar×rejeitar") **foram fundidos com C1 e C2 acima** — deixaram
de ser lacuna de teste e viraram bug confirmado.

---

## O que exigia decisão do dono antes de corrigir — todas tomadas, FASE 2 concluída

1. **M1 (estorno de plano no cancelamento):** ✅ decidido — cancelamento
   futuro estorna, gestor pode forçar exceção manual, sem prazo de
   antecedência dedicado (usa o `cancelamento_horas_minimas` que já existia
   por tenant). Implementado em `52f2887`.
2. **C1 (divergência de valor na aprovação de compra):** ✅ decidido —
   honrar sempre o valor congelado; se o cupom estourou o limite global
   nesse meio-tempo, honra a venda mesmo assim e só não incrementa o
   contador global (`CupomUso.honrado_fora_limite=True` + warning log).
   Implementado em `e1606b1`.
3. **M3 (e-mail duplicado global):** ✅ confirmado intencional (e-mail é
   único no sistema todo, não por tenant) — documentado em `e74f501`, sem
   mudança de comportamento.

---

## Ordem de correção — executada na FASE 2 (2026-08-02/04)

1. ✅ **C2** — `303a18b`
2. ✅ **C1** — `e1606b1`
3. ✅ **A1** — `d931b04`
4. ✅ **M2** — `eeded14`
5. ✅ **M1** — `52f2887`
6. ✅ **M3** — `e74f501`
7. ⏳ **B1** — nenhuma ação de código necessária, só não reaproveitar esse
   endpoint futuramente. Continua aberto/monitorado, não é bug ativo.
8. ⏳ **Débito de testes** (`LACUNAS_TESTE.md`) — fora do escopo da FASE 2
   (que cobriu só achados de comportamento). Cada correção acima já nasceu
   com seu próprio teste de regressão; o restante da lista original
   (`_autenticar_bot`, token de comprovante, cupom multi-item, etc.)
   continua sem cobertura permanente.

**Regra seguida à risca:** um bloco por vez, um commit por bloco, cada
correção com teste de regressão confirmado falhando sem ela e passando com
ela antes do commit. Detalhes completos (migrations, ação manual
necessária, o que testar antes de liberar) em `RESUMO_FASE2.md`.
