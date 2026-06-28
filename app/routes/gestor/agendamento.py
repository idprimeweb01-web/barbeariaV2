from flask import Blueprint, request, g, jsonify
from app.extensions import db
from app.models import (
    Agendamento, AgendamentoServico, AgendamentoSolicitacaoPix,
    Cliente, Servico, Barbeiro, Usuario,
)
from app.exceptions import APIError
from app.decorators.auth import gestor_required
from app.utils.agenda import fim_agendamento
from app.labels import L

gestor_agenda_bp = Blueprint('gestor_agenda', __name__, url_prefix='/api/v1/gestor')


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

    pix = AgendamentoSolicitacaoPix.query.filter_by(agendamento_id=ag.id).first()

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
        'pix':              {'status': pix.status} if pix else None,
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
        q = q.filter_by(barbeiro_id=barbeiro_f)

    status_f = request.args.get('status')
    if status_f:
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
    if ag.status != 'aguardando_pagamento':
        raise APIError(
            f'Apenas agendamentos com status "aguardando_pagamento" podem ser aprovados. '
            f'Status atual: "{ag.status}".'
        )

    pix = AgendamentoSolicitacaoPix.query.filter_by(agendamento_id=ag.id).first()
    if pix:
        pix.status = 'aprovado'
        from datetime import datetime
        pix.respondido_em = datetime.utcnow()

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

    pix = AgendamentoSolicitacaoPix.query.filter_by(agendamento_id=ag.id).first()
    if pix and pix.status == 'pendente':
        pix.status = 'rejeitado'

    ag.status = 'cancelado'
    db.session.commit()
    return jsonify({'mensagem': f'{L("agendamento")} cancelado pelo gestor.', 'id': ag_id}), 200
