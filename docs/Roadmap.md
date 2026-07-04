# Roadmap

Registro de decisões e próximos passos. Atualizar conforme fases avançam — não é necessário detalhar tarefas de implementação aqui (isso fica em PRs/commits), só o estado das fases e decisões em aberto.

## Fase 0 — Congelar a arquitetura ✅

Concluída. Este `docs/` (Arquitetura, Banco, Features, Fluxos, Roadmap) registra o estado atual do sistema antes de iniciar a limpeza de código legado.

## Fase 1 — Remover código morto (em andamento, pausada)

Baseado em `ANALISE_ARQUITETURA_V1_V2.txt`. Resumo: V1 não está estruturalmente misturado ao V2 (nenhum blueprint legado é importado), mas ~6.572 linhas de Python morto e diversos templates órfãos continuam no disco, além de 6 páginas "híbridas" (rota V2 real, mas JS legado `api.js` que não existe mais no shell — quebram com `ReferenceError` se acessadas direto pela URL).

**1.1 Remover código morto** ✅ (executado via `automate_cleanup_and_fix.py`, script mantido no repo para auditoria)
- [x] Apagar rotas V1 realmente inutilizadas — 13 dos 15 arquivos soltos em `app/routes/` (`caixa.py` e `vip.py` mantidos de propósito, ver abaixo)
- [x] Remover templates órfãos (8 confirmados, nunca renderizados por nenhuma rota)
- [x] Remover JS legado (`api.js`, `upload-widget.js`)
- [x] Verificar scripts de teste na raiz (`pw_*.py`, `test_*.py`) — nenhum importava os módulos removidos
- [x] Conferir imports quebrados após as remoções + reiniciar servidor — boot limpo, 189 rotas registradas, smoke test ok

**Decisão em aberto antes de apagar (não são só sobra, são gap de produto):**
- `barbeiro/caixa.html` + `app/routes/caixa.py` (PDV/checkout) — sem equivalente V2. Decidir: reconstruir no V2 ou descartar de vez (negócio ainda precisa de PDV?).
- `gestor/vip.html` + `app/routes/vip.py` (CRUD de níveis VIP pelo gestor) — V2 hoje só tem leitura (`cliente/beneficios.html` mostra nível atual), sem tela de administração. Decidir: criar CRUD V2 ou manter só leitura por ora.
- `gestor/esqueci_senha.html` — órfão dos dois lados (V1 quebrado e o link "Esqueci a senha" no `staff/login.html` é `href="#"`, não funcional). Decidir se recuperação de senha de gestor é uma necessidade real agora.

**Risco identificado para não reativar V1 por engano:**
- `app/routes/cliente_perfil.py` (legado) define `Blueprint('cliente_perfil', ...)` — mesmo nome interno do blueprint novo registrado (`app/routes/cliente/perfil.py`). Reativar sem renomear quebra o boot do Flask.
- `app/routes/publica.py` (legado) usa `url_prefix='/b'`, mesmo prefixo já usado pelo `views_bp` ativo.

## Fases seguintes (a definir)

Mais fases serão adicionadas a este roadmap conforme forem decididas. Não inventar escopo aqui — só registrar o que já foi efetivamente combinado.

## Dívidas técnicas

- **DT-001:** ✅ Resolvida. `datetime.utcnow()`/`date.today()` usados em lógica de negócio (slots, dashboards, cancelamento, expiração de cupom, aprovação de plano, relatórios) foram trocados por `naive_brasilia()`/`hoje_brasilia()` (`app/utils/tz.py`). Arquivos corrigidos: `app/utils/vip.py`, `app/utils/scheduler.py`, `app/routes/cliente/agendamento.py`, `app/routes/cliente/dashboard.py`, `app/routes/cliente/planos.py`, `app/routes/barbeiro/dashboard.py`, `app/routes/barbeiro/agendamentos.py`, `app/routes/gestor/dashboard.py`, `app/routes/gestor/clientes.py`, `app/routes/gestor/planos.py`, `app/routes/gestor/cupons.py`, `app/routes/gestor/relatorios.py`, `app/routes/super/dashboard.py`. Usos de `datetime.utcnow()` que sobraram são *intencionais* — timestamps de auditoria (`criado_em`/`atualizado_em`/`respondido_em`/`aprovado_em`) ou texto explicitamente rotulado "UTC" em relatórios — corretos como estão por convenção do `tz.py`. Validado: `ast.parse()` em todos os arquivos tocados, boot limpo (189 rotas), smoke test HTTP em `/entrar`, `/gestor`, `/barbeiro`, `/super` e endpoints `/api/v1/*` afetados sem erros 500.

## Visão multi-segmento (futuro, não é V1 nem é MVP atual)

A plataforma foi desenhada para ir além de barbearia (salão, clínica, etc.) sem reescrever regra de negócio:
- Rótulos centralizados (`app/labels.py`, models `Segmento`/`SegmentoRotulo`) já existem e têm infraestrutura parcial em `super/barbearias.py` + telas `super/segmentos.html`/`super/segmento_rotulos.html` (em desenvolvimento, ainda não commitado).
- Regra de negócio deve permanecer genérica — evitar hardcode de "barbeiro"/"corte" em lógica nova; usar rótulo por chave.
- Campo `segmento` na `Barbearia` é o ponto de extensão previsto, mas a aplicação completa do multi-segmento ainda não está finalizada — tratar como trabalho futuro, não pendência da Fase 1.
