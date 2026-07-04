"""
Scheduler de lembretes de agendamento.

Roda em background thread via APScheduler.
A cada minuto, verifica agendamentos cujo horário está a ~X minutos de distância
e gera notificação in_app para o cliente e para o barbeiro.

A antecedência é lida de ConfiguracaoAgendamento (A3: regras como config, nunca constante):
  - notif_antecedencia_cliente_min  (default 30)
  - notif_antecedencia_barbeiro_min (default 15)

Deduplicação: uma notificação por (agendamento_id, tipo) — skip se já existe.
"""
import logging
from datetime import timedelta
from app.utils.tz import naive_brasilia

logger = logging.getLogger(__name__)

# Margem para janela de detecção: o job roda a cada INTERVALO_JOB_MIN minutos,
# então a janela precisa cobrir esse intervalo com alguma folga.
INTERVALO_JOB_MIN = 1
JANELA_MIN = INTERVALO_JOB_MIN + 1  # 2 minutos de janela — evita miss e evita duplicata


def _processar_lembretes(app) -> None:
    with app.app_context():
        try:
            _executar_lembretes()
        except Exception:
            logger.exception('Scheduler: erro não tratado em _executar_lembretes')


def _executar_lembretes() -> None:
    from app.extensions import db
    from app.models import (
        Agendamento, Barbeiro, Cliente, Usuario,
        ConfiguracaoAgendamento, Notificacao,
    )
    from app.utils.notificacoes import criar_notificacao

    agora = naive_brasilia()

    # ── Coleta todas as barbearias com agendamentos futuros e as configs delas ──
    # Janela ampla: até 60min no futuro (cobre qualquer antecedência configurável razoável)
    janela_fim = agora + timedelta(minutes=60)
    ags_futuros = (
        Agendamento.query
        .filter(
            Agendamento.status == 'agendado',
            Agendamento.data_hora > agora,
            Agendamento.data_hora <= janela_fim,
        )
        .all()
    )

    if not ags_futuros:
        return

    # Agrupa configs por barbearia para evitar N+1
    configs_cache: dict[int, ConfiguracaoAgendamento | None] = {}

    def _config(barbearia_id: int):
        if barbearia_id not in configs_cache:
            configs_cache[barbearia_id] = ConfiguracaoAgendamento.query.filter_by(
                barbearia_id=barbearia_id
            ).first()
        return configs_cache[barbearia_id]

    # Coleta notificações já existentes para os agendamentos em questão (dedup em memória)
    ag_ids = [ag.id for ag in ags_futuros]
    ja_notificados: set[tuple[int, str]] = {
        (n.agendamento_id, n.tipo)
        for n in Notificacao.query
        .filter(
            Notificacao.agendamento_id.in_(ag_ids),
            Notificacao.tipo.in_(['lembrete_cliente', 'lembrete_barbeiro']),
        )
        .all()
    }

    for ag in ags_futuros:
        cfg = _config(ag.barbearia_id)
        ant_cli  = cfg.notif_antecedencia_cliente_min  if cfg else 30
        ant_barb = cfg.notif_antecedencia_barbeiro_min if cfg else 15
        minutos_restantes = (ag.data_hora - agora).total_seconds() / 60

        # ── Lembrete do CLIENTE ───────────────────────────────────────────────
        if (
            (ag.id, 'lembrete_cliente') not in ja_notificados
            and ant_cli <= minutos_restantes < ant_cli + JANELA_MIN
        ):
            cli = db.session.get(Cliente, ag.cliente_id)
            if cli and cli.usuario_id:
                from app.models import Servico, AgendamentoServico
                itens = AgendamentoServico.query.filter_by(agendamento_id=ag.id).all()
                nomes = ', '.join(
                    (db.session.get(Servico, it.servico_id).nome
                     for it in itens
                     if db.session.get(Servico, it.servico_id))
                )
                criar_notificacao(
                    barbearia_id=ag.barbearia_id,
                    usuario_id=cli.usuario_id,
                    tipo='lembrete_cliente',
                    titulo='Lembrete de agendamento',
                    corpo=(
                        f'Seu agendamento de {nomes or "serviço"} '
                        f'começa em {ant_cli} minutos '
                        f'({ag.data_hora.strftime("%H:%M")}).'
                    ),
                    canal='in_app',
                    agendamento_id=ag.id,
                )
                ja_notificados.add((ag.id, 'lembrete_cliente'))
                logger.info('Lembrete cliente gerado: ag#%s usuario#%s', ag.id, cli.usuario_id)

        # ── Lembrete do BARBEIRO ──────────────────────────────────────────────
        if (
            (ag.id, 'lembrete_barbeiro') not in ja_notificados
            and ant_barb <= minutos_restantes < ant_barb + JANELA_MIN
        ):
            barb = db.session.get(Barbeiro, ag.barbeiro_id)
            if barb and barb.usuario_id:
                cli = db.session.get(Cliente, ag.cliente_id)
                cli_nome = cli.nome if cli else 'cliente'
                criar_notificacao(
                    barbearia_id=ag.barbearia_id,
                    usuario_id=barb.usuario_id,
                    tipo='lembrete_barbeiro',
                    titulo='Próximo agendamento',
                    corpo=(
                        f'{cli_nome} chega em {ant_barb} minutos '
                        f'({ag.data_hora.strftime("%H:%M")}).'
                    ),
                    canal='in_app',
                    agendamento_id=ag.id,
                )
                ja_notificados.add((ag.id, 'lembrete_barbeiro'))
                logger.info('Lembrete barbeiro gerado: ag#%s usuario#%s', ag.id, barb.usuario_id)


def iniciar_scheduler(app) -> object:
    """
    Inicia o BackgroundScheduler e retorna a instância (para shutdown ordenado).
    Deve ser chamado uma única vez dentro de create_app().
    Protegido contra double-start no modo debug do Flask (Werkzeug reloader fork).
    """
    import os
    from apscheduler.schedulers.background import BackgroundScheduler

    # Werkzeug debug reloader roda o processo filho com WERKZEUG_RUN_MAIN=true.
    # Só o processo filho executa o app de verdade; o pai apenas monitora arquivos.
    # Em produção (gunicorn) WERKZEUG_RUN_MAIN não existe — scheduler sempre sobe.
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'false':
        logger.debug('Scheduler: processo pai do Werkzeug reloader — não iniciado.')
        return None

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        _processar_lembretes,
        trigger='interval',
        minutes=INTERVALO_JOB_MIN,
        args=[app],
        id='lembretes_agendamentos',
        replace_existing=True,
        max_instances=1,
        coalesce=True,        # se atrasou, roda uma vez só (não acumula)
    )
    scheduler.start()
    logger.info('Scheduler de lembretes iniciado (intervalo: %dmin, janela: %dmin)', INTERVALO_JOB_MIN, JANELA_MIN)
    return scheduler
