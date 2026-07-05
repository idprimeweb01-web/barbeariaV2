from flask import Blueprint, request, g, jsonify
from app.extensions import db
from app.models import Agendamento, AgendamentoServico, Servico, Barbeiro, Cliente, ClienteNota
from app.exceptions import APIError
from app.decorators.auth import barbeiro_required
from app.utils.db import commit_ou_falhar

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

    resultado = []
    for cli, ultima in rows:
        # Últimos 3 agendamentos para exibir na tabela
        ags = (Agendamento.query
               .filter_by(barbearia_id=g.barbearia_id, cliente_id=cli.id, barbeiro_id=b.id)
               .order_by(Agendamento.data_hora.desc()).limit(3).all())
        ultimos = []
        for ag in ags:
            itens = AgendamentoServico.query.filter_by(agendamento_id=ag.id).all()
            nomes = [db.session.get(Servico, it.servico_id).nome
                     for it in itens if db.session.get(Servico, it.servico_id)]
            ultimos.append({'data': ag.data_hora.strftime('%d/%m/%Y'), 'servico': ', '.join(nomes) or '—'})

        total_visitas = Agendamento.query.filter_by(
            barbearia_id=g.barbearia_id, cliente_id=cli.id,
            barbeiro_id=b.id, status='concluido',
        ).count()

        # Última nota (preferências)
        ultima_nota = (ClienteNota.query
                       .filter_by(barbearia_id=g.barbearia_id, cliente_id=cli.id)
                       .order_by(ClienteNota.criado_em.desc()).first())

        resultado.append({
            'id':                  cli.id,
            'nome':                cli.nome,
            'telefone':            cli.telefone,
            'ultimos_agendamentos': ultimos,
            'total_visitas':       total_visitas,
            'ultima_visita':       ultima.strftime('%d/%m/%Y') if ultima else None,
            'preferencias':        ultima_nota.conteudo if ultima_nota else None,
        })

    resultado.sort(key=lambda x: x['ultima_visita'] or '', reverse=True)
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
