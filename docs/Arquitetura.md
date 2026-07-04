# Arquitetura

> Documento "congelado" — registra decisões já tomadas. Não é um README de onboarding completo. Para o raio-x detalhado de código morto/legado, ver `ANALISE_ARQUITETURA_V1_V2.txt` na raiz do projeto.

## Stack

- **Backend:** Flask + SQLAlchemy + Flask-Migrate (Alembic) + Flask-JWT-Extended
- **Banco:** PostgreSQL
- **Frontend:** server-rendered (Jinja2) + JS vanilla por tela, sem framework SPA
- **Deploy:** Railway

## V1 (legado) vs V2 (ativo) — decisão já tomada

Existem dois "projetos" fisicamente no mesmo repositório:

- **V2 (ativo, é o que roda em produção):** blueprints organizados em `app/routes/<papel>/` (subpastas: `gestor/`, `barbeiro/`, `cliente/`, `super/`, `pub/`, `views/`). Todo blueprint usado de fato é importado e registrado explicitamente em `app/__init__.py` via `app.register_blueprint(...)`.
- **V1 (legado):** arquivos soltos direto em `app/routes/*.py` (ex.: `agenda.py`, `gestor_admin.py`, `publica.py`, `caixa.py`, `vip.py`, etc.). **Nenhum desses arquivos é importado em `app/__init__.py`** — ou seja, não rodam, não atendem requisição nenhuma. Foram a versão de exemplo/protótipo inicial e deveriam ter sido descartados quando o V2 foi construído do zero.

Regra prática: **se um blueprint não aparece em `app.register_blueprint(...)` dentro de `app/__init__.py`, ele é código morto.** Esse é o teste de verdade para "vivo" vs "morto" no backend.

O mesmo vale para templates: **um template só é alcançável se aparecer como argumento de `render_template(...)` em algum arquivo dentro de `app/routes/`.** Templates fora desse grafo são órfãos.

A limpeza desse código morto é trabalho planejado (ver `Roadmap.md`, Fase 1), ainda não executado.

## Padrões centrais (V2)

### Contexto por requisição
`app/context.py` → `load_user_context()`, registrado via `app.before_request`. Roda em **toda** requisição (inclusive públicas), faz `verify_jwt_in_request(optional=True)` e popula `g.user_id` / `g.perfil` / `g.barbearia_id` se houver um JWT válido (cookie ou header). É isso que permite rotas públicas (`pub/`) detectarem um cliente já logado sem decorator extra.

### Autorização por papel
`app/decorators/auth.py` — `cliente_required`, `barbeiro_required`, `gestor_required`, `super_required`, todos construídos sobre um helper comum `_require(perfis, allow_super=True)` que lança `APIError(401)` se não houver usuário e `APIError(403)` se o perfil não bater.

### Multi-tenant
`app/models/mixins.py` → `TenantMixin`. Adiciona coluna `barbearia_id` via `@declared_attr` a qualquer model e expõe `query_tenant()`, que filtra automaticamente por `g.barbearia_id`. É fail-safe: se `g.barbearia_id` não existir e o perfil não for `super_admin`, retorna query vazia (nunca não-filtrada).

### Feature flags por barbearia
`app/utils/features.py` → `feature_required(nome)` (decorator) + `feature_ativa(barbearia_id, nome)`, apoiados nos models `FeatureMetadata`/`FeatureBarbearia`. Permite ligar/desligar funcionalidades (ex.: `cupons`) por barbearia sem deploy separado. Detalhes em `Features.md`.

### Erros centralizados
`APIError` (`app/exceptions.py`), capturado globalmente em `app/__init__.py` via `@app.errorhandler(APIError)`, sempre devolvendo `{"erro": "..."}`.

## Frontend (V2)

- **Client JS único e ativo:** `app/static/js/bos.js` (`Bos`). Baseado em cookie (`credentials: 'same-origin'`), sem localStorage, base path `/api/v1`. Métodos: `get/post/patch/put/delete/upload/logout`. Faz retry automático em 401 via refresh, e redireciona para `window.BOS_LOGIN_URL` (configurável por shell, default `/entrar`).
- `api.js` (legado, localStorage + `Authorization: Bearer` manual) está **morto** — usado só por um template já órfão. Não usar em código novo.
- Cada papel tem seu `base.html` (`gestor/base.html`, `barbeiro/base.html`, `cliente/base.html`, `super/base.html`) que carrega `bos.js` e define o shell/navegação daquele papel.

## Autenticação

- Staff (`gestor`/`barbeiro`/`super`): login único em `/entrar` (não tem slug).
- Cliente: login/cadastro **escopados por barbearia**, via slug: `/b/<slug>/entrar` e `/b/<slug>/cadastro`. Fluxo separado do staff.
- Cookies: `bos_at` (access, 15 min) e `bos_rt` (refresh, 30 dias). Config JWT em `app/__init__.py`: `JWT_TOKEN_LOCATION=['headers','cookies']`, `JWT_COOKIE_SAMESITE='Lax'`, `JWT_COOKIE_CSRF_PROTECT=False`.

Fluxos completos (passo a passo, por persona) estão em `Fluxos.md`.
