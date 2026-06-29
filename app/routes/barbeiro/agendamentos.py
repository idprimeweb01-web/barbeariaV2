from datetime import date
from flask import Blueprint, request, g, jsonify
from app.extensions import db
from app.models import Agendamento, AgendamentoServico, Servico, Barbeiro, Cliente, ClienteNota
from app.exceptions import APIError
from app.decorators.auth import barbeiro_required

barbeiro_ag_bp = Blueprint('barbeiro_agendamentos', __name__, url_prefix='/api/v1/barbeiro')


def _get_barbeiro(user_id, barbearia_id):
    b = Barbeiro.query.filter_by(usuario_id=user_id, barbearia_id=barbearia_id, ativo=True).first()
    if not b:
        raise APIError('Profissional não encontrado.', 404)
    return b


def _fmt_ag(ag):
    cli   = db.session.get(Cliente, ag.cliente_id)
    itens = AgendamentoServico.query.filter_by(agendamento_id=ag.id).all()
    servicos_info = []
    for it in itens:
        s = db.session.get(Servico, it.servico_id)
        servicos_info.append({
            'nome':             s.nome if s else None,
            'duracao_minutos':  s.duracao_minutos if s else None,
            'preco':            float(it.preco_unitario),
        })

    # Últimas 5 visitas do cliente (concluídas)
    historico = []
    if cli:
        ags_h = (Agendamento.query
                 .filter_by(barbearia_id=ag.barbearia_id, cliente_id=cli.id, status='concluido')
                 .order_by(Agendamento.data_hora.desc()).limit(5).all())
        for h in ags_h:
            h_itens = AgendamentoServico.query.filter_by(agendamento_id=h.id).all()
            nomes   = [db.session.get(Servico, hi.servico_id).nome
                       for hi in h_itens
                       if db.session.get(Servico, hi.servico_id)]
            historico.append({
                'data':    h.data_hora.strftime('%d/%m/%Y'),
                'hora':    h.data_hora.strftime('%H:%M'),
                'servico': ', '.join(nomes) or '—',
                'valor':   float(h.valor_total),
            })

    # Notas do cliente registradas por qualquer barbeiro desta barbearia
    notas = []
    if cli:
        notas_q = (ClienteNota.query
                   .filter_by(barbearia_id=ag.barbearia_id, cliente_id=cli.id)
                   .order_by(ClienteNota.criado_em.desc()).limit(5).all())
        notas = [{'conteudo': n.conteudo, 'tipo': n.tipo,
                  'criado_em': n.criado_em.strftime('%d/%m/%Y') if n.criado_em else None}
                 for n in notas_q]

    return {
        'id':              ag.id,
        'status':          ag.status,
        'valor_total':     float(ag.valor_total),
        'duracao_minutos': ag.duracao_minutos,
        'inicio':          ag.data_hora.isoformat(),
        'hora':            ag.data_hora.strftime('%H:%M'),
        'data':            ag.data_hora.strftime('%d/%m/%Y'),
        'observacao':      ag.observacao,
        'cliente': {'id': cli.id, 'nome': cli.nome, 'telefone': cli.telefone} if cli else None,
        'servicos':        servicos_info,
        'historico_cliente': historico,
        'notas_cliente':   notas,
    }


# ── GET /api/v1/barbeiro/agendamentos ─────────────────────────────────────────

@barbeiro_ag_bp.get('/agendamentos')
@barbeiro_required
def listar_agendamentos():
    b = _get_barbeiro(g.user_id, g.barbearia_id)
    q = Agendamento.query.filter_by(barbearia_id=g.barbearia_id, barbeiro_id=b.id)

    data_f = request.args.get('data')
    if data_f:
        try:
            d = date.fromisoformat(data_f)
        except ValueError:
            raise APIError('"data" deve ser YYYY-MM-DD.', 422)
        q = q.filter(db.func.date(Agendamento.data_hora) == d)
    else:
        q = q.filter(db.func.date(Agendamento.data_hora) == date.today())

    status_f = request.args.get('status')
    if status_f:
        q = q.filter(Agendamento.status == status_f)

    ags = q.order_by(Agendamento.data_hora).all()
    return jsonify([_fmt_ag(ag) for ag in ags]), 200


# ── PATCH iniciar ─────────────────────────────────────────────────────────────

@barbeiro_ag_bp.patch('/agendamentos/<int:ag_id>/iniciar')
@barbeiro_required
def iniciar_agendamento(ag_id):
    b  = _get_barbeiro(g.user_id, g.barbearia_id)
    ag = Agendamento.query.filter_by(id=ag_id, barbearia_id=g.barbearia_id, barbeiro_id=b.id).first()
    if not ag:
        raise APIError('Agendamento não encontrado.', 404)
    if ag.status != 'agendado':
        raise APIError(f'Não é possível iniciar agendamento com status "{ag.status}".', 422)
    ag.status = 'em_atendimento'
    db.session.commit()
    return jsonify({'id': ag.id, 'status': ag.status}), 200


# ── PATCH concluir ────────────────────────────────────────────────────────────

@barbeiro_ag_bp.patch('/agendamentos/<int:ag_id>/concluir')
@barbeiro_required
def concluir_agendamento(ag_id):
    b  = _get_barbeiro(g.user_id, g.barbearia_id)
    ag = Agendamento.query.filter_by(id=ag_id, barbearia_id=g.barbearia_id, barbeiro_id=b.id).first()
    if not ag:
        raise APIError('Agendamento não encontrado.', 404)
    if ag.status not in ('agendado', 'em_atendimento'):
        raise APIError(f'Não é possível concluir agendamento com status "{ag.status}".', 422)
    dados = request.get_json(silent=True) or {}
    if dados.get('notas_internas'):
        ag.observacao = str(dados['notas_internas'])[:300]
    ag.status = 'concluido'
    db.session.commit()
    return jsonify({'id': ag.id, 'status': ag.status}), 200


# ── PATCH cancelar ────────────────────────────────────────────────────────────

@barbeiro_ag_bp.patch('/agendamentos/<int:ag_id>/cancelar')
@barbeiro_required
def cancelar_agendamento(ag_id):
    b  = _get_barbeiro(g.user_id, g.barbearia_id)
    ag = Agendamento.query.filter_by(id=ag_id, barbearia_id=g.barbearia_id, barbeiro_id=b.id).first()
    if not ag:
        raise APIError('Agendamento não encontrado.', 404)
    if ag.status in ('concluido', 'cancelado'):
        raise APIError(f'Agendamento já está "{ag.status}".', 422)
    dados = request.get_json(silent=True) or {}
    motivo = (dados.get('motivo') or '').strip()
    if motivo:
        ag.observacao = motivo[:300]
    ag.status = 'cancelado'
    db.session.commit()
    return jsonify({'id': ag.id, 'status': ag.status}), 200


# ── POST notas (salva como ClienteNota) ───────────────────────────────────────

@barbeiro_ag_bp.post('/agendamentos/<int:ag_id>/notas')
@barbeiro_required
def adicionar_nota_agendamento(ag_id):
    b  = _get_barbeiro(g.user_id, g.barbearia_id)
    ag = Agendamento.query.filter_by(id=ag_id, barbearia_id=g.barbearia_id, barbeiro_id=b.id).first()
    if not ag:
        raise APIError('Agendamento não encontrado.', 404)
    dados = request.get_json(silent=True) or {}
    texto = (dados.get('texto') or '').strip()
    if not texto:
        raise APIError('"texto" é obrigatório.', 422)
    nota = ClienteNota(
        barbearia_id=g.barbearia_id,
        cliente_id=ag.cliente_id,
        autor_usuario_id=g.user_id,
        tipo=dados.get('tipo') or 'observacao',
        conteudo=texto,
    )
    db.session.add(nota)
    db.session.commit()
    return jsonify({
        'id':        nota.id,
        'conteudo':  nota.conteudo,
        'tipo':      nota.tipo,
        'criado_em': nota.criado_em.strftime('%d/%m/%Y %H:%M'),
    }), 201
