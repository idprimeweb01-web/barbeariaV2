# Relatório de Regras de Negócio — Rodada 1 (módulos novos)

Agente: caca-bugs · Escopo: cupom multi-item, loja/compras de produto,
notificação in-app (dúvidas/compras/whatsapp bot), bot de agendamento via
WhatsApp. Leitura de código apenas — nada foi corrigido ou alterado.

---

## 1. Cupom multi-item (serviços × produtos, 3 modos)

**Arquivos:** `app/utils/cupons.py` (`_subtotal_elegivel`, `calcular_desconto`,
`validar_cupom`), `app/routes/gestor/cupons.py` (`_resolver_modo`, `criar_cupom`,
`editar_cupom`), model `Cupom` (`app/models/__init__.py:755-808`).

### 1.1 — Verificação da suspeita de inversão nenhum↔todos

Lido linha a linha:

- `Cupom.aplica_todos_servicos` / `aplica_todos_produtos` — default `False`
  (models/__init__.py:784-785).
- `_resolver_modo` (gestor/cupons.py:18-45): `modo == 'nenhum'` →
  `(veio=True, aplica_todos=False, ids=[])`; `modo == 'todos'` →
  `(True, True, [])`; `modo == 'selecionar'` → `(True, False, ids_validados)`.
  Consistente com o docstring.
- `_subtotal_elegivel` (cupons.py:46-67): inclui a linha do carrinho se
  `cupom.aplica_todos_servicos` OR `ref_id in servico_ids` (idem produto).
  Serviço e produto são checados em branches `if`/`elif` independentes,
  então um cupom "todos os serviços" + "produto X selecionado" funciona
  como esperado (dimensões independentes, conforme o comentário do módulo).

**Resultado real:** não encontrei a inversão suspeitada — a lógica atual
(criação, edição, formatação `_fmt_cupom`, aplicação) está coerente em
todos os pontos que li, incluindo o template `gestor/cupons.html` (rádios
`nenhum`/`todos`/`selecionar` mapeados 1:1 com o payload). **Severidade: não
é um bug, é uma observação de risco** — não existe NENHUM teste automatizado
cobrindo essa matriz (nenhuma pasta `tests/` no projeto além de bibliotecas
de terceiros na `venv/`). A suspeita do agente irmão (audita-testes) sobre
"uma inversão passaria despercebida por falta de teste" está correta como
afirmação de risco futuro — só não há evidência de que a inversão já
aconteceu. Recomendo cobrir isso com teste antes de qualquer refator nesse
arquivo.

### 1.2 — Desconto pode deixar subtotal negativo?

`calcular_desconto` (cupons.py:94-99): `round(min(valor, subtotal), 2)` —
o desconto nunca excede o subtotal elegível. Em `criar_compra`
(cliente/produtos.py:165) e em `_criar_agendamento_core`
(pub/agendamento.py:286), `valor_total = subtotal_carrinho_inteiro -
valor_desconto`, e como `valor_desconto ≤ subtotal_elegível ≤
subtotal_carrinho_inteiro`, o total nunca fica negativo. **Não é um bug.**

### 1.3 — Cupom aplicado fora da lista de "selecionar"?

Os itens usados para calcular o desconto real (compra de produto, venda de
produto, agendamento) são sempre montados server-side a partir dos objetos
`Produto`/`Servico` reais do carrinho (`cliente/produtos.py:162`,
`vendas.py:94`, `pub/agendamento.py:283`) — o cliente não controla o campo
`valor` desses itens nesses fluxos. **Não é um bug** nesses três pontos.

**Achado à parte (severidade BAIXA/informativo):** o endpoint de preview
`POST /api/v1/cliente/cupons/validar` (`app/routes/cliente/cupons.py:30-34`)
aceita `itens` **vindo direto do corpo da requisição do cliente**,
incluindo o campo `valor` de cada item, sem recálculo server-side — usado
só pra devolver uma prévia de desconto (`valor_desconto`/`valor_final`) que
não encontrei sendo consumida por nenhum fluxo de cobrança real (sem match
em `frontend/src`, só documentação). Hoje é inofensivo porque a cobrança de
verdade é sempre recalculada nos endpoints de criação de pedido/venda/
agendamento. **Risco:** se algum dia essa prévia for reaproveitada como
valor de cobrança (ex: pra montar o PIX sem revalidar), vira uma forma
direta de pagar menos, pois o `valor` de cada item é 100% controlado pelo
cliente. Recomendo não usar esse endpoint pra nada além de exibição de UI.

---

## 2. Loja/compras de produto (solicitação do cliente → aprovação do gestor)

**Arquivos:** `app/routes/cliente/produtos.py` (`criar_compra`),
`app/routes/gestor/compras.py` (`aprovar_compra`, `rejeitar_compra`),
`app/utils/vendas.py` (`criar_venda_core`).

### 2.1 — CRÍTICO: valor congelado na solicitação é descartado na aprovação

**Entrada:** cliente pede um produto de R$ 100 com cupom de 50% de desconto.
`criar_compra` congela `sol.valor_original=100`, `sol.valor_desconto=50`,
`sol.valor_total=50` (cliente/produtos.py:165-172) e gera cobrança PIX
de **R$ 50** (linha 218: `valor=valor_total`). Cliente paga R$ 50 e sobe
comprovante. Antes do gestor aprovar, **o preço do produto muda** (editado
pelo gestor) **ou o cupom expira/atinge o limite/é desativado**.

**Resultado esperado:** a `Venda` criada na aprovação deveria refletir
exatamente o que o cliente pagou (R$ 50), ou a aprovação deveria falhar de
forma auditável/reconciliável, nunca gerar um registro de venda com valor
diferente do que entrou via PIX.

**Resultado real:** `aprovar_compra` (gestor/compras.py:100-108) chama
`criar_venda_core(..., cupom_codigo=sol.cupom_codigo, ...)` passando só o
**código** do cupom, não o desconto congelado. Dentro de `criar_venda_core`
(app/utils/vendas.py):
- linha 70-74: `produto = Produto.query...` e `preco_unitario =
  float(produto.preco)` — **preço atual**, não o preço no momento da
  solicitação (`SolicitacaoCompraItem.preco_unitario`, que existe e nunca é
  lido em `aprovar_compra`).
- linha 96-104: `validar_cupom(...)` é chamado **do zero** — reexecuta
  todas as checagens de expiração/limite/vínculo do cupom.

Consequências:
- Se o **preço do produto mudou**: `venda.valor_total` (usado em relatórios,
  cálculo de comissão do barbeiro em `calcular_comissao_venda`) diverge do
  que o cliente efetivamente pagou via PIX (`sol.valor_total`, congelado).
  Nenhum código em `aprovar_compra` compara os dois valores — `sol.venda_id`
  é setado e segue em frente sem qualquer alerta (compras.py:110-111). Se o
  preço subiu, o caixa "registra" mais dinheiro do que realmente entrou
  (comissão do barbeiro calculada sobre valor não recebido). Se caiu, o
  cliente pagou mais do que a venda registra.
- Se o **cupom expirou/atingiu o limite/foi desativado** entre a
  solicitação e a aprovação: `validar_cupom` levanta `APIError` (cupons.py:
  30-35), e `aprovar_compra` **falha inteiro** — o gestor não consegue
  aprovar um pedido que o cliente já pagou (com desconto) via PIX. Não há
  fallback nem reaproveitamento do `sol.valor_desconto` já congelado; o
  pedido fica travado (só resta rejeitar, sem reembolso automatizado).

**Arquivo/linha:** `app/routes/gestor/compras.py:100-113`;
`app/utils/vendas.py:70-109` (crítico: linha 74 `preco_unitario`, linha 99
`validar_cupom`); valor congelado original em
`app/routes/cliente/produtos.py:159-172` e uso no PIX em linha 209-224.

**Severidade: CRÍTICO** — permite divergência financeira entre o que foi
cobrado via PIX e o que é registrado como venda (inclusive base de cálculo
de comissão), e pode travar a aprovação de pedidos já pagos.

### 2.2 — CRÍTICO: `rejeitar_compra` sem lock — corrida com `aprovar_compra`

**Entrada:** dois requests simultâneos para a mesma `solicitacao_id`
pendente: um `POST /gestor/compras/<id>/aprovar`, outro
`POST /gestor/compras/<id>/rejeitar` (dois gestores, ou duplo clique em
duas abas).

**Resultado esperado:** apenas uma operação deveria vencer; a outra deveria
falhar com `409 "Este pedido já foi processado."`.

**Resultado real:** `aprovar_compra` usa `.with_for_update()`
(compras.py:94) — trava a linha no Postgres (confirmado: `DATABASE_URL`
Postgres em `app/__init__.py:79-83`, sem override de isolation level, logo
READ COMMITTED). `rejeitar_compra` faz um `SELECT` comum, **sem
`with_for_update()`** (compras.py:141-143). Sequência possível:

1. `aprovar_compra` pega o lock (FOR UPDATE) e ainda não comitou.
2. `rejeitar_compra` faz seu `SELECT` comum — em READ COMMITTED, leitura
   simples não é bloqueada por lock de outra transação, então lê
   `status='pendente'` (o commit do aprovar ainda não aconteceu) e passa
   pela checagem em Python (`if sol.status != PENDENTE: raise 409` —
   linha 146-147, não dispara).
3. `rejeitar_compra` monta o `UPDATE` (via `commit_ou_falhar` →
   `db.session.commit()`, `app/utils/db.py:19`) — esse `UPDATE` **não tem
   nenhuma cláusula `WHERE status='pendente'`** (SQLAlchemy ORM gera
   `WHERE id = :id`, sem coluna de versão/otimista lock no model). Esse
   `UPDATE` **bloqueia** esperando o lock do `aprovar_compra` liberar.
4. `aprovar_compra` comita: `Venda` criada de verdade (estoque baixado via
   `criar_venda_core`, comissão registrada), `sol.status='aprovada'`,
   `sol.venda_id` setado. Lock liberado.
5. O `UPDATE` de `rejeitar_compra`, que estava esperando, agora roda **sem
   revalidar nada** e sobrescreve `sol.status='rejeitada'` +
   `sol.motivo_rejeicao` — por cima do registro que acabou de virar
   aprovado. `rejeitar_compra` retorna `200 "Pedido rejeitado."` (sem
   erro!) e dispara notificação ao cliente dizendo "Seu pedido foi
   rejeitado" (compras.py:157-162) — **mesmo o pedido tendo sido aprovado,
   com Venda real criada e estoque já baixado**.

Estado final inconsistente: `SolicitacaoCompraProduto.status='rejeitada'`
mas `sol.venda_id` aponta pra uma `Venda` `CONCLUIDA` real, com
`MovimentacaoEstoque` de saída já lançada e comissão de barbeiro já
registrada — nada disso é revertido (`cancelar_venda_core` nunca é
chamado nesse caminho). Cliente recebe mensagem falsa de rejeição; produto
e dinheiro já saíram do estoque/entraram no caixa.

**Arquivo/linha:** `app/routes/gestor/compras.py:94` (lock em `aprovar`)
vs. `app/routes/gestor/compras.py:141-143` (sem lock em `rejeitar`);
UPDATE incondicional efetivado via `app/utils/db.py:19`.

**Severidade: CRÍTICO** — baixa de estoque e comissão não revertidas,
registro de status contraditório, cliente notificado incorretamente. (Nota
de método: comportamento deduzido da semântica de lock do Postgres em READ
COMMITTED + do UPDATE gerado pelo SQLAlchemy sem coluna de versão; não foi
executado um teste de carga real para confirmar em runtime, mas a lógica do
código sustenta integralmente este cenário.)

---

## 3. Notificação in-app — ordem `notificar()` vs `commit_ou_falhar()`

Regra do projeto: `notificar()` comita a própria transação
(`app/utils/notificacoes.py:104`), então só pode ser chamada **depois** do
`commit_ou_falhar()` do caller — chamá-la antes arrisca notificar um evento
que depois sofre rollback.

Conferido nos três grupos de gatilhos novos desta leva:

- **Dúvidas** (`app/routes/cliente/duvidas.py`, `app/routes/gestor/duvidas.py`,
  `app/routes/super/duvidas.py`) — todas as chamadas a `notificar_responsaveis`
  / `notificar_admins` / `notificar()` direto vêm **depois** do
  `commit_ou_falhar` correspondente (ex.: cliente/duvidas.py:199→202,
  274→277/280, 334→343/345; gestor/duvidas.py:293→297, 442→444;
  super/duvidas.py:276→280/292). **Nenhuma violação encontrada.**
- **Compras** (`app/routes/cliente/produtos.py:188→193`,
  `app/routes/gestor/compras.py:113→123` e `153→157`) — idem, sempre depois
  do commit. **Nenhuma violação encontrada.**
- **WhatsApp bot / automação n8n** (`app/routes/webhook_inbound.py:52→67/73/80`) —
  `commit_ou_falhar` na linha 52, notificações nas linhas 67, 73 e 80,
  todas depois. **Nenhuma violação encontrada.**

**Severidade: não é um bug** — o padrão foi seguido corretamente em todos
os gatilhos novos revisados.

---

## 4. Bot de WhatsApp / agendamento via bot

**Arquivos:** `app/routes/pub/whatsapp.py`, `app/routes/gestor/whatsapp_bot.py`,
`app/routes/pub/agendamento.py`.

`app/routes/pub/whatsapp.py` só expõe dois `GET`s protegidos por
`X-Bot-Secret` (`_autenticar_bot`, linha 24-34): consulta de
barbearia-por-instância e próximo agendamento do cliente. **Não existe
nenhum endpoint de criação de agendamento nesse blueprint** — não há
`POST` nenhum ali, e não há nenhuma referência a "bot" dentro de
`app/routes/pub/agendamento.py`. `app/routes/gestor/whatsapp_bot.py` cuida
só do pareamento da instância Evolution API (status/conectar/desconectar),
não de lógica de agendamento.

Isso indica que o fluxo do bot (n8n) cria o agendamento chamando o **mesmo**
endpoint público usado pelo widget de agendamento do site:
`POST /api/v1/pub/<slug>/agendar` (`quick_booking`, pub/agendamento.py:
622-714), que delega para o núcleo compartilhado `_criar_agendamento_core`
(linhas 170-450). Esse núcleo aplica, sem exceção alguma pro bot:

- checagem de antecedência máxima e "não agendar no passado" (linhas 190-196
  e 233-234);
- `verificar_conflito` — trava o barbeiro/horário contra outro agendamento
  já existente (linha 221-228);
- `gerar_slots` revalidando contra `ConfiguracaoAgenda`/
  `HorarioBloqueado`/pausas — pega o caso do gestor ter fechado o horário
  entre o cliente abrir a tela e confirmar (linhas 236-247);
- rede de segurança final via `IntegrityError` na constraint única
  `uq_ag_barbeiro_slot` para corrida entre requisições paralelas (linhas
  311-318);
- `db.session.commit()` só então, com `notificar_cliente`/`notificar`
  disparados **depois** do commit (linhas 393-436) — mesma ordem correta
  do item 3.

**Severidade: não é um bug** — não encontrei um caminho de criação de
agendamento separado para o bot; ele reaproveita o núcleo público completo,
incluindo lock/revalidação de conflito. **Ressalva de método:** esta
conclusão vale para o que existe no repositório do backend; não tive acesso
ao workflow real do n8n, então não posso confirmar 100% que a automação de
fato chama só esse endpoint e não alguma integração externa fora deste
código. Vale confirmar com quem manteve o workflow n8n se não há nenhuma
chamada direta a nível de banco/admin que pule essa rota.

---

## Resumo por severidade

| # | Cenário | Severidade | Status |
|---|---|---|---|
| 2.1 | Compra: recálculo de preço/cupom na aprovação diverge do PIX pago | **CRÍTICO** | confirmado |
| 2.2 | Compra: corrida aprovar×rejeitar sem lock simétrico | **CRÍTICO** | confirmado |
| 1.3b | Preview de cupom aceita `valor` do cliente sem recálculo | BAIXO (informativo) | hoje inofensivo, risco futuro |
| 1.1 | Suspeita de inversão nenhum↔todos | — | não confirmada; zero cobertura de teste |
| 1.2 | Desconto podendo zerar/negativar subtotal | — | não é um bug |
| 1.3a | Cupom fora da lista "selecionar" nos fluxos reais | — | não é um bug |
| 3 | Ordem notificar() × commit_ou_falhar() (dúvidas/compras/bot) | — | não é um bug |
| 4 | Bot de agendamento pulando validação de horário/conflito | — | não é um bug (reaproveita o núcleo público) |

---

# Rodada 2 — Reconfirmação de 3 achados da AUDITORIA_PRODUCAO.md (07/23) após 35 commits novos

Agente: caca-bugs · Escopo: só os achados #6, #7 e #8 de `AUDITORIA_PRODUCAO.md`
(auditoria feita em 2026-07-23, antes de 35 commits novos entrarem no repo).
Objetivo: confirmar se o código de hoje (2026-08-02, `git log` mais recente
`06ee774`) ainda sustenta cada achado, com arquivo:linha atualizado. Leitura
de código apenas — nada foi corrigido. Não altero nada além de acrescentar
esta seção ao final deste arquivo.

## Achado #6 — Cupom sem limite de uso por cliente

**Status: CONFIRMADO — ainda é verdade hoje.**

`app/utils/cupons.py:9-43` (`validar_cupom`) recebe só
`(barbearia_id, codigo, itens)` — não recebe `cliente_id` como parâmetro
em lugar nenhum da assinatura. As checagens em sequência são: cupom existe
(linha 27-29), `ativo` (30-31), não expirado (32-33) e limite **global**
`quantidade_maxima_usos` vs `quantidade_usos` (linha 34-35). Não há,
em nenhum ponto da função, uma consulta a `CupomUso` filtrando por
`cliente_id` — confirmei que a única leitura de `CupomUso` no módulo é a
criação de linha nova em `registrar_uso_cupom` (linha 125-140), nunca uma
leitura pra bloquear reuso.

Modelos hoje: `Cupom` em `app/models/__init__.py:755-787` — colunas
`quantidade_maxima_usos`/`quantidade_usos` (777-778), sem nenhum campo tipo
`limite_uso_por_cliente`. `CupomUso` em `app/models/__init__.py:816-829` —
guarda `cliente_id` (linha 824, nullable) por uso, exatamente como na
auditoria original; a informação existe no banco e continua não sendo
consultada na validação.

Chequei os 35 commits recentes por relação com este arquivo
(`git log -- app/utils/cupons.py app/models/__init__.py`): o cupom
multi-item (commit `d036448`) mexeu em `_subtotal_elegivel`/modo
todos-nenhum-selecionar, e `904887e` criou o schema de cupom multi-item —
nenhum dos dois tocou a lógica de limite por cliente. Nenhum commit
recente adicionou o campo ou a checagem.

**Severidade: mantida 🟠 ALTO** — nada mudou no cenário (cupom "primeira
visita" continua reaplicável pelo mesmo cliente indefinidamente).

## Achado #7 — Cancelamento não estorna crédito de plano

**Status: CONFIRMADO — ainda é verdade hoje, com linhas atualizadas.**

- `app/routes/cliente/agendamento.py` — função `cancelar_agendamento`,
  linhas 138-206. Único efeito colateral de negócio no cancelamento:
  `decrementar_uso_cupom(ag.cupom_id, ag.barbearia_id)` na linha 177,
  só quando `ag.cupom_id` existe. Nenhuma referência a `ClientePlanoUso`
  no arquivo inteiro (grep vazio).
- `app/routes/gestor/agendamento.py` — função `cancelar_agendamento_gestor`,
  linhas 212-260. Mesmo padrão: `decrementar_uso_cupom` na linha 231,
  sem qualquer toque em `ClientePlanoUso`. (O import de `is_plano` na
  linha 64 é só pra formatar a resposta de listagem, não usado no
  cancelamento.)
- `app/routes/barbeiro/agendamentos.py` — função `cancelar_agendamento`,
  linhas 213-255. `decrementar_uso_cupom` na linha 227, mesma ausência.

Confirmei via `grep -r "ClientePlanoUso" app/` que o model só é referenciado
em `app/routes/gestor/planos.py`, `app/routes/cliente/planos.py`,
`app/routes/pub/agendamento.py` (onde o crédito é **consumido** na criação
do agendamento) e `app/models/__init__.py` (definição) — nunca nos três
arquivos de cancelamento. O crédito mensal de plano continua sendo
consumido no momento do agendamento e nunca devolvido no cancelamento,
por nenhum dos três atores (cliente, gestor, barbeiro).

Nenhum dos 35 commits recentes tocou esse comportamento — é decisão de
produto pendente, como já registrado na auditoria original (estornar
sempre? só com antecedência mínima, igual à regra de cancelamento com
cupom?). Não sugiro a correção aqui, só confirmo o estado.

**Severidade: mantida 🟡 MÉDIO.**

## Achado #8 — Corrida de double-booking no agendamento manual do gestor cai em erro genérico

**Status: CONFIRMADO — ainda é verdade hoje, com linhas atualizadas.**

`app/routes/gestor/agendamento.py`, função `agendamento_manual` (começa na
linha 396): `db.session.add(ag)` na linha 460, `db.session.flush()` na
linha 461, **sem** try/except ao redor — se a constraint única
`uq_ag_barbeiro_slot` disparar aqui, a `IntegrityError` sobe sem tratamento
específico.

Comparei com `app/routes/pub/agendamento.py:310-318`, que continua com o
padrão correto:
```python
db.session.add(ag)
try:
    db.session.flush()
except IntegrityError:
    db.session.rollback()
    raise APIError('Este horário acabou de ser reservado. Escolha outro.', 409)
```
Esse padrão não foi replicado em `gestor/agendamento.py`.

Investiguei especificamente o commit `79ee5d7` ("fix: checkup de produção —
double-booking real...", 24/07), porque o nome sugeria que poderia ter
mexido nisso — o `git show 79ee5d7 -- app/routes/gestor/agendamento.py`
confirma que esse commit **adicionou notificações e auditoria** em volta de
`agendamento_manual` (blocos `notificar(...)` após o `commit_ou_falhar`,
diff nas linhas ~468-479) mas não tocou nas linhas 460-461 nem adicionou
try/except ali. O problema real de double-booking que esse commit corrigiu
foi outro (índices únicos `uq_ag_barbeiro_slot`/`uq_usuario_email_staff`
ausentes do banco por bug de migration — migration `6c106d8fec79`), não a
falta de tratamento de `IntegrityError` no fluxo manual do gestor. A
proteção de banco (índice único) continua ativa e é o que realmente evita
o double-booking; o que falta é só a mensagem amigável — mesma leitura da
auditoria original.

**Severidade: mantida 🟡 MÉDIO** (não é falha de integridade, é UX pior
numa corrida rara — dois gestores/telas criando manualmente o mesmo
horário ao mesmo tempo).

## Resumo Rodada 2

| Achado original | Status hoje | Severidade |
|---|---|---|
| #6 — Cupom sem limite por cliente | **CONFIRMADO** (`app/utils/cupons.py:9-43`, `app/models/__init__.py:755-787,816-829`) | 🟠 ALTO (mantida) |
| #7 — Cancelamento não estorna plano | **CONFIRMADO** (`cliente/agendamento.py:138-206`, `gestor/agendamento.py:212-260`, `barbeiro/agendamentos.py:213-255`) | 🟡 MÉDIO (mantida) |
| #8 — Double-booking manual do gestor sem 409 amigável | **CONFIRMADO** (`gestor/agendamento.py:396,460-461` vs `pub/agendamento.py:310-318`) | 🟡 MÉDIO (mantida) |

Nenhum dos 35 commits recentes entre a auditoria original (07/23) e hoje
(08/02) resolveu ou mudou de forma nenhum dos três achados — todos
continuam com a mesma severidade e o mesmo comportamento descrito
originalmente, só com números de linha atualizados por causa de código
novo inserido acima/entre esses trechos.
