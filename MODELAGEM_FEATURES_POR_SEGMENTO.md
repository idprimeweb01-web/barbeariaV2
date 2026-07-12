# MODELAGEM_FEATURES_POR_SEGMENTO.md

Modelagem técnica da Frente 1 do BarberOS — features ativa/inativa por
segmento de barbearia.

Gerado em: 2026-07-10, com base em `INVENTARIO_COMPLETO_BARBEROS.txt`
(código na tag v1.1.0, commit dbb1826) e em releitura direta do código atual
para os pontos usados nesta modelagem (`app/routes/super/barbearias.py`,
`app/routes/gestor/features.py`, `app/routes/barbeiro/produtos.py`,
`app/utils/features.py`, `app/labels.py`, `app/seeds.py`,
`app/templates/gestor/base.html`, `migrations/versions/c5d7f9a1b3e5_*`).

**Este documento é SOMENTE PLANEJAMENTO.** Nenhum arquivo do projeto original
foi alterado para produzi-lo. Nada aqui está implementado — tudo marcado
"PROPOSTA" precisa ser construído depois, e o dono precisa validar antes de
qualquer código ser escrito.

---

## PARTE A — ANÁLISE

### A.1 Quais features já existem hoje e como são aplicadas?

Duas tabelas resolvem isso hoje:

- `FeatureMetadata` (`app/models/__init__.py:701`) — catálogo global da
  plataforma. 11 linhas, seedadas por `app/seeds.py:FEATURES` (12-24):
  `planos`, `relatorios_avancados`, `vip_brindes`, `agendamento_login`,
  `historico_cliente`, `cupons`, `fila_espera`, `comissao`, `notificacoes`,
  `pix_integrado`, `produtos_venda` (única com `ativo_por_padrao=True`).
- `FeatureBarbearia` (`app/models/__init__.py:718`) — flag `ativo` por
  **barbearia individual**, `UNIQUE(barbearia_id, feature_id)`.

Checagem em runtime: `app/utils/features.py`, duas funções:
- `feature_ativa(barbearia_id, nome)` (linha 6) — consulta direta, usada
  para esconder/mostrar comportamento sem bloquear (ex.: dashboard).
- `feature_required(nome)` (linha 19) — decorator que levanta `APIError`
  403 se a feature estiver off para `g.barbearia_id`.

Das 11 features do catálogo, **7 têm enforcement real** no backend
(`cupons`, `planos`, `vip_brindes`, `produtos_venda`, `comissao`,
`notificacoes`, `historico_cliente` — este último só num endpoint de
exemplo). **4 são decorativas** — o super admin liga/desliga no painel, mas
nada no sistema muda:

| Feature | Situação real |
|---|---|
| `relatorios_avancados` | Zero checagem. `gestor/relatorios.py` roda sempre, incondicional. |
| `agendamento_login` | Zero checagem. Quick-booking público sempre aceita agendar sem conta. |
| `fila_espera` | Tabela `FilaEspera` existe, mas nenhuma rota Flask cria/lista/promove uma entrada. Feature + tabela órfãs. |
| `pix_integrado` | Só o **frontend** respeita (esconde 1 link de nav em `gestor/base.html:540-543`). O backend de aprovação PIX (`gestor/agendamento.py:aprovar_agendamento`, `barbeiro/agendamentos.py:aprovar_comprovante`) não checa a feature — API continua acessível mesmo desligada. |

Descoberta de features pelo frontend hoje:
- `GET /api/v1/gestor/features` (`app/routes/gestor/features.py:13`) — usado
  por `gestor/base.html:526-553`, só liga/desliga **3 de 11** links de
  sidebar (`nav-pix`, `nav-cupons`, `nav-vendas`). As outras 8 features
  (inclusive `planos` e `vip_brindes`) não têm `id` de nav correspondente —
  o link sempre aparece, e só falha (403) ao tentar criar/editar.
- `GET /api/v1/barbeiro/features` (`app/routes/barbeiro/produtos.py:16`) —
  mesmo formato, usado só para decidir se mostra o botão "Vender produto".
- **Para o cliente: NÃO EXISTE.** A SPA React (`frontend/src/`) nunca
  consulta feature flags — zero referência a "feature" em `frontend/src`.

### A.2 Qual o esquema atual de Segmento e FeatureMetadata/FeatureBarbearia?

```
Segmento (segmentos)                    FeatureMetadata (feature_metadata)
  id PK                                   id PK
  nome String(100)                        nome String(50) UNIQUE
  chave String(50) UNIQUE, index          descricao String(200)
                                           ativo_por_padrao Boolean

SegmentoRotulo (segmento_rotulos)       FeatureBarbearia (feature_barbearia)
  id PK                                   id PK
  segmento_id FK->segmentos.id UNIQUE     barbearia_id FK->barbearias.id, index
  rotulo_tenant, rotulo_profissional,     feature_id FK->feature_metadata.id
  rotulo_servico, rotulo_agendamento,     ativo Boolean default=False
  rotulo_cliente, rotulo_produto,         atualizado_em DateTime
  rotulo_plano, rotulo_pagamento,         UNIQUE(barbearia_id, feature_id)
  rotulo_faturamento, rotulo_relatorio
  (String(50) cada, com default em PT)

Barbearia.segmento_id → Integer FK->segmentos.id, nullable
```

**Confirmado por leitura direta do código nesta sessão — achado que NÃO
estava explícito no inventário original:** `app/labels.py` já tem um método
`L.get(segmento_id, 'chave')` (linha 96) pronto para resolver rótulos
dinâmicos por segmento a partir de `SegmentoRotulo`, com cache em memória.
**Porém, `L.get(...)` NUNCA é chamado em lugar nenhum do código** (grep em
todo `app/` por `L.get(` e `L.todos(` → zero ocorrências fora da própria
definição em `labels.py`). Todo template e rota usa `L('chave')` — a forma
**estática** que ignora `segmento_id` completamente e sempre devolve o
rótulo de `_STATIC` (vocabulário "barbearia" fixo). **Na prática, hoje,
trocar o segmento de uma barbearia não muda absolutamente nenhum rótulo
visível em nenhuma tela** — o mecanismo dinâmico existe no código mas está
desconectado do runtime. Isso é maior que a lacuna já documentada
("Segmento serve só para vocabulário") — o vocabulário por segmento em si
também não está de fato ligado a nada ainda.

Zero relação entre `Segmento`/`SegmentoRotulo` e `FeatureMetadata`/
`FeatureBarbearia` — nenhuma FK, nenhuma tabela ponte, nenhuma lógica que
leia `segmento_id` para decidir features.

### A.3 Onde uma nova barbearia recebe suas features padrão?

`criar_barbearia()` (`app/routes/super/barbearias.py:108-191`). Trecho
relevante (linhas 178-183):

```python
for fm in FeatureMetadata.query.all():
    db.session.add(FeatureBarbearia(
        barbearia_id=barbearia.id,
        feature_id=fm.id,
        ativo=fm.ativo_por_padrao,
    ))
```

Cria uma `FeatureBarbearia` para **cada** feature do catálogo, usando
`FeatureMetadata.ativo_por_padrao` — um valor **global**, igual para toda
barbearia nova, independente de segmento.

**Achado confirmado nesta sessão:** o payload de `criar_barbearia()` (linhas
113-119) só lê `nome`, `slug`, `nome_exibicao`, `gestor_nome`,
`gestor_email`, `gestor_telefone`, `gestor_senha` + campos de endereço. **Não
lê `segmento_id` em nenhum momento.** Ou seja, hoje **não existe forma de
uma barbearia nascer já com segmento definido** — o segmento só pode ser
atribuído depois, num segundo passo, via `PATCH /api/v1/super/barbearias/
<id>/segmento`. Isso é relevante para a modelagem: o fluxo de criação
precisa ganhar o campo `segmento_id` no payload, e não apenas a lógica de
features.

### A.4 Os 4 pontos onde "mudar o segmento de uma barbearia existente" toca no código hoje

Levantamento exaustivo (grep de `segmento_id` e `Segmento` em todo `app/`):

1. **`PATCH /api/v1/super/barbearias/<id>/segmento`**
   (`app/routes/super/barbearias.py:705-722`, função
   `patch_barbearia_segmento`) — único endpoint que escreve
   `Barbearia.segmento_id`. Faz **apenas** isso: valida que o `Segmento`
   existe (ou aceita `null` para remover), grava, comita. Não toca
   `FeatureBarbearia`, não invalida cache de rótulos, não dispara nada.

2. **`app/labels.py` (`_RotuloStore._carregar`, linha 110-125)** — é o único
   lugar que *leria* `segmento_id` para produzir rótulos diferentes, via
   `L.get(segmento_id, chave)`. Como demonstrado em A.2, esse caminho nunca
   é chamado — é código morto em termos de efeito prático hoje, mas é o
   ponto certo onde a mudança de segmento *deveria* refletir, e não
   reflete.

3. **`app/routes/super/barbearias.py:646-702`** — trio de endpoints que
   administram `Segmento`/`SegmentoRotulo` em si (não a atribuição a uma
   barbearia): `GET /segmentos` (lista + contagem de barbearias por
   segmento), `GET/PUT /segmentos/<id>/rotulos` (edita o vocabulário do
   segmento), `POST /segmentos/seed` (roda `seed_segmentos()` de novo). O
   `PUT` de rótulos chama `L.invalidar()` ao final — o único lugar do
   código que interage com o cache de `_RotuloStore`, reforçando que o
   mecanismo dinâmico foi construído mas nunca conectado a uma tela que o
   leia de fato.

4. **UI (frontend server-rendered)** — **achado confirmado nesta sessão:**
   `app/templates/super/barbearias.html` (a tela onde o super admin
   gerencia barbearias) **não tem nenhuma referência a "segmento"** (grep
   confirmado). A única UI que toca segmento é `super/segmentos.html` (CRUD
   dos segmentos da plataforma) e `super/segmento_rotulos.html` (edição de
   rótulos de um segmento) — nenhuma delas atribui um segmento a uma
   barbearia específica. **O endpoint `PATCH .../segmento` existe no
   backend, funciona, mas não tem botão nenhum que o chame.** Hoje, mudar o
   segmento de uma barbearia só é possível via chamada direta à API (Postman
   ou similar), nunca pela tela do super admin.

**Síntese de A.4:** dos "4 pontos", só 1 (o endpoint PATCH) tem efeito real
hoje (grava a coluna). Os outros 3 são pontos onde a mudança de segmento
*deveria* ter consequência (rótulos visíveis, resumo de contagem,
formulário de atribuição) e ou não têm consequência nenhuma (rótulos), ou
são leitura/administração à parte (listagem/CRUD de segmento), ou
simplesmente não existem ainda (UI de atribuição). Isso muda o escopo desta
frente: **não basta ligar Segmento↔Feature — a própria ligação
Segmento↔Barbearia já está incompleta na camada de produto (falta UI) e na
camada de efeito (rótulos dinâmicos mortos).**

---

## PARTE B — MODELAGEM

### B.1 Schema completo da nova tabela `SegmentoFeaturePadrao`

Segue exatamente o padrão de nomenclatura e estilo já usado em
`FeatureBarbearia`/`SegmentoRotulo` (colunas alinhadas, `UniqueConstraint`
nomeada, sem `TenantMixin` porque não é dado de tenant — é dado de
plataforma, como `FeatureMetadata`).

```python
class SegmentoFeaturePadrao(db.Model):
    """Define quais features nascem ativas para barbearias de um dado segmento.
    Aplicado em criar_barbearia() por cima do ativo_por_padrao global,
    e usado por editar_segmento() ao reajustar features de barbearias existentes."""
    __tablename__ = 'segmento_feature_padrao'
    __table_args__ = (
        db.UniqueConstraint('segmento_id', 'feature_id', name='uq_segmento_feature_padrao'),
    )

    id            = db.Column(db.Integer, primary_key=True)
    segmento_id   = db.Column(db.Integer, db.ForeignKey('segmentos.id'), nullable=False, index=True)
    feature_id    = db.Column(db.Integer, db.ForeignKey('feature_metadata.id'), nullable=False)
    ativo_por_padrao = db.Column(db.Boolean, nullable=False, default=False)
    atualizado_em = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)
```

Relação: `Segmento` (1) → `SegmentoFeaturePadrao` (N), `FeatureMetadata` (1)
→ `SegmentoFeaturePadrao` (N). Não precisa de `relationship`/`backref`
obrigatório — o padrão do projeto (`FeatureBarbearia`) só declara um
`backref` do lado de `FeatureMetadata.flags`; aqui bastaria manter simétrico
se for útil no admin (`Segmento.features_padrao = db.relationship(...)`,
opcional).

**Semântica**: uma linha "existe e `ativo_por_padrao=True`" = o segmento
liga a feature por padrão. Uma linha "existe e `ativo_por_padrao=False`" =
o segmento explicitamente desliga a feature por padrão (diferente de
"ausência de linha"). Ausência de linha para o par
`(segmento_id, feature_id)` = **usa o `FeatureMetadata.ativo_por_padrao`
global** como fallback (mesmo comportamento de hoje, preservado para
segmentos que não têm override). Essa é uma decisão de design que evita
forçar todo segmento a ter as 11 linhas desde o dia 1 — DECISÃO PENDENTE
confirmar com o dono se prefere exigir cobertura completa (11 linhas por
segmento, sem fallback) — ver B.7/C.2.

### B.2 Novo fluxo de `criar_barbearia` — passo a passo

Estado atual: `super/barbearias.py:108-191`, loop simples sobre
`FeatureMetadata.ativo_por_padrao`.

Proposta:

1. Payload ganha campo opcional `segmento_id` (novo — hoje não existe, ver
   A.3).
2. Validação: se `segmento_id` vier, `Segmento.query.get(segmento_id)` deve
   existir (mesmo padrão de erro 404 já usado em
   `patch_barbearia_segmento`).
3. `Barbearia(...)` passa a incluir `segmento_id=seg.id if seg else None` na
   construção (hoje a criação não seta esse campo — fica `NULL` sempre).
4. Bloco de features (substitui linhas 178-183):
   ```python
   overrides = {}
   if barbearia.segmento_id:
       overrides = {
           sfp.feature_id: sfp.ativo_por_padrao
           for sfp in SegmentoFeaturePadrao.query.filter_by(
               segmento_id=barbearia.segmento_id
           ).all()
       }
   for fm in FeatureMetadata.query.all():
       ativo = overrides.get(fm.id, fm.ativo_por_padrao)
       db.session.add(FeatureBarbearia(
           barbearia_id=barbearia.id, feature_id=fm.id, ativo=ativo,
       ))
   ```
5. Resto do fluxo (gestor, `BarbeariaCustomizacao`, `ConfiguracaoAgendamento`,
   commit atômico) **inalterado**.

Efeito: se a barbearia nascer sem segmento (`segmento_id=None`), o
comportamento é **idêntico ao de hoje** (usa só o padrão global) —
compatibilidade total com o fluxo atual.

### B.3 Novo fluxo de `editar_segmento` (trocar segmento de barbearia existente) — passo a passo

Estado atual: `patch_barbearia_segmento` só grava a coluna. Proposta
consciente da pergunta em aberto nº 1 do inventário ("segmento DEFINE ou só
SUGERE") — modelagem para a opção mais segura por padrão, com flag explícito
para o modo automático:

1. Endpoint recebe `segmento_id` (como hoje) **+ novo parâmetro opcional
   `reajustar_features: bool` (default `False`)**.
2. Sempre grava `b.segmento_id = seg.id` (comportamento hoje já existe,
   mantido).
3. **Sempre** chama `L.invalidar(barbearia_antigo_segmento_id)` e
   `L.invalidar(novo_segmento_id)` — corrige o gap de A.4 item 2 (cache de
   rótulos nunca invalidado para esse caso específico; hoje só é invalidado
   em `put_segmento_rotulos`).
4. Se `reajustar_features=True`:
   - Busca `SegmentoFeaturePadrao` do novo segmento.
   - Para cada `feature_id` com override no segmento: faz
     `upsert` em `FeatureBarbearia` (mesmo padrão de `toggle_feature`,
     linha 342-350: busca existente, senão cria).
   - Features **sem override** no novo segmento **não são tocadas** — o
     estado atual da barbearia (ligado/desligado manualmente pelo super)
     é preservado. Isso evita apagar customizações manuais feitas
     anteriormente por engano.
   - Resposta inclui a lista de features que mudaram (`{feature, de, para}`)
     para auditoria/confirmação visual na tela.
5. Se `reajustar_features=False` (default): comportamento **idêntico ao
   atual** — só rótulo/segmento muda, features não são tocadas. Preserva
   retrocompatibilidade com qualquer chamador existente da API.
6. Registrar em `AuditoriaLog` (tabela já existe, `tipo_acao='edit'`,
   `entidade='Barbearia'`) a troca de segmento — **hoje esse endpoint não
   grava auditoria nenhuma**, gap adicional encontrado nesta modelagem (o
   princípio A6 da memória do projeto — "toda ação de negócio → registro" —
   não está sendo seguido aqui hoje).

DECISÃO PENDENTE (mapeada para a pergunta 1 e 2 do inventário): se o dono
preferir que a troca de segmento **sempre** reajuste automaticamente
(sem flag opcional), o passo 4 vira incondicional e o parâmetro
`reajustar_features` é removido da proposta. A modelagem acima assume a
opção mais conservadora (reajuste é opt-in) por ser reversível a favor da
opção automática sem quebrar nada; o inverso (automático por padrão) seria
mais arriscado de simplificar depois. Recomendo o modo opt-in, mas é uma
escolha do dono.

### B.4 As 4 "features decorativas" — onde e como implementar de fato

DECISÃO PENDENTE geral (pergunta 3 do inventário): decidir **por feature**
se ganha enforcement real ou é removida do catálogo. A modelagem abaixo
assume "ganha enforcement" para as 3 primeiras (fazem sentido de produto
óbvio) e trata `fila_espera` à parte por exigir lógica de negócio nova, não
só um gate.

**a) `relatorios_avancados`**
- Onde: `app/routes/gestor/relatorios.py`, 4 endpoints (`:50, :94, :118,
  :142` no inventário) hoje só com `@gestor_required`.
- Como: adicionar `@feature_required('relatorios_avancados')` nos endpoints
  que forem considerados "avançados". **Requer decisão de produto**: qual
  subconjunto de relatórios é "básico" (sempre liberado) vs "avançado"
  (gateado)? Hoje os 4 endpoints não têm essa distinção no código — ver
  pergunta 11 do inventário. Sem essa decisão, a única opção mecânica é
  gatear os 4 endpoints inteiros, o que pode ser mais restritivo do que o
  produto original pretendia.

**b) `agendamento_login`**
- Onde: `app/routes/pub/agendamento.py`, função de quick-booking público
  (endpoint `POST /api/v1/pub/<slug>/agendar`).
- Como: quando a feature estiver ativa para a barbearia, o endpoint público
  passa a exigir que a requisição traga um cliente autenticado (JWT válido
  de perfil `cliente`) em vez de aceitar cadastro "na hora" por telefone.
  Implica ramificar a validação de entrada hoje incondicional
  (`_criar_agendamento_core`, `pub/agendamento.py:208`) para checar
  `feature_ativa(barbearia_id, 'agendamento_login')` antes de permitir o
  caminho "sem login". Já existe o campo irmão em
  `ConfiguracaoAgendamento.quick_booking_sem_login` (comentado no princípio
  A3 da memória do projeto como "ligado com feature flag
  `agendamento_login`") — **achado**: esse campo já existe no model
  (`app/models/__init__.py:838`) mas hoje **não é lido em lugar nenhum do
  código de agendamento público** (mesma lacuna de enforcement). A
  implementação correta é: `pub/agendamento.py` passar a checar
  `configuracao_agendamento.quick_booking_sem_login` (não a feature
  diretamente) — e a feature `agendamento_login`, quando desativada,
  deveria forçar esse campo para `True` (ou a UI do gestor escondê-lo).

**c) `fila_espera`**
- Onde: não existe rota hoje — é o caso mais caro dos 4.
- Como: exige construir CRUD completo sobre a tabela `FilaEspera`
  (já existe, `app/models/__init__.py:791`): endpoint para cliente entrar
  na fila (público ou autenticado), endpoint para gestor/barbeiro listar e
  "chamar" o próximo da fila, lógica de posição/prioridade. Isso é
  significativamente maior que um simples `@feature_required` — é uma
  funcionalidade nova do zero. **Fora do escopo natural desta frente**
  (features por segmento) — recomendo tratar como item de backlog
  separado, e nesta frente apenas decidir se a feature continua no
  catálogo como "em breve" (visível mas sinalizada) ou é retirada até ter
  lógica.

**d) `pix_integrado`**
- Onde: `app/routes/gestor/agendamento.py:aprovar_agendamento` e
  `app/routes/barbeiro/agendamentos.py:aprovar_comprovante`.
- Como: adicionar `@feature_required('pix_integrado')` nesses dois
  endpoints de aprovação — mesmo padrão já usado em `vip.py`/`cupons.py`.
  Simples de implementar, sem decisão de produto pendente (o comportamento
  esperado já está implícito no nome da feature e no que o frontend já faz
  parcialmente).

### B.5 Novo endpoint `/api/v1/cliente/features`

Não existe hoje (confirmado na A.1). Réplica direta do padrão já usado em
`gestor/features.py:listar_features` (linha 13-29) e
`barbeiro/produtos.py:listar_features_barbeiro` (linha 16-30) — mesmo
formato de resposta, para manter os 3 endpoints (`gestor`, `barbeiro`,
`cliente`) consistentes:

- **Rota**: `GET /api/v1/cliente/features`
- **Blueprint**: novo endpoint dentro de `app/routes/cliente/perfil.py` (já
  existe `cliente_perfil_bp`, prefixo `/api/v1/cliente`) ou um novo arquivo
  `app/routes/cliente/features.py` — recomendo arquivo novo, espelhando a
  organização de `gestor_features_bp`/inexistência de um
  `barbeiro_features_bp` dedicado (ali foi colado em `produtos.py`, o que o
  próprio inventário já aponta como não ideal). Ver F.1.
- **Decorator**: `@cliente_required` (já existe em `app/decorators/auth.py`,
  usado em todo `cliente_*` blueprint).
- **Resposta**:
  ```json
  [
    {"nome": "planos", "descricao": "Planos de assinatura mensal para clientes", "ativo": true},
    {"nome": "cupons", "descricao": "Cupons de desconto para clientes", "ativo": false}
  ]
  ```
  (idêntico ao formato de `gestor/features` e `barbeiro/features` — 11
  entradas, todas as features do catálogo, com `ativo` resolvido via
  `FeatureBarbearia.filter_by(barbearia_id=g.barbearia_id)`.)
- **Quem chama**: a SPA React (`frontend/src/api.js`) — hoje o cliente HTTP
  `api` (linha 1-29) não tem nenhum método de features; seria necessário
  adicionar `api.features.listar()` lá, e consumir nas páginas
  `frontend/src/pages/*.jsx` para esconder/mostrar seções (ex.:
  `Planos.jsx` esconder tudo se `planos` estiver off, `Beneficios.jsx`
  esconder se `vip_brindes` estiver off). Isso é trabalho de frontend, fora
  do escopo backend desta modelagem, mas precisa ser contado no
  cronograma (ver G).
- **Por que precisa de `g.barbearia_id` no contexto cliente**: confirmar que
  `cliente_required` já popula `g.barbearia_id` do mesmo jeito que
  `gestor_required`/`barbeiro_required` — **verificar em
  `app/decorators/auth.py` na implementação** antes de codar (não
  confirmado nesta sessão de modelagem, é checagem rápida na fase de
  implementação, não bloqueia a modelagem).

### B.6 Alterações na sidebar do gestor (`gestor/base.html`)

Estado atual (`app/templates/gestor/base.html:526-553`): busca
`GET /gestor/features`, monta `window._features`, e só liga/desliga **3
links** (`nav-pix`, `nav-cupons`, `nav-vendas`) via `style="display:none"`
no HTML + JS que remove o `display:none` se a feature estiver ativa.

Proposta — cobrir os 11 links (mapeamento feature → nav id):

| Feature | Link de nav hoje | Ação proposta |
|---|---|---|
| `produtos_venda` | `#nav-vendas` (já gateado) | manter |
| `cupons` | `#nav-cupons` (já gateado) | manter |
| `pix_integrado` | `#nav-pix` (já gateado) | manter |
| `planos` | `/gestor/planos` (linha 369, **sem id**) | adicionar `id="nav-planos" style="display:none"`, adicionar ao JS |
| `vip_brindes` | link de VIP (confirmar linha exata na implementação — não localizado nesta sessão de modelagem, grep por `data-path="/gestor/vip"` não encontrou correspondência exata no arquivo atual; **verificar na implementação**, pode estar sob outro id/rota) | idem, mapear e gatear |
| `relatorios_avancados` | `/gestor/relatorios` (linha 375, **sem id**, e a tela mistura básico+avançado — ver B.4a) | DECISÃO PENDENTE — só gatear se B.4a definir separação básico/avançado; senão não faz sentido esconder a tela toda |
| `comissao` | não é uma tela própria — aparece dentro de outras telas (ex. `barbeiro/dashboard.html`) | não é um item de nav a esconder — fora do escopo desta tabela |
| `historico_cliente` | endpoint de exemplo, sem tela própria hoje | não aplicável a nav até virar feature real de tela |
| `notificacoes` | não é uma tela, é comportamento (disparo de notificação) | não aplicável a nav |
| `agendamento_login` | não é tela do gestor, é comportamento do booking público | não aplicável a nav |
| `fila_espera` | não existe tela hoje (ver B.4c) | não aplicável até a feature ganhar UI própria |

Ação técnica no JS (`gestor/base.html:526-553`), generalizando o bloco
repetitivo atual (3 `if` iguais) em um loop orientado a dados — reduz
duplicação e cobre os novos casos automaticamente:

```js
const NAV_POR_FEATURE = {
  pix_integrado: 'nav-pix',
  cupons: 'nav-cupons',
  produtos_venda: 'nav-vendas',
  planos: 'nav-planos',
  vip_brindes: 'nav-vip',
};
Object.entries(NAV_POR_FEATURE).forEach(([feature, navId]) => {
  if (f[feature]) {
    const el = document.getElementById(navId);
    if (el) el.style.display = '';
  }
});
```

Isso também resolve a inconsistência [4] do inventário (gestor conseguia
"listar" mas não "criar/editar" em Planos/VIP mesmo com a feature
desligada — agora o link nem aparece).

---

## PARTE C — REVISÃO

### C.1 O modelo acima cobre 100% do levantamento da Parte B do inventário?

Cobertura ponto a ponto contra a síntese "FALTA" da Parte F.15 do
inventário (Frente 1):

| Item do inventário | Coberto por esta modelagem? |
|---|---|
| Relação Segmento↔Feature (tabela nova) | ✅ B.1 (`SegmentoFeaturePadrao`) |
| Enforcement das 4 features decorativas | ⚠️ Parcial — `pix_integrado` sim (B.4d); `relatorios_avancados` e `agendamento_login` dependem de decisão de produto ainda em aberto (B.4a/b); `fila_espera` explicitamente fora de escopo por ser feature nova, não gate (B.4c) |
| Endpoint de features para o cliente | ✅ B.5 |
| Sincronizar sidebar do gestor (11 de 11) | ⚠️ Parcial — 5 dos 11 mapeiam para nav real (`produtos_venda`, `cupons`, `pix_integrado`, `planos`, `vip_brindes`); os outros 6 não são telas de nav, não se aplica gatear (comportamento correto, não uma lacuna) |
| Decisão: trocar segmento reajusta features? | ✅ Modelado com flag opt-in (B.3) — decisão final de "automático vs opt-in" ainda é do dono |

**Achados adicionais que o inventário não havia detalhado e esta modelagem
trouxe à tona** (ver A.2 e A.4): rótulos dinâmicos por segmento
(`L.get()`) existem no código mas nunca são chamados — vocabulário por
segmento é hoje 100% inerte, não só "serve pra vocabulário" como o
inventário registrou, mas **nem isso está de fato ligado**. E não existe UI
para atribuir segmento a uma barbearia (só API crua). Isso não estava
listado como pendência na Parte F do inventário — é um gap novo desta
sessão de modelagem.

### C.2 Quais pontos ainda estão em aberto e precisam de decisão de produto?

Consolidado (numeração própria desta modelagem, referenciando as perguntas
do inventário item 16 onde aplicável):

1. **Fallback de `SegmentoFeaturePadrao`** (B.1): ausência de linha usa
   `ativo_por_padrao` global, ou todo segmento deve ter cobertura completa
   das 11 features? — modelagem assume fallback (menos fricção de
   cadastro).
2. **Reajuste automático vs opt-in ao trocar segmento** (B.3, = pergunta 1
   e 2 do inventário) — modelagem assume opt-in por segurança.
3. **`relatorios_avancados`**: qual relatório é básico vs avançado? (B.4a,
   = pergunta 11 do inventário) — sem isso, a feature não pode ganhar
   enforcement granular.
4. **`agendamento_login`**: confirmar que a leitura correta é via
   `ConfiguracaoAgendamento.quick_booking_sem_login` e não direto da
   feature — e decidir quem seta esse campo quando a feature muda (B.4b).
5. **`fila_espera`**: construir lógica de negócio agora (escopo bem maior
   que esta frente) ou manter fora do catálogo funcional por ora? (= pergunta
   4 do inventário)
6. **Vale a pena remover as features do catálogo que não ganharem
   enforcement**, em vez de deixá-las "quebradas" no painel super? (=
   pergunta 3 do inventário, decisão por feature)
7. **Cobertura de `SegmentoFeaturePadrao` nos 4 segmentos já seedados**
   (barbearia/salão/manicure/clínica) — que combinação de features faz
   sentido de negócio para cada um? Puramente uma decisão de produto, não
   técnica (ver D.2 para a mecânica de popular).

### C.3 Esta modelagem prepara terreno para a Frente 2 (n8n) ou deixa gap?

**Prepara, sem gap direto**, pelas seguintes razões:

- A Frente 2 usa o mesmo padrão de extensão por-tenant que esta frente
  reforça (`FeatureBarbearia` por barbearia, agora também por segmento) —
  não há conflito arquitetural: um futuro `BarbeariaWebhookConfig`
  seguiria o mesmo padrão de tabela `*_barbearia` já estabelecido.
- O evento "feature ativada/desativada" **não está** nos 5 eventos de
  negócio já mapeados pelo inventário para n8n (agendamento
  criado/aprovado/cancelado, plano ativado, venda concluída). Se o dono
  quiser que mudança de feature dispare um webhook (ex.: notificar
  integração externa que "cupons" foi ligado), isso não está coberto aqui
  e precisaria ser adicionado à lista de eventos da Frente 2 depois — não é
  um bloqueio, é um lembrete para quando a Frente 2 for modelada.
- O novo campo de auditoria proposto em B.3 passo 6 (`AuditoriaLog` para
  troca de segmento) é reaproveitável como fonte de eventos caso a Frente 2
  decida também disparar webhooks a partir de `AuditoriaLog` no futuro.

---

## PARTE D — BANCO DE DADOS

### D.1 SQL completo para `SegmentoFeaturePadrao`

```sql
CREATE TABLE segmento_feature_padrao (
    id                INTEGER PRIMARY KEY,
    segmento_id       INTEGER NOT NULL REFERENCES segmentos(id),
    feature_id        INTEGER NOT NULL REFERENCES feature_metadata(id),
    ativo_por_padrao  BOOLEAN NOT NULL DEFAULT FALSE,
    atualizado_em     TIMESTAMP,
    CONSTRAINT uq_segmento_feature_padrao UNIQUE (segmento_id, feature_id)
);

CREATE INDEX ix_segmento_feature_padrao_segmento_id
    ON segmento_feature_padrao (segmento_id);
```

Migration Alembic equivalente (seguindo o estilo exato de
`migrations/versions/c5d7f9a1b3e5_segmentos_e_rotulos.py`):

```python
"""segmento feature padrao

Revision ID: <gerado pelo alembic>
Revises: df41b77230dd
Create Date: <data da implementação>

"""
from alembic import op
import sqlalchemy as sa


revision = '<gerado>'
down_revision = 'df41b77230dd'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('segmento_feature_padrao',
        sa.Column('id',               sa.Integer(), nullable=False),
        sa.Column('segmento_id',      sa.Integer(), nullable=False),
        sa.Column('feature_id',       sa.Integer(), nullable=False),
        sa.Column('ativo_por_padrao', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('atualizado_em',    sa.DateTime()),
        sa.ForeignKeyConstraint(['segmento_id'], ['segmentos.id']),
        sa.ForeignKeyConstraint(['feature_id'], ['feature_metadata.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('segmento_id', 'feature_id', name='uq_segmento_feature_padrao'),
    )
    op.create_index(
        'ix_segmento_feature_padrao_segmento_id',
        'segmento_feature_padrao', ['segmento_id'],
    )


def downgrade():
    op.drop_index('ix_segmento_feature_padrao_segmento_id', table_name='segmento_feature_padrao')
    op.drop_table('segmento_feature_padrao')
```

`down_revision` aponta para `df41b77230dd` (head atual confirmado no
inventário, Parte A.4) — **precisa ser reconfirmado no momento da
implementação** caso outras migrations tenham sido criadas entre a data
deste documento e a implementação real.

### D.2 Como popular a tabela inicial: manual, migration, ou seed?

Recomendo o **mesmo padrão já usado para `Segmento`/`SegmentoRotulo`**:
função idempotente em `app/seeds.py`, **não** dados hardcoded na própria
migration (migrations no projeto só criam schema, nunca populam dados de
negócio — confirmado revisando todas as 17 migrations existentes no
inventário, nenhuma faz `op.bulk_insert`).

Proposta de função nova em `app/seeds.py`, espelhando `seed_segmentos()`
(linha 104-128):

```python
# Combinação padrão de features por segmento — dados de PRODUTO, decididos
# pelo dono (ver C.2 item 7). Placeholder abaixo é ilustrativo, não a
# decisão final.
_SEGMENTO_FEATURES_PADRAO = {
    'barbearia': {'produtos_venda': True, 'comissao': True, 'notificacoes': True},
    'salao':     {'produtos_venda': True, 'planos': True, 'vip_brindes': True},
    'manicure':  {'produtos_venda': True},
    'clinica':   {'historico_cliente': True, 'notificacoes': True},
}


def seed_segmento_feature_padrao():
    """Popula os padrões de feature por segmento. Idempotente."""
    from app.models import Segmento, FeatureMetadata, SegmentoFeaturePadrao
    for chave, features in _SEGMENTO_FEATURES_PADRAO.items():
        seg = Segmento.query.filter_by(chave=chave).first()
        if not seg:
            continue
        for nome_feature, ativo in features.items():
            fm = FeatureMetadata.query.filter_by(nome=nome_feature).first()
            if not fm:
                continue
            row = SegmentoFeaturePadrao.query.filter_by(
                segmento_id=seg.id, feature_id=fm.id
            ).first()
            if not row:
                row = SegmentoFeaturePadrao(segmento_id=seg.id, feature_id=fm.id)
                db.session.add(row)
            row.ativo_por_padrao = ativo
    commit_ou_falhar('seeds.seed_segmento_feature_padrao')
    print('[seed] SegmentoFeaturePadrao sincronizado.')
```

Rodada via CLI (`flask seed-segmento-features`, novo comando espelhando os
existentes `flask seed-metadata`/`flask seed-admin` — ver onde esses
comandos são registrados, provavelmente `app/__init__.py` ou um
`cli.py`, **verificar na implementação**).

`_SEGMENTO_FEATURES_PADRAO` acima é **ilustrativo, não a decisão real** —
o valor de cada combinação segmento→features é 100% decisão de produto do
dono (C.2 item 7), não uma inferência técnica.

### D.3 Migrations necessárias nas tabelas existentes

Nenhuma migration em tabela existente é estritamente necessária para o
schema de `SegmentoFeaturePadrao` em si (é tabela nova, isolada). Porém, a
modelagem completa desta frente toca comportamento (não schema) em dois
pontos que vale registrar aqui para não serem esquecidos na implementação:

- `criar_barbearia()` passa a aceitar `segmento_id` no payload — **não
  precisa de migration**, `Barbearia.segmento_id` já existe (nullable,
  desde `c5d7f9a1b3e5_segmentos_e_rotulos.py`).
- Nenhuma alteração de coluna é necessária em `FeatureBarbearia`,
  `FeatureMetadata`, `Segmento` ou `SegmentoRotulo`.

Se o dono decidir (C.2 item 4) que `agendamento_login` deve de fato
controlar `ConfiguracaoAgendamento.quick_booking_sem_login`
automaticamente, **isso também não exige migration** — o campo já existe
(`app/models/__init__.py:838`), só falta a lógica de leitura/escrita.

---

## PARTE E — FLUXOS

### E.1 Fluxo completo — criar uma barbearia nova (com as alterações propostas)

```
1. Super admin preenche formulário em super/barbearias.html:
   nome, slug, nome_exibicao, gestor_*, endereço + [NOVO] segmento (select)
2. Frontend chama POST /api/v1/super/barbearias com segmento_id no body
3. criar_barbearia() (super/barbearias.py):
   a. Valida campos obrigatórios (como hoje)
   b. [NOVO] Se segmento_id vier: valida que o Segmento existe (404 se não)
   c. Cria Barbearia (agora com segmento_id preenchido, se houver)
   d. flush() para obter barbearia.id
   e. Cria Usuario gestor (como hoje)
   f. Cria BarbeariaCustomizacao, ConfiguracaoAgendamento (como hoje)
   g. [ALTERADO] Para cada FeatureMetadata:
        - Busca override em SegmentoFeaturePadrao (se houver segmento)
        - ativo = override ?? FeatureMetadata.ativo_por_padrao
        - Cria FeatureBarbearia com esse ativo
   h. commit_ou_falhar (atômico, como hoje)
4. Resposta 201 com barbearia + gestor (formato inalterado, ou
   [OPCIONAL] incluir lista de features já resolvidas, para a tela
   confirmar visualmente o que foi ativado)
```

### E.2 Fluxo completo — trocar o segmento de uma barbearia existente

```
1. Super admin abre [NOVO] formulário de atribuição de segmento em
   super/barbearias.html (hoje não existe — ver A.4 item 4)
2. Frontend chama PATCH /api/v1/super/barbearias/<id>/segmento
   com { segmento_id, reajustar_features: bool }
3. patch_barbearia_segmento() (super/barbearias.py):
   a. Busca Barbearia (404 se não existe, como hoje)
   b. Guarda segmento_id_antigo = b.segmento_id
   c. Valida novo Segmento (404 se não existe, como hoje)
   d. Grava b.segmento_id = seg.id (como hoje)
   e. [NOVO] L.invalidar(segmento_id_antigo); L.invalidar(seg.id)
   f. [NOVO] Se reajustar_features=True:
        - Busca SegmentoFeaturePadrao do novo segmento
        - Para cada override: upsert em FeatureBarbearia
        - Acumula lista de mudanças (feature, valor_antigo, valor_novo)
   g. [NOVO] Grava AuditoriaLog (tipo_acao='edit', entidade='Barbearia',
      descricao com segmento_antigo → segmento_novo)
   h. commit_ou_falhar
4. Resposta 200 com segmento_id + [NOVO] lista de features alteradas
   (vazia se reajustar_features=False ou se não houve override aplicável)
```

### E.3 Fluxo de ativação/desativação — as 4 "features decorativas"

**`relatorios_avancados`** (depende de C.2 item 3 estar resolvido):
```
Super ativa/desativa via PUT /super/barbearias/<id>/features/relatorios_avancados
  → grava FeatureBarbearia.ativo (já funciona hoje, mecânica inalterada)
Gestor acessa GET /gestor/relatorios/<endpoint-avancado>
  → [NOVO] @feature_required('relatorios_avancados') bloqueia com 403 se off
```

**`agendamento_login`**:
```
Super ativa a feature para a barbearia (mecânica já existe)
  → [NOVO] ao ativar, sistema seta ConfiguracaoAgendamento.quick_booking_sem_login = False
  → [NOVO] ao desativar, seta de volta para True
Cliente público tenta agendar sem login (POST /api/v1/pub/<slug>/agendar)
  → _criar_agendamento_core lê configuracao_agendamento.quick_booking_sem_login
  → Se False: exige g.user_id de perfil 'cliente' válido, senão 401/403
```
(Alternativa mais simples, sem sincronizar dois campos: `_criar_agendamento_core`
checa a feature diretamente via `feature_ativa()`, ignorando
`quick_booking_sem_login` como campo redundante. DECISÃO PENDENTE — a
modelagem aponta as duas opções; a segunda é mais simples de implementar,
a primeira preserva o campo já existente no model como fonte de verdade
única e mais granular por-tenant sem depender de feature global.)

**`fila_espera`** (fora do escopo mínimo desta frente, ver B.4c):
```
[NÃO MODELADO NESTA FRENTE] — exigiria endpoints novos de CRUD sobre
FilaEspera antes de qualquer gate de feature fazer sentido. Se o dono
quiser priorizar, é um documento de modelagem à parte.
```

**`pix_integrado`**:
```
Super ativa/desativa via PUT .../features/pix_integrado (já funciona hoje)
Gestor tenta PUT /gestor/agendamentos/<id>/aprovar
  → [NOVO] @feature_required('pix_integrado') bloqueia com 403 se off
Barbeiro tenta PATCH /barbeiro/agendamentos/<id>/aprovar-comprovante
  → [NOVO] @feature_required('pix_integrado') bloqueia com 403 se off
Sidebar do gestor (já funciona hoje) esconde o link se off — sem mudança
```

---

## PARTE F — APIs

Contrato completo de **todas** as alterações de API propostas por esta
modelagem. Endpoints já existentes e inalterados não são listados de novo.

### F.1 `POST /api/v1/super/barbearias` (alterado)

- **Método/rota**: inalterados.
- **Novo campo no body**: `segmento_id` (int, opcional, nullable).
- **Validação nova**: 404 `"Segmento não encontrado."` se `segmento_id`
  vier e não existir.
- **Retorno**: formato inalterado (`{mensagem, barbearia, gestor}`);
  `barbearia` (via `_fmt_barbearia`) já deve incluir `segmento_id` se essa
  função já o serializa hoje — **verificar `_fmt_barbearia` na
  implementação**, não confirmado nesta sessão se o campo já está no
  serializer.

### F.2 `PATCH /api/v1/super/barbearias/<int:barbearia_id>/segmento` (alterado)

- **Método/rota**: inalterados.
- **Novo campo no body**: `reajustar_features` (bool, opcional, default
  `False`).
- **Retorno alterado**:
  ```json
  {
    "mensagem": "Segmento atualizado.",
    "segmento_id": 3,
    "features_alteradas": [
      {"feature": "vip_brindes", "de": false, "para": true}
    ]
  }
  ```
  (`features_alteradas` sempre presente, lista vazia se
  `reajustar_features=False` ou sem overrides aplicáveis — evita quebrar
  chamadores existentes que só leem `segmento_id`.)

### F.3 `GET /api/v1/cliente/features` (novo)

- **Método/rota**: `GET /api/v1/cliente/features`
- **Auth**: `@cliente_required`
- **Parâmetros**: nenhum (usa `g.barbearia_id` do contexto de sessão do
  cliente, como os equivalentes de gestor/barbeiro).
- **Retorno 200**:
  ```json
  [
    {"nome": "planos", "descricao": "Planos de assinatura mensal para clientes", "ativo": true},
    {"nome": "vip_brindes", "descricao": "Programa VIP com níveis e brindes por fidelidade", "ativo": false}
  ]
  ```
  (array com as 11 features do catálogo, mesmo formato de
  `GET /gestor/features` e `GET /barbeiro/features`.)
- **Quem chama**: `frontend/src/api.js` (novo método `api.features.listar()`
  a ser adicionado), consumido pelas páginas React
  (`Planos.jsx`, `Beneficios.jsx`, `Historico.jsx` etc.) para
  esconder/mostrar seções conforme a feature correspondente.

### F.4 Endpoints existentes que ganham `@feature_required` (novo gate, mesma rota/método)

| Rota | Método | Feature adicionada |
|---|---|---|
| `/api/v1/gestor/agendamentos/<id>/aprovar` | PUT | `pix_integrado` |
| `/api/v1/barbeiro/agendamentos/<id>/aprovar-comprovante` | PATCH | `pix_integrado` |
| `/api/v1/gestor/relatorios/...` (subconjunto avançado — a definir em C.2.3) | GET | `relatorios_avancados` |

Nenhum desses gates muda a rota, método ou payload — apenas adiciona
possibilidade de resposta `403` (`{"erro": "Feature \"...\" não está ativa
para esta barbearia."}`, formato já padronizado por `APIError` em
`feature_required`).

### F.5 `GET /api/v1/gestor/segmentos-feature-padrao/<int:segmento_id>` (novo, administrativo)

Não mencionado explicitamente no pedido, mas necessário para a UI de
D.2/E.2 existir: o super admin precisa de uma tela para editar
`SegmentoFeaturePadrao` por segmento (equivalente a `segmento_rotulos.html`,
mas para features).

- **Método/rota**: `GET /api/v1/super/segmentos/<int:segmento_id>/features`
- **Auth**: `@super_required`
- **Retorno 200**:
  ```json
  [
    {"feature": "produtos_venda", "descricao": "...", "ativo_por_padrao": true, "origem": "segmento"},
    {"feature": "cupons", "descricao": "...", "ativo_por_padrao": false, "origem": "global"}
  ]
  ```
  (`origem: "segmento"` = tem linha em `SegmentoFeaturePadrao`; `origem:
  "global"` = fallback para `FeatureMetadata.ativo_por_padrao`, sem
  override — ajuda a UI a distinguir visualmente o que foi customizado.)

### F.6 `PUT /api/v1/super/segmentos/<int:segmento_id>/features/<nome_feature>` (novo, administrativo)

- **Método/rota**: `PUT /api/v1/super/segmentos/<int:segmento_id>/features/<nome_feature>`
- **Auth**: `@super_required`
- **Body**: `{"ativo_por_padrao": true}`
- **Comportamento**: upsert em `SegmentoFeaturePadrao` (mesmo padrão de
  `toggle_feature`, `super/barbearias.py:333-355` — busca existente, cria
  se não existir).
- **Retorno 200**: `{"feature": "vip_brindes", "segmento_id": 2, "ativo_por_padrao": true, "mensagem": "Padrão atualizado."}`

---

## PARTE G — IMPLEMENTAÇÃO

### G.1 Arquivos `.py` a alterar, com todas as funções afetadas

**`app/models/__init__.py`**
- Adicionar classe `SegmentoFeaturePadrao` (nova, após `FeatureBarbearia`,
  linha ~730).

**`migrations/versions/`**
- Novo arquivo de migration (D.1) — cria `segmento_feature_padrao`.

**`app/seeds.py`**
- Nova função `seed_segmento_feature_padrao()` + constante
  `_SEGMENTO_FEATURES_PADRAO` (D.2).
- Registrar novo comando CLI (verificar onde os comandos `seed-metadata`/
  `seed-admin` são registrados — provavelmente em `app/__init__.py` ou
  arquivo de CLI dedicado, não confirmado nesta sessão).

**`app/routes/super/barbearias.py`**
- `criar_barbearia()` (linha 108-191) — aceitar `segmento_id`, resolver
  overrides de `SegmentoFeaturePadrao` (E.1).
- `patch_barbearia_segmento()` (linha 705-722) — aceitar
  `reajustar_features`, invalidar cache de rótulos, gravar auditoria,
  aplicar overrides condicionalmente (E.2).
- Duas funções novas: `listar_segmento_features(segmento_id)` (F.5) e
  `toggle_segmento_feature(segmento_id, nome_feature)` (F.6).
- `_fmt_barbearia()` — confirmar/garantir que `segmento_id` está no
  serializer.

**`app/routes/gestor/agendamento.py`**
- `aprovar_agendamento()` — adicionar `@feature_required('pix_integrado')`
  (E.3).

**`app/routes/barbeiro/agendamentos.py`**
- `aprovar_comprovante()` — adicionar `@feature_required('pix_integrado')`
  (E.3).

**`app/routes/gestor/relatorios.py`**
- Endpoint(s) definidos como "avançado" após C.2.3 — adicionar
  `@feature_required('relatorios_avancados')`.

**`app/routes/pub/agendamento.py`**
- `_criar_agendamento_core()` — checar `agendamento_login` (via
  `ConfiguracaoAgendamento.quick_booking_sem_login` ou direto via
  `feature_ativa`, conforme decisão de E.3).

**`app/routes/cliente/features.py`** (novo arquivo)
- `listar_features()` — espelha `gestor/features.py:listar_features` (F.3).
- Registrar blueprint em `app/__init__.py` (novo
  `register_blueprint(cliente_features_bp)`).

**`app/labels.py`**
- Nenhuma mudança de código necessária — já tem `L.get()`/`L.todos()`
  prontos. Mudança é de **uso**: os templates/rotas que hoje chamam
  `L('chave')` estático precisariam trocar para `L.get(g.barbearia.segmento_id,
  'chave')` para o vocabulário dinâmico finalmente ter efeito — **isso é um
  escopo maior, tocando muitos arquivos de template/rota, e não está
  contado no cronograma abaixo** porque é a Frente 3 (recriação de
  frontend) ou um documento de modelagem à parte, não a Frente 1. Registrado
  aqui só para não ser esquecido — é um pré-requisito latente para
  qualquer segmento não-"barbearia" parecer de fato diferente na UI.

**`app/templates/gestor/base.html`**
- Bloco JS de features (linha 526-553) — generalizar para loop orientado a
  dados, adicionar `id`/`style="display:none"` aos links de Planos e VIP
  (B.6).

**`app/templates/super/barbearias.html`**
- Adicionar campo de seleção de segmento no formulário de criação de
  barbearia, e (novo) formulário/modal de atribuição de segmento a
  barbearia existente com o toggle `reajustar_features`.

**`app/templates/super/segmentos.html`** (ou novo template)
- Nova seção/tela para editar `SegmentoFeaturePadrao` por segmento
  (consumindo F.5/F.6).

**`frontend/src/api.js`**
- Novo método `api.features.listar()` (F.3).

**`frontend/src/pages/*.jsx`**
- `Planos.jsx`, `Beneficios.jsx`, `Historico.jsx` — consumir features para
  esconder/mostrar seções conforme aplicável.

### G.2 Estimativa de horas por etapa

| Etapa | Escopo | Horas |
|---|---|---|
| Banco de dados | Model `SegmentoFeaturePadrao` + migration + testar upgrade/downgrade | 2h |
| Seeds | `seed_segmento_feature_padrao()` + comando CLI + validar idempotência | 2h |
| `criar_barbearia` | Aceitar `segmento_id`, resolver overrides, testes | 3h |
| `patch_barbearia_segmento` | `reajustar_features`, invalidação de cache, auditoria, testes | 4h |
| Endpoints admin de `SegmentoFeaturePadrao` (F.5/F.6) | 2 rotas novas + serialização + testes | 3h |
| `GET /api/v1/cliente/features` | Endpoint novo + blueprint + registro + testes | 2h |
| Gate `pix_integrado` (2 endpoints) | Decorator + testes de regressão (garantir que aprovação sem PIX continua ok) | 2h |
| Gate `relatorios_avancados` (depende de C.2.3 resolvida) | Decorator nos endpoints definidos + testes | 3h |
| `agendamento_login` (depende de decisão em E.3) | Lógica de leitura + testes de quick-booking | 4h |
| Sidebar do gestor (`base.html`) | Refatorar JS + adicionar ids Planos/VIP + teste manual visual | 2h |
| UI super — seleção de segmento na criação de barbearia | Form + integração API | 3h |
| UI super — atribuição/troca de segmento em barbearia existente (tela nova, hoje não existe) | Form/modal + integração API + preview de `features_alteradas` | 5h |
| UI super — edição de `SegmentoFeaturePadrao` por segmento (tela nova) | Tela completa (lista + toggle por feature) | 5h |
| Frontend cliente (`api.js` + páginas React) | Método novo + consumo em 3 páginas | 4h |
| `fila_espera` | **Fora de escopo** desta frente (ver B.4c/E.3) | 0h |
| Testes de regressão gerais + revisão de auditoria (`AuditoriaLog`) | Rodar suíte, checar que fluxos antigos continuam ok | 4h |
| **TOTAL** | | **44h** |

**Total em dias (44h / 8h por dia útil): ≈ 5,5 dias** de trabalho de
implementação, assumindo que as decisões de produto pendentes (C.2) já
estejam resolvidas antes de começar — se não estiverem, as linhas
`relatorios_avancados` (3h) e `agendamento_login` (4h) e a definição de
`_SEGMENTO_FEATURES_PADRAO` real (parte de "Seeds", 2h) ficam bloqueadas até
o dono decidir, o que pode adicionar dias de espera (não de trabalho) ao
cronograma.

---

## Resumo de decisões pendentes (para validação do dono antes de implementar)

1. Fallback de `SegmentoFeaturePadrao` sem override — usa padrão global? (D.1/C.2.1)
2. Reajuste de features ao trocar segmento — automático ou opt-in? (B.3/C.2.2)
3. `relatorios_avancados` — quais relatórios são "avançados"? (B.4a/C.2.3)
4. `agendamento_login` — via `quick_booking_sem_login` ou feature direta? (E.3/C.2.4)
5. `fila_espera` — construir lógica de negócio agora ou manter fora? (B.4c/C.2.5)
6. Features sem enforcement viável — remover do catálogo ou manter sinalizadas? (C.2.6)
7. Combinação real de `SegmentoFeaturePadrao` para os 4 segmentos seedados — decisão de produto pura (D.2/C.2.7)

Nenhuma linha de código foi alterada para produzir este documento.
