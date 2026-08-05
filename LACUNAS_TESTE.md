# LACUNAS_TESTE.md — Rodada 1 (módulos novos, 35 commits recentes)

Auditoria adversarial da suíte de testes existente, restrita aos 6 módulos
listados pelo coordenador. Não escrevi nem corrigi nada — só aponto buracos.

Suíte lida por completo antes de concluir qualquer coisa:
`teste_duvidas_cliente.py`, `teste_frente1_completa.py`,
`teste_v1_2_pdv_vip_reset.py`, `teste_concorrencia.py`.

## Veredito por módulo (visão geral)

| # | Módulo | Cobertura hoje | Nota |
|---|--------|-----------------|------|
| 1 | Dúvidas do Cliente | **Boa** — `teste_duvidas_cliente.py` (35KB) | tem buracos pontuais, não zero |
| 2 | Loja/compras (cliente + gestor) | **ZERO** | nenhum teste toca `cliente/produtos.py` ou `gestor/compras.py` |
| 3 | Bot WhatsApp | **ZERO** | nenhum teste toca `whatsapp_bot.py`, `pub/whatsapp.py` ou `evolution.py` |
| 4 | Cupom multi-serviço/produto (modo todos/nenhum/selecionar) | **ZERO** | nenhum teste toca `cupons.py` (gestor ou cliente) nem `app/utils/cupons.py` |
| 5 | Notificação in-app (`notificar()` + 4 blueprints) | **Parcial/indireta** | só exercitada como efeito colateral de outros fluxos; os endpoints dos blueprints em si (listar/contador/marcar lida/marcar todas) nunca são chamados |
| 6 | Perfil do gestor + comprovante via link assinado | **ZERO** | nenhum teste toca `gestor/perfil.py`; `comprovante.py`/`comprovante_link.py` só testado para o tipo `duvida_msg`, nunca para `compra`/`plano`/`agendamento` |

Confirmado por grep nos 4 scripts de teste: zero ocorrências de
`cliente/produtos`, `gestor/compras`, `whatsapp`, `gerar_link_comprovante`
fora de `duvidas.py`, `CupomServico`/`CupomProduto`/`aplica_todos`, ou
`/api/v1/gestor/perfil`.

---

## 1. Dúvidas do Cliente — boa cobertura, mas com buracos reais

`teste_duvidas_cliente.py` já prova IDOR entre barbearias (`testar_isolamento`:
gestor de outro tenant vendo dúvida alheia → 404) e entre clientes da MESMA
barbearia. Isso é o padrão que falta nos outros 5 módulos. Mesmo assim:

- **CSAT baixo nunca dispara notificação nos testes.** O código
  (`cliente/duvidas.py::avaliar_satisfacao`) chama `notificar_admins()` ou
  `notificar_responsaveis()` quando `nota <= 2`, mas `testar_csat()` só usa
  nota 5 e nota 6 (fora do range) e nota 3 (duplicata) — o caminho de alerta
  de qualidade ruim (o motivo de a feature existir) nunca é exercitado.
  **Teste que falta**: avaliar com nota 1 ou 2, checar que gestor/admin
  recebeu notificação com o texto certo.
- **`barbeiro_id` de outro tenant na abertura do ticket nunca é testado.**
  `criar_duvida()` faz `Barbeiro.query.filter_by(id=..., barbearia_id=g.barbearia_id, ...)`
  e, se não encontrar, ignora silenciosamente (cai no direcionamento padrão).
  Isso é o comportamento correto de isolamento, mas **não há teste que prove
  isso** — um cliente mandando o `barbeiro_id` de um barbeiro de OUTRA
  barbearia deveria continuar funcionando (ticket vai pra fila do gestor),
  não vazar nem quebrar. Sem esse teste, uma regressão que trocasse o filtro
  por um `Barbeiro.query.get(id)` sem tenant passaria despercebida — seria
  um IDOR silencioso (o ticket ficaria "direcionado" a um funcionário de
  outra empresa).
- **Rate limit nunca é exercitado de verdade.** O script sobrescreve
  `RL_DUVIDA=1000 per minute` via env ANTES de criar a app — ou seja, o
  limite de produção (`5 per minute`) nunca roda em nenhum teste. Se alguém
  quebrar o wiring do decorator `@limiter.limit(...)` (nome de env errado,
  decorator na ordem errada em relação a `@cliente_required`), nenhum teste
  acusa.
- **Webhooks nunca são verificados.** `disparar_webhook(...)` é chamado em
  4 pontos (`DUVIDA_CRIADA`, `DUVIDA_URGENTE`, `DUVIDA_NOVA_MENSAGEM` × 3
  variações) mas nenhum teste inspeciona o payload ou confirma que o evento
  foi enfileirado/disparado — só os efeitos em banco/notificação são
  checados. Payload errado ou evento trocado não seria pego.
- **Limite de 3 imagens só é testado no `responder`, não na abertura.**
  `_abrir(..., imagens_bytes=[4 imagens])` nunca é chamado — só
  `_responder(...)`. Mesmo núcleo (`criar_mensagem`), risco baixo, mas é
  caminho de código não coberto.
- **`super_required` bloqueando não-admin nas rotas de `super/duvidas.py`
  não é testado neste arquivo** (pode estar coberto genericamente em outro
  lugar do projeto, mas não localmente aqui) — vale confirmar que um gestor
  comum batendo em `/api/v1/super/duvidas` toma 401/403, não 200.

**Prioridade dos gaps deste módulo**: CSAT baixo → notificação (médio-alto,
é a razão de negócio da feature) > `barbeiro_id` cross-tenant (médio,
silencioso) > webhooks/rate-limit (baixo-médio, infraestrutura).

---

## 2. Loja / compras de produto — ZERO teste, e há lógica financeira sensível aqui

Fluxo: cliente monta carrinho (`POST /api/v1/cliente/compras`) → opcionalmente
aplica cupom e paga PIX → sobe comprovante → gestor aprova
(`POST /api/v1/gestor/compras/<id>/aprovar`) → **só na aprovação** vira uma
`Venda` de verdade via `criar_venda_core` (baixa de estoque, comissão, e
**só aqui** o cupom é de fato consumido — `incrementar_uso_cupom` +
`registrar_uso_cupom`).

Isso é elegante mas cria uma janela real entre "cliente vê o valor" e "valor
que efetivamente vira venda", e ela está 100% sem teste.

### O que falta, em ordem de criticidade

1. **[CRÍTICO] Preço/desconto mostrado ao cliente pode divergir do valor
   final da venda, e nada garante consistência.** `criar_compra()` calcula
   `subtotal`/`valor_desconto`/`valor_total` a partir do preço ATUAL do
   produto e do estado ATUAL do cupom, e grava isso em
   `SolicitacaoCompraProduto`. O PIX copia-e-cola gerado usa esse
   `valor_total`. Só que `aprovar_compra()` **recalcula tudo de novo do
   zero** (`criar_venda_core` chama `validar_cupom` de novo, com o preço do
   produto no momento da APROVAÇÃO). Se o gestor mudar o preço do produto,
   ou o cupom expirar/esgotar, ou desativar o cupom **entre o pedido e a
   aprovação**, o cliente pode ter pago R$ X via PIX e a `Venda` registrada
   ficar com um valor diferente — sem nenhum reconciliação ou alerta.
   **Teste que falta**: criar pedido com cupom válido, alterar preço do
   produto (ou desativar/expirar o cupom) antes de aprovar, aprovar, e
   verificar que `venda.valor_total` diverge de `sol.valor_total` — hoje
   ninguém sabe se isso acontece silenciosamente ou se há alguma trava.
2. **[CRÍTICO] Cupom aplicado duas vezes / esgotado entre duas solicitações
   concorrentes nunca é testado.** `validar_cupom()` (chamado na
   solicitação, só para preview) NÃO decrementa/trava nada — dois clientes
   (ou o mesmo, duas vezes) podem criar `SolicitacaoCompraProduto` pendentes
   usando o mesmo cupom de uso único. O consumo de fato só acontece em
   `aprovar_compra` → `incrementar_uso_cupom` (UPDATE atômico). Não há
   teste comprovando que: (a) a 2ª aprovação de fato falha com "Cupom
   esgotado"; (b) quando falha, a `Venda`/`VendaItem`/movimentação de
   estoque já criadas são revertidas via rollback e a `SolicitacaoCompraProduto`
   **continua pendente** (não fica travada em estado intermediário); (c) o
   estoque não fica descontado sem uma venda válida.
3. **[CRÍTICO] Nenhum teste de IDOR entre barbearias neste módulo.**
   Precisa provar: gestor de tenant B não consegue `GET /api/v1/gestor/compras`,
   `.../aprovar` ou `.../rejeitar` de uma solicitação do tenant A (código já
   filtra por `barbearia_id=g.barbearia_id`, mas isso nunca foi exercitado
   por teste); cliente de tenant B não consegue ver/enviar comprovante para
   `solicitacao_id` do tenant A via `POST /api/v1/cliente/compras/<id>/comprovante`.
4. **[ALTO] Corrida aprovar × rejeitar não é protegida nem testada.**
   `aprovar_compra` usa `.with_for_update()` na `SolicitacaoCompraProduto`;
   `rejeitar_compra` **não usa lock nenhum** — só um
   `filter_by(...).first()` simples. Duas requisições simultâneas (uma
   aprovando, outra rejeitando o mesmo pedido) podem ambas passar do check
   `status != PENDENTE` antes de qualquer commit. Nem o código garante
   serialização aqui, nem existe teste (nem manual como
   `teste_concorrencia.py`, que só cobre double-booking de agendamento e
   dupla aprovação de plano) cobrindo este caso.
5. **[ALTO] PIX: valor vindo do backend nunca é testado explicitamente
   neste módulo.** O código já faz certo — `valor_total` usado no
   `gerar_pix_copia_cola` vem do servidor, nunca de `request.json` — mas
   não há teste que tente mandar um `valor_total` forjado no payload de
   `POST /api/v1/cliente/compras` (o endpoint nem aceita esse campo,
   então na prática está seguro, mas isso é inferência de leitura de
   código, não algo comprovado por teste).
6. **[MÉDIO] Validação de estoque insuficiente, produto inativo/de outra
   barbearia, quantidade ≤ 0, `metodo_pagamento` inválido, PIX indisponível
   sem `feature pix_integrado`/sem `chave_pix` da barbearia — nenhum caso
   de erro é testado.**
7. **[MÉDIO] `upload_comprovante_compra`**: mimetype inválido, magic bytes
   falsos, arquivo > 5MB, reenvio de comprovante para pedido já
   aprovado/rejeitado (`status != PENDENTE` → deveria dar 422) — zero
   testes, mesmo já existindo um padrão de teste equivalente pronto em
   `teste_duvidas_cliente.py` (magic bytes falsos) que dava pra copiar.
8. **[BAIXO] Notificações do módulo (`compra_solicitada` ao gestor,
   `compra_aprovada`/`compra_rejeitada` ao cliente) nunca verificadas.**

---

## 3. Bot de WhatsApp — ZERO teste, e é o módulo com o risco de segurança mais explícito do lote

O próprio código documenta a ameaça em `app/routes/pub/whatsapp.py`: sem o
header `X-Bot-Secret` correto, essas rotas "pub" virariam um jeito de
qualquer um consultar a agenda de qualquer cliente sabendo só o telefone —
e cita `AUDITORIA_PRODUCAO.md`. Isso NUNCA foi testado.

### O que falta, em ordem de criticidade

1. **[CRÍTICO] `_autenticar_bot()` — a barreira de segurança inteira do
   módulo — nunca é exercitada por teste.** Faltam:
   - Requisição sem header `X-Bot-Secret` → deve dar 404 (não 401/403,
     por design, pra não confirmar que a rota existe).
   - Header com valor errado → 404.
   - `N8N_BOT_API_SECRET` não configurado no ambiente (string vazia) → deve
     **negar tudo**, inclusive uma tentativa com string vazia como header
     (`hmac.compare_digest('', '')` sozinho retornaria `True`; o código tem
     `not segredo_esperado` pra curto-circuitar antes — isso é exatamente o
     tipo de lógica que se quebra silenciosamente numa refatoração e só um
     teste pega).
   - Header correto → 200 e dados corretos.
   Sem isso, é impossível saber se essa proteção funciona hoje ou já
   regrediu.
2. **[ALTO] `GET /api/v1/pub/barbearia-por-instancia` sem teste nenhum**:
   instância inexistente → 404; barbearia inativa com aquela instância →
   deve tratar como não encontrada (`ativo=True` no filtro, mas nunca
   testado); telefone informado que bate com cliente cadastrado → retorna
   nome certo; telefone que não bate → `{'existe': False}`; telefone
   malformado → não deve quebrar a resposta principal (código ignora erro
   de normalização silenciosamente — comportamento não verificado).
3. **[ALTO] `GET /api/v1/pub/<slug>/clientes/<telefone>/proximo-agendamento`
   sem teste nenhum**: cliente com agendamento futuro `status=agendado`
   aparece; cliente sem agendamento retorna `tem_agendamento: False`;
   **IDOR entre barbearias via slug + telefone** — um telefone que é
   cliente da barbearia A não deve "vazar" dados se alguém consultar com o
   `slug` da barbearia B (o filtro já é `barbearia_id=barbearia.id` do slug
   pedido, então parece protegido, mas isso nunca foi comprovado); status
   diferente de `agendado` (concluído, cancelado) não deve aparecer como
   "próximo".
4. **[MÉDIO] `app/utils/evolution.py` e `gestor/whatsapp_bot.py` inteiros
   sem teste** (nem mockado): `EvolutionNaoConfigurado` quando faltam
   `EVOLUTION_API_URL`/`EVOLUTION_API_KEY` → deveria dar 503 em
   `status()`/`conectar()`/`desconectar()`/`excluir()`; falha de rede/HTTP
   da Evolution API → 502; fluxo feliz de `conectar()` criando instância +
   retornando QR code; `desconectar()` sem instância configurada → 422;
   `excluir()` limpando `whatsapp_instance_id` no banco. Como são chamadas
   HTTP externas, o teste precisa mockar `requests.post/get/delete` — não
   existe nenhuma infraestrutura de mock pra isso na suíte atual (os
   scripts existentes só testam via `test_client()` interno, sem
   `unittest.mock`).
5. **[MÉDIO] Rate limit destas rotas públicas (`60/min`, `30/min`) nunca
   testado** — mesma lacuna do módulo de Dúvidas.

---

## 4. Cupom multi-serviço/produto (modo todos/nenhum/selecionar) — ZERO teste

A mudança mais recente e mais arriscada no model `Cupom` (comentário no
código já avisa: "Independentes um do outro... quando False e não há
nenhuma linha em CupomServico/CupomProduto pra essa dimensão, o cupom não
vale pra NADA daquele tipo"). Isso é uma regra fácil de inverter por
engano (`nenhum` vs `todos` trocados) e não há UM teste que prove o
comportamento dos 3 modos.

### O que falta, em ordem de criticidade

1. **[CRÍTICO] Os 3 modos (`nenhum`/`todos`/`selecionar`) nunca são testados
   nem para serviço nem para produto**, nem isoladamente nem a combinação
   (ex.: cupom com `servicos_modo=todos` + `produtos_modo=selecionar` só
   para 1 produto específico — o caso que o comentário do código usa como
   exemplo). Sem teste:
   - Cupom `nenhum`/`nenhum` (o default) deve rejeitar QUALQUER item do
     carrinho — nunca verificado. Se `_subtotal_elegivel` tivesse um bug
     que tratasse "sem restrição" como "vale pra tudo" em vez de "não vale
     pra nada", nenhum teste pegaria — e essa é exatamente a inversão de
     lógica mais perigosa possível num sistema de desconto (dá desconto
     onde não devia).
   - Cupom `selecionar` com uma lista de `servico_ids`/`produto_ids` deve
     valer só pra esses itens — outro item do carrinho não pode "vazar"
     desconto.
   - **`quantidade_maxima_usos` e não-uso-duplo nunca são testados no
     nível HTTP.** Existe a trava atômica em `incrementar_uso_cupom` (SQL
     `UPDATE ... WHERE quantidade_usos < quantidade_maxima_usos`), mas
     nenhum teste comprova que: (a) o 2º uso de um cupom `quantidade_maxima_usos=1`
     falha; (b) `CupomUso` é gravado corretamente a cada aplicação; (c)
     `quantidade_usos` no cupom bate com a contagem real de `CupomUso`.
   - Cupom expirado (`data_expiracao` no passado) → rejeitado — não
     testado.
   - Cupom `ativo=False` → rejeitado — não testado.
   - Cupom percentual > 100% → deve ser rejeitado na criação (constraint de
     banco + validação de rota) — não testado.
2. **[CRÍTICO] IDOR: `servico_ids`/`produto_ids` de outra barbearia num
   payload de criar/editar cupom.** `_resolver_modo` filtra
   `model.id.in_(ids), model.barbearia_id == barbearia_id` e levanta 404
   se algum id "faltar" — o código parece proteger corretamente, mas **não
   existe nenhum teste** provando que um gestor não consegue vincular um
   serviço/produto de outra barbearia ao próprio cupom.
3. **[ALTO] Código de cupom duplicado dentro da mesma barbearia** (`409`) e
   **o mesmo código em barbearias diferentes** (deveria ser permitido,
   já que o `UniqueConstraint` é `(barbearia_id, codigo)`) — nenhum teste.
4. **[ALTO] `PATCH /cupons/<id>` trocando de `selecionar` pra `nenhum`/`todos`
   deve APAGAR as linhas antigas de `CupomServico`/`CupomProduto`** (o
   código faz `CupomServico.query.filter_by(cupom_id=c.id).delete()` antes
   de reinserir) — comportamento crítico pra não deixar "lixo" de
   vinculação antiga valendo, e não testado.
5. **[MÉDIO] `GET /cupons/<id>/uso` (relatório de uso)** — nunca testado;
   é o mesmo tipo de rota que noutros módulos já causou bug de N+1 ou de
   soma errada (`valor_total_descontado`).
6. **[MÉDIO] `feature_required('cupons')` desligada bloqueando as rotas —
   não testado neste módulo** (só é testado no módulo de Dúvidas via
   `feature_required('duvidas_cliente')`; o padrão existe mas cada feature
   flag precisa do próprio teste, porque o nome da flag é uma string solta
   passível de typo).

---

## 5. Notificação in-app — helper testado por acidente, blueprints nunca testados diretamente

`notificar()` (o helper central) e a tabela `Notificacao` são usados e
verificados indiretamente em `teste_duvidas_cliente.py` (checa
`GET /api/v1/cliente/notificacoes` → `total >= 1`) e em
`teste_v1_2_pdv_vip_reset.py` (notificação de reset de senha). Isso prova
que `notificar()` grava algo, mas é uma **asserção fraca**: `total >= 1`
não confirma título/corpo/link/tipo corretos, nem que a notificação foi
endereçada ao usuário certo.

### O que falta, em ordem de criticidade

1. **[ALTO] Os 4 blueprints de notificação (`gestor`, `super`, `cliente`,
   `barbeiro`) nunca são chamados diretamente nos testes** — nenhum teste
   bate em `GET /notificacoes`, `GET /notificacoes/contador`,
   `PATCH /notificacoes/<id>/lida`, `POST /notificacoes/marcar-todas-lidas`
   pra nenhum dos 4 perfis. São 16 endpoints, código idêntico copiado 4x
   (o próprio código admite isso: "espelha exatamente..."), e cópia colada
   é exatamente onde um `barbearia_id` esquecido ou um filtro trocado passa
   despercebido.
2. **[ALTO] IDOR em `marcar_lida`: nunca testado.** Cada blueprint filtra
   por `id=notif_id` + `usuario_id=g.user_id` (+ `barbearia_id` pros perfis
   tenant-scoped) — o `usuario_id` já isola por si só, mas ninguém testou
   um usuário tentando marcar como lida uma notificação de outro usuário
   (mesma barbearia ou não) e confirmando 404.
3. **[ALTO] `super/notificacoes.py` filtra SÓ por `usuario_id`, sem
   `barbearia_id`** (comentário no código explica: admin não tem
   `barbearia_id` fixo) — isso é intencional, mas nunca foi testado que
   um super consegue ver notificações originadas de QUALQUER barbearia
   endereçadas a ele (ex.: `notificar_admins` de Dúvidas), e que
   `marcar_todas_lidas` do super não afeta notificações de outro admin.
4. **[MÉDIO] Paginação/filtro `apenas_nao_lidas=1`, `page`/`per_page`
   inválidos (`page=abc` → 422) — nunca testado em nenhum dos 4
   blueprints.**
5. **[MÉDIO] `marcar_todas_lidas` retornando a contagem certa de
   `atualizados`, e não afetando notificações já lidas ou de outro
   usuário/canal (`canal='email'` não deveria ser "marcado como lida" já
   que nem é lida em app) — não testado.**
6. **[BAIXO] Canal `email`/`web_push` (stubs) — `notif.enviada` permanece
   `False` de propósito; nenhum teste confirma que os stubs não quebram o
   fluxo principal quando chamados** (hoje só canal `in_app` é exercitado
   em qualquer teste do projeto).
7. **[BAIXO] `notificar()` nunca propaga exceção mesmo se o `db.session.add`
   falhar** (`try/except Exception: rollback + log`, nunca re-raise) — essa
   é uma decisão de design (falha de notificação não derruba a operação
   principal), mas não existe teste que force um erro dentro de
   `notificar()` (ex.: `usuario_id` inexistente/`barbearia_id` inválido) e
   confirme que a operação chamadora (ex.: `criar_duvida`) ainda retorna
   201 normalmente.

---

## 6. Perfil do gestor + comprovante via link assinado — ZERO teste, maior risco estrutural do lote

`gestor/perfil.py` tem zero testes — nem os casos felizes. Mas o achado
mais sério deste módulo é em `comprovante.py`/`comprovante_link.py`: é uma
rota **pública, sem decorator de autenticação**, cujo único controle de
acesso é a assinatura do token. Ela é reutilizada por 4 tipos de recurso
(`agendamento`, `plano`, `compra`, `duvida_msg`), e só o tipo `duvida_msg`
tem QUALQUER teste (dentro de `teste_duvidas_cliente.py`, e mesmo esse é
raso — só confirma `200` + `content_type` começando com `image/`).

### O que falta, em ordem de criticidade

1. **[CRÍTICO] Nenhum teste dos tipos `compra`, `plano` e `agendamento` em
   `/comprovante/<token>`.** `compra` está diretamente no escopo desta
   rodada (é o comprovante do módulo de loja). Precisa: gerar link via
   `gestor/compras.py::_fmt_solicitacao` (chamado com `s.comprovante_url`
   truthy), acessar sem sessão nenhuma (rota é pública de propósito) e
   confirmar que retorna a imagem certa.
2. **[CRÍTICO] Token adulterado nunca é testado.** O design depende 100%
   de `itsdangerous` rejeitar qualquer payload cujo `tipo`/`ref_id`/
   `barbearia_id` tenha sido alterado após a assinatura. Isso NUNCA foi
   testado ativamente: pegar um token válido, tentar trocar o `ref_id`
   (ex.: decodificar base64 e reencriptar manualmente, ou simplesmente
   testar com um token de outro registro concatenado/truncado) e confirmar
   410. Sem esse teste, uma futura migração de `SECRET_KEY` handling, de
   `itsdangerous` pra outra lib, ou uma mudança no formato do payload pode
   quebrar silenciosamente a proteção sem nenhum teste vermelho.
3. **[ALTO] Expiração do token (10 min) nunca é testada.** `LINK_TTL_SEGUNDOS
   = 600` é o único motivo do link não ser permanente — precisa de um teste
   que force `max_age` a estourar (ex.: gerar o token, mockar/avançar o
   relógio, ou chamar `decodificar_token_comprovante` diretamente com um
   token gerado por um serializer configurado com salt/segredo igual mas
   timestamp manipulado) e confirmar `410`.
4. **[ALTO] Token de um tipo pedindo registro de outro tipo, ou `ref_id`
   que existe mas pertence a OUTRA barbearia (mesmo com token
   assinado corretamente, se o payload foi gerado com `barbearia_id`
   errado por algum bug de chamada) — os handlers de busca já filtram por
   `barbearia_id=payload['barbearia_id']`, então isso deveria dar 404, mas
   nunca foi comprovado por teste.** Isso é o teste de IDOR mais direto
   que falta no módulo 6.
5. **[MÉDIO] `gestor/perfil.py` sem nenhum teste**, incluindo caminhos de
   erro que já existem no código e são fáceis de quebrar numa refatoração:
   - `trocar_senha`: senha atual errada → 401; senha nova < 8 caracteres →
     422; fluxo feliz muda o hash e (não testado) permite login com a nova
     senha e bloqueia a antiga.
   - `editar_conta`: e-mail duplicado → 409. **A checagem de duplicidade é
     GLOBAL (`Usuario.query.filter(Usuario.email == email, ...)`), não
     escopada por barbearia** — ou seja, um gestor da barbearia A que tenta
     trocar seu e-mail para um e-mail já usado por alguém da barbearia B
     recebe 409 "já existe uma conta com este e-mail", o que **confirma a
     existência de uma conta em outra barbearia** (enumeração cross-tenant
     via resposta HTTP). Pode ser intencional (login parece ser global por
     e-mail no sistema), mas isso nunca foi documentado nem testado — vale
     pelo menos um teste que capture o comportamento atual explicitamente,
     pra não virar regressão "silenciosa" se alguém decidir que devia ser
     escopado por tenant.
   - `editar_barbearia`: horário inválido (`"25:99"`) → 422; campos de
     endereço sendo limpos com string vazia (`'' → None`) — comportamento
     existe no código, não testado.
   - `upload_logo`: sem arquivo → 400; tipo de imagem inválido
     (`validar_upload_imagem`) — não testado neste módulo (só uma função
     compartilhada, provavelmente testada em outro lugar, mas não aqui).

---

## Resumo — lista priorizada de testes que faltam escrever (mais crítico primeiro)

1. **`_autenticar_bot()` (whatsapp)** — sem secret / secret errado / secret
   vazio no ambiente / secret certo. É a única barreira de segurança de
   todo um blueprint que expõe telefone+agenda de clientes.
2. **Token de comprovante adulterado + expirado**, para os 4 tipos
   (`agendamento`, `plano`, `compra`, `duvida_msg`) — hoje só `duvida_msg`
   tem um teste raso de caminho feliz.
3. **Cupom: os 3 modos (`nenhum`/`todos`/`selecionar`) pra serviço E
   produto, isolados e combinados** — maior risco de "dar desconto onde
   não devia" do sistema, zero coberto.
4. **Cupom: não-uso-duplo / esgotamento no fluxo real de aprovação de
   compra** (2 solicitações pendentes com o mesmo cupom de uso único,
   1 aprova, a outra deve falhar e permanecer pendente sem efeitos
   colaterais no estoque).
5. **IDOR entre barbearias em `gestor/compras.py`** (aprovar/rejeitar/listar
   de tenant alheio) e em `cliente/produtos.py` (comprovante de tenant
   alheio).
6. **Divergência de valor entre solicitação e aprovação de compra**
   (preço/cupom mudam no meio do caminho) — hoje é um comportamento
   completamente não observado, pode ser bug real de cobrança.
7. **Corrida aprovar × rejeitar em `gestor/compras.py`** — `rejeitar_compra`
   não usa `with_for_update()`, diferente de `aprovar_compra`.
8. **Os 16 endpoints de notificação (4 blueprints × 4 rotas)** — nunca
   chamados diretamente; IDOR em `marcar_lida` nunca testado.
9. **CSAT baixo (nota 1-2) disparando notificação em Dúvidas** — caminho
   de negócio central do CSAT, não coberto.
10. **`gestor/perfil.py` completo** — zero testes, incluindo o achado de
    enumeração de e-mail cross-tenant via 409.
11. **`evolution.py` mockado** (criar/status/desconectar/excluir instância,
    incluindo `EvolutionNaoConfigurado` → 503 e falha HTTP → 502).
12. **Casos de erro em `cliente/produtos.py`**: estoque insuficiente,
    produto de outra barbearia/inativo, PIX sem feature/sem chave PIX,
    comprovante com magic bytes falsos ou reenviado após pedido já
    processado.
13. **`barbeiro_id` de outro tenant na abertura de dúvida** — comportamento
    correto existe no código, mas é silencioso e não comprovado por teste.

---

## Observação sobre método

Os itens acima foram derivados de leitura completa do código de rota de
cada um dos 6 módulos (não só grep) e comparados linha a linha contra os 4
scripts de teste existentes. Onde a suíte já cobre bem (Dúvidas), apontei
os buracos residuais em vez de reafirmar o que já está OK — o pedido era
achar os buracos da rede, não recontar os nós que já existem.
