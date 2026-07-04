from datetime import datetime
from flask import Blueprint, request, g, jsonify
from app.extensions import db
from app.models import Agendamento, AgendamentoServico, Cliente, Servico, Barbeiro
from app.exceptions import APIError
from app.decorators.auth import cliente_required
from app.utils.agenda import fim_agendamento
from app.utils.cupons import decrementar_uso_cupom
from app.utils.tz import naive_brasilia
from app.labels import L
from app.routes.pub.agendamento import _get_config, _criar_agendamento_core, _fmt_agendamento

cliente_bp = Blueprint('cliente', __name__, url_prefix='/api/v1/cliente')


def _get_cliente_do_usuario():
    """Encontra o Cliente ligado ao g.user_id na barbearia do g.barbearia_id."""
    c = Cliente.query.filter_by(usuario_id=g.user_id, barbearia_id=g.barbearia_id, ativo=True).first()
    if not c:
        raise APIError('Perfil de cliente não encontrado para este usuário.', 404)
    return c


# ── GET /api/v1/cliente/agendamentos ─────────────────────────────────────────

@cliente_bp.get('/agendamentos')
@cliente_required
def listar_agendamentos():
    cliente = _get_cliente_do_usuario()
    q = Agendamento.query.filter_by(cliente_id=cliente.id, barbearia_id=g.barbearia_id)
    status_f = request.args.get('status')
    if status_f:
        q = q.filter_by(status=status_f)
    ags = q.order_by(Agendamento.data_hora.desc()).all()

    resultado = []
    for ag in ags:
        itens = AgendamentoServico.query.filter_by(agendamento_id=ag.id).all()
        servicos_info = []
        for it in itens:
            s = db.session.get(Servico, it.servico_id)
            servicos_info.append({
                'servico_id': it.servico_id,
                'nome':       s.nome if s else None,
                'preco':      float(it.preco_unitario),
                'is_plano':   it.is_plano,
            })
        resultado.append(_fmt_agendamento(ag, servicos_info))

    return jsonify(resultado), 200


# ── POST /api/v1/cliente/agendamentos ────────────────────────────────────────

@cliente_bp.post('/agendamentos')
@cliente_required
def criar_agendamento():
    cliente = _get_cliente_do_usuario()
    barbearia_id = g.barbearia_id

    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    barbeiro_id   = dados.get('barbeiro_id')
    data_hora_str = dados.get('data_hora')
    itens         = dados.get('servicos') or []
    metodo        = (dados.get('metodo_pagamento') or 'local').strip().lower()
    observacao    = (dados.get('observacao') or '').strip() or None
    cupom_codigo  = (dados.get('cupom_codigo') or '').strip() or None

    if not isinstance(barbeiro_id, int):
        raise APIError('"barbeiro_id" é obrigatório e deve ser um inteiro.')
    if not itens:
        raise APIError(f'Pelo menos um {L("servico").lower()} é obrigatório.')
    if not data_hora_str:
        raise APIError('"data_hora" é obrigatório.')

    try:
        data_hora = datetime.fromisoformat(data_hora_str)
    except ValueError:
        raise APIError('"data_hora" inválido. Use ISO 8601 (YYYY-MM-DDTHH:MM:SS).')

    br = Barbeiro.query.filter_by(id=barbeiro_id, barbearia_id=barbearia_id, ativo=True).first()
    if not br:
        raise APIError(f'{L("profissional")} não encontrado.', 404)

    ag, servicos_info, pix_info = _criar_agendamento_core(
        barbearia_id=barbearia_id,
        barbeiro_id=barbeiro_id,
        cliente_id=cliente.id,
        data_hora=data_hora,
        itens=itens,
        metodo=metodo,
        observacao=observacao,
        cupom_codigo=cupom_codigo,
    )

    return jsonify({**_fmt_agendamento(ag, servicos_info), 'pix': pix_info}), 201


# ── POST /api/v1/cliente/agendamentos/<id>/cancelar ──────────────────────────

@cliente_bp.post('/agendamentos/<int:ag_id>/cancelar')
@cliente_required
def cancelar_agendamento(ag_id):
    cliente = _get_cliente_do_usuario()

    ag = Agendamento.query.filter_by(
        id=ag_id, cliente_id=cliente.id, barbearia_id=g.barbearia_id
    ).first()
    if not ag:
        raise APIError(f'{L("agendamento")} não encontrado.', 404)

    if ag.status == 'cancelado':
        raise APIError(f'{L("agendamento")} já está cancelado.')
    if ag.status == 'concluido':
        raise APIError(f'Não é possível cancelar um {L("agendamento").lower()} já concluído.')

    # Lê regra de cancelamento da configuração do tenant (A3)
    config = _get_config(g.barbearia_id)
    horas_min = config.cancelamento_horas_minimas
    agora = naive_brasilia()
    horas_ate = (ag.data_hora - agora).total_seconds() / 3600

    if horas_ate < horas_min:
        raise APIError(
            f'Cancelamento não permitido. O prazo mínimo é de {horas_min}h antes do horário agendado. '
            f'Faltam {max(0, horas_ate):.1f}h.',
            422,
        )

    if ag.cupom_id and ag.status == 'agendado':
        decrementar_uso_cupom(ag.cupom_id)

    ag.status = 'cancelado'
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise APIError(f'Erro ao cancelar {L("agendamento").lower()}. Tente novamente.', 500)
    return jsonify({'mensagem': f'{L("agendamento")} cancelado com sucesso.', 'id': ag_id}), 200
