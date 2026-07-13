from flask import Blueprint, jsonify
from sqlalchemy import func
from app.extensions import db
from app.models import Barbearia, Agendamento, Cliente, Usuario, Venda, VendaItem, ItemCaixa
from app.decorators.auth import super_required
from app.utils.tz import hoje_brasilia
from app.labels import L
from app.constants import StatusAgendamento, StatusPagamento

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
        if ag.status in (StatusAgendamento.AGENDADO, StatusAgendamento.CONCLUIDO)
    )
    concluidos_mes = sum(1 for ag in ags_mes if ag.status == StatusAgendamento.CONCLUIDO)
    cancelados_mes = sum(1 for ag in ags_mes if ag.status == StatusAgendamento.CANCELADO)

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
            Agendamento.status.in_([StatusAgendamento.AGENDADO, StatusAgendamento.CONCLUIDO]),
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

    # ── Pagamentos do mês — TODAS as barbearias, sem filtro de tenant ────────
    # 3 origens que nunca se cruzam em nenhum outro lugar do sistema:
    # Agendamento (recebimento local + pix online), Venda (PDV do gestor),
    # ItemCaixa (caixa diária do barbeiro).
    por_forma = {'dinheiro': 0.0, 'cartao': 0.0, 'pix': 0.0}
    por_origem = {'local': 0.0, 'online': 0.0}

    ags_pagos_mes = [
        ag for ag in ags_mes
        if ag.status_pagamento == StatusPagamento.PAGO
    ]
    for ag in ags_pagos_mes:
        valor = float(ag.valor_total)
        if ag.metodo_pagamento == 'pix':
            por_origem['online'] += valor
        else:
            por_origem['local'] += valor
        if ag.forma_pagamento_recebido in por_forma:
            por_forma[ag.forma_pagamento_recebido] += valor

    vendas_mes = (
        db.session.query(VendaItem, Venda.metodo_pagamento)
        .join(Venda, VendaItem.venda_id == Venda.id)
        .filter(
            Venda.status == 'concluida',
            db.extract('year',  Venda.criado_em) == ano,
            db.extract('month', Venda.criado_em) == mes,
        )
        .all()
    )
    receita_vendas = 0.0
    for vi, metodo in vendas_mes:
        valor = float(vi.preco_unitario) * vi.quantidade
        receita_vendas += valor
        por_origem['local'] += valor
        if metodo in por_forma:
            por_forma[metodo] += valor

    itens_caixa_mes = ItemCaixa.query.filter(
        db.extract('year',  ItemCaixa.criado_em) == ano,
        db.extract('month', ItemCaixa.criado_em) == mes,
    ).all()
    receita_caixa = 0.0
    for item in itens_caixa_mes:
        receita_caixa += item.total
        por_origem['local'] += item.total
        if item.forma_pagamento in por_forma:
            por_forma[item.forma_pagamento] += item.total

    pagamentos_mes = {
        'atendimentos_recebidos': round(sum(float(ag.valor_total) for ag in ags_pagos_mes), 2),
        'vendas_avulsas':         round(receita_vendas, 2),
        'vendas_caixa':           round(receita_caixa, 2),
        'por_forma_pagamento':    {k: round(v, 2) for k, v in por_forma.items()},
        'por_origem':             {k: round(v, 2) for k, v in por_origem.items()},
        'total_geral':            round(sum(por_origem.values()), 2),
    }

    return jsonify({
        'pagamentos_mes': pagamentos_mes,
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
