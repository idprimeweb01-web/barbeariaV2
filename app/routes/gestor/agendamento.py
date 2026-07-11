import calendar
from datetime import date, datetime, timedelta, time as time_t
from flask import Blueprint, request, g, jsonify
from sqlalchemy.orm import selectinload
from app.extensions import db
from app.models import (
    Agendamento, AgendamentoServico, AgendamentoSolicitacaoPix,
    Cliente, Servico, Barbeiro, Usuario,
    HorarioBloqueado, ConfiguracaoAgenda, SolicitacaoLiberacao, BarbeiroServico,
    TransferenciaAgendamento,
)
from app.exceptions import APIError
from app.decorators.auth import gestor_required
from app.utils.features import feature_required
from app.utils.agenda import (
    fim_agendamento, verificar_conflito, gerar_slots,
    servicos_do_agendamento, barbeiro_atende_todos_servicos, barbeiro_elegivel_para_transferencia,
)
from app.utils.cupons import incrementar_uso_cupom, decrementar_uso_cupom
from app.utils.notificacoes import criar_notificacao
from app.utils.tz import naive_brasilia
from app.labels import L
from app.utils import normalizar_telefone
from app.utils.db import commit_ou_falhar
from app.constants import StatusAgendamento, StatusTransferencia

gestor_agenda_bp = Blueprint('gestor_agenda', __name__, url_prefix='/api/v1/gestor')


def _fmt_ag_gestor(ag, clientes=None, barbeiros=None, pixes=None):
    """
    clientes/barbeiros/pixes: dicts pré-carregados em lote {id: objeto} —
    passados pela listagem (Bloco 5.1) pra evitar N+1. Quando None (chamadas
    de item único: detalhar/aprovar/cancelar), cai numa query pontual —
    aceitável, não é o padrão de loop que causa N+1.
    """
    fim = fim_agendamento(ag.data_hora, ag.duracao_minutos)
    cliente = clientes.get(ag.cliente_id) if clientes is not None else db.session.get(Cliente, ag.cliente_id)
    barbeiro = barbeiros.get(ag.barbeiro_id) if barbeiros is not None else db.session.get(Barbeiro, ag.barbeiro_id)
    barbeiro_nome = barbeiro.usuario.nome if barbeiro and barbeiro.usuario else None

    itens = ag.itens  # relationship (selectinload em lote quando a query de origem eager-carrega)
    servicos_info = []
    for it in itens:
        s = it.servico
        # Comissão separada: atendimento de plano usa comissao_plano_percentual
        if it.is_plano:
            comissao_pct = float(barbeiro.comissao_plano_percentual) if barbeiro else 0
            comissao_tipo = 'plano'
        else:
            comissao_pct = float(barbeiro.comissao_percentual) if barbeiro else 0
            comissao_tipo = 'avulso'
        comissao_valor = round(float(it.preco_unitario) * comissao_pct / 100, 2)
        servicos_info.append({
            'servico_id':           it.servico_id,
            'nome':                 s.nome if s else None,
            'preco':                float(it.preco_unitario),
            'duracao_minutos':      s.duracao_minutos if s else None,
            'is_plano':             it.is_plano,
            'comissao_tipo':        comissao_tipo,
            'comissao_percentual':  comissao_pct,
            'comissao_valor':       comissao_valor,
        })

    pix = pixes.get(ag.id) if pixes is not None else (
        AgendamentoSolicitacaoPix.query.filter_by(agendamento_id=ag.id, barbearia_id=ag.barbearia_id).first()
    )

    return {
        'id':               ag.id,
        'status':           ag.status,
        'valor_total':      float(ag.valor_total),
        'duracao_minutos':  ag.duracao_minutos,
        'inicio':           ag.data_hora.isoformat(),
        'fim':              fim.isoformat(),
        'metodo_pagamento': ag.metodo_pagamento,
        'observacao':       ag.observacao,
        'cliente':          {
            'id': cliente.id, 'nome': cliente.nome, 'telefone': cliente.telefone
        } if cliente else None,
        'barbeiro':         {'id': ag.barbeiro_id, 'nome': barbeiro_nome},
        'servicos':         servicos_info,
        'pix':              {'status': pix.status, 'comprovante_url': pix.comprovante_url} if pix else None,
    }


# ── GET /api/v1/gestor/agendamentos ──────────────────────────────────────────

@gestor_agenda_bp.get('/agendamentos')
@gestor_required
def listar_agendamentos():
    q = (
        Agendamento.query
        .options(selectinload(Agendamento.itens).selectinload(AgendamentoServico.servico))
        .filter_by(barbearia_id=g.barbearia_id)
    )

    data_f = request.args.get('data')
    if not data_f:
        # Nunca retornar o histórico inteiro por omissão — default é hoje.
        data_f = naive_brasilia().date().isoformat()
    try:
        from datetime import date
        d = date.fromisoformat(data_f)
        q = q.filter(db.func.date(Agendamento.data_hora) == d)
    except ValueError:
        raise APIError('Parâmetro "data" inválido. Use YYYY-MM-DD.')

    barbeiro_f = request.args.get('barbeiro_id', type=int)
    if barbeiro_f:
        b = Barbeiro.query.filter_by(id=barbeiro_f, barbearia_id=g.barbearia_id).first()
        if not b:
            raise APIError(f'{L("profissional")} não encontrado.', 404)
        q = q.filter_by(barbeiro_id=barbeiro_f)

    status_f = request.args.get('status')
    if status_f:
        if status_f not in StatusAgendamento.TODOS:
            raise APIError(f'Status inválido: "{status_f}".', 422)
        q = q.filter_by(status=status_f)

    try:
        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 50))))
    except ValueError:
        raise APIError('"page" e "per_page" devem ser inteiros.', 422)

    paginado = q.order_by(Agendamento.data_hora).paginate(page=page, per_page=per_page, error_out=False)

    ags_pagina = paginado.items
    clientes  = {c.id: c for c in Cliente.query.filter(
        Cliente.id.in_({ag.cliente_id for ag in ags_pagina})).all()} if ags_pagina else {}
    barbeiros = {b.id: b for b in Barbeiro.query.filter(
        Barbeiro.id.in_({ag.barbeiro_id for ag in ags_pagina})).all()} if ags_pagina else {}
    pixes = {p.agendamento_id: p for p in AgendamentoSolicitacaoPix.query.filter(
        AgendamentoSolicitacaoPix.agendamento_id.in_({ag.id for ag in ags_pagina})).all()} if ags_pagina else {}

    return jsonify({
        'dados':     [_fmt_ag_gestor(ag, clientes, barbeiros, pixes) for ag in ags_pagina],
        'page':      paginado.page,
        'per_page':  paginado.per_page,
        'total':     paginado.total,
        'pages':     paginado.pages,
    }), 200


# ── GET /api/v1/gestor/agendamentos/<id> ─────────────────────────────────────

@gestor_agenda_bp.get('/agendamentos/<int:ag_id>')
@gestor_required
def detalhar_agendamento(ag_id):
    ag = Agendamento.query.filter_by(id=ag_id, barbearia_id=g.barbearia_id).first()
    if not ag:
        raise APIError(f'{L("agendamento")} não encontrado.', 404)
    return jsonify(_fmt_ag_gestor(ag)), 200


# ── PUT /api/v1/gestor/agendamentos/<id>/aprovar ─────────────────────────────
# PIX nunca vira 'agendado' automaticamente — sempre exige aprovação do gestor.

@gestor_agenda_bp.put('/agendamentos/<int:ag_id>/aprovar')
@gestor_required
@feature_required('pix_integrado')
def aprovar_agendamento(ag_id):
    ag = (
        Agendamento.query
        .filter_by(id=ag_id, barbearia_id=g.barbearia_id)
        .with_for_update()
        .first()
    )
    if not ag:
        raise APIError(f'{L("agendamento")} não encontrado.', 404)
    _aprovavel = {
        StatusAgendamento.AGUARDANDO_APROVACAO, StatusAgendamento.AGUARDANDO_COMPROVANTE,
        StatusAgendamento.AGUARDANDO_PAGAMENTO,
    }
    if ag.status not in _aprovavel:
        raise APIError('Este agendamento já foi processado.', 409)

    pix = AgendamentoSolicitacaoPix.query.filter_by(agendamento_id=ag.id, barbearia_id=ag.barbearia_id).first()
    if pix:
        pix.status = 'aprovado'
        pix.respondido_em = naive_brasilia()

    if ag.cupom_id:
        incrementar_uso_cupom(ag.cupom_id, ag.barbearia_id)

    ag.status = StatusAgendamento.AGENDADO
    commit_ou_falhar('gestor.agendamento.aprovar_agendamento')
    return jsonify({'mensagem': f'{L("agendamento")} aprovado.', 'id': ag_id, 'status': StatusAgendamento.AGENDADO}), 200


# ── PUT /api/v1/gestor/agendamentos/<id>/cancelar ────────────────────────────

@gestor_agenda_bp.put('/agendamentos/<int:ag_id>/cancelar')
@gestor_required
def cancelar_agendamento_gestor(ag_id):
    ag = Agendamento.query.filter_by(id=ag_id, barbearia_id=g.barbearia_id).first()
    if not ag:
        raise APIError(f'{L("agendamento")} não encontrado.', 404)
    if ag.status in (StatusAgendamento.CANCELADO, StatusAgendamento.CONCLUIDO):
        raise APIError(f'Não é possível cancelar. Status atual: "{ag.status}".')

    pix = AgendamentoSolicitacaoPix.query.filter_by(agendamento_id=ag.id, barbearia_id=ag.barbearia_id).first()
    if pix and pix.status == 'pendente':
        pix.status = 'rejeitado'

    if ag.cupom_id and ag.status == StatusAgendamento.AGENDADO:
        decrementar_uso_cupom(ag.cupom_id, ag.barbearia_id)

    ag.status = StatusAgendamento.CANCELADO
    commit_ou_falhar('gestor.agendamento.cancelar_agendamento_gestor')
    return jsonify({'mensagem': f'{L("agendamento")} cancelado pelo gestor.', 'id': ag_id}), 200


# ══════════════════════════════════════════════════════════════════════════════
# Grade do Dia
# ══════════════════════════════════════════════════════════════════════════════

def _fmt_ag_grade(ag, clientes):
    """Formato compacto para exibição na grade diária. `clientes`: dict {id: Cliente} pré-carregado."""
    cliente = clientes.get(ag.cliente_id)
    itens   = ag.itens  # eager-carregado (selectinload) pelo caller

    sv_nome  = '—'
    sv_preco = 0.0
    servicos = []
    for it in itens:
        sv = it.servico
        nome = sv.nome if sv else '—'
        sub  = float(it.preco_unitario)
        servicos.append({'nome': nome, 'subtotal': sub})
        if not sv_nome or sv_nome == '—':
            sv_nome  = nome
            sv_preco = sub

    return {
        'id':              ag.id,
        'status':          ag.status,
        'data_hora':       ag.data_hora.isoformat(),
        'duracao_minutos': ag.duracao_minutos,
        'cliente':         cliente.nome if cliente else '—',
        'servico':         sv_nome,
        'servico_preco':   sv_preco,
        'total':           float(ag.valor_total),
        'servicos':        servicos,
        'produtos':        [],
        'em_atendimento':  False,
    }


@gestor_agenda_bp.get('/agenda/grade')
@gestor_required
def grade_do_dia():
    bid        = g.barbearia_id
    barbeiro_f = request.args.get('barbeiro_id', type=int)
    data_str   = request.args.get('data', '')

    if not barbeiro_f:
        raise APIError('"barbeiro_id" é obrigatório.')
    if not data_str:
        raise APIError('"data" é obrigatório (YYYY-MM-DD).')

    try:
        data = date.fromisoformat(data_str)
    except ValueError:
        raise APIError('"data" inválido. Use YYYY-MM-DD.')

    barb = Barbeiro.query.filter_by(id=barbeiro_f, barbearia_id=bid, ativo=True).first()
    if not barb:
        raise APIError('Barbeiro não encontrado.', 404)

    config = ConfiguracaoAgenda.query.filter_by(barbeiro_id=barbeiro_f).first()

    servicos = (
        db.session.query(Servico)
        .join(BarbeiroServico, BarbeiroServico.servico_id == Servico.id)
        .filter(BarbeiroServico.barbeiro_id == barbeiro_f, Servico.ativo == True)
        .order_by(Servico.nome)
        .all()
    )

    dia_ini = datetime.combine(data, time_t(0, 0))
    dia_fim = datetime.combine(data, time_t(23, 59, 59))
    ags = (
        Agendamento.query
        .options(selectinload(Agendamento.itens).selectinload(AgendamentoServico.servico))
        .filter(
            Agendamento.barbearia_id == bid,
            Agendamento.barbeiro_id == barbeiro_f,
            Agendamento.data_hora >= dia_ini,
            Agendamento.data_hora <= dia_fim,
        )
        .order_by(Agendamento.data_hora)
        .all()
    )
    clientes_grade = {c.id: c for c in Cliente.query.filter(
        Cliente.id.in_({ag.cliente_id for ag in ags})).all()} if ags else {}

    return jsonify({
        'config':       {
            'horario_abertura':   config.horario_abertura.strftime('%H:%M') if config and config.horario_abertura else None,
            'horario_fechamento': config.horario_fechamento.strftime('%H:%M') if config and config.horario_fechamento else None,
            'intervalo_minutos':  config.intervalo_minutos if config else 30,
        } if config else None,
        'servicos':     [{'id': s.id, 'nome': s.nome, 'duracao_minutos': s.duracao_minutos, 'preco': float(s.preco)} for s in servicos],
        'agendamentos': [_fmt_ag_grade(ag, clientes_grade) for ag in ags],
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
# Agendamento Manual (gestor agenda pelo cliente)
# ══════════════════════════════════════════════════════════════════════════════

@gestor_agenda_bp.post('/agenda/agendamento-manual')
@gestor_required
def agendamento_manual():
    bid   = g.barbearia_id
    dados = request.get_json(silent=True) or {}

    barbeiro_id = dados.get('barbeiro_id')
    nome        = (dados.get('nome') or '').strip()
    telefone    = (dados.get('telefone') or '').strip()
    servico_id  = dados.get('servico_id')
    data_hora_s = (dados.get('data_hora') or '').strip()

    if not all([barbeiro_id, nome, telefone, servico_id, data_hora_s]):
        raise APIError('Campos obrigatórios: barbeiro_id, nome, telefone, servico_id, data_hora.')

    tel_norm, tel_err = normalizar_telefone(telefone)
    if tel_err:
        raise APIError(tel_err)

    barb = Barbeiro.query.filter_by(id=barbeiro_id, barbearia_id=bid, ativo=True).first()
    if not barb:
        raise APIError('Barbeiro não encontrado ou inativo.', 404)

    sv = Servico.query.filter_by(id=servico_id, barbearia_id=bid, ativo=True).first()
    if not sv:
        raise APIError('Serviço não encontrado ou inativo.', 404)

    try:
        data_hora = datetime.fromisoformat(data_hora_s)
    except ValueError:
        raise APIError('"data_hora" inválido. Use ISO 8601 (ex: 2024-01-15T09:00).')

    # Agendamento manual do gestor pode encaixar fora da grade normal (fora do
    # horário configurado, em pausa, etc. — decisão de produto), mas não pode
    # ser no passado nem colidir com outro agendamento existente.
    if data_hora <= naive_brasilia():
        raise APIError('Este horário já passou. Escolha um horário futuro.', 422)

    conflito = verificar_conflito(barbeiro_id, data_hora, sv.duracao_minutos)
    if conflito:
        raise APIError(f'Conflito de horário com agendamento existente às {conflito.data_hora.strftime("%H:%M")}.')

    # Buscar ou criar cliente
    cliente = Cliente.query.filter_by(barbearia_id=bid, telefone=tel_norm).first()
    if not cliente:
        cliente = Cliente(
            barbearia_id=bid,
            nome=nome,
            telefone=tel_norm,
        )
        db.session.add(cliente)
        db.session.flush()
    else:
        if cliente.nome != nome:
            cliente.nome = nome

    ag = Agendamento(
        barbearia_id=bid,
        barbeiro_id=barbeiro_id,
        cliente_id=cliente.id,
        data_hora=data_hora,
        duracao_minutos=sv.duracao_minutos,
        valor_total=sv.preco,
        status=StatusAgendamento.AGENDADO,
        metodo_pagamento='presencial',
    )
    db.session.add(ag)
    db.session.flush()

    db.session.add(AgendamentoServico(
        agendamento_id=ag.id,
        servico_id=sv.id,
        preco_unitario=sv.preco,
        is_plano=False,
    ))
    commit_ou_falhar('gestor.agendamento.agendamento_manual')

    return jsonify({'mensagem': 'Agendamento criado.', 'id': ag.id}), 201


# ══════════════════════════════════════════════════════════════════════════════
# Bloqueios de Horário (barbearia-wide — afeta todos os barbeiros)
# ══════════════════════════════════════════════════════════════════════════════

def _fmt_bloqueio(b):
    dia_ini = b.data_hora_inicio
    dia_fim = b.data_hora_fim
    # dia_inteiro = bloqueia das 00:00 às 23:59:59 (ou dia seguinte à meia-noite)
    e_dia_inteiro = (
        dia_ini.hour == 0 and dia_ini.minute == 0 and
        (dia_fim.hour == 23 or (dia_fim.date() > dia_ini.date()))
    )
    return {
        'id':          b.id,
        'dia_inteiro': e_dia_inteiro,
        'hora_inicio': dia_ini.strftime('%H:%M') if not e_dia_inteiro else None,
        'hora_fim':    dia_fim.strftime('%H:%M')  if not e_dia_inteiro else None,
        'motivo':      b.motivo,
    }


@gestor_agenda_bp.get('/agenda/bloqueios/mes')
@gestor_required
def bloqueios_mes():
    bid = g.barbearia_id
    mes = request.args.get('mes', type=int)
    ano = request.args.get('ano', type=int)

    if not mes or not ano:
        raise APIError('"mes" e "ano" são obrigatórios.')

    primeiro = date(ano, mes, 1)
    _, dias_no_mes = calendar.monthrange(ano, mes)
    ultimo   = date(ano, mes, dias_no_mes)

    # Todos os bloqueios do mês para a barbearia
    bloqueios = (
        HorarioBloqueado.query
        .filter(
            HorarioBloqueado.barbearia_id == bid,
            HorarioBloqueado.data_hora_inicio < datetime(ano, mes, dias_no_mes, 23, 59, 59),
            HorarioBloqueado.data_hora_fim    > datetime(ano, mes, 1, 0, 0, 0),
        )
        .all()
    )

    # Agrupar por data (sem duplicar por barbeiro)
    bloqueios_por_data: dict = {}
    seen_key: set = set()
    for blk in bloqueios:
        d = blk.data_hora_inicio.date()
        key = (d, blk.data_hora_inicio, blk.data_hora_fim, blk.motivo)
        if key in seen_key:
            continue
        seen_key.add(key)
        if d not in bloqueios_por_data:
            bloqueios_por_data[d] = []
        bloqueios_por_data[d].append(blk)

    dias = []
    for i in range(dias_no_mes):
        d       = date(ano, mes, i + 1)
        blks_d  = bloqueios_por_data.get(d, [])
        dia_int = any(
            b.data_hora_inicio.hour == 0 and b.data_hora_inicio.minute == 0 and
            (b.data_hora_fim.hour == 23 or b.data_hora_fim.date() > b.data_hora_inicio.date())
            for b in blks_d
        )
        # Pegar apenas um bloqueio por id único (o primeiro por barbeiro agrupado)
        unique_blks = []
        seen_ids = set()
        for blk in blks_d:
            # Deduplicar por (data_hora_inicio, data_hora_fim, motivo) — representar como 1 bloqueio
            k = (blk.data_hora_inicio, blk.data_hora_fim, blk.motivo)
            if k not in seen_ids:
                seen_ids.add(k)
                unique_blks.append(blk)

        dias.append({
            'data':                 d.isoformat(),
            'dia':                  d.day,
            'tem_bloqueio':         bool(blks_d),
            'dia_inteiro_bloqueado': dia_int,
            'bloqueios':            [_fmt_bloqueio(b) for b in unique_blks],
        })

    # primeiro_dia_semana: weekday() 0=Seg … 6=Dom (para offset do calendário)
    return jsonify({
        'primeiro_dia_semana': primeiro.weekday(),
        'dias':                dias,
    }), 200


@gestor_agenda_bp.post('/agenda/bloqueios')
@gestor_required
def criar_bloqueio():
    bid   = g.barbearia_id
    dados = request.get_json(silent=True) or {}

    data_str   = (dados.get('data') or '').strip()
    dia_inteiro = bool(dados.get('dia_inteiro'))
    hora_ini_s = (dados.get('hora_inicio') or '').strip()
    hora_fim_s = (dados.get('hora_fim') or '').strip()
    tipo       = dados.get('tipo', 'pontual')   # pontual | recorrente
    padrao     = dados.get('padrao')             # dia_semana | data_especifica
    motivo     = (dados.get('motivo') or '').strip() or None

    if not data_str:
        raise APIError('"data" é obrigatório (YYYY-MM-DD).')
    try:
        data_base = date.fromisoformat(data_str)
    except ValueError:
        raise APIError('"data" inválido.')

    if not dia_inteiro:
        if not hora_ini_s or not hora_fim_s:
            raise APIError('"hora_inicio" e "hora_fim" são obrigatórios para bloqueio parcial.')
        try:
            hora_ini = time_t.fromisoformat(hora_ini_s)
            hora_fim = time_t.fromisoformat(hora_fim_s)
        except ValueError:
            raise APIError('"hora_inicio"/"hora_fim" inválidos. Use HH:MM.')
        if hora_fim <= hora_ini:
            raise APIError('"hora_fim" deve ser após "hora_inicio".')

    # Gerar lista de datas a bloquear
    datas = [data_base]
    if tipo == 'recorrente' and padrao:
        hoje = data_base
        limite = date(data_base.year + 1, data_base.month, data_base.day)
        cursor = data_base + timedelta(days=1)
        while cursor <= limite:
            if padrao == 'dia_semana' and cursor.weekday() == data_base.weekday():
                datas.append(cursor)
            elif padrao == 'data_especifica' and cursor.day == data_base.day:
                datas.append(cursor)
            cursor += timedelta(days=1)

    # Barbeiros ativos desta barbearia
    barbeiros = Barbeiro.query.filter_by(barbearia_id=bid, ativo=True).all()
    if not barbeiros:
        raise APIError('Nenhum barbeiro ativo encontrado.', 404)

    criados = 0
    for d in datas:
        if dia_inteiro:
            ini = datetime.combine(d, time_t(0, 0))
            fim = datetime.combine(d, time_t(23, 59, 59))
        else:
            ini = datetime.combine(d, hora_ini)
            fim = datetime.combine(d, hora_fim)

        for barb in barbeiros:
            db.session.add(HorarioBloqueado(
                barbearia_id=bid,
                barbeiro_id=barb.id,
                data_hora_inicio=ini,
                data_hora_fim=fim,
                motivo=motivo,
            ))
        criados += 1

    commit_ou_falhar('gestor.agendamento.criar_bloqueio')
    return jsonify({'mensagem': f'{criados} bloqueio(s) criado(s).', 'total': criados}), 201


@gestor_agenda_bp.delete('/agenda/bloqueios/<int:bloqueio_id>')
@gestor_required
def remover_bloqueio(bloqueio_id):
    bid = g.barbearia_id
    blk = HorarioBloqueado.query.filter_by(id=bloqueio_id, barbearia_id=bid).first()
    if not blk:
        raise APIError('Bloqueio não encontrado.', 404)

    # Remover todos os bloqueios com mesmo intervalo/motivo (todos os barbeiros)
    ini, fim, mot = blk.data_hora_inicio, blk.data_hora_fim, blk.motivo
    irmãos = HorarioBloqueado.query.filter_by(
        barbearia_id=bid,
        data_hora_inicio=ini,
        data_hora_fim=fim,
        motivo=mot,
    ).all()
    for b in irmãos:
        db.session.delete(b)

    commit_ou_falhar('gestor.agendamento.remover_bloqueio')
    return jsonify({'mensagem': 'Bloqueio removido.'}), 200


# ── Bloqueio por barbeiro (Tab 1 — modalBloquear) ────────────────────────────

@gestor_agenda_bp.post('/barbeiros/<int:barbeiro_id>/bloqueios')
@gestor_required
def criar_bloqueio_barbeiro(barbeiro_id):
    bid  = g.barbearia_id
    barb = Barbeiro.query.filter_by(id=barbeiro_id, barbearia_id=bid).first()
    if not barb:
        raise APIError('Barbeiro não encontrado.', 404)

    dados = request.get_json(silent=True) or {}
    ini_s = (dados.get('data_hora_inicio') or '').strip()
    fim_s = (dados.get('data_hora_fim') or '').strip()
    motivo = (dados.get('motivo') or '').strip() or None

    if not ini_s or not fim_s:
        raise APIError('"data_hora_inicio" e "data_hora_fim" são obrigatórios.')
    try:
        ini = datetime.fromisoformat(ini_s)
        fim = datetime.fromisoformat(fim_s)
    except ValueError:
        raise APIError('Datas inválidas. Use ISO 8601 (ex: 2024-01-15T09:00).')
    if fim <= ini:
        raise APIError('"data_hora_fim" deve ser após "data_hora_inicio".')

    db.session.add(HorarioBloqueado(
        barbearia_id=bid,
        barbeiro_id=barbeiro_id,
        data_hora_inicio=ini,
        data_hora_fim=fim,
        motivo=motivo,
    ))
    commit_ou_falhar('gestor.agendamento.criar_bloqueio_barbeiro')
    return jsonify({'mensagem': 'Horário bloqueado.'}), 201


# ══════════════════════════════════════════════════════════════════════════════
# Solicitações de Liberação
# ══════════════════════════════════════════════════════════════════════════════

@gestor_agenda_bp.get('/agenda/solicitacoes-liberacao')
@gestor_required
def listar_solicitacoes():
    bid    = g.barbearia_id
    status = request.args.get('status', 'pendente')
    q      = SolicitacaoLiberacao.query.filter_by(barbearia_id=bid)
    if status:
        q = q.filter_by(status=status)
    solis  = q.order_by(SolicitacaoLiberacao.data_solicitacao.desc()).all()

    resultado = []
    for s in solis:
        barb = db.session.get(Barbeiro, s.barbeiro_id)
        barb_nome = barb.usuario.nome if barb and barb.usuario else '—'
        resultado.append({
            'id':               s.id,
            'barbeiro_nome':    barb_nome,
            'data':             s.data.isoformat(),
            'hora_inicio':      s.hora_inicio.strftime('%H:%M') if s.hora_inicio else None,
            'hora_fim':         s.hora_fim.strftime('%H:%M')    if s.hora_fim    else None,
            'dia_inteiro':      s.hora_inicio is None,
            'motivo':           s.motivo,
            'status':           s.status,
            'data_solicitacao': s.data_solicitacao.isoformat() if s.data_solicitacao else None,
        })

    return jsonify(resultado), 200


@gestor_agenda_bp.put('/agenda/solicitacoes-liberacao/<int:solic_id>')
@gestor_required
def responder_solicitacao(solic_id):
    bid = g.barbearia_id
    s   = SolicitacaoLiberacao.query.filter_by(id=solic_id, barbearia_id=bid).first()
    if not s:
        raise APIError('Solicitação não encontrada.', 404)
    if s.status != 'pendente':
        raise APIError(f'Solicitação já foi respondida (status: {s.status}).')

    dados = request.get_json(silent=True) or {}
    novo_status = dados.get('status', '').strip()
    if novo_status not in ('aprovado', 'rejeitado'):
        raise APIError('"status" deve ser "aprovado" ou "rejeitado".')

    s.status      = novo_status
    s.data_resposta = naive_brasilia()
    s.notificado    = False

    if novo_status == 'aprovado':
        # Remover os bloqueios correspondentes
        ini = datetime.combine(s.data, s.hora_inicio or time_t(0, 0))
        fim = datetime.combine(s.data, s.hora_fim or time_t(23, 59, 59))
        blks = HorarioBloqueado.query.filter_by(
            barbearia_id=bid,
            barbeiro_id=s.barbeiro_id,
        ).filter(
            HorarioBloqueado.data_hora_inicio >= ini,
            HorarioBloqueado.data_hora_fim    <= fim + timedelta(minutes=1),
        ).all()
        for blk in blks:
            db.session.delete(blk)

    commit_ou_falhar('gestor.agendamento.responder_solicitacao')
    msg = ('Solicitação aprovada. Bloqueios removidos.' if novo_status == 'aprovado'
           else 'Solicitação rejeitada.')
    return jsonify({'mensagem': msg}), 200


# ══════════════════════════════════════════════════════════════════════════════
# Transferência de agendamento entre barbeiros (Script 17 / Bloco 3.4)
# ══════════════════════════════════════════════════════════════════════════════

_STATUS_TRANSFERIVEL = StatusAgendamento.ATIVOS | {StatusAgendamento.AGUARDANDO_TRANSFERENCIA}


@gestor_agenda_bp.post('/agendamentos/<int:ag_id>/transferir')
@gestor_required
def transferir_agendamento(ag_id):
    bid = g.barbearia_id
    dados = request.get_json(silent=True) or {}
    destino_id = dados.get('barbeiro_id')
    if not isinstance(destino_id, int):
        raise APIError('"barbeiro_id" é obrigatório e deve ser um inteiro.')

    ag = (
        Agendamento.query
        .filter_by(id=ag_id, barbearia_id=bid)
        .with_for_update()
        .first()
    )
    if not ag:
        raise APIError(f'{L("agendamento")} não encontrado.', 404)
    if ag.status not in _STATUS_TRANSFERIVEL:
        raise APIError(f'Não é possível transferir um {L("agendamento").lower()} com status "{ag.status}".', 409)

    destino = Barbeiro.query.filter_by(id=destino_id, barbearia_id=bid, ativo=True).first()
    if not destino:
        raise APIError(f'{L("profissional")} destino não encontrado ou inativo.', 404)
    if destino.id == ag.barbeiro_id:
        raise APIError(f'Este {L("agendamento").lower()} já é deste {L("profissional").lower()}.', 422)

    servico_ids = servicos_do_agendamento(ag.id)
    if not barbeiro_atende_todos_servicos(destino.id, servico_ids):
        raise APIError(f'{L("profissional")} não oferece todos os serviços deste {L("agendamento").lower()}.', 422)

    # Revalidação de horário: verificar_conflito (trava a linha, olha outros
    # agendamentos) + gerar_slots (agenda real: ConfiguracaoAgenda,
    # HorarioBloqueado, PausaBarbeiro) — mesmo padrão do Script 08.
    conflito = verificar_conflito(destino.id, ag.data_hora, ag.duracao_minutos, excluir_id=ag.id)
    if conflito:
        fim_conf = fim_agendamento(conflito.data_hora, conflito.duracao_minutos)
        raise APIError(
            f'{L("profissional")} tem outro agendamento das {conflito.data_hora.strftime("%H:%M")} '
            f'às {fim_conf.strftime("%H:%M")}.',
            409,
        )
    slots_validos = gerar_slots(destino.id, ag.data_hora.date(), ag.duracao_minutos)
    if ag.data_hora.strftime('%H:%M') not in slots_validos:
        raise APIError(f'{L("profissional")} não está disponível nesse horário.', 422)

    origem_id = ag.barbeiro_id
    era_aguardando_transferencia = ag.status == StatusAgendamento.AGUARDANDO_TRANSFERENCIA
    ag.barbeiro_id = destino.id
    if era_aguardando_transferencia:
        # Só força 'agendado' quem estava órfão no mural — um agendamento
        # PIX transferido continua no mesmo status até o fluxo de aprovação
        # normal resolver (a transferência não pula essa etapa).
        ag.status = StatusAgendamento.AGENDADO

    transf = TransferenciaAgendamento.query.filter_by(
        barbearia_id=bid, agendamento_id=ag.id, status=StatusTransferencia.PENDENTE,
    ).first()
    if transf:
        transf.status = StatusTransferencia.CONCLUIDA
        transf.barbeiro_destino_id = destino.id
        transf.concluido_em = naive_brasilia()
    else:
        db.session.add(TransferenciaAgendamento(
            barbearia_id=bid,
            agendamento_id=ag.id,
            barbeiro_origem_id=origem_id,
            barbeiro_destino_id=destino.id,
            motivo='solicitado_gestor',
            status=StatusTransferencia.CONCLUIDA,
            concluido_em=naive_brasilia(),
        ))

    cli = db.session.get(Cliente, ag.cliente_id)
    destino_usr = db.session.get(Usuario, destino.usuario_id)
    destino_nome = destino_usr.nome if destino_usr else L("profissional")
    if cli and cli.usuario_id:
        criar_notificacao(
            barbearia_id=bid,
            usuario_id=cli.usuario_id,
            tipo='agendamento_transferido',
            titulo='Seu atendimento mudou de profissional',
            corpo=f'Seu atendimento agora será com {destino_nome}.',
            canal='in_app',
            agendamento_id=ag.id,
        )

    commit_ou_falhar('gestor.agendamento.transferir_agendamento')
    return jsonify({
        'mensagem': f'{L("agendamento")} transferido para {destino_nome}.',
        'id': ag.id,
        'barbeiro_id': destino.id,
        'status': ag.status,
    }), 200


# ── GET /api/v1/gestor/agendamentos-sem-barbeiro ─────────────────────────────

@gestor_agenda_bp.get('/agendamentos-sem-barbeiro')
@gestor_required
def listar_agendamentos_sem_barbeiro():
    bid = g.barbearia_id
    ags = (
        Agendamento.query
        .filter_by(barbearia_id=bid, status=StatusAgendamento.AGUARDANDO_TRANSFERENCIA)
        .order_by(Agendamento.data_hora)
        .all()
    )
    if not ags:
        return jsonify([]), 200

    barbeiros_ativos = Barbeiro.query.filter_by(barbearia_id=bid, ativo=True).all()
    usuarios_map = {
        u.id: u for u in Usuario.query.filter(
            Usuario.id.in_({b.usuario_id for b in barbeiros_ativos})
        ).all()
    } if barbeiros_ativos else {}

    resultado = []
    for ag in ags:
        cli = db.session.get(Cliente, ag.cliente_id)
        itens = AgendamentoServico.query.filter_by(agendamento_id=ag.id).all()
        servicos_nomes = [s.nome for s in (db.session.get(Servico, it.servico_id) for it in itens) if s]

        elegiveis = []
        for b in barbeiros_ativos:
            if b.id == ag.barbeiro_id:
                continue
            if barbeiro_elegivel_para_transferencia(b.id, ag):
                usr = usuarios_map.get(b.usuario_id)
                elegiveis.append({'id': b.id, 'nome': usr.nome if usr else None})

        resultado.append({
            'id':                  ag.id,
            'cliente_nome':        cli.nome if cli else None,
            'data_hora':           ag.data_hora.isoformat(),
            'duracao_minutos':     ag.duracao_minutos,
            'servicos':            servicos_nomes,
            'barbeiro_origem_id':  ag.barbeiro_id,
            'barbeiros_elegiveis': elegiveis,
        })

    return jsonify(resultado), 200
