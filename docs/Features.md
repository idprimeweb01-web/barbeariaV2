# Sistema de Feature Flags

Permite ligar/desligar funcionalidades por barbearia, sem deploy separado. Pensado desde o início para suportar múltiplos perfis de negócio (ver `Roadmap.md` — multi-segmento).

## Como funciona

- `FeatureMetadata` — catálogo global de features existentes na plataforma (nome técnico + descrição).
- `FeatureBarbearia` — liga uma `FeatureMetadata` a uma `barbearia_id` específica com `ativo: bool`.
- `app/utils/features.py`:
  - `feature_ativa(barbearia_id, nome) -> bool` — true só se existir registro `FeatureBarbearia` ativo para aquele par.
  - `feature_required(nome)` — decorator de rota; lança `APIError(403)` se a feature não estiver ativa para `g.barbearia_id`.

```python
@feature_required('cupons')
def listar_cupons():
    ...
```

- O catálogo de features (`FeatureMetadata`) é sincronizado via seed (`app/seeds.py`, `seed_feature_metadata()`), idempotente — seguro rodar múltiplas vezes.
- Ativação/desativação por barbearia é feita pela tela `super/features.html` (super admin liga/desliga por tenant) e também há uma visão em `gestor/features.py`.

## Features hoje cadastradas (seed)

| nome                  | descrição                                                  |
|-----------------------|-------------------------------------------------------------|
| `planos`              | Planos de assinatura mensal para clientes                  |
| `relatorios_avancados`| Relatórios customizáveis e exportação Excel/PDF             |
| `vip_brindes`         | Programa VIP com níveis e brindes por fidelidade            |
| `agendamento_login`   | Exige login do cliente para agendar online                  |
| `historico_cliente`   | Histórico completo de atendimentos por cliente               |
| `cupons`              | Cupons de desconto para clientes                            |
| `fila_espera`         | Lista de espera para horários lotados                       |
| `comissao`            | Cálculo de comissão por barbeiro (avulso e plano)            |
| `notificacoes`        | Notificações por SMS/WhatsApp/e-mail                         |
| `pix_integrado`       | Pagamento PIX com comprovante e aprovação manual             |

> Nem toda feature listada acima tem `@feature_required` aplicado em código ainda (ex.: `notificacoes`, `pix_integrado`, `comissao` existem no catálogo mas o gate em rota só está confirmado em `cupons` e `historico_cliente` até o momento). Verificar no código antes de assumir que uma feature está de fato gateando alguma rota.

## Regra de ouro

Funcionalidade nova "opcional por barbearia" → catalogar em `FEATURES` (`app/seeds.py`) + aplicar `@feature_required('nome')` na(s) rota(s) correspondente(s). Não inventar outro mecanismo de flag paralelo.
