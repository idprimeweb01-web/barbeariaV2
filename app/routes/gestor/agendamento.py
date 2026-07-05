import calendar
from datetime import date, datetime, timedelta, time as time_t
from flask import Blueprint, request, g, jsonify
from app.extensions import db
from app.models import (
    Agendamento, AgendamentoServico, AgendamentoSolicitacaoPix,
    Cliente, Servico, Barbeiro, Usuario,
    HorarioBloqueado, ConfiguracaoAgenda, SolicitacaoLiberacao, BarbeiroServico,
)
from app.exceptions import APIError
from app.decorators.auth import gestor_required
from app.utils.agenda import fim_agendamento, verificar_conflito
from app.utils.cupons import incrementar_uso_cupom, decrementar_uso_cupom
from app.utils.tz import naive_brasilia
from app.labels import L
from app.utils import normalizar_telefone

gestor_agenda_bp = Blueprint('gestor_agenda', __name__, url_prefix='/api/v1/gestor')

# Mesma lista aceita pelo CHECK constraint ck_agendamentos_status_valido (Bloco 2.1).
# Migra para app/constants.py no Script 14.
_STATUS_AGENDAMENTO_VALIDOS = {
    'agendado', 'concluido', 'cancelado', 'em_atendimento',
    'aguardando_comprovante', 'aguardando_aprovacao', 'aguardando_pagamento',
    'nao_realizado', 'aguardando_transferencia',
}


def _fmt_ag_gestor(ag):
    fim = fim_agendamento(ag.data_hora, ag.duracao_minutos)
    cliente = db.session.get(Cliente, ag.cliente_id)
    barbeiro = db.session.get(Barbeiro, ag.barbeiro_id)
    barbeiro_nome = barbeiro.usuario.nome if barbeiro and barbeiro.usuario else None

    itens = AgendamentoServico.query.filter_by(agendamento_id=ag.id).all()
    servicos_info = []
    for it in itens:
        s = db.session.get(Servico, it.servico_id)
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

    pix = AgendamentoSolicitacaoPix.query.filter_by(agendamento_id=ag.id, barbearia_id=ag.barbearia_id).first()

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
    q = Agendamento.query.filter_by(barbearia_id=g.barbearia_id)

    data_f = request.args.get('data')
    if data_f:
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
        if status_f not in _STATUS_AGENDAMENTO_VALIDOS:
            raise APIError(f'Status inválido: "{status_f}".', 422)
        q = q.filter_by(status=status_f)

    ags = q.order_by(Agendamento.data_hora).all()
    return jsonify([_fmt_ag_gestor(ag) for ag in ags]), 200


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
def aprovar_agendamento(ag_id):
    ag = Agendamento.query.filter_by(id=ag_id, barbearia_id=g.barbearia_id).first()
    if not ag:
        raise APIError(f'{L("agendamento")} não encontrado.', 404)
    _aprovavel = {'aguardando_aprovacao', 'aguardando_comprovante', 'aguardando_pagamento'}
    if ag.status not in _aprovavel:
        raise APIError(
            f'Agendamento não pode ser aprovado. Status atual: "{ag.status}".'
        )

    pix = AgendamentoSolicitacaoPix.query.filter_by(agendamento_id=ag.id, barbearia_id=ag.barbearia_id).first()
    if pix:
        pix.status = 'aprovado'
        pix.respondido_em = naive_brasilia()

    if ag.cupom_id:
        incrementar_uso_cupom(ag.cupom_id)

    ag.status = 'agendado'
    db.session.commit()
    return jsonify({'mensagem': f'{L("agendamento")} aprovado.', 'id': ag_id, 'status': 'agendado'}), 200


# ── PUT /api/v1/gestor/agendamentos/<id>/cancelar ────────────────────────────

@gestor_agenda_bp.put('/agendamentos/<int:ag_id>/cancelar')
@gestor_required
def cancelar_agendamento_gestor(ag_id):
    ag = Agendamento.query.filter_by(id=ag_id, barbearia_id=g.barbearia_id).first()
    if not ag:
        raise APIError(f'{L("agendamento")} não encontrado.', 404)
    if ag.status in ('cancelado', 'concluido'):
        raise APIError(f'Não é possível cancelar. Status atual: "{ag.status}".')

    pix = AgendamentoSolicitacaoPix.query.filter_by(agendamento_id=ag.id, barbearia_id=ag.barbearia_id).first()
    if pix and pix.status == 'pendente':
        pix.status = 'rejeitado'

    if ag.cupom_id and ag.status == 'agendado':
        decrementar_uso_cupom(ag.cupom_id)

    ag.status = 'cancelado'
    db.session.commit()
    return jsonify({'mensagem': f'{L("agendamento")} cancelado pelo gestor.', 'id': ag_id}), 200


# ══════════════════════════════════════════════════════════════════════════════
# Grade do Dia
# ══════════════════════════════════════════════════════════════════════════════

def _fmt_ag_grade(ag):
    """Formato compacto para exibição na grade diária."""
    cliente = db.session.get(Cliente, ag.cliente_id)
    itens   = AgendamentoServico.query.filter_by(agendamento_id=ag.id).all()

    sv_nome  = '—'
    sv_preco = 0.0
    servicos = []
    for it in itens:
        sv = db.session.get(Servico, it.servico_id)
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
        .filter(
            Agendamento.barbearia_id == bid,
            Agendamento.barbeiro_id == barbeiro_f,
            Agendamento.data_hora >= dia_ini,
            Agendamento.data_hora <= dia_fim,
        )
        .order_by(Agendamento.data_hora)
        .all()
    )

    return jsonify({
        'config':       {
            'horario_abertura':   config.horario_abertura.strftime('%H:%M') if config and config.horario_abertura else None,
            'horario_fechamento': config.horario_fechamento.strftime('%H:%M') if config and config.horario_fechamento else None,
            'intervalo_minutos':  config.intervalo_minutos if config else 30,
        } if config else None,
        'servicos':     [{'id': s.id, 'nome': s.nome, 'duracao_minutos': s.duracao_minutos, 'preco': float(s.preco)} for s in servicos],
        'agendamentos': [_fmt_ag_grade(ag) for ag in ags],
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
        status='agendado',
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
    db.session.commit()

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

    db.session.commit()
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

    db.session.commit()
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
    db.session.commit()
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

    db.session.commit()
    msg = ('Solicitação aprovada. Bloqueios removidos.' if novo_status == 'aprovado'
           else 'Solicitação rejeitada.')
    return jsonify({'mensagem': msg}), 200
