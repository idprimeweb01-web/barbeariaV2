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


class StatusSolicitacaoPlano:
    PENDENTE = 'pendente'
    APROVADO = 'aprovado'
    REJEITADO = 'rejeitado'

    TODOS = frozenset({PENDENTE, APROVADO, REJEITADO})
