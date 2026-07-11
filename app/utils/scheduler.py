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
from datetime import datetime, timedelta, timezone
from app.utils.tz import naive_brasilia, hoje_brasilia, BRASILIA
from app.utils.db import commit_ou_falhar
from app.constants import StatusAgendamento

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
            Agendamento.status == StatusAgendamento.AGENDADO,
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


def _processar_limpeza_tokens_revogados(app) -> None:
    with app.app_context():
        try:
            _limpar_tokens_revogados()
        except Exception:
            logger.exception('Scheduler: erro não tratado em _limpar_tokens_revogados')


def _limpar_tokens_revogados() -> None:
    """Remove da tabela tokens_revogados linhas com mais de 31 dias.
    O access token (15min) e o refresh token (30 dias) já expiraram naturalmente
    nesse ponto — a linha na blacklist virou lixo, mantê-la só custa espaço."""
    from app.extensions import db
    from app.models import TokenRevogado

    limite = datetime.now(timezone.utc) - timedelta(days=31)
    removidos = TokenRevogado.query.filter(TokenRevogado.revogado_em < limite).delete()
    commit_ou_falhar('utils.scheduler._limpar_tokens_revogados')
    if removidos:
        logger.info('Scheduler: %d token(s) revogado(s) expirado(s) removido(s)', removidos)


def _processar_expiracao_planos(app) -> None:
    with app.app_context():
        try:
            _expirar_planos()
        except Exception:
            logger.exception('Scheduler: erro não tratado em _expirar_planos')


def _expirar_planos() -> None:
    """EC02: sem isso, um ClientePlano com data_fim vencida nunca era
    desativado — _resolver_plano agora ignora planos vencidos na hora de
    cobrar (Bloco 3.2), mas aqui é onde `ativo` de fato vira False e o
    cliente é avisado."""
    from app.extensions import db
    from app.models import ClientePlano, Cliente
    from app.utils.notificacoes import criar_notificacao

    hoje = hoje_brasilia()
    vencidos = (
        ClientePlano.query
        .filter(
            ClientePlano.data_fim.isnot(None),
            ClientePlano.data_fim < hoje,
            ClientePlano.ativo == True,  # noqa: E712 — comparação SQLAlchemy, não Python
        )
        .all()
    )
    if not vencidos:
        return

    for cp in vencidos:
        cp.ativo = False
        cli = db.session.get(Cliente, cp.cliente_id)
        if cli and cli.usuario_id:
            criar_notificacao(
                barbearia_id=cp.barbearia_id,
                usuario_id=cli.usuario_id,
                tipo='plano_expirado',
                titulo='Seu plano expirou',
                corpo='Seu plano expirou. Fale com o estabelecimento para renovar e continuar aproveitando os benefícios.',
                canal='in_app',
            )

    commit_ou_falhar('utils.scheduler._expirar_planos')
    logger.info('Scheduler: %d plano(s) expirado(s) desativado(s)', len(vencidos))

    # VIP leveling (v1.2) — expiração passiva (cliente não renovou) abre a
    # mesma janela de tolerância que um cancelamento ativo. Depois do commit
    # principal: falha aqui não pode desfazer a desativação do plano.
    from app.utils.vip_leveling import processar_evento_plano
    for cp in vencidos:
        processar_evento_plano(cp.cliente_id, cp.barbearia_id, 'cancelamento')
    commit_ou_falhar('utils.scheduler._expirar_planos.vip_leveling')


def _processar_vencimento_vip(app) -> None:
    with app.app_context():
        try:
            _varrer_vencimento_vip()
        except Exception:
            logger.exception('Scheduler: erro não tratado em _varrer_vencimento_vip')


def _varrer_vencimento_vip() -> None:
    """v1.2: varredura diária de quem está na janela de tolerância pós-
    cancelamento (ClienteVip.data_proxima_renovacao setada) — envia lembrete
    nos dias certos e reseta a progressão pra quem deixou a janela fechar
    sem renovar. Não usa o mesmo laço de _expirar_planos porque a janela
    continua relevante todo santo dia até fechar, não só no dia em que o
    plano venceu."""
    from app.models import ClienteVip
    from app.utils.vip_leveling import processar_evento_plano

    abertos = ClienteVip.query.filter(ClienteVip.data_proxima_renovacao.isnot(None)).all()
    if not abertos:
        return

    for cv in abertos:
        processar_evento_plano(cv.cliente_id, cv.barbearia_id, 'vencimento')
    commit_ou_falhar('utils.scheduler._varrer_vencimento_vip')
    logger.info('Scheduler: %d janela(s) de tolerância VIP verificada(s)', len(abertos))


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
    scheduler.add_job(
        _processar_limpeza_tokens_revogados,
        trigger='interval',
        hours=24,
        args=[app],
        id='limpeza_tokens_revogados',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _processar_expiracao_planos,
        trigger='cron',
        hour=3, minute=0,
        timezone=BRASILIA,
        args=[app],
        id='expiracao_planos',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _processar_vencimento_vip,
        trigger='cron',
        hour=3, minute=30,  # depois de expiracao_planos, mesma janela de baixo tráfego
        timezone=BRASILIA,
        args=[app],
        id='vencimento_vip',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info('Scheduler de lembretes iniciado (intervalo: %dmin, janela: %dmin)', INTERVALO_JOB_MIN, JANELA_MIN)
    return scheduler
