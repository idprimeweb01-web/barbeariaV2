from datetime import date
from flask import Blueprint, request, g, jsonify
from sqlalchemy.orm import selectinload
from app.extensions import db
from app.models import Agendamento, AgendamentoServico, AgendamentoSolicitacaoPix, Servico, Barbeiro, Cliente, ClienteNota
from app.exceptions import APIError
from app.decorators.auth import barbeiro_required
from app.utils.cupons import incrementar_uso_cupom, decrementar_uso_cupom
from app.utils.tz import hoje_brasilia, naive_brasilia
from app.utils.db import commit_ou_falhar
from app.constants import StatusAgendamento

barbeiro_ag_bp = Blueprint('barbeiro_agendamentos', __name__, url_prefix='/api/v1/barbeiro')


def _get_barbeiro(user_id, barbearia_id):
    b = Barbeiro.query.filter_by(usuario_id=user_id, barbearia_id=barbearia_id, ativo=True).first()
    if not b:
        raise APIError('Profissional não encontrado.', 404)
    return b


def _batch_historico(barbearia_id, cliente_ids):
    """{cliente_id: [até 5 últimas visitas concluídas, mais recente primeiro]}.
    Uma query só (não uma por cliente) — eager load dos itens/serviço junto."""
    if not cliente_ids:
        return {}
    ags_h = (
        Agendamento.query
        .options(selectinload(Agendamento.itens).selectinload(AgendamentoServico.servico))
        .filter(
            Agendamento.barbearia_id == barbearia_id,
            Agendamento.cliente_id.in_(cliente_ids),
            Agendamento.status == StatusAgendamento.CONCLUIDO,
        )
        .order_by(Agendamento.data_hora.desc())
        .all()
    )
    out = {}
    for h in ags_h:
        lst = out.setdefault(h.cliente_id, [])
        if len(lst) >= 5:
            continue
        nomes = [it.servico.nome for it in h.itens if it.servico]
        lst.append({
            'data':    h.data_hora.strftime('%d/%m/%Y'),
            'hora':    h.data_hora.strftime('%H:%M'),
            'servico': ', '.join(nomes) or '—',
            'valor':   float(h.valor_total),
        })
    return out


def _batch_notas(barbearia_id, cliente_ids):
    """{cliente_id: [até 5 notas mais recentes]} — uma query só."""
    if not cliente_ids:
        return {}
    notas_q = (
        ClienteNota.query
        .filter(ClienteNota.barbearia_id == barbearia_id, ClienteNota.cliente_id.in_(cliente_ids))
        .order_by(ClienteNota.criado_em.desc())
        .all()
    )
    out = {}
    for n in notas_q:
        lst = out.setdefault(n.cliente_id, [])
        if len(lst) >= 5:
            continue
        lst.append({
            'conteudo':  n.conteudo, 'tipo': n.tipo,
            'criado_em': n.criado_em.strftime('%d/%m/%Y') if n.criado_em else None,
        })
    return out


def _fmt_ag(ag, cli, historico, notas):
    servicos_info = [
        {
            'nome':            it.servico.nome if it.servico else None,
            'duracao_minutos': it.servico.duracao_minutos if it.servico else None,
            'preco':           float(it.preco_unitario),
        }
        for it in ag.itens
    ]

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
    q = (
        Agendamento.query
        .options(selectinload(Agendamento.itens).selectinload(AgendamentoServico.servico))
        .filter_by(barbearia_id=g.barbearia_id, barbeiro_id=b.id)
    )

    data_f = request.args.get('data')
    if data_f:
        try:
            d = date.fromisoformat(data_f)
        except ValueError:
            raise APIError('"data" deve ser YYYY-MM-DD.', 422)
        q = q.filter(db.func.date(Agendamento.data_hora) == d)
    else:
        q = q.filter(db.func.date(Agendamento.data_hora) == hoje_brasilia())

    status_f = request.args.get('status')
    if status_f:
        q = q.filter(Agendamento.status == status_f)

    ags = q.order_by(Agendamento.data_hora).all()
    if not ags:
        return jsonify([]), 200

    cliente_ids = {ag.cliente_id for ag in ags}
    clientes = {c.id: c for c in Cliente.query.filter(Cliente.id.in_(cliente_ids)).all()}
    historico_map = _batch_historico(g.barbearia_id, cliente_ids)
    notas_map = _batch_notas(g.barbearia_id, cliente_ids)

    return jsonify([
        _fmt_ag(ag, clientes.get(ag.cliente_id), historico_map.get(ag.cliente_id, []), notas_map.get(ag.cliente_id, []))
        for ag in ags
    ]), 200


# ── PATCH iniciar ─────────────────────────────────────────────────────────────

@barbeiro_ag_bp.patch('/agendamentos/<int:ag_id>/iniciar')
@barbeiro_required
def iniciar_agendamento(ag_id):
    b  = _get_barbeiro(g.user_id, g.barbearia_id)
    ag = Agendamento.query.filter_by(id=ag_id, barbearia_id=g.barbearia_id, barbeiro_id=b.id).first()
    if not ag:
        raise APIError('Agendamento não encontrado.', 404)
    if ag.status != StatusAgendamento.AGENDADO:
        raise APIError(f'Não é possível iniciar agendamento com status "{ag.status}".', 422)
    ag.status = StatusAgendamento.EM_ATENDIMENTO
    commit_ou_falhar('barbeiro.agendamentos.iniciar_agendamento')
    return jsonify({'id': ag.id, 'status': ag.status}), 200


# ── PATCH concluir ────────────────────────────────────────────────────────────

@barbeiro_ag_bp.patch('/agendamentos/<int:ag_id>/concluir')
@barbeiro_required
def concluir_agendamento(ag_id):
    b  = _get_barbeiro(g.user_id, g.barbearia_id)
    ag = Agendamento.query.filter_by(id=ag_id, barbearia_id=g.barbearia_id, barbeiro_id=b.id).first()
    if not ag:
        raise APIError('Agendamento não encontrado.', 404)
    if ag.status not in (StatusAgendamento.AGENDADO, StatusAgendamento.EM_ATENDIMENTO):
        raise APIError(f'Não é possível concluir agendamento com status "{ag.status}".', 422)
    dados = request.get_json(silent=True) or {}
    if dados.get('notas_internas'):
        ag.observacao = str(dados['notas_internas'])[:300]
    ag.status = StatusAgendamento.CONCLUIDO
    commit_ou_falhar('barbeiro.agendamentos.concluir_agendamento')
    return jsonify({'id': ag.id, 'status': ag.status}), 200


# ── PATCH cancelar ────────────────────────────────────────────────────────────

@barbeiro_ag_bp.patch('/agendamentos/<int:ag_id>/cancelar')
@barbeiro_required
def cancelar_agendamento(ag_id):
    b  = _get_barbeiro(g.user_id, g.barbearia_id)
    ag = Agendamento.query.filter_by(id=ag_id, barbearia_id=g.barbearia_id, barbeiro_id=b.id).first()
    if not ag:
        raise APIError('Agendamento não encontrado.', 404)
    if ag.status in (StatusAgendamento.CONCLUIDO, StatusAgendamento.CANCELADO):
        raise APIError(f'Agendamento já está "{ag.status}".', 422)
    dados = request.get_json(silent=True) or {}
    motivo = (dados.get('motivo') or '').strip()
    if motivo:
        ag.observacao = motivo[:300]
    if ag.cupom_id and ag.status == StatusAgendamento.AGENDADO:
        decrementar_uso_cupom(ag.cupom_id, ag.barbearia_id)
    ag.status = StatusAgendamento.CANCELADO
    commit_ou_falhar('barbeiro.agendamentos.cancelar_agendamento')
    return jsonify({'id': ag.id, 'status': ag.status}), 200


# ── PATCH aprovar-comprovante ─────────────────────────────────────────────────

@barbeiro_ag_bp.patch('/agendamentos/<int:ag_id>/aprovar-comprovante')
@barbeiro_required
def aprovar_comprovante(ag_id):
    b  = _get_barbeiro(g.user_id, g.barbearia_id)
    ag = (
        Agendamento.query
        .filter_by(id=ag_id, barbearia_id=g.barbearia_id, barbeiro_id=b.id)
        .with_for_update()
        .first()
    )
    if not ag:
        raise APIError('Agendamento não encontrado.', 404)
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
    commit_ou_falhar('barbeiro.agendamentos.aprovar_comprovante')
    return jsonify({'id': ag.id, 'status': StatusAgendamento.AGENDADO}), 200


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
    commit_ou_falhar('barbeiro.agendamentos.adicionar_nota_agendamento')
    return jsonify({
        'id':        nota.id,
        'conteudo':  nota.conteudo,
        'tipo':      nota.tipo,
        'criado_em': nota.criado_em.strftime('%d/%m/%Y %H:%M'),
    }), 201
