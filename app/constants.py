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


class StatusSolicitacaoCompra:
    PENDENTE = 'pendente'
    APROVADA = 'aprovada'
    REJEITADA = 'rejeitada'

    TODOS = frozenset({PENDENTE, APROVADA, REJEITADA})


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
    1 URL única por barbearia, gestor escolhe quais destes ficam ativos."""
    AGENDAMENTO_CRIADO    = 'agendamento_criado'
    AGENDAMENTO_APROVADO  = 'agendamento_aprovado'
    AGENDAMENTO_CANCELADO = 'agendamento_cancelado'
    PLANO_ATIVADO         = 'plano_ativado'
    VENDA_CONCLUIDA       = 'venda_concluida'
    # Dispara no upload do comprovante PIX, ANTES de qualquer aprovação
    # humana — é o ponto onde uma automação (n8n) pode agir. Se o gestor
    # ligou BarbeariaWebhookConfig.permite_auto_aprovacao, a automação pode
    # chamar de volta POST /api/v1/webhook/agendamentos/<id>/aprovar
    # (ver app/routes/webhook_inbound.py) pra aprovar sozinha.
    COMPROVANTE_ENVIADO   = 'comprovante_enviado'
    # Dúvidas do Cliente (chat de suporte) — dispara quando o cliente abre
    # uma dúvida nova e a cada mensagem nova de qualquer lado da conversa,
    # pra automação (n8n) poder avisar o gestor no WhatsApp.
    DUVIDA_CRIADA         = 'duvida_criada'
    DUVIDA_NOVA_MENSAGEM  = 'duvida_nova_mensagem'
    # Dispara quando um ticket nasce ou é reclassificado como prioridade
    # urgente — hook pronto pro n8n alertar alguém na hora (ex: WhatsApp
    # pro gestor), mesmo sem nenhum workflow configurado ainda pra ele
    # (disparar_webhook() já é um no-op seguro se o evento não estiver
    # marcado como ativo na config da barbearia).
    DUVIDA_URGENTE        = 'duvida_urgente'

    TODOS = frozenset({
        AGENDAMENTO_CRIADO, AGENDAMENTO_APROVADO, AGENDAMENTO_CANCELADO,
        PLANO_ATIVADO, VENDA_CONCLUIDA, COMPROVANTE_ENVIADO,
        DUVIDA_CRIADA, DUVIDA_NOVA_MENSAGEM, DUVIDA_URGENTE,
    })


class StatusClienteDuvida:
    """Situação de ClienteDuvida (ticket de suporte). v2: renomeado de
    aberta/fechada pra um ciclo de vida de 3 estados — 'cancelada' é
    terminal e NUNCA reabre sozinho (só ação explícita de gestor/barbeiro/
    admin); 'concluida' reabre automaticamente pra 'pendente' se chegar
    mensagem nova (ver app.utils.duvidas.criar_mensagem)."""
    PENDENTE  = 'pendente'
    CONCLUIDA = 'concluida'
    CANCELADA = 'cancelada'

    TODOS = frozenset({PENDENTE, CONCLUIDA, CANCELADA})


class AutorTipoDuvida:
    """Quem escreveu uma ClienteDuvidaMensagem."""
    CLIENTE  = 'cliente'
    GESTOR   = 'gestor'
    BARBEIRO = 'barbeiro'
    ADMIN    = 'admin'  # super_admin respondendo pela fila cross-tenant

    TODOS = frozenset({CLIENTE, GESTOR, BARBEIRO, ADMIN})


class CategoriaDuvida:
    """Catálogo de categorias de ticket — cada uma tem rótulo+ícone
    consistente na UI (ver ROTULOS no frontend/template). 'ERRO' é especial:
    força direcionamento pro gestor mesmo se o cliente tiver escolhido um
    funcionário específico (ver app.utils.duvidas.resolver_direcionamento)."""
    DUVIDA      = 'duvida'
    ERRO        = 'erro'
    FINANCEIRO  = 'financeiro'
    SUGESTAO    = 'sugestao'
    TREINAMENTO = 'treinamento'
    INTEGRACAO  = 'integracao'
    CONTA       = 'conta'
    OUTRO       = 'outro'

    TODOS = frozenset({
        DUVIDA, ERRO, FINANCEIRO, SUGESTAO, TREINAMENTO, INTEGRACAO, CONTA, OUTRO,
    })


class PrioridadeDuvida:
    """Quem abre sugere; gestor/barbeiro/admin podem reclassificar. ORDEM é
    usado pra ordenar a fila (urgente > alta > normal > baixa, depois por
    ultima_mensagem_em) — menor valor = mais prioritário."""
    BAIXA   = 'baixa'
    NORMAL  = 'normal'
    ALTA    = 'alta'
    URGENTE = 'urgente'

    TODOS = frozenset({BAIXA, NORMAL, ALTA, URGENTE})
    ORDEM  = {URGENTE: 0, ALTA: 1, NORMAL: 2, BAIXA: 3}


class DirecionadoTipo:
    """Pra quem um ticket foi endereçado pelo cliente na abertura —
    'barbeiro' é um funcionário específico (direcionado_para_usuario_id
    preenchido); 'gestor' é a fila geral do estabelecimento (sem dono
    específico, qualquer gestor/barbeiro com acesso pode responder)."""
    GESTOR   = 'gestor'
    BARBEIRO = 'barbeiro'

    TODOS = frozenset({GESTOR, BARBEIRO})


class TipoEventoDuvida:
    """Tipo de ClienteDuvidaEvento — timeline de auditoria própria do
    ticket, além do AuditoriaLog geral do sistema."""
    CATEGORIA_ALTERADA  = 'categoria_alterada'
    PRIORIDADE_ALTERADA = 'prioridade_alterada'
    SITUACAO_ALTERADA   = 'situacao_alterada'
    DIRECIONADO_ADMIN   = 'direcionado_admin'
    REABERTO            = 'reaberto'
    ATRIBUIDO           = 'atribuido'

    TODOS = frozenset({
        CATEGORIA_ALTERADA, PRIORIDADE_ALTERADA, SITUACAO_ALTERADA,
        DIRECIONADO_ADMIN, REABERTO, ATRIBUIDO,
    })
