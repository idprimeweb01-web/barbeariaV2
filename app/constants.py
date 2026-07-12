"""
Constantes centralizadas de status/pagamento (Bloco 6.1).

Os valores abaixo NÃO podem ser alterados sem uma migration — são os
mesmos strings já gravados no banco e validados pelos CHECK constraints
criados no Bloco 2.1 (ver migrations/versions/0fc98933f5eb_...).
"""


class StatusAgendamento:
    AGENDADO = 'agendado'
    CONCLUIDO = 'concluido'
    CANCELADO = 'cancelado'
    EM_ATENDIMENTO = 'em_atendimento'
    AGUARDANDO_COMPROVANTE = 'aguardando_comprovante'
    AGUARDANDO_APROVACAO = 'aguardando_aprovacao'
    AGUARDANDO_PAGAMENTO = 'aguardando_pagamento'
    NAO_REALIZADO = 'nao_realizado'
    AGUARDANDO_TRANSFERENCIA = 'aguardando_transferencia'  # Script 17

    TODOS = frozenset({
        AGENDADO, CONCLUIDO, CANCELADO, EM_ATENDIMENTO,
        AGUARDANDO_COMPROVANTE, AGUARDANDO_APROVACAO, AGUARDANDO_PAGAMENTO,
        NAO_REALIZADO, AGUARDANDO_TRANSFERENCIA,
    })
    ATIVOS = frozenset({AGENDADO, AGUARDANDO_COMPROVANTE, AGUARDANDO_APROVACAO})


class MetodoPagamento:
    PIX = 'pix'
    LOCAL = 'local'

    TODOS = frozenset({PIX, LOCAL})


class StatusPagamento:
    """Agendamento.status_pagamento — controle de dívida/recebimento,
    independente do Agendamento.status (que é sobre o atendimento em si)."""
    PENDENTE = 'pendente'
    PAGO = 'pago'

    TODOS = frozenset({PENDENTE, PAGO})


class StatusSolicitacaoPlano:
    PENDENTE = 'pendente'
    APROVADO = 'aprovado'
    REJEITADO = 'rejeitado'

    TODOS = frozenset({PENDENTE, APROVADO, REJEITADO})


class StatusTransferencia:
    """Status de TransferenciaAgendamento (Script 17)."""
    PENDENTE = 'pendente'
    CONCLUIDA = 'concluida'
    REAGENDADA = 'reagendada'
    CANCELADA = 'cancelada'

    TODOS = frozenset({PENDENTE, CONCLUIDA, REAGENDADA, CANCELADA})


class MetodoPagamentoVenda:
    """Métodos de pagamento de Venda (Script 18) — confirmado com o usuário
    (AskUserQuestion): pix, dinheiro, cartao. Mesmo conjunto já usado (como
    literal, não centralizado) em ClientePlanoSolicitacao.metodo_pagamento —
    NÃO é o mesmo enum de Agendamento.metodo_pagamento (MetodoPagamento
    acima), que só tem pix/local."""
    PIX = 'pix'
    DINHEIRO = 'dinheiro'
    CARTAO = 'cartao'

    TODOS = frozenset({PIX, DINHEIRO, CARTAO})


class StatusVenda:
    CONCLUIDA = 'concluida'
    CANCELADA = 'cancelada'

    TODOS = frozenset({CONCLUIDA, CANCELADA})


class TipoMovimentacaoEstoque:
    """
    Tipo de MovimentacaoEstoque (Script 18). Decisão de semântica (pedida
    explicitamente pela tarefa): a coluna `quantidade` SEMPRE grava a
    MAGNITUDE positiva do movimento — quem decide se soma ou subtrai do
    estoque é o `tipo` + a função do serviço central (app/utils/estoque.py)
    que a gravou, nunca o sinal armazenado na própria linha.

    ENTRADA        → sempre soma (reposição de fornecedor).
    SAIDA_VENDA     → sempre subtrai (venda avulsa de produto).
    SAIDA_USO       → sempre subtrai (consumo em atendimento/serviço).
    AJUSTE          → bidirecional (correção manual de inventário — quebra,
                       perda, contagem física). A DIREÇÃO vem de qual função
                       do serviço foi chamada (registrar_entrada/
                       registrar_saida), não de um campo extra na tabela;
                       a rota HTTP de ajuste aceita quantidade com sinal no
                       payload e decide internamente qual função chamar,
                       sempre gravando a magnitude (abs) na coluna.
    """
    ENTRADA = 'entrada'
    SAIDA_VENDA = 'saida_venda'
    SAIDA_USO = 'saida_uso'
    AJUSTE = 'ajuste'

    TODOS = frozenset({ENTRADA, SAIDA_VENDA, SAIDA_USO, AJUSTE})
    SAIDAS = frozenset({SAIDA_VENDA, SAIDA_USO})


class TipoEventoWebhook:
    """Eventos de negócio que disparam webhook n8n (v1.2/Frente 2) —
    1 URL única por barbearia, gestor escolhe quais destes 5 ficam ativos."""
    AGENDAMENTO_CRIADO    = 'agendamento_criado'
    AGENDAMENTO_APROVADO  = 'agendamento_aprovado'
    AGENDAMENTO_CANCELADO = 'agendamento_cancelado'
    PLANO_ATIVADO         = 'plano_ativado'
    VENDA_CONCLUIDA       = 'venda_concluida'

    TODOS = frozenset({
        AGENDAMENTO_CRIADO, AGENDAMENTO_APROVADO, AGENDAMENTO_CANCELADO,
        PLANO_ATIVADO, VENDA_CONCLUIDA,
    })
