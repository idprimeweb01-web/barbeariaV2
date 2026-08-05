from app.extensions import db

PLANO_LIMITE_ILIMITADO = 99999  # sentinela: PlanoServico.limite_uso_mensal é NOT NULL


def estornar_creditos_plano(ag, forcar_sem_estorno: bool = False) -> int:
    """
    Devolve o(s) crédito(s) de plano consumido(s) por um agendamento que
    está sendo cancelado — apagando a linha de `ClientePlanoUso` que o
    booking gravou (ver pub/agendamento.py::_criar_agendamento_core), o que
    libera a vaga na contagem mensal (`_resolver_plano`).

    Regra de negócio (decisão do dono, PLANO_DE_ACAO.md achado M1):
    - Só estorna agendamento ainda no FUTURO. Um cancelamento de agendamento
      já passado (sem status de "falta" dedicado no sistema — o valor
      `nao_realizado` existe no schema mas nenhuma rota o usa hoje) é
      tratado como equivalente a no-show: não devolve o crédito.
    - `forcar_sem_estorno=True` deixa o chamador (hoje só o gestor, via
      exceção manual) cancelar sem devolver o crédito mesmo se ainda for
      futuro — ex: cliente já confirmou presença fora do sistema, ou algum
      motivo de negócio que não justifica o estorno.

    Retorna quantas linhas de ClientePlanoUso foram removidas (0 = nada
    aplicável — sem item de plano, no passado, ou forçado sem estorno).
    """
    from app.models import AgendamentoServico, ClientePlanoUso
    from app.utils.tz import naive_brasilia

    if forcar_sem_estorno:
        return 0
    if ag.data_hora <= naive_brasilia():
        return 0

    itens_plano = AgendamentoServico.query.filter_by(
        agendamento_id=ag.id, is_plano=True,
    ).filter(AgendamentoServico.cliente_plano_id.isnot(None)).all()
    if not itens_plano:
        return 0

    dia = ag.data_hora.date()
    removidos = 0
    for item in itens_plano:
        uso = ClientePlanoUso.query.filter_by(
            cliente_plano_id=item.cliente_plano_id, servico_id=item.servico_id, data_uso=dia,
        ).first()
        if uso:
            db.session.delete(uso)
            removidos += 1
    return removidos


def limite_para_fora(valor):
    """Converte o sentinela de 'ilimitado' para None ao expor um limite na API."""
    return None if valor is None or valor >= PLANO_LIMITE_ILIMITADO else valor


def limite_para_dentro(valor):
    """Converte None/0/ausente vindo do front para o sentinela de ilimitado."""
    if valor is None:
        return PLANO_LIMITE_ILIMITADO
    try:
        valor = int(valor)
    except (TypeError, ValueError):
        return PLANO_LIMITE_ILIMITADO
    return valor if valor > 0 else PLANO_LIMITE_ILIMITADO
