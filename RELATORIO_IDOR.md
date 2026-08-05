# Relatório de Teste Adversarial de Controle de Acesso (IDOR) — Rodada 1

Agente: caca-falhas. Metodologia: revisão estática de código (leitura linha a
linha de toda rota do escopo desta rodada), rastreando a origem de todo `id`
usado em query contra `g.barbearia_id`/`g.user_id` do usuário autenticado.
`g.barbearia_id`/`g.perfil`/`g.user_id` são resolvidos em
`app/context.py:47-49` **a partir do registro `Usuario` no banco** (nunca de
parâmetro de URL, header ou body) — essa é a raiz de confiança usada em toda
a análise abaixo.

Escopo: módulo Dúvidas do Cliente, Loja/Compras, Bot WhatsApp, Notificações
in-app, Perfil do gestor + Comprovante via link assinado, e verificação do
item de cookies `Secure` do AUDITORIA_PRODUCAO.md achado #3.

---

## 1. Módulo "Dúvidas do Cliente" (tickets/suporte)

### 1.1 Cliente — `app/routes/cliente/duvidas.py`
Toda rota (`GET /duvidas`, `GET /duvidas/<id>`, `POST /duvidas`,
`POST /duvidas/<id>/mensagens`, `PUT /duvidas/<id>/fechar`,
`POST /duvidas/<id>/satisfacao`) resolve o ticket via `_duvida_ou_404`
(linhas 35-41), que filtra por `barbearia_id=g.barbearia_id AND
cliente_id=cli.id`, e `cli` vem de `_cliente_ou_404` (linhas 28-32), também
filtrado por `usuario_id=g.user_id`. **Correto** — cliente A não consegue
trocar o id na URL e ver ticket de cliente B, nem de outra barbearia.

`GET /duvidas/funcionarios` (linha 124) filtra `Barbeiro` por
`barbearia_id=g.barbearia_id`. **Correto**.

### 1.2 Gestor/Barbeiro — `app/routes/gestor/duvidas.py`
`_query_tenant_ou_barbeiro()` (linhas 52-56) sempre filtra por
`barbearia_id=g.barbearia_id`; se `g.perfil == 'barbeiro'`, adiciona filtro
extra `direcionado_para_usuario_id == g.user_id`. Todas as rotas de detalhe/
ação (`_get_duvida_ou_404`, linha 59) passam por essa função. **Correto** —
testei mentalmente os 3 cenários do escopo:
- Gestor da barbearia B tentando abrir ticket da barbearia A pelo id: bloqueado
  pelo filtro `barbearia_id=g.barbearia_id` (retorna 404, não vaza dado).
- Barbeiro tentando abrir ticket de outro barbeiro da mesma barbearia
  (direcionado a colega, não a ele): bloqueado pelo filtro
  `direcionado_para_usuario_id == g.user_id` — barbeiro só vê o que foi
  direcionado a ele mesmo. **Correto**.
- `exportar_excel` (linha 450) usa a mesma `_query_filtrada` → mesmo escopo.
  **Correto**.

### 1.3 Admin/Super — `app/routes/super/duvidas.py`
`_get_duvida_ou_404` (linha 53-57) usa `db.session.get(ClienteDuvida,
duvida_id)` **sem** filtro de `barbearia_id` — isso é cross-tenant por
design (confirmado no docstring do arquivo, linhas 1-8, e no comportamento
espelhado de `super/auditoria.py`/`super/solicitacoes_senha.py`). Protegido
por `@super_required`, que exige `g.perfil == 'super_admin'`
(`app/decorators/auth.py:45-54`) — não há bypass por gestor/barbeiro, pois
`_STAFF_REQUIRED` em gestor/duvidas.py só permite `['gestor', 'barbeiro',
'super_admin']`, e as rotas do `super_duvidas_bp` exigem estritamente
`super_admin`. **Confirmado: gestor e barbeiro NÃO herdam acesso
cross-tenant** — não é possível um gestor chamar
`GET /api/v1/super/duvidas/<id>` e ver ticket de outra barbearia, porque
`super_required` rejeita perfil `gestor` com 403 antes mesmo de tocar o
banco.

### 1.4 Núcleo compartilhado — `app/utils/duvidas.py`
`notificar_responsaveis` (linha 20) e `notificar_admins` (linha 49) resolvem
destinatários por query própria (`Usuario.filter_by(barbearia_id=...,
perfil='gestor')` / `perfil='super_admin'`) — não dependem de input do
chamador além do objeto `duvida` já validado. Sem problema.

**Veredito módulo Dúvidas: nenhuma falha encontrada.**

---

## 2. Loja / Compras de produto

### 2.1 `app/routes/cliente/produtos.py`
- `GET /produtos` (linha 47): `Produto.query_tenant()` — filtro automático
  por `g.barbearia_id` via `TenantMixin.query_tenant()`
  (`app/models/mixins.py:13-25`), que é fail-safe (perfil não-super sem
  `barbearia_id` recebe `query.filter(False)`, nunca lista tudo). **Correto**.
- `GET /compras` (linha 90): `SolicitacaoCompraProduto.filter_by(
  barbearia_id=g.barbearia_id, cliente_id=cli.id)`. **Correto**.
- `POST /compras` (linha 119): cada item valida `Produto.filter_by(id=...,
  barbearia_id=g.barbearia_id, ativo=True)` (linha 149) antes de aceitar —
  cliente não consegue comprar produto de outra barbearia trocando
  `produto_id`. **Correto**.
- `POST /compras/<id>/comprovante` (linha 231): `SolicitacaoCompraProduto.
  filter_by(id=solicitacao_id, barbearia_id=g.barbearia_id, cliente_id=
  cli.id)` (linha 237) — cliente não consegue anexar comprovante em pedido
  de outro cliente/barbearia. **Correto**.

### 2.2 `app/routes/gestor/compras.py`
- `GET /compras` (linha 55): `filter_by(barbearia_id=g.barbearia_id)`.
  **Correto**.
- `POST /<id>/aprovar` (linha 88) e `POST /<id>/rejeitar` (linha 137):
  ambos filtram `filter_by(id=solicitacao_id, barbearia_id=g.barbearia_id)`
  antes de agir — gestor da barbearia B não consegue aprovar/rejeitar (nem
  causar baixa de estoque/venda) em pedido da barbearia A trocando o id na
  URL. **Correto**. `aprovar_compra` ainda usa `.with_for_update()`,
  prevenindo double-approve por race condition (fora do escopo IDOR, mas
  nota de robustez positiva).

**Veredito módulo Loja/Compras: nenhuma falha encontrada.**

---

## 3. Bot de WhatsApp

### 3.1 `app/routes/pub/whatsapp.py` — `_autenticar_bot()` (linhas 24-34)
```python
segredo_esperado = os.environ.get('N8N_BOT_API_SECRET', '')
segredo_recebido = request.headers.get('X-Bot-Secret', '')
if not segredo_esperado or not hmac.compare_digest(segredo_recebido, segredo_esperado):
    abort(404)
```
**Confirmado fail-closed.** Testei os dois casos que importam:
- `N8N_BOT_API_SECRET` não configurado no ambiente → `segredo_esperado ==
  ''` → `not segredo_esperado` é `True` → `abort(404)` **antes** de chegar
  no `hmac.compare_digest`. Não há como a ausência da env var abrir a rota
  (o bug clássico seria comparar `'' == ''` e deixar passar; aqui o `or`
  curto-circuita e barra isso explicitamente).
- Secret configurado mas header ausente/errado →
  `hmac.compare_digest(recebido, esperado)` retorna `False` (comparação em
  tempo constante, sem vazamento por timing) → 404.
- 404 (não 401/403) é escolha correta de design pra não confirmar a um
  scanner que a rota existe — mitiga enumeração.

Ambas as rotas do blueprint (`barbearia_por_instancia`,
`proximo_agendamento`) chamam `_autenticar_bot()` como primeira linha.
**Correto — nenhuma rota do bot está desprotegida.**

Nota à parte (não é IDOR, é observação de design já documentada no próprio
docstring do arquivo, linhas 1-8): `proximo_agendamento` devolve dados de
agendamento de um cliente a partir só do telefone, sem exigir prova adicional
de identidade além do secret do bot — isso é aceitável porque o secret já
restringe a chamada ao workflow n8n interno, e é o n8n quem garante que quem
está pedindo o telefone "X" é o dono do número "X" (a mensagem chegou desse
número no WhatsApp). Não é uma falha de tenant isolation.

### 3.2 `app/routes/gestor/whatsapp_bot.py`
Todas as 4 rotas (`GET ''`, `POST /conectar`, `POST /desconectar`,
`DELETE ''`) usam `@gestor_required` e sempre operam sobre
`db.session.get(Barbearia, g.barbearia_id)` (`_barbearia()`, linha 20-24) —
nunca recebem um id de barbearia via URL/body. Não há superfície de IDOR
aqui: o gestor só consegue conectar/desconectar/excluir a instância WhatsApp
da própria barbearia. **Correto**.

### 3.3 `app/utils/evolution.py`
Camada HTTP pura para a Evolution API, chamada só a partir de
`gestor/whatsapp_bot.py` (que já valida tenant antes de chamar) e do webhook
inbound (fora do escopo desta rodada). Nenhuma tomada de decisão de
autorização acontece aqui — não há id de recurso BarberOS sendo aceito
diretamente do cliente. Sem achados.

**Veredito módulo Bot WhatsApp: nenhuma falha encontrada. `_autenticar_bot()`
é fail-closed, confirmado por leitura de código.**

---

## 4. Notificações in-app

Os 4 blueprints (`gestor_notif_bp`, `super_notif_bp`, `barbeiro_notif_bp`,
`cliente_notif_bp`) seguem o mesmo padrão:

| Blueprint | Arquivo | Filtro em `listar`/`contador`/`marcar_lida` |
|---|---|---|
| gestor | `app/routes/gestor/notificacoes.py:35-39, 69-74, 83-87` | `barbearia_id=g.barbearia_id, usuario_id=g.user_id` |
| barbeiro | `app/routes/barbeiro/notificacoes.py:31-35, 65-70, 79-83` | `barbearia_id=g.barbearia_id, usuario_id=g.user_id` |
| cliente | `app/routes/cliente/notificacoes.py:40-44, 76-81, 92-96` | `barbearia_id=g.barbearia_id, usuario_id=g.user_id` |
| super | `app/routes/super/notificacoes.py:37, 64-66, 75` | `usuario_id=g.user_id` (sem `barbearia_id` — correto, pois super não tem tenant fixo e a notificação carrega o `barbearia_id` de origem só como metadado exibido) |

`marcar_todas_lidas` em todos os 4 usa `.update({'lida': True})` sobre a
mesma query já filtrada por `usuario_id` (+ `barbearia_id` quando aplicável)
— não existe um `UPDATE` sem `WHERE` escopado. **Confirmado: gestor só
lista/marca como lida notificação da própria barbearia E do próprio
usuário** (um segundo gestor da mesma barbearia não vê a caixa de entrada
do primeiro, porque o filtro inclui `usuario_id`, não só `barbearia_id`).

**Veredito módulo Notificações: nenhuma falha encontrada.**

---

## 5. Perfil do gestor + Comprovante via link assinado (prioridade alta)

### 5.1 `app/utils/comprovante_link.py`
Token gerado com `itsdangerous.URLSafeTimedSerializer(SECRET_KEY, salt=
'comprovante-temp-link')` (linha 18), carregando `{'tipo', 'ref_id',
'barbearia_id'}` assinado (linha 24). `decodificar_token_comprovante`
(linha 28-33) usa `max_age=LINK_TTL_SEGUNDOS` (600s = 10 min, linha 14) e
levanta `ValueError` em `BadSignature` OU `SignatureExpired`.

- **Adulteração de token**: como o payload é assinado com `SECRET_KEY`
  (server-side, não exposto), qualquer tentativa de trocar `ref_id` ou
  `barbearia_id` manualmente (ex.: decodificar base64, editar o JSON, tentar
  re-enviar) quebra a assinatura HMAC e cai em `BadSignature` → 410. **Não é
  possível forjar um token pra acessar comprovante de outro tenant sem
  conhecer `SECRET_KEY`.**
- **Expiração**: `max_age=600` é reforçado pelo próprio `itsdangerous` no
  `.loads()` — não é um cálculo manual de timestamp que possa ter erro de
  fuso/lógica. **Expira de verdade.**
- **Vínculo ao recurso/tenant correto**: verificado em
  `app/routes/comprovante.py:59-85` — `servir_comprovante` decodifica o
  token e, para cada `tipo`, refaz a busca do registro **filtrando de novo
  por `barbearia_id=payload['barbearia_id']`** (linhas 25, 33, 41, 51 — ex.:
  `AgendamentoSolicitacaoPix.query.filter_by(agendamento_id=ref_id,
  barbearia_id=barbearia_id)`). Isso é defesa em profundidade: mesmo que o
  `ref_id` batesse por acaso com um registro de outra barbearia, o filtro
  duplo bloqueia.
- Rastreei todo ponto de **geração** do token pra confirmar que o
  `barbearia_id` embutido vem sempre do contexto já autorizado, nunca de
  input do requisitante:
  - `app/routes/cliente/duvidas.py:49` — `img.barbearia_id` de uma imagem
    de mensagem de um ticket já filtrado por `_duvida_ou_404` (tenant +
    cliente dono).
  - `app/routes/gestor/duvidas.py:71` — idem, ticket já filtrado por
    `_get_duvida_ou_404` (tenant, + barbeiro-scoped se aplicável).
  - `app/routes/super/duvidas.py:65` — `img.barbearia_id` real do registro
    (super é cross-tenant por design).
  - `app/routes/gestor/compras.py:37` — `s.barbearia_id` de uma
    `SolicitacaoCompraProduto` já filtrada por `barbearia_id=g.barbearia_id`
    na query pai.
  Em nenhum caso o `barbearia_id` do token vem de um parâmetro de URL/body
  controlado pelo cliente — sempre do objeto ORM já carregado sob filtro de
  tenant. **Não há caminho de geração de token para recurso de barbearia
  errada.**
- A rota `GET /comprovante/<token>` (`app/routes/comprovante.py:59`) é
  pública (sem `@gestor_required`/`@cliente_required`) por design — é um
  bearer token de posse, não uma sessão. Isso é aceitável dado TTL curto
  (10 min) + assinatura criptográfica + filtro duplo por tenant; o único
  risco residual é vazamento do link em si (histórico de navegador, proxy
  de log, referrer) dentro da janela de 10 min — risco genérico de qualquer
  design de "signed URL" e não um IDOR de controle de acesso quebrado.

**Veredito: sistema de comprovante via link assinado está correto.** Token
vinculado ao recurso e ao `barbearia_id` certos, adulteração é bloqueada
pela assinatura HMAC + filtro duplo no servidor, e expira de verdade via
`max_age` do `itsdangerous`.

### 5.2 `app/routes/gestor/perfil.py`
Todas as rotas (`GET ''`, `PATCH /barbearia`, `PATCH /conta`,
`POST /senha`, `POST /logo`) operam exclusivamente sobre
`db.session.get(Barbearia, g.barbearia_id)` e
`db.session.get(Usuario, g.user_id)` — nunca aceitam um id de barbearia ou
de usuário vindo da requisição. `PATCH /conta` (linha 103-110) checa
unicidade de e-mail contra `Usuario.id != u.id` mas não expõe nem modifica
outro usuário. `POST /senha` (linha 118) exige `senha_atual` correta via
`check_password_hash` antes de trocar. **Nenhuma falha — gestor só edita a
própria conta e a própria barbearia.**

**Veredito módulo Perfil/Comprovante: nenhuma falha encontrada.**

---

## 6. Cookies de sessão — flag `Secure` (AUDITORIA_PRODUCAO.md achado #3)

**STATUS: RESOLVIDO**, confirmado por leitura do código atual. Os 3 cookies
citados usam a mesma condição, de forma consistente, em todos os pontos onde
são setados:

| Cookie | Onde é configurado | Condição `Secure` |
|---|---|---|
| `bos_at` / `bos_rt` (JWT) — config global | `app/__init__.py:104` | `JWT_COOKIE_SECURE=os.environ.get('FLASK_ENV') == 'production'` |
| `bos_at` / `bos_rt` — cada `set_cookie` manual | `app/routes/views/auth.py:26-36` (`_cookie_opts()`), usado em `auth.py:148,151,179,677,679,778,779` | `secure=(os.environ.get('FLASK_ENV') == 'production')` |
| `session` (Flask) | `app/__init__.py:111` | `SESSION_COOKIE_SECURE=(os.environ.get('FLASK_ENV') == 'production')` |

Confirmei também que `session` é de fato usado em produção (guard de página
`session_required` em `app/routes/views/auth.py:42-50`, e referenciado em
mais 37 arquivos de rota), então a flag não está protegendo um cookie morto.

Não encontrei nenhum ponto com condição diferente/hardcoded (ex.:
`secure=False` fixo, ou checagem de uma env var diferente) — busquei todas
as ocorrências de `FLASK_ENV` no projeto (`app/__init__.py:104,111,148,185`
e `app/routes/views/auth.py:35`) e todas usam exatamente
`os.environ.get('FLASK_ENV') == 'production'`.

**Ressalva operacional (não é bug de código, é configuração de deploy):**
a proteção só funciona se a variável de ambiente `FLASK_ENV=production`
estiver de fato setada no servidor de produção — se ela faltar por engano
no ambiente real, o código local cai silenciosamente para `Secure=False`
sem erro nem aviso. Vale confirmar isso no `.env`/painel do provedor de
hospedagem (fora do que dá pra verificar por leitura de código).

---

## Resumo

Nenhuma falha de IDOR / cross-tenant encontrada nos 5 módulos desta rodada.
Toda rota revisada resolve o recurso combinando o id da URL com
`g.barbearia_id` e/ou `g.user_id` — que por sua vez vêm do registro
`Usuario` no banco (`app/context.py:47-49`), nunca de input do cliente. O
único cross-tenant intencional (fila do admin em `super/duvidas.py`) está
corretamente restrito a `super_admin` via `@super_required`, sem vazamento
de acesso para `gestor`/`barbeiro`. `_autenticar_bot()` em `pub/whatsapp.py`
é fail-closed. O sistema de comprovante via link assinado está corretamente
vinculado a tenant/recurso e expira de verdade. O achado #3 do
AUDITORIA_PRODUCAO.md (cookies sem `Secure`) está RESOLVIDO no código,
condicionado a `FLASK_ENV=production` estar corretamente setado no ambiente
real de produção.
