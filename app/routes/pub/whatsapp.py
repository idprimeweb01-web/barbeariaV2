"""
Endpoints públicos de apoio ao bot de agendamento via WhatsApp (n8n + Evolution
API). Mesma filosofia de confiança do quick-booking em pub/agendamento.py:
sem login, identificação por telefone (quem manda a mensagem já provou ser
dono do número, na própria conversa do WhatsApp).
"""
from flask import Blueprint, request, jsonify
from app.extensions import db, limiter
from app.models import Barbearia, Cliente, Agendamento, AgendamentoServico, Servico, Barbeiro, Usuario, Segmento
from app.exceptions import APIError
from app.utils import normalizar_telefone
from app.utils.tz import naive_brasilia
from app.constants import StatusAgendamento
from app.labels import L

pub_whatsapp_bp = Blueprint('pub_whatsapp', __name__, url_prefix='/api/v1/pub')


# ── GET /api/v1/pub/barbearia-por-instancia?instance=...&telefone=... ────────
# Não é escopado por slug (é exatamente o que resolve) — usado pelo n8n logo
# na entrada do workflow do bot, pra identificar de qual barbearia veio a
# mensagem a partir do nome da instância Evolution API que recebeu.
#
# "telefone" é opcional: se vier (o bot já extraiu da própria mensagem antes
# de chamar isso), a resposta já inclui se esse número já é cliente cadastrado
# e com QUE NOME — o agente deve cumprimentar por esse nome, nunca pelo nome
# de exibição do WhatsApp (pushName), que o dono do número pode trocar à vontade.

@pub_whatsapp_bp.get('/barbearia-por-instancia')
@limiter.limit('60 per minute')
def barbearia_por_instancia():
    instance = (request.args.get('instance') or '').strip()
    if not instance:
        raise APIError('Parâmetro "instance" é obrigatório.', 422)

    barbearia = Barbearia.query.filter_by(whatsapp_instance_id=instance, ativo=True).first()
    if not barbearia:
        raise APIError('Nenhuma barbearia conectada a esta instância.', 404)

    segmento = db.session.get(Segmento, barbearia.segmento_id) if barbearia.segmento_id else None

    resposta = {
        'barbearia_id': barbearia.id,
        'slug': barbearia.slug,
        'nome': barbearia.nome_exibicao or barbearia.nome,
        'segmento': segmento.nome if segmento else None,
        'telefone_contato': barbearia.telefone_contato,
    }

    telefone = (request.args.get('telefone') or '').strip()
    if telefone:
        tel_norm, tel_erro = normalizar_telefone(telefone)
        if not tel_erro:
            cliente = Cliente.query.filter_by(barbearia_id=barbearia.id, telefone=tel_norm).first()
            resposta['cliente'] = {'existe': True, 'nome': cliente.nome} if cliente else {'existe': False}

    return jsonify(resposta), 200


# ── GET /api/v1/pub/<slug>/clientes/<telefone>/proximo-agendamento ───────────
# Mesma definição de "próximo" usada no dashboard do cliente (ver
# app/routes/cliente/dashboard.py): futuro, status=agendado, o mais cedo.

@pub_whatsapp_bp.get('/<slug>/clientes/<telefone>/proximo-agendamento')
@limiter.limit('30 per minute')
def proximo_agendamento(slug, telefone):
    barbearia = Barbearia.query.filter_by(slug=slug, ativo=True).first()
    if not barbearia:
        raise APIError(f'{L("tenant")} não encontrada ou inativa.', 404)

    tel_norm, tel_erro = normalizar_telefone(telefone)
    if tel_erro:
        raise APIError(f'Telefone: {tel_erro}')

    cliente = Cliente.query.filter_by(barbearia_id=barbearia.id, telefone=tel_norm).first()
    if not cliente:
        return jsonify({'tem_agendamento': False}), 200

    ag = (
        Agendamento.query
        .filter(
            Agendamento.barbearia_id == barbearia.id,
            Agendamento.cliente_id == cliente.id,
            Agendamento.data_hora >= naive_brasilia(),
            Agendamento.status == StatusAgendamento.AGENDADO,
        )
        .order_by(Agendamento.data_hora)
        .first()
    )
    if not ag:
        return jsonify({'tem_agendamento': False}), 200

    br = db.session.get(Barbeiro, ag.barbeiro_id)
    br_usr = db.session.get(Usuario, br.usuario_id) if br else None
    servicos = [
        s.nome for s in (
            db.session.get(Servico, it.servico_id)
            for it in AgendamentoServico.query.filter_by(agendamento_id=ag.id).all()
        ) if s
    ]

    return jsonify({
        'tem_agendamento': True,
        'agendamento_id': ag.id,
        'data_hora': ag.data_hora.isoformat(),
        'valor_total': float(ag.valor_total),
        'profissional': br_usr.nome if br_usr else None,
        'servicos': servicos,
    }), 200
