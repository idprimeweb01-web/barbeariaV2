from datetime import datetime
from flask import Blueprint, request, g, jsonify
from app.extensions import db
from app.models import Agendamento, AgendamentoServico, Servico, Barbeiro, Cliente, ClienteNota
from app.exceptions import APIError
from app.decorators.auth import barbeiro_required
from app.utils.db import commit_ou_falhar
from app.constants import StatusAgendamento

barbeiro_cli_bp = Blueprint('barbeiro_clientes', __name__, url_prefix='/api/v1/barbeiro')


def _get_barbeiro(user_id, barbearia_id):
    b = Barbeiro.query.filter_by(usuario_id=user_id, barbearia_id=barbearia_id, ativo=True).first()
    if not b:
        raise APIError('Profissional não encontrado.', 404)
    return b


# ── GET /api/v1/barbeiro/clientes ─────────────────────────────────────────────

@barbeiro_cli_bp.get('/clientes')
@barbeiro_required
def listar_clientes():
    b = _get_barbeiro(g.user_id, g.barbearia_id)

    # Clientes distintos com agendamento com este barbeiro
    subq = (
        db.session.query(
            Agendamento.cliente_id,
            db.func.max(Agendamento.data_hora).label('ultima'),
        )
        .filter_by(barbearia_id=g.barbearia_id, barbeiro_id=b.id)
        .group_by(Agendamento.cliente_id)
        .subquery()
    )
    rows = (
        db.session.query(Cliente, subq.c.ultima)
        .join(subq, Cliente.id == subq.c.cliente_id)
        .all()
    )
    # BUG-01: ordena pela data REAL (antes ordenava pela string 'dd/mm/aaaa'
    # já formatada, o que quebrava a ordem entre meses/anos diferentes).
    rows.sort(key=lambda r: r[1] or datetime.min, reverse=True)

    cliente_ids = [cli.id for cli, _ in rows]

    # PERF-01: as 3 seções abaixo eram N+1 (uma query por cliente, e até 3
    # queries extras por agendamento dentro do loop) — agora cada uma é uma
    # única query em lote, independente da quantidade de clientes.

    # Total de visitas concluídas, agrupado por cliente.
    visitas_rows = (
        db.session.query(Agendamento.cliente_id, db.func.count(Agendamento.id).label('total'))
        .filter_by(barbearia_id=g.barbearia_id, barbeiro_id=b.id, status=StatusAgendamento.CONCLUIDO)
        .group_by(Agendamento.cliente_id)
        .all()
    )
    visitas_por_cliente = {r.cliente_id: r.total for r in visitas_rows}

    # Últimos 3 agendamentos por cliente (feito em memória: busca todos os
    # agendamentos deste barbeiro de uma vez, já que o conjunto é limitado
    # aos clientes dele, e mantém só os 3 mais recentes de cada um).
    todos_ags = (
        Agendamento.query
        .filter_by(barbearia_id=g.barbearia_id, barbeiro_id=b.id)
        .order_by(Agendamento.data_hora.desc())
        .all()
    )
    ags_por_cliente = {}
    for ag in todos_ags:
        lista = ags_por_cliente.setdefault(ag.cliente_id, [])
        if len(lista) < 3:
            lista.append(ag)

    ag_ids_relevantes = [ag.id for lista in ags_por_cliente.values() for ag in lista]
    nomes_por_agendamento = {}
    if ag_ids_relevantes:
        itens = (
            db.session.query(AgendamentoServico.agendamento_id, Servico.nome)
            .join(Servico, Servico.id == AgendamentoServico.servico_id)
            .filter(AgendamentoServico.agendamento_id.in_(ag_ids_relevantes))
            .all()
        )
        for agendamento_id, nome in itens:
            nomes_por_agendamento.setdefault(agendamento_id, []).append(nome)

    # Última nota (preferências) por cliente.
    nota_por_cliente = {}
    if cliente_ids:
        notas = (
            ClienteNota.query
            .filter(ClienteNota.barbearia_id == g.barbearia_id, ClienteNota.cliente_id.in_(cliente_ids))
            .order_by(ClienteNota.criado_em.desc())
            .all()
        )
        for n in notas:
            nota_por_cliente.setdefault(n.cliente_id, n)

    resultado = []
    for cli, ultima in rows:
        ultimos = [
            {
                'data':    ag.data_hora.strftime('%d/%m/%Y'),
                'servico': ', '.join(nomes_por_agendamento.get(ag.id, [])) or '—',
            }
            for ag in ags_por_cliente.get(cli.id, [])
        ]
        nota = nota_por_cliente.get(cli.id)

        resultado.append({
            'id':                  cli.id,
            'nome':                cli.nome,
            'telefone':            cli.telefone,
            'ultimos_agendamentos': ultimos,
            'total_visitas':       visitas_por_cliente.get(cli.id, 0),
            'ultima_visita':       ultima.strftime('%d/%m/%Y') if ultima else None,
            'preferencias':        nota.conteudo if nota else None,
        })

    return jsonify(resultado), 200


# ── GET /api/v1/barbeiro/clientes/<id>/historico ─────────────────────────────

@barbeiro_cli_bp.get('/clientes/<int:cliente_id>/historico')
@barbeiro_required
def historico_cliente(cliente_id):
    b   = _get_barbeiro(g.user_id, g.barbearia_id)
    cli = Cliente.query.filter_by(id=cliente_id, barbearia_id=g.barbearia_id).first()
    if not cli:
        raise APIError('Cliente não encontrado.', 404)

    ags = (Agendamento.query
           .filter_by(barbearia_id=g.barbearia_id, cliente_id=cliente_id, barbeiro_id=b.id)
           .order_by(Agendamento.data_hora.desc()).limit(10).all())

    historico = []
    for ag in ags:
        itens = AgendamentoServico.query.filter_by(agendamento_id=ag.id).all()
        nomes = [db.session.get(Servico, it.servico_id).nome
                 for it in itens if db.session.get(Servico, it.servico_id)]
        historico.append({
            'id':               ag.id,
            'data':             ag.data_hora.strftime('%d/%m/%Y'),
            'hora':             ag.data_hora.strftime('%H:%M'),
            'servico':          ', '.join(nomes) or '—',
            'valor':            float(ag.valor_total),
            'status':           ag.status,
            'duracao_minutos':  ag.duracao_minutos,
            'observacao':       ag.observacao,
        })

    # Notas do cliente
    notas = (ClienteNota.query
             .filter_by(barbearia_id=g.barbearia_id, cliente_id=cliente_id)
             .order_by(ClienteNota.criado_em.desc()).all())

    return jsonify({
        'cliente': {'id': cli.id, 'nome': cli.nome, 'telefone': cli.telefone},
        'historico': historico,
        'notas': [{'id': n.id, 'tipo': n.tipo, 'conteudo': n.conteudo,
                   'criado_em': n.criado_em.strftime('%d/%m/%Y') if n.criado_em else None}
                  for n in notas],
    }), 200


# ── GET /api/v1/barbeiro/clientes/<id>/notas ─────────────────────────────────

@barbeiro_cli_bp.get('/clientes/<int:cliente_id>/notas')
@barbeiro_required
def listar_notas(cliente_id):
    _get_barbeiro(g.user_id, g.barbearia_id)
    cli = Cliente.query.filter_by(id=cliente_id, barbearia_id=g.barbearia_id).first()
    if not cli:
        raise APIError('Cliente não encontrado.', 404)

    notas = (ClienteNota.query
             .filter_by(barbearia_id=g.barbearia_id, cliente_id=cliente_id)
             .order_by(ClienteNota.criado_em.desc()).all())
    return jsonify([{
        'id':        n.id,
        'tipo':      n.tipo,
        'conteudo':  n.conteudo,
        'criado_em': n.criado_em.strftime('%d/%m/%Y %H:%M') if n.criado_em else None,
    } for n in notas]), 200


# ── POST /api/v1/barbeiro/clientes/<id>/notas ────────────────────────────────

@barbeiro_cli_bp.post('/clientes/<int:cliente_id>/notas')
@barbeiro_required
def criar_nota(cliente_id):
    _get_barbeiro(g.user_id, g.barbearia_id)
    cli = Cliente.query.filter_by(id=cliente_id, barbearia_id=g.barbearia_id).first()
    if not cli:
        raise APIError('Cliente não encontrado.', 404)

    dados = request.get_json(silent=True) or {}
    texto = (dados.get('texto') or '').strip()
    if not texto:
        raise APIError('"texto" é obrigatório.', 422)
    tipo = (dados.get('categoria') or dados.get('tipo') or 'observacao').strip()

    nota = ClienteNota(
        barbearia_id=g.barbearia_id,
        cliente_id=cliente_id,
        autor_usuario_id=g.user_id,
        tipo=tipo,
        conteudo=texto,
    )
    db.session.add(nota)
    commit_ou_falhar('barbeiro.clientes.criar_nota')
    return jsonify({
        'id':        nota.id,
        'tipo':      nota.tipo,
        'conteudo':  nota.conteudo,
        'criado_em': nota.criado_em.strftime('%d/%m/%Y %H:%M'),
    }), 201
