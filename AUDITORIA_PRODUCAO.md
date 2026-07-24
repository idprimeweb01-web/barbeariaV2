# Auditoria de Prontidão para Produção — BarberOS

Data: 2026-07-23. Escopo: todo o backend Flask (`app/routes/*`, 46 arquivos, 311
rotas), models, utils de negócio, configuração e histórico do git. Metodologia:
leitura direta do código-fonte + grep sistemático + `git log` no histórico real
do repositório. Nenhuma alteração foi feita no código nesta auditoria — é
apenas leitura e relatório, conforme pedido.

**Nada foi corrigido.** Este documento é só o relatório da Fase 1.

---

## Tabela resumo

| # | Severidade | Item | Arquivo:linha |
|---|---|---|---|
| 1 | 🔴 CRÍTICO | Sequestro de conta via telefone sem verificação por código | `app/routes/views/auth.py:724-748` |
| 2 | ✅ RESOLVIDO | ~~Endpoint público vaza próximo agendamento por telefone, sem autenticação~~ | `app/routes/pub/whatsapp.py:64-109` |
| 3 | 🟠 ALTO | Cookies de sessão (`bos_at`/`bos_rt`) nunca recebem a flag `Secure`, nem em produção | `app/routes/views/auth.py:26,136,139,167,665-667,766-767` |
| 4 | 🟠 ALTO | Upload de comprovante PIX anônimo não valida dono do agendamento | `app/routes/pub/agendamento.py:737-771` |
| 5 | 🟠 ALTO | Normalização de telefone não trata DDI/nono dígito — mesmo número pode virar 2 clientes diferentes | `app/utils/telefone.py:4-11` |
| 6 | 🟠 ALTO | Cupom não tem limite de uso por cliente (só limite global) | `app/utils/cupons.py:9-43`, `app/models/__init__.py:755-789` |
| 7 | 🟡 MÉDIO | Cancelamento de agendamento não estorna o crédito de plano usado | `app/routes/cliente/agendamento.py:138-206`, `app/routes/gestor/agendamento.py:212-260`, `app/routes/barbeiro/agendamentos.py:213-255` |
| 8 | 🟡 MÉDIO | Corrida de double-booking no agendamento manual do gestor cai em erro genérico (não trata `IntegrityError`) | `app/routes/gestor/agendamento.py:450-469` |
| 9 | 🟡 MÉDIO | Nenhum serviço de captura de erro em produção (Sentry ou equivalente) | N/A (ausência confirmada em todo `app/` e `requirements.txt`) |
| 10 | 🟡 MÉDIO | Credenciais reais do Cloudinary/banco/SECRET_KEY expostas no histórico do git, já pushadas no GitHub | commit `49735eedc561846aab20ef296b6110fdecaf76b8`, arquivo `.env` |
| 11 | 🔵 BAIXO/LGPD | Nenhuma política de privacidade ou termos de uso | N/A (ausência confirmada) |
| 12 | 🔵 BAIXO/LGPD | Nenhum consentimento (geral ou específico para WhatsApp) no cadastro | `app/routes/views/auth.py:696-776` |
| 13 | 🔵 BAIXO/LGPD | Nenhuma exportação de dados do titular | N/A (ausência confirmada) |
| 14 | 🔵 BAIXO/LGPD | Nenhuma exclusão de conta (soft ou hard) | N/A (ausência confirmada) |

Itens já corrigidos em sessão anterior a esta auditoria (headers de segurança,
XSS em templates, validação de magic bytes no upload de logo, isolamento de
auditoria gestor×admin, índices de integridade do banco) **não** estão
listados de novo aqui — ver `DEPLOY_CHECKLIST.txt` seção 7 e a memória do
projeto (DT-008/DT-009) para o histórico completo deles.

---

## 🔴 CRÍTICO

### 1. Sequestro de conta via telefone sem verificação por código

**O que está errado:** `POST /b/<slug>/cadastro` (`app/routes/views/auth.py:696-776`)
cria uma conta nova a partir de nome+e-mail+telefone+senha. Se já existir um
`Cliente` com aquele telefone mas **sem** conta vinculada (`usuario_id is None`),
o código simplesmente vincula a conta nova a esse `Cliente` já existente:

```python
# app/routes/views/auth.py:729-731
cliente = Cliente.query.filter_by(barbearia_id=barbearia.id, telefone=tel_norm).first()
if cliente and cliente.usuario_id:
    return jsonify({'erro': 'Este telefone já possui uma conta. Faça login.'}), 409
```

Se `cliente.usuario_id` for `None`, cai direto em `cliente.usuario_id = usuario.id`
(linha 746) — **sem pedir nenhum código de confirmação por SMS/WhatsApp**. Não
existe NENHUMA infraestrutura de OTP no projeto (confirmei via grep por
`twilio`/`sms`/`otp`/`codigo_verificacao` em todo `app/` e `requirements.txt` —
zero resultados).

Um `Cliente` sem conta vinculada é um estado **comum, não raro** — é exatamente
o que se cria em três fluxos legítimos:
- `POST /<slug>/agendar` (quick-booking anônimo) — `app/routes/pub/agendamento.py:648-666`
- Agendamento manual feito pelo gestor pra um cliente walk-in — `app/routes/gestor/agendamento.py:436-449`
- Bot de WhatsApp (`app/routes/pub/whatsapp.py`), que identifica cliente só por telefone

**Por que é problema:** qualquer pessoa que souber (ou adivinhar/vazar) o
telefone de outra pessoa que já tenha um agendamento com aquela barbearia
consegue criar uma conta e "assumir" o histórico dela — vê todos os
agendamentos passados e futuros, pode cancelar agendamentos em nome dela, vê
status de plano. É exatamente o cenário que você descreveu.

**Como corrigir:** antes de vincular a um `Cliente` já existente, exigir
confirmação de posse do número (código de 6 dígitos por SMS ou WhatsApp,
válido por poucos minutos, checado nesta mesma rota antes do
`cliente.usuario_id = usuario.id`). Alternativa mais simples de curto prazo:
exigir que o e-mail do cadastro bata com o e-mail já registrado nesse
`Cliente` (se houver) — não resolve o caso de `Cliente` sem e-mail nenhum, mas
reduz a superfície.

---

### 2. ~~Endpoint público vaza o próximo agendamento de qualquer cliente, sem autenticação~~ ✅ RESOLVIDO

**Resolução (Fase 2, Bloco 2):** as duas rotas agora exigem header
`X-Bot-Secret` batendo com `N8N_BOT_API_SECRET` (comparação em tempo
constante, mesmo padrão do `webhook_inbound.py`), falha fechado se a env
var não estiver configurada, e devolvem 404 (não 401/403) em qualquer
rejeição. Ver `app/routes/pub/whatsapp.py:_autenticar_bot`.


**O que está errado:** `GET /api/v1/pub/<slug>/clientes/<telefone>/proximo-agendamento`
(`app/routes/pub/whatsapp.py:64-109`) não tem NENHUM decorator de autenticação
e NENHUM segredo compartilhado — só `@limiter.limit('30 per minute')`. Recebe
`slug` (público, é a própria URL da página de agendamento) e `telefone` (dado
pessoal, potencialmente adivinhável/vazado) direto no path, e devolve:

```python
# app/routes/pub/whatsapp.py:102-109
return jsonify({
    'tem_agendamento': True,
    'agendamento_id': ag.id,
    'data_hora': ag.data_hora.isoformat(),
    'valor_total': float(ag.valor_total),
    'profissional': br_usr.nome if br_usr else None,
    'servicos': servicos,
}), 200
```

O comentário no código (linha 4-5) explica a premissa: *"quem manda a
mensagem já provou ser dono do número, na própria conversa do WhatsApp"* — mas
essa premissa só vale se este endpoint HTTP for inacessível para qualquer
coisa que não seja o workflow interno do n8n. Não há nada no código Flask que
garanta isso: é uma rota pública normal, chamável direto por qualquer cliente
HTTP (curl, Postman, um script) que conheça `slug` + `telefone`.

**Por que é problema:** vaza data/hora exata, valor e profissional do próximo
agendamento de qualquer cliente pra quem souber/adivinhar o telefone dele —
isso é informação de paradeiro futuro de uma pessoa (onde ela vai estar e
quando), risco de privacidade sério, não só um vazamento de dado comercial.
30 requisições/minuto por IP também não impede uma enumeração lenta e
distribuída de números de telefone.

Achado relacionado, mesmo arquivo: `GET /api/v1/pub/barbearia-por-instancia`
(`app/routes/pub/whatsapp.py:29-57`) também aceita `telefone` opcional e
devolve nome do cliente se existir — mesmo problema, severidade menor porque
depende também de saber um `instance` válido (provavelmente menos previsível
que um `slug`).

**Como corrigir:** exigir um segredo compartilhado nesta rota (o mesmo padrão
já usado em `app/routes/webhook_inbound.py:47-49`, que valida
`X-Webhook-Secret` com `hmac.compare_digest`) — só o n8n, que conhece o
secret, deveria conseguir chamar esses dois endpoints. Isso fecha a rota pra
chamadas HTTP diretas de fora do workflow autorizado.

---

## 🟠 ALTO

### 3. Cookies de sessão nunca recebem a flag `Secure`

**O que está errado:** `app/routes/views/auth.py:26` define:
```python
_COOKIE_OPTS = dict(httponly=True, samesite='Lax', path='/')
```
sem `secure=True`, e é o único lugar do projeto inteiro onde os cookies reais
de sessão (`bos_at`/`bos_rt`) são setados — confirmei via grep por
`set_cookie` em todo `app/`: só existem essas 7 ocorrências (linhas 136, 139,
167, 665, 667, 766, 767), todas usando esse mesmo dict fixo.

Existe uma config `JWT_COOKIE_SECURE=os.environ.get('FLASK_ENV') == 'production'`
em `app/__init__.py:104`, mas ela é **configuração morta** — só se aplica se o
código chamar os helpers do Flask-JWT-Extended (`set_access_cookies()`), e
isso nunca acontece; os cookies são todos setados manualmente via
`resp.set_cookie(...)` com `_COOKIE_OPTS`.

**Por que é problema:** mesmo em produção com `FLASK_ENV=production` e HTTPS
configurado, os cookies `bos_at`/`bos_rt` (usados pelo login de
gestor/barbeiro/super/cliente — todo o acesso via tela, não só a API pura)
continuam sendo enviados pelo navegador em qualquer requisição HTTP, não só
HTTPS. Isso é uma janela real de interceptação de sessão em rede
(downgrade attack, proxy mal configurado, link http:// antigo). O HSTS que já
existe (`app/__init__.py:186`) ajuda depois da primeira visita HTTPS, mas não
substitui a flag `Secure` no cookie.

**Como corrigir:** adicionar `secure=(os.environ.get('FLASK_ENV') == 'production')`
em `_COOKIE_OPTS`, ou construir o dict dinamicamente por ambiente — mesmo
padrão que já existe pra `SESSION_COOKIE_SECURE`/`JWT_COOKIE_SECURE` em
`app/__init__.py`.

---

### 4. Upload de comprovante PIX anônimo não valida dono do agendamento

**O que está errado:** `POST /api/v1/pub/<slug>/agendamentos/<id>/comprovante`
(`app/routes/pub/agendamento.py:737-771`) é uma rota pública por design (o
cliente ainda não fez login quando sobe o comprovante), e valida só que o
`agendamento_id` pertence à `barbearia` do `slug` — não valida que quem está
enviando é o dono daquele agendamento específico:

```python
# app/routes/pub/agendamento.py:742-746
ag = Agendamento.query.filter_by(
    id=agendamento_id, barbearia_id=barbearia.id
).first()
```

**Por que é problema:** `agendamento_id` é um inteiro sequencial. Qualquer um
que souber (ou testar sequencialmente) um `agendamento_id` válido de outro
cliente da mesma barbearia com PIX pendente consegue subir um comprovante
falso pro agendamento dela — no melhor caso, atrapalha a aprovação real; no
pior, pode ser usado pra tentar "provar" pagamento de outra pessoa.

**Como corrigir:** vincular o link de upload a um token específico daquele
agendamento (o mesmo padrão de token assinado que já existe em
`app/utils/comprovante_link.py` pra LER o comprovante poderia ser adaptado
pra também autorizar o UPLOAD), gerado no momento em que o agendamento é
criado e devolvido só pra quem criou o agendamento naquela sessão/resposta.

---

### 5. Normalização de telefone incompleta

**O que está errado:** `app/utils/telefone.py:4-11`:
```python
def normalizar_telefone(tel):
    digitos = re.sub(r'\D', '', tel or '')
    if len(digitos) < 8:
        return None, 'Telefone deve ter no mínimo 8 dígitos.'
    if len(digitos) > 13:
        return None, 'Telefone inválido — dígitos demais.'
    return digitos, None
```
Só remove não-dígitos e checa um intervalo de tamanho (8–13). Não normaliza
DDI (+55), não trata o nono dígito de forma consistente. `"11987654321"`
(sem DDI), `"5511987654321"` (com DDI) e `"+55 11 98765-4321"` (formatado)
normalizam para strings **diferentes**.

**Por que é problema:** todo o sistema usa `telefone` como chave de
correspondência entre canais — cadastro no app, quick-booking, agendamento
manual do gestor e o bot de WhatsApp (que naturalmente recebe o número
sempre COM DDI, formato E.164). Se o cliente se cadastra no app digitando sem
DDI e o bot do WhatsApp busca com DDI, viram dois `Cliente` diferentes na
mesma barbearia — quebra histórico, planos, cupons "não encontra conta" etc.
Não é uma falha de segurança por si só (não causa over-matching, só
under-matching), mas é uma inconsistência de dados real que atrapalha
diretamente o fluxo do bot.

**Como corrigir:** normalizar sempre pro mesmo formato canônico (ex.: sempre
13 dígitos com DDI 55, inserindo o "55" quando ausente e validando/inserindo
o nono dígito pra celulares). Usar uma lib como `phonenumbers` (Google
libphonenumber) evita reinventar essa lógica.

---

### 6. Cupom sem limite de uso por cliente

**O que está errado:** o model `Cupom` (`app/models/__init__.py:755-789`) tem
`quantidade_maxima_usos`/`quantidade_usos` — um contador **global**, comum a
todos os clientes. Não existe nenhum campo tipo `limite_uso_por_cliente`, e
`validar_cupom()` (`app/utils/cupons.py:9-43`) nunca consulta `CupomUso`
filtrando por `cliente_id` pra bloquear reuso pelo mesmo cliente:

```python
# app/utils/cupons.py:27-35 — checks existentes: existe, ativo, não expirado, limite GLOBAL
cupom = Cupom.query.filter_by(barbearia_id=barbearia_id, codigo=codigo_norm).first()
...
if cupom.quantidade_maxima_usos is not None and cupom.quantidade_usos >= cupom.quantidade_maxima_usos:
    raise APIError('Este cupom atingiu o limite de utilizações.', 422)
# nenhum check de "esse cliente_id já usou esse cupom_id antes"
```
O model `CupomUso` (linha 816-830) até guarda `cliente_id` por uso — a
informação existe, só não é consultada na hora de validar.

**Por que é problema:** um cupom pensado como "10% na primeira visita" (sem
limite de uso global, ou com limite alto) pode ser reaplicado pelo MESMO
cliente indefinidamente — agenda, cancela, reagenda com o mesmo cupom de
novo. Abuso financeiro direto contra a barbearia.

**Como corrigir:** adicionar campo opcional `limite_uso_por_cliente` em
`Cupom` e, em `validar_cupom()`, contar `CupomUso.query.filter_by(cupom_id=...,
cliente_id=...).count()` contra esse limite quando o `cliente_id` estiver
disponível no contexto da chamada.

---

## 🟡 MÉDIO

### 7. Cancelamento não estorna crédito de plano

**O que está errado:** os três endpoints de cancelamento —
`app/routes/cliente/agendamento.py:138-206` (cliente),
`app/routes/gestor/agendamento.py:212-260` (gestor),
`app/routes/barbeiro/agendamentos.py:213-255` (barbeiro) — tratam cupom
(`decrementar_uso_cupom`) mas nenhum dos três toca em `ClientePlanoUso`
quando o agendamento cancelado tinha um item marcado `is_plano=True`. O
crédito mensal do plano fica consumido mesmo com o agendamento cancelado.

**Por que é problema:** cliente perde uma sessão do plano mensal que pagou,
mesmo cancelando com antecedência — pode gerar reclamação/disputa. (Nota:
isso já era uma decisão de negócio pendente documentada na sessão anterior —
"estornar uso de plano no cancelamento" — só estou reconfirmando aqui porque
a tarefa pediu explicitamente esse teste.)

**Como corrigir:** decisão de produto primeiro (estornar sempre? só se
cancelado com X horas de antecedência, igual à regra de reembolso normal?).
Depois, no código: no momento do cancelamento, se `ag` tiver itens com
`is_plano=True`, apagar (ou marcar `usado=False`) as linhas correspondentes
de `ClientePlanoUso` daquele `cliente_plano_id`/`servico_id`/`data_uso`.

---

### 8. Corrida de double-booking no agendamento manual do gestor cai em erro genérico

**O que está errado:** `app/routes/gestor/agendamento.py:450-469` insere o
`Agendamento` com `db.session.flush()` (linha 461) **sem** o mesmo
try/except `IntegrityError` que existe no fluxo público
(`app/routes/pub/agendamento.py:311-318`). Se a constraint de banco
`uq_ag_barbeiro_slot` disparar aqui (dois gestores/telas criando manualmente
o mesmo horário ao mesmo tempo), a exceção sobe sem tratamento específico e
cai no handler genérico de 500 (`commit_ou_falhar`/`errorhandler(500)` em
`app/__init__.py:208-210`, que devolve `{'erro': 'Erro interno do
servidor.'}`).

**Por que é problema:** não é falha de segurança nem de integridade — o
índice único do banco continua garantindo que o double-booking real não
acontece (a lição de DT-008 se aplica aqui também, corretamente). É só uma
experiência pior: gestor vê "erro interno" genérico em vez de uma mensagem
clara tipo "esse horário acabou de ser ocupado".

**Como corrigir:** envolver o `db.session.add(ag); db.session.flush()` num
try/except `IntegrityError`, igual ao padrão já usado em
`pub/agendamento.py:311-318`, devolvendo uma `APIError(409, "horário já
ocupado")`.

---

### 9. Nenhum serviço de captura de erro em produção

**O que está errado:** grep por `sentry` em todo `app/` e `requirements.txt`
não retornou nenhum resultado. Erros 500 em produção só aparecem no log de
texto do gunicorn (Railway), sem agregação, alerta ou stack trace
pesquisável centralizada.

**Por que é problema:** não é uma vulnerabilidade — é um buraco operacional.
Sem isso, bugs em produção só são descobertos quando um usuário reclama, e
investigar exige vasculhar log bruto do Railway.

**Como corrigir:** integrar Sentry (tem free tier, SDK Flask é
plug-and-play: `sentry_sdk.init(dsn=..., integrations=[FlaskIntegration()])`
em `app/__init__.py`). Não é bloqueador de lançamento, mas recomendo fazer
antes do primeiro cliente real em produção.

---

### 10. Segredos reais expostos no histórico do git, já pushados

**O que está errado:** reconfirmei via `git log --all -p -- .env` que o
commit `49735eedc561846aab20ef296b6110fdecaf76b8` ("BarberOS v1 - Deploy
inicial") contém `SECRET_KEY`, `JWT_SECRET_KEY`, senha do Postgres local
(`barberos123`) e as credenciais reais do Cloudinary
(`api_key=366411938841532`, `api_secret=M_sGVbp_9XWUHz5BffO7Dd-qFWY`) em
texto puro. `git branch -r --contains 49735eed` confirma que esse commit
**está em `origin/main`** no GitHub (`idprimeweb01-web/barbeariaV2`) agora
mesmo.

**Por que é problema:** qualquer colaborador atual ou futuro com acesso de
leitura ao repo consegue extrair o secret do Cloudinary do histórico, mesmo
o `.env` não existindo mais no HEAD.

**Como corrigir:** já documentado com destaque em `DEPLOY_CHECKLIST.txt`
(topo do arquivo) e na memória do projeto (DT-007) desde 2026-07-07 —
rotacionar a API Secret do Cloudinary no console deles é ação manual do
dono, ainda **não feita** segundo a última confirmação registrada (2026-07-23).
Reconfirmando aqui porque a tarefa pediu varredura explícita do histórico do
git.

---

## 🔵 BAIXO / LGPD (decisão de produto, não bug de código)

### 11-14. Ausência de infraestrutura LGPD

Confirmei por grep case-insensitive (`lgpd|consentimento|anonimiz|termos.*uso|
politica.*privacidade|exportar.*dados|excluir.*conta`) em todo `app/` — zero
resultados. Especificamente:

- **Termos de uso / política de privacidade:** nenhuma página, nenhum
  registro de aceite. **Proposta de modelo de tabela**, já que a tarefa
  pediu isso especificamente:
  ```python
  class ConsentimentoLegal(db.Model):
      __tablename__ = 'consentimentos_legais'
      id           = db.Column(db.Integer, primary_key=True)
      usuario_id   = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
      tipo         = db.Column(db.String(30), nullable=False)  # 'termos_uso', 'privacidade', 'whatsapp_marketing'
      versao       = db.Column(db.String(20), nullable=False)  # ex: '2026-07-23'
      aceito_em    = db.Column(db.DateTime, nullable=False, default=_utcnow)
      ip           = db.Column(db.String(45))  # suporta IPv6
  ```
  Gravar uma linha por tipo aceito, no momento do cadastro (`views/auth.py:696`)
  e sempre que a versão do texto mudar (reexigir aceite).

- **Consentimento separado para WhatsApp:** hoje o cliente já é contatável
  via bot de WhatsApp sem opt-in explícito separado do cadastro geral. Existe
  `notif_whatsapp` como campo de opt-OUT no `Cliente` (confirmar no model),
  mas não um opt-IN afirmativo no primeiro contato.

- **Exportação de dados:** nenhum endpoint. Seria um `GET
  /api/v1/cliente/meus-dados/exportar` reunindo `Cliente`, `Agendamento`,
  `ClientePlano`, `CupomUso` etc. daquele `cliente_id` em JSON.

- **Exclusão de conta:** nenhum endpoint. A tarefa já aponta a solução
  correta — **nunca DELETE puro**, porque quebraria o histórico
  financeiro/fiscal do barbeiro (vendas, comissões, relatórios). O padrão
  certo é anonimização: zerar `nome`→"Cliente removido", `telefone`,
  `email`, `foto`, `observacoes`, manter `Agendamento`/`Venda`/`CupomUso`
  intactos (eles já referenciam só o `cliente_id`, não dados pessoais
  diretamente).

Isso está alinhado com o que a sessão anterior já havia decidido como escopo
mínimo do projeto (ver memória "Princípios A1-A7", princípio A6 — registro
total + nunca logar segredo, que já está OK) — os itens 11-14 são LGPD
completa, que é escopo maior do que A6 cobria. Não implementei nada disso
agora, como pedido ("só ler e reportar").

---

## Itens verificados e CORRETOS (não são achados — confirmando por item pedido)

- **Isolamento multi-tenant:** amostrei sistematicamente todas as rotas com
  `<int:...>` nos 46 arquivos de `app/routes/` — o padrão é consistente:
  toda query em rota gestor/barbeiro/cliente filtra por
  `barbearia_id=g.barbearia_id` (derivado do JWT, nunca de um param de URL),
  ou deriva a identidade do barbeiro/cliente logado via helper
  (`_get_barbeiro(g.user_id, ...)` em `barbeiro/clientes.py:13-17`,
  `_get_cliente_do_usuario()` em `cliente/agendamento.py:22-27`) em vez de
  confiar em qualquer id vindo do cliente. Exemplos verificados linha a
  linha nesta auditoria: `gestor/clientes.py:238`, `cliente/agendamento.py:39,143-145`,
  `barbeiro/agendamentos.py:217`, `comprovante.py:70` (deriva `barbearia_id`
  do token assinado, não da URL).
- **Cliente não acessa rota de Gestor / Barbeiro não acessa dados de outro
  Barbeiro:** confirmado — `cliente_required` não dá `allow_super`/bypass
  algum (`app/decorators/auth.py:30-32`), e toda rota de barbeiro deriva o
  `barbeiro_id` do próprio usuário logado, nunca de um param de URL.
- **Valor do PIX é sempre calculado no backend:** `_criar_agendamento_core`
  (`app/routes/pub/agendamento.py:249-286`) computa `valor_total` a partir de
  `Servico.preco` (banco) — nunca lê um valor vindo do corpo da requisição.
- **Comprovante nunca libera plano/agendamento automaticamente por padrão:**
  status vai para `AGUARDANDO_APROVACAO` após upload
  (`pub/agendamento.py:805-806`), exigindo ação manual do
  gestor/barbeiro. A única aprovação automática é a rota de automação n8n
  (`webhook_inbound.py`), que exige opt-in explícito do gestor
  (`permite_auto_aprovacao`) + secret HMAC comparado em tempo constante.
- **Cupom nunca gera total negativo:** `calcular_desconto()`
  (`app/utils/cupons.py:94-99`) usa `min(valor, subtotal)` — mesmo com plano
  zerando o preço do item, o desconto nunca ultrapassa o subtotal elegível.
- **Plano vencido é revogado no momento certo:** `_resolver_plano()`
  (`pub/agendamento.py:117-127`) checa `data_fim` em tempo real a cada
  tentativa de uso do plano — não depende de um job agendado que poderia
  atrasar.
- **Double-booking tem duas camadas de proteção:** lock otimista
  (`verificar_conflito` com `.with_for_update()`,
  `app/utils/agenda.py:29-41`) + constraint de banco `uq_ag_barbeiro_slot`
  como rede de segurança final (já testado sob carga real na sessão
  anterior — ver DT-008). Cobre tanto o fluxo público quanto o do cliente
  logado (compartilham `_criar_agendamento_core`); o fluxo manual do gestor
  tem a MESMA proteção de banco, só com pior mensagem de erro na corrida
  (item 8 acima).
- **Barbeiro desativado com agendamentos futuros nunca "some" silenciosamente:**
  `gestor/profissionais.py:218-289` BLOQUEIA a desativação por padrão se
  houver agendamento futuro, a menos que o gestor peça explicitamente
  `acao='transferir_mural'` — aí cada agendamento futuro vira
  `AGUARDANDO_TRANSFERENCIA` com notificação pro cliente e pros outros
  gestores.
- **Senha usa hash forte:** `werkzeug.security.generate_password_hash`
  (Werkzeug 3.1.8) usa **scrypt** por padrão (`scrypt:32768:8:1$...`) — KDF
  memory-hard, equivalente ou superior a bcrypt/argon2 pra esse propósito.
  Não é bcrypt/argon2 literalmente, mas não é fraco.
- **DEBUG desligado:** nunca setado `True` em nenhum lugar; Flask 3.1.3
  tem default `False`, e `app.run()` só executa fora do Procfile de produção
  (que usa gunicorn direto).
- **CORS:** não há `flask-cors` nem headers `Access-Control-Allow-*`
  configurados — correto, porque toda a stack (Jinja + SPA React) é
  same-origin, servida pelo próprio Flask; não existe necessidade de CORS.
- **Stack trace nunca vaza:** `@app.errorhandler(500)` sempre devolve JSON
  fixo genérico (`app/__init__.py:208-210`); `commit_ou_falhar()`
  (`app/utils/db.py:15-23`) captura qualquer exceção de commit, faz
  rollback e loga só no servidor, nunca no corpo da resposta.
- **Reset de senha não permite enumeração de e-mail:** mensagem de resposta
  é sempre a mesma, exista ou não a conta (`auth.py:156-159`).
- **Rate limiting presente em todos os endpoints sensíveis:** login (5/min),
  cadastro (5/min), reset de senha (5/min), comprovante (3/min), validar
  cupom (20/min), agendar (10/min), slots (60/min), dúvida (5/min),
  solicitar plano (5/min), webhook inbound (20/min) — confirmado via grep
  em todos os arquivos de rota.
- **Webhook inbound (n8n→sistema) autenticado corretamente:** compara o
  secret com `hmac.compare_digest` (tempo constante) —
  `webhook_inbound.py:47-49`.
- **Link de comprovante (leitura) não usa URL previsível do Cloudinary:**
  token assinado com TTL curto, `barbearia_id`/`ref_id` decodificados do
  próprio token, nunca de parâmetro de URL — `comprovante.py:59-73`.

---

## Ordem de correção sugerida

1. **#1 e #2 (CRÍTICO)** — bloqueiam qualquer lançamento em produção. São
   vazamento/sequestro de dados pessoais de clientes reais. Corrigir antes
   de qualquer outra coisa nesta lista.
2. **#3 (cookie Secure)** — mudança de uma linha, risco alto, sem
   dependência de decisão de produto. Fazer junto com os itens 1-2.
3. **#4 (IDOR comprovante) e #6 (cupom por cliente)** — exigem um pouco mais
   de desenho (token por agendamento; novo campo no model de cupom), mas
   são bem delimitados. Fazer antes do lançamento.
4. **#5 (normalização de telefone)** — vale resolver antes de ligar o bot
   de WhatsApp pra valer, porque é exatamente o campo que conecta os dois
   canais.
5. **#7 e #8 (MÉDIO, agendamento)** — não bloqueiam lançamento, mas #7
   precisa de uma decisão de produto sua primeiro (quando estornar plano no
   cancelamento).
6. **#9 e #10** — #10 é ação manual sua (rotacionar Cloudinary, já
   documentada há duas semanas, ainda pendente); #9 (Sentry) é
   recomendado antes do primeiro cliente real, não bloqueador técnico.
7. **#11-14 (LGPD)** — exigem decisão de produto/jurídica sua (texto da
   política, o que a exclusão de conta realmente anonimiza). Não são
   bugs de código; são funcionalidades que faltam.

---

## Não consegui verificar (precisa de teste manual seu)

- **Comportamento real do rate limiter sob múltiplos workers em produção**
  — o código já documenta (DT-006) que `memory://` é por-worker; só um
  teste em produção real com carga confirma o comportamento efetivo.
- **Se o Cloudinary já foi rotacionado** — perguntei sobre isso em sessões
  anteriores e a resposta mais recente registrada foi "não rotacionei"; não
  tenho como verificar isso lendo código, só você confirma no console deles.
- **Comportamento visual/UX dos dois achados CRÍTICOS num navegador real**
  — validei a lógica lendo o código-fonte com atenção a cada branch de
  decisão, mas não reproduzi o exploit fim-a-fim num browser (a tarefa
  pediu só auditoria nesta fase, sem alterar nada — não criei dados de
  teste nem rodei o app pra não misturar com o pedido explícito de "não
  corrija nada ainda").
- **Endereço do cliente (segunda versão, atendimento domiciliar):** hoje não
  há campo de endereço no `Cliente` nem rota relacionada — não há o que
  auditar ainda; quando esse campo for adicionado, ele entra automaticamente
  na mesma categoria de "dado pessoal sensível" dos itens 11-14 (LGPD) e
  deveria reusar a mesma infraestrutura de consentimento proposta ali.
- **Infraestrutura fora do código** (regras de firewall/proxy na Railway,
  se existe algum WAF, se há algum gateway na frente do Flask que já
  restrinja `pub/whatsapp.py` só ao IP do n8n) — audito só o que está no
  repositório; se você já tem uma dessas camadas configurada fora do
  código, o achado #2 pode já estar mitigado na prática, mas não há como eu
  confirmar isso sem acesso à infraestrutura.
