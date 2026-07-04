# Banco de Dados

PostgreSQL, gerenciado via Flask-Migrate (Alembic). Todos os models vivem em **um único arquivo**: `app/models/__init__.py`. Migrations em `migrations/versions/`.

Migration head atual: `843668e4f632` (cupons).

## Padrão multi-tenant

Models que pertencem a uma barbearia específica herdam `TenantMixin` (`app/models/mixins.py`), que injeta a coluna `barbearia_id` e o método `query_tenant()` (filtra automaticamente por `g.barbearia_id`). Ver `Arquitetura.md` para o porquê.

Models com `TenantMixin` hoje: `Servico`, `Produto`, `Agendamento`, `HorarioBloqueado`, `Atendimento`, `SolicitacaoLiberacao`, `Plano`, `VipNivel`, `Cupom`.

## Tabelas por domínio

**Core / tenant**
- `barbearias` (`Barbearia`) — o tenant raiz
- `segmentos` (`Segmento`), `segmento_rotulos` (`SegmentoRotulo`) — base do multi-segmento futuro (ver `Roadmap.md`)
- `usuarios` (`Usuario`) — login (staff e cliente, mesmo model, diferenciado por `perfil`)
- `barbeiros` (`Barbeiro`), `clientes` (`Cliente`)

**Catálogo**
- `servicos` (`Servico`), `barbeiro_servicos` (`BarbeiroServico`)
- `produtos` (`Produto`)

**Agenda**
- `configuracao_agenda` (`ConfiguracaoAgenda`), `configuracao_agendamento` (`ConfiguracaoAgendamento`)
- `agendamentos` (`Agendamento`), `agendamento_servicos` (`AgendamentoServico`)
- `agendamento_solicitacao_pix` (`AgendamentoSolicitacaoPix`)
- `horarios_bloqueados` (`HorarioBloqueado`), `pausa_barbeiro` (`PausaBarbeiro`)
- `fila_espera` (`FilaEspera`)

**Caixa / atendimento**
- `atendimentos` (`Atendimento`), `atendimento_itens` (`AtendimentoItem`)
- `pagamentos` (`Pagamento`), `reservas_produtos` (`ReservaProduto`)
- `barbeiro_comissao_servico` (`BarbeiroComissaoServico`)

> Atenção: o fluxo de caixa/PDV (`Atendimento`/`Pagamento`) tem model pronto, mas a tela V2 correspondente (`barbeiro/caixa.html`) ainda usa JS legado quebrado — é um gap de produto, não só sobra de código. Ver `Roadmap.md`.

**Planos / assinatura**
- `planos` (`Plano`), `plano_servicos` (`PlanoServico`), `plano_barbeiros` (`PlanoBarbeiro`)
- `cliente_plano` (`ClientePlano`), `cliente_plano_uso` (`ClientePlanoUso`), `cliente_plano_solicitacao` (`ClientePlanoSolicitacao`)

**VIP**
- `vip_niveis` (`VipNivel`), `cliente_vip` (`ClienteVip`)

> CRUD de níveis VIP pelo gestor também é gap de produto (hoje só leitura no app do cliente). Ver `Roadmap.md`.

**Cupons** (mais recente, MVP já entregue)
- `cupons` (`Cupom`)

**Plataforma / governança**
- `feature_metadata` (`FeatureMetadata`), `feature_barbearia` (`FeatureBarbearia`) — feature flags, ver `Features.md`
- `auditoria_log` (`AuditoriaLog`)
- `solicitacoes_senha` (`SolicitacaoSenha`), `solicitacoes_liberacao` (`SolicitacaoLiberacao`)
- `barbearia_customizacao` (`BarbeariaCustomizacao`)
- `cliente_notas` (`ClienteNota`)
- `notificacoes` (`Notificacao`)

## Migrations — fluxo de trabalho

```
flask db migrate -m "descrição"   # gera nova revisão a partir do diff dos models
flask db upgrade                  # aplica no banco
flask db heads                    # confirma head único (evitar múltiplos heads)
```

Já houve necessidade de `merge_heads` uma vez (`992b53c7662d`) — atenção ao criar migrations em paralelo a outras em andamento.

## Dívidas técnicas conhecidas

- **DT-001:** uso de `datetime.utcnow()` em vez de datetime timezone-aware. Resolver antes do deploy em produção — risco de erro de horas em slots de agendamento e cancelamento (Railway roda em UTC, negócio é UTC-3).
