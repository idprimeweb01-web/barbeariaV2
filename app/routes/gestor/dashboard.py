from flask import Blueprint, g, jsonify
from sqlalchemy import func
from app.extensions import db
from app.models import (
    Agendamento, AgendamentoServico, AgendamentoSolicitacaoPix,
    Servico, Barbeiro, Usuario, Cliente, Produto,
    ClientePlano,
)
from app.decorators.auth import gestor_required
from app.utils.features import feature_ativa
from app.utils.tz import hoje_brasilia
from app.labels import L

gestor_dash_bp = Blueprint('gestor_dashboard', __name__, url_prefix='/api/v1/gestor')


@gestor_dash_bp.get('/dashboard')
@gestor_required
def dashboard_gestor():
    bid = g.barbearia_id
    hoje = hoje_brasilia()
    mes, ano = hoje.month, hoje.year

    # ── Hoje ──────────────────────────────────────────────────────────────────
    ags_hoje_concluidos = Agendamento.query.filter(
        Agendamento.barbearia_id == bid,
        db.func.date(Agendamento.data_hora) == hoje,
        Agendamento.status == 'concluido',
    ).all()
    ags_hoje_agendados = Agendamento.query.filter(
        Agendamento.barbearia_id == bid,
        db.func.date(Agendamento.data_hora) == hoje,
        Agendamento.status == 'agendado',
    ).count()
    ags_hoje_cancelados = Agendamento.query.filter(
        Agendamento.barbearia_id == bid,
        db.func.date(Agendamento.data_hora) == hoje,
        Agendamento.status == 'cancelado',
    ).count()

    receita_hoje = sum(float(ag.valor_total) for ag in ags_hoje_concluidos)

    # ── Mês ───────────────────────────────────────────────────────────────────
    ags_mes_concluidos = Agendamento.query.filter(
        Agendamento.barbearia_id == bid,
        db.extract('year',  Agendamento.data_hora) == ano,
        db.extract('month', Agendamento.data_hora) == mes,
        Agendamento.status == 'concluido',
    ).all()

    receita_mes = sum(float(ag.valor_total) for ag in ags_mes_concluidos)
    n_concluidos_mes = len(ags_mes_concluidos)
    ticket_medio = round(receita_mes / n_concluidos_mes, 2) if n_concluidos_mes else 0.0

    # Todos os agendamentos do mês (qualquer status) para contagem
    total_mes = Agendamento.query.filter(
        Agendamento.barbearia_id == bid,
        db.extract('year',  Agendamento.data_hora) == ano,
        db.extract('month', Agendamento.data_hora) == mes,
    ).count()

    # ── PIX pendentes ─────────────────────────────────────────────────────────
    pendentes_pix = Agendamento.query.filter(
        Agendamento.barbearia_id == bid,
        Agendamento.status.in_(['aguardando_comprovante', 'aguardando_aprovacao', 'aguardando_pagamento']),
    ).count()

    # ── Top serviços do mês ───────────────────────────────────────────────────
    top_servicos_raw = (
        db.session.query(
            AgendamentoServico.servico_id,
            func.count(AgendamentoServico.id).label('qtd'),
            func.sum(AgendamentoServico.preco_unitario).label('total'),
        )
        .join(Agendamento, Agendamento.id == AgendamentoServico.agendamento_id)
        .filter(
            Agendamento.barbearia_id == bid,
            db.extract('year',  Agendamento.data_hora) == ano,
            db.extract('month', Agendamento.data_hora) == mes,
            Agendamento.status.in_(['agendado', 'concluido']),
        )
        .group_by(AgendamentoServico.servico_id)
        .order_by(func.count(AgendamentoServico.id).desc())
        .limit(5)
        .all()
    )
    top_servicos = []
    for row in top_servicos_raw:
        s = db.session.get(Servico, row.servico_id)
        top_servicos.append({
            'servico_id':  row.servico_id,
            'nome':        s.nome if s else None,
            'quantidade':  row.qtd,
            'total':       float(row.total or 0),
        })

    # ── Estoque crítico (só se feature 'produto' não existe — produtos sempre disponíveis)
    estoque_critico = []
    produtos_criticos = Produto.query.filter(
        Produto.barbearia_id == bid,
        Produto.ativo == True,
        Produto.quantidade_estoque <= 5,
    ).order_by(Produto.quantidade_estoque).limit(10).all()
    for p in produtos_criticos:
        estoque_critico.append({
            'id':         p.id,
            'nome':       p.nome,
            'estoque':    p.quantidade_estoque,
        })

    # ── Planos — assinantes ativos (só se feature ativa) ─────────────────────
    assinantes_ativos = None
    if feature_ativa(bid, 'planos'):
        assinantes_ativos = ClientePlano.query.filter_by(
            barbearia_id=bid, ativo=True
        ).count()

    return jsonify({
        'hoje': {
            L('agendamento').lower() + 's_concluidos': len(ags_hoje_concluidos),
            L('agendamento').lower() + 's_agendados':  ags_hoje_agendados,
            L('agendamento').lower() + 's_cancelados': ags_hoje_cancelados,
            L('receita').lower():                      round(receita_hoje, 2),
        },
        'mes': {
            'total_' + L('agendamento').lower() + 's': total_mes,
            'concluidos':                              n_concluidos_mes,
            L('receita').lower():                      round(receita_mes, 2),
            'ticket_medio':                            ticket_medio,
        },
        'pendentes_pix':     pendentes_pix,
        'top_' + L('servicos').lower(): top_servicos,
        'estoque_critico':   estoque_critico,
        'assinantes_ativos': assinantes_ativos,
        'rotulos': {
            'agendamento': L('agendamento'),
            'receita':     L('receita'),
            'servicos':    L('servicos'),
            'produto':     L('produto'),
            'plano':       L('plano'),
            'tenant':      L('tenant'),
            'dashboard':   L('dashboard'),
        },
    }), 200
