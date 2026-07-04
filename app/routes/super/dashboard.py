from flask import Blueprint, jsonify
from sqlalchemy import func
from app.extensions import db
from app.models import Barbearia, Agendamento, Cliente, Usuario
from app.decorators.auth import super_required
from app.utils.tz import hoje_brasilia
from app.labels import L

super_dash_bp = Blueprint('super_dashboard', __name__, url_prefix='/api/v1/super')


@super_dash_bp.get('/dashboard')
@super_required
def dashboard_super():
    """
    Agrega métricas de TODAS as barbearias intencionalmente sem filtro de tenant.
    Query sem barbearia_id scope — propósito: visão consolidada da plataforma.
    """
    hoje = hoje_brasilia()
    mes, ano = hoje.month, hoje.year

    # ── Totais de barbearias ──────────────────────────────────────────────────
    total_barbearias_ativas   = Barbearia.query.filter_by(ativo=True).count()
    total_barbearias_inativas = Barbearia.query.filter_by(ativo=False).count()

    # ── Usuários ──────────────────────────────────────────────────────────────
    total_clientes  = Usuario.query.filter_by(perfil='cliente',  ativo=True).count()
    total_barbeiros = Usuario.query.filter_by(perfil='barbeiro', ativo=True).count()
    total_gestores  = Usuario.query.filter_by(perfil='gestor',   ativo=True).count()

    # ── Agendamentos do mês — SEM filtro de barbearia (cross-tenant) ─────────
    ags_mes = (
        Agendamento.query
        .filter(
            db.extract('year',  Agendamento.data_hora) == ano,
            db.extract('month', Agendamento.data_hora) == mes,
        )
        .all()
    )

    n_agendamentos_mes = len(ags_mes)
    receita_mes = sum(
        float(ag.valor_total)
        for ag in ags_mes
        if ag.status in ('agendado', 'concluido')
    )
    concluidos_mes = sum(1 for ag in ags_mes if ag.status == 'concluido')
    cancelados_mes = sum(1 for ag in ags_mes if ag.status == 'cancelado')

    # ── Por barbearia — receita e contagem do mês ─────────────────────────────
    por_barbearia_raw = (
        db.session.query(
            Agendamento.barbearia_id,
            func.count(Agendamento.id).label('n_ags'),
            func.sum(Agendamento.valor_total).label('receita'),
        )
        .filter(
            db.extract('year',  Agendamento.data_hora) == ano,
            db.extract('month', Agendamento.data_hora) == mes,
            Agendamento.status.in_(['agendado', 'concluido']),
        )
        .group_by(Agendamento.barbearia_id)
        .order_by(func.sum(Agendamento.valor_total).desc())
        .all()
    )

    por_barbearia = []
    for row in por_barbearia_raw:
        b = db.session.get(Barbearia, row.barbearia_id)
        por_barbearia.append({
            'barbearia_id':  row.barbearia_id,
            L('tenant').lower(): b.nome if b else None,
            'agendamentos':  row.n_ags,
            L('receita').lower(): float(row.receita or 0),
        })

    return jsonify({
        L('tenants').lower(): {
            'ativas':   total_barbearias_ativas,
            'inativas': total_barbearias_inativas,
        },
        'usuarios': {
            L('cliente').lower() + 's':      total_clientes,
            L('profissional').lower() + 's': total_barbeiros,
            'gestores':                       total_gestores,
        },
        'mes': {
            'total_' + L('agendamento').lower() + 's': n_agendamentos_mes,
            'concluidos':    concluidos_mes,
            'cancelados':    cancelados_mes,
            L('receita').lower() + '_total': round(receita_mes, 2),
        },
        'por_' + L('tenant').lower(): por_barbearia,
        'rotulos': {
            'tenant':       L('tenant'),
            'tenants':      L('tenants'),
            'agendamento':  L('agendamento'),
            'receita':      L('receita'),
            'cliente':      L('cliente'),
            'profissional': L('profissional'),
            'dashboard':    L('dashboard'),
        },
    }), 200
