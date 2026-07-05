from datetime import timedelta
from flask import Blueprint, request, g, jsonify
from sqlalchemy import func
from app.extensions import db
from app.models import Cliente, Usuario, Agendamento, AgendamentoServico, Servico, Barbeiro
from app.exceptions import APIError
from app.decorators.auth import gestor_required
from app.labels import L
from app.utils.tz import hoje_brasilia, naive_brasilia

gestor_clientes_bp = Blueprint('gestor_clientes', __name__, url_prefix='/api/v1/gestor')

# Migra para app/constants.py no Script 14.
_STATUS_CLIENTE_VALIDOS = {'ativo', 'novos', 'em_risco', 'vip', 'inativos'}


def _bid():
    bid = g.barbearia_id
    if not bid:
        raise APIError('Sem barbearia no contexto.', 403)
    return bid


def _stats_map(bid):
    """Retorna {cliente_id: (visitas, gasto, ultima_visita)} para todos os clientes com agendamentos concluídos."""
    rows = (
        db.session.query(
            Agendamento.cliente_id,
            func.count(Agendamento.id).label('visitas'),
            func.sum(Agendamento.valor_total).label('gasto'),
            func.max(Agendamento.data_hora).label('ultima'),
        )
        .filter(Agendamento.barbearia_id == bid, Agendamento.status == 'concluido')
        .group_by(Agendamento.cliente_id)
        .all()
    )
    return {r.cliente_id: (int(r.visitas), float(r.gasto or 0), r.ultima) for r in rows}


def _status_cliente(c, visitas, gasto, ultima, hoje):
    if not c.ativo:
        return 'inativo'
    if gasto >= 500:
        return 'vip'
    if c.criado_em and (hoje - c.criado_em.date()).days <= 7:
        return 'novo'
    if ultima and (naive_brasilia() - ultima).days > 60:
        return 'em_risco'
    return 'ativo'


def _fmt_cliente(c, visitas=0, gasto=0.0, ultima=None, hoje=None):
    hoje = hoje or hoje_brasilia()
    ticket = round(gasto / visitas, 2) if visitas else 0.0
    return {
        'id':            c.id,
        'nome':          c.nome,
        'telefone':      c.telefone,
        'email':         c.email,
        'foto':          c.foto,
        'criado_em':     c.criado_em.isoformat() if c.criado_em else None,
        'ativo':         c.ativo,
        'total_visitas': visitas,
        'total_gasto':   gasto,
        'ticket_medio':  ticket,
        'ultima_visita': ultima.isoformat() if ultima else None,
        'status':        _status_cliente(c, visitas, gasto, ultima, hoje),
    }


@gestor_clientes_bp.get('/clientes')
@gestor_required
def listar_clientes():
    bid     = _bid()
    hoje    = hoje_brasilia()
    mes_ini = hoje.replace(day=1)
    agora   = naive_brasilia()

    q_texto  = request.args.get('q', '').strip()
    filtro   = request.args.get('status', '').strip()
    barb_f   = request.args.get('barbeiro_id', type=int)

    if filtro and filtro not in _STATUS_CLIENTE_VALIDOS:
        raise APIError(f'Status inválido: "{filtro}".', 422)

    if barb_f:
        b = Barbeiro.query.filter_by(id=barb_f, barbearia_id=bid).first()
        if not b:
            raise APIError(f'{L("profissional")} não encontrado.', 404)

    try:
        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 50))))
    except ValueError:
        raise APIError('"page" e "per_page" devem ser inteiros.', 422)

    # ── Todos os clientes do tenant — usado só para os widgets agregados
    # (stats/gráfico/insights), que precisam do panorama completo por natureza.
    # A tabela paginada abaixo NUNCA usa esta lista. ────────────────────────────
    todos = Cliente.query.filter_by(barbearia_id=bid).all()
    stats = _stats_map(bid)

    # ── Query da tabela: busca migrada pro SQL, paginação no banco ────────────
    q = Cliente.query.filter_by(barbearia_id=bid)
    if q_texto:
        like = f'%{q_texto}%'
        q = q.filter(
            db.or_(
                Cliente.nome.ilike(like),
                Cliente.telefone.ilike(like),
                Cliente.email.ilike(like),
            )
        )
    if barb_f:
        ids_barb = {ag.cliente_id for ag in
                    Agendamento.query.filter_by(barbearia_id=bid, barbeiro_id=barb_f).all()}
        q = q.filter(Cliente.id.in_(ids_barb))

    if filtro:
        # A classificação depende de visitas/gasto agregados (stats, já calculado
        # em UMA query acima) — não sobre .all() de objetos completos por cliente.
        ids_status = set()
        for c in todos:
            v, gv, u = stats.get(c.id, (0, 0.0, None))
            st = _status_cliente(c, v, gv, u, hoje)
            dias_sem_visita = int((agora - u).days) if u else None
            match = False
            if filtro == 'ativo'      and st == 'ativo':  match = True
            elif filtro == 'novos'    and st == 'novo':   match = True
            elif filtro == 'em_risco' and st == 'em_risco': match = True
            elif filtro == 'vip'      and st == 'vip':    match = True
            elif filtro == 'inativos' and (
                (u is None and v == 0) or (dias_sem_visita is not None and dias_sem_visita > 30)
            ):
                match = True
            if match:
                ids_status.add(c.id)
        q = q.filter(Cliente.id.in_(ids_status))

    paginado = q.order_by(Cliente.nome).paginate(page=page, per_page=per_page, error_out=False)

    # ── Stats por cliente calculados só para os itens da página atual ─────────
    resultado = []
    for c in paginado.items:
        v, gv, u = stats.get(c.id, (0, 0.0, None))
        resultado.append(_fmt_cliente(c, v, gv, u, hoje))

    # ── Stats totais (independentes dos filtros) ──────────────────────────────
    total      = len(todos)
    novos_mes  = sum(1 for c in todos if c.criado_em and c.criado_em.date() >= mes_ini)
    inat_30d   = 0
    vip_count  = 0
    gastos_lst = []
    retencao   = 0
    for c in todos:
        v2, gv2, u2 = stats.get(c.id, (0, 0.0, None))
        sem_visita = (u2 is None and v2 == 0) or (u2 and (agora - u2).days > 30)
        if sem_visita:
            inat_30d += 1
        if gv2 >= 500:
            vip_count += 1
        if v2 > 0:
            gastos_lst.append(gv2)
        if v2 >= 2:
            retencao += 1

    ticket_medio  = round(sum(gastos_lst) / len(gastos_lst), 2) if gastos_lst else 0
    retencao_pct  = round(retencao * 100 / total, 1) if total else 0

    # ── Gráfico: novos por mês (últimos 6 meses) ──────────────────────────────
    chart = []
    for i in range(5, -1, -1):
        ref  = (mes_ini - timedelta(days=i * 30)).replace(day=1)
        if ref.month < 12:
            prox = ref.replace(month=ref.month + 1)
        else:
            prox = ref.replace(year=ref.year + 1, month=1)
        label = f'{ref.strftime("%b")}/{str(ref.year)[2:]}'
        count = sum(1 for c in todos if c.criado_em and ref <= c.criado_em.date() < prox)
        chart.append({'label': label, 'value': count})

    # ── Insights ──────────────────────────────────────────────────────────────
    em_risco  = []
    follow_up = []
    novos_7d  = []
    top5_lst  = []

    for c in todos:
        if not c.ativo:
            continue
        v2, gv2, u2 = stats.get(c.id, (0, 0.0, None))
        dias = int((agora - u2).days) if u2 else None
        row = {'id': c.id, 'nome': c.nome, 'tel': c.telefone, 'gasto': gv2, 'dias': dias}

        if u2 is None or (dias is not None and dias > 60):
            em_risco.append(row)
        elif dias is not None and 7 < dias <= 30:
            follow_up.append(row)
        if c.criado_em and (hoje - c.criado_em.date()).days <= 7:
            novos_7d.append(row)
        top5_lst.append({'id': c.id, 'nome': c.nome, 'tel': c.telefone, 'gasto': gv2})

    em_risco  = sorted(em_risco,  key=lambda x: x['dias'] or 9999, reverse=True)[:5]
    follow_up = sorted(follow_up, key=lambda x: x['dias'], reverse=True)[:5]
    novos_7d  = novos_7d[:5]
    top5_lst  = sorted(top5_lst, key=lambda x: x['gasto'], reverse=True)[:5]

    return jsonify({
        'stats': {
            'total':        total,
            'novos_mes':    novos_mes,
            'inativos_30d': inat_30d,
            'ticket_medio': ticket_medio,
            'retencao_pct': retencao_pct,
            'vip':          vip_count,
        },
        'chart_novos': chart,
        'dados':       resultado,
        'page':        paginado.page,
        'per_page':    paginado.per_page,
        'total':       paginado.total,
        'pages':       paginado.pages,
        'insights': {
            'em_risco':  em_risco,
            'follow_up': follow_up,
            'novos_7d':  novos_7d,
            'top5':      top5_lst,
        },
    }), 200


@gestor_clientes_bp.get('/clientes/<int:cliente_id>')
@gestor_required
def perfil_cliente(cliente_id):
    bid = _bid()
    c   = Cliente.query.filter_by(id=cliente_id, barbearia_id=bid).first()
    if not c:
        raise APIError('Cliente não encontrado.', 404)

    v, gv, u = _stats_map(bid).get(c.id, (0, 0.0, None))

    top_sv = (
        db.session.query(AgendamentoServico.servico_id, func.count(AgendamentoServico.id).label('qtd'))
        .join(Agendamento, Agendamento.id == AgendamentoServico.agendamento_id)
        .filter(
            Agendamento.barbearia_id == bid,
            Agendamento.cliente_id == c.id,
            Agendamento.status == 'concluido',
        )
        .group_by(AgendamentoServico.servico_id)
        .order_by(func.count(AgendamentoServico.id).desc())
        .first()
    )
    servico_fav = None
    if top_sv:
        sv = db.session.get(Servico, top_sv.servico_id)
        servico_fav = sv.nome if sv else None

    hist_ags = (
        Agendamento.query
        .filter_by(barbearia_id=bid, cliente_id=c.id, status='concluido')
        .order_by(Agendamento.data_hora.desc())
        .limit(5)
        .all()
    )
    historico = []
    for ag in hist_ags:
        barb = db.session.get(Barbeiro, ag.barbeiro_id)
        barb_nome = barb.usuario.nome if barb and barb.usuario else '—'
        itens = AgendamentoServico.query.filter_by(agendamento_id=ag.id).all()
        sv_nome = '—'
        if itens:
            sv = db.session.get(Servico, itens[0].servico_id)
            sv_nome = sv.nome if sv else '—'
        historico.append({
            'data':     ag.data_hora.isoformat(),
            'servico':  sv_nome,
            'barbeiro': barb_nome,
            'valor':    float(ag.valor_total),
        })

    return jsonify({
        'dados_pessoais': {
            'id':          c.id,
            'nome':        c.nome,
            'telefone':    c.telefone,
            'email':       c.email,
            'foto':        c.foto,
            'observacoes': c.observacoes,
        },
        'total_visitas':      v,
        'total_gasto':        gv,
        'ultima_visita':      u.isoformat() if u else None,
        'servico_mais_feito': servico_fav,
        'historico':          historico,
    }), 200


@gestor_clientes_bp.patch('/clientes/<int:cliente_id>')
@gestor_required
def editar_cliente(cliente_id):
    bid = _bid()
    c   = Cliente.query.filter_by(id=cliente_id, barbearia_id=bid).first()
    if not c:
        raise APIError('Cliente não encontrado.', 404)

    dados = request.get_json(silent=True) or {}

    if 'nome' in dados:
        nome = (dados['nome'] or '').strip()
        if not nome:
            raise APIError('"nome" não pode ser vazio.')
        c.nome = nome
    if 'email' in dados:
        c.email = (dados['email'] or '').strip().lower() or None
    if 'telefone' in dados:
        tel = (dados['telefone'] or '').strip()
        if tel:
            c.telefone = tel
    if 'observacoes' in dados:
        c.observacoes = (dados['observacoes'] or '').strip() or None
    if 'data_nascimento' in dados:
        from datetime import date as date_cls
        val = dados['data_nascimento']
        if val:
            try:
                c.data_nascimento = date_cls.fromisoformat(val)
            except ValueError:
                raise APIError('"data_nascimento" inválido. Use YYYY-MM-DD.')
        else:
            c.data_nascimento = None
    if 'ativo' in dados:
        c.ativo = bool(dados['ativo'])
        if c.usuario_id:
            u_obj = db.session.get(Usuario, c.usuario_id)
            if u_obj:
                u_obj.ativo = c.ativo

    db.session.commit()
    return jsonify({'mensagem': 'Cliente atualizado.', 'id': c.id}), 200
