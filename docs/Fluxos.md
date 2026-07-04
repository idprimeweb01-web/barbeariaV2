# Fluxos

Como as partes do sistema conversam, na prática. Análise de código completa (com mais exemplos) em `ANALISE_ARQUITETURA_V1_V2.txt`.

## Padrão geral de uma tela V2

1. Rota em `app/routes/views/auth.py` (blueprint `views_bp`) faz `render_template('<papel>/<tela>.html', ...)` — só entrega o HTML/shell, sem dados.
2. O template estende `<papel>/base.html`, que carrega `bos.js`.
3. JS da própria tela chama `Bos.get/post/patch/...('/api/v1/...')` ao carregar (`carregar()` ou similar) para buscar os dados de verdade.
4. A chamada cai num blueprint de API em `app/routes/<papel>/*.py`, protegido por decorator de papel (`cliente_required` etc.), que filtra por tenant via `query_tenant()` quando aplicável.
5. Resposta JSON volta pro JS, que renderiza no DOM.

Exemplo concreto — `cliente/dashboard.html` carregando status VIP:

```js
// cliente/dashboard.html
async function carregarVip() {
  const v = await Bos.get('/cliente/vip');
  ...
}
```
```python
# app/routes/cliente/perfil.py
@cliente_bp.get('/vip')
@cliente_required
def status_vip():
    ...
```

## Mapa de telas por papel (rotas reais, registradas)

**Staff (login único, sem slug):** `GET/POST /entrar`, `POST /sair`

**Gestor** (`/gestor/...`): dashboard, barbeiros, serviços, produtos, agenda, clientes, cupons, relatórios, planos, vip, pix-approval, esqueci-senha, configurações/pix

**Barbeiro** (`/barbeiro/...`): dashboard, agendamentos, horário, clientes, configurações, redefinições — **+ páginas híbridas quebradas** (`agenda`, `perfil`, `produtos`, `caixa/<id>`, ver análise de código morto)

**Super admin** (`/super/...`): dashboard, barbearias, gestores, relatórios, features, auditoria, segmentos, segmentos/`<id>`/rotulos, customização

**Cliente** (escopado por barbearia via slug):
- `GET/POST /b/<slug>/entrar` — login do cliente, separado do staff
- `GET/POST /b/<slug>/cadastro` — cadastro
- `GET /b/<slug>` ou `/b/<slug>/` — página pública de agendamento (não exige login; `load_user_context` detecta sozinho se já tem cookie válido)
- `GET /cliente/dashboard` — Home (bottom nav)
- `GET /cliente/agendar` — Agendar
- `GET /cliente/beneficios` — Benefícios (VIP + planos + cupons)
- `GET /cliente/historico` — Histórico
- `GET /cliente/perfil` — Perfil

As 5 últimas formam a bottom nav do app do cliente (MVP entregue).

## Autenticação — dois fluxos distintos

- **Staff:** `/entrar` único, sem slug, perfis `gestor`/`barbeiro`/`super_admin`.
- **Cliente:** `/b/<slug>/entrar` e `/b/<slug>/cadastro`, escopado por barbearia (um cliente pertence a uma barbearia). Propositalmente separado do login de staff.

Ambos resultam no mesmo mecanismo por baixo: cookies `bos_at`/`bos_rt` + `load_user_context()` populando `g.user_id`/`g.perfil`/`g.barbearia_id` em toda requisição subsequente.

## Reuso de rotas públicas pelo app logado

Telas do cliente logado (ex.: `beneficios.html`) chamam direto endpoints **públicos** como `/api/v1/pub/<slug>/planos` em vez de duplicar uma rota autenticada equivalente — porque `load_user_context()` já roda em toda rota, pública ou não, então o backend sabe quem é o cliente mesmo numa rota nominalmente "pública". Evita duplicação de endpoint.

## Exemplo ponta-a-ponta: cliente aplica cupom no agendamento

1. `cliente/agendar.html` → `Bos.post('/pub/<slug>/agendamentos', {..., cupom_codigo})`
2. Cai em `app/routes/pub/agendamento.py` → `_criar_agendamento_core(...)`
3. Que chama `app/utils/cupons.py`:
   - `validar_cupom(codigo, barbearia_id, subtotal)` — checa validade/limite de uso
   - `calcular_desconto(cupom, subtotal)` — aplica percentual ou valor fixo, com cap no subtotal
   - `incrementar_uso_cupom(cupom)` — contabiliza uso após confirmar
4. Resultado persistido em `Agendamento`, resposta volta pro JS, que mostra o valor final.

## Fluxo de erro padronizado

Qualquer `raise APIError(mensagem, status)` em qualquer camada do backend é capturado globalmente (`app/__init__.py`) e vira `{"erro": "..."}` com o status code certo. `Bos` no frontend trata isso de forma uniforme — não existe tratamento de erro "especial" por tela.
