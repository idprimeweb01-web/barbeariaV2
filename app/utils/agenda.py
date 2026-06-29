"""
Motor de slots e conflito de agendamento.
Princípio A1: a lógica opera sobre resource_id + intervalo de tempo,
não sobre o conceito de "barbeiro". O recurso hoje é um Barbeiro;
futuramente pode ser Sala, Equipamento etc. — sem mudar esta função.
"""
from datetime import datetime, timedelta, time as time_t, date as date_t
from typing import Optional
from app.utils.tz import naive_brasilia, hoje_brasilia


def fim_agendamento(data_hora: datetime, duracao_minutos: int) -> datetime:
    return data_hora + timedelta(minutes=duracao_minutos)


def verificar_conflito(resource_id: int, data_hora: datetime, duracao_minutos: int,
                       excluir_id: Optional[int] = None):
    """
    Retorna o Agendamento conflitante ou None.
    resource_id: hoje = barbeiro_id; futuramente qualquer recurso agendável.
    """
    from app.models import Agendamento
    from app.extensions import db

    fim = fim_agendamento(data_hora, duracao_minutos)
    dia = data_hora.date()

    q = (
        db.session.query(Agendamento)
        .filter(
            Agendamento.barbeiro_id == resource_id,
            Agendamento.status != 'cancelado',
            db.func.date(Agendamento.data_hora) == dia,
        )
    )
    if excluir_id:
        q = q.filter(Agendamento.id != excluir_id)

    for ag in q.all():
        ag_fim = fim_agendamento(ag.data_hora, ag.duracao_minutos)
        if ag.data_hora < fim and ag_fim > data_hora:
            return ag

    return None


def gerar_slots(resource_id: int, data, duracao_necessaria: int) -> list[str]:
    """
    Retorna lista de horários disponíveis ('HH:MM') para o recurso na data dada.
    Considera ConfiguracaoAgenda do barbeiro, agendamentos existentes e horários bloqueados.
    """
    from app.models import ConfiguracaoAgenda, Agendamento, HorarioBloqueado, PausaBarbeiro
    from app.extensions import db

    config = ConfiguracaoAgenda.query.filter_by(barbeiro_id=resource_id).first()
    if not config or not config.loja_aberta:
        return []

    abertura  = datetime.combine(data, config.horario_abertura)
    fechamento = datetime.combine(data, config.horario_fechamento)
    intervalo  = timedelta(minutes=config.intervalo_minutos)

    dia_inicio = datetime.combine(data, time_t(0, 0))
    dia_fim    = datetime.combine(data, time_t(23, 59, 59))

    agendamentos = (
        Agendamento.query
        .filter(
            Agendamento.barbeiro_id == resource_id,
            Agendamento.data_hora >= dia_inicio,
            Agendamento.data_hora <= dia_fim,
            Agendamento.status != 'cancelado',
        )
        .all()
    )

    bloqueios = (
        HorarioBloqueado.query
        .filter(
            HorarioBloqueado.barbeiro_id == resource_id,
            HorarioBloqueado.data_hora_inicio < dia_fim,
            HorarioBloqueado.data_hora_fim > dia_inicio,
        )
        .all()
    )

    pausas = PausaBarbeiro.query.filter_by(barbeiro_id=resource_id).all()

    # Para hoje: descartar slots já passados (usando horário de Brasília)
    agora = naive_brasilia() if data == hoje_brasilia() else None

    slots = []
    slot = abertura

    while slot + timedelta(minutes=duracao_necessaria) <= fechamento:
        # Pula slots passados quando a data for hoje
        if agora is not None and slot < agora:
            slot += intervalo
            continue

        slot_fim = slot + timedelta(minutes=duracao_necessaria)
        ocupado = False

        for ag in agendamentos:
            ag_fim = fim_agendamento(ag.data_hora, ag.duracao_minutos)
            if ag.data_hora < slot_fim and ag_fim > slot:
                ocupado = True
                break

        if not ocupado:
            for b in bloqueios:
                if b.data_hora_inicio < slot_fim and b.data_hora_fim > slot:
                    ocupado = True
                    break

        if not ocupado:
            for p in pausas:
                pausa_ini = datetime.combine(data, p.hora_inicio)
                pausa_fim = datetime.combine(data, p.hora_fim)
                if pausa_ini < slot_fim and pausa_fim > slot:
                    ocupado = True
                    break

        if not ocupado:
            slots.append(slot.strftime('%H:%M'))

        slot += intervalo

    return slots
