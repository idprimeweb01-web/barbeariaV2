"""
Callback inbound de automação (n8n) — direção oposta do webhook normal
(app/utils/webhooks.py dispara PRA FORA; aqui é a automação chamando DE
VOLTA pro sistema). Autenticado por webhook_secret no header, não por
sessão/JWT — quem chama é um sistema externo, não um usuário logado.

Fluxo pensado: cliente sobe comprovante PIX -> dispara webhook
'comprovante_enviado' (com pode_aprovar_automaticamente no payload) ->
automação n8n decide o que fazer -> se o gestor permitiu, chama este
endpoint pra aprovar sozinha. Gestor sempre pode desligar em
/gestor/configuracoes/webhook.
"""
import hmac
import os
from flask import Blueprint, request, jsonify
from app.extensions import db, limiter
from app.models import Agendamento, BarbeariaWebhookConfig
from app.exceptions import APIError
from app.utils.agenda import aprovar_comprovante_pix
from app.utils.db import commit_ou_falhar
from app.utils.webhooks import disparar_webhook
from app.utils.auditoria import registrar_auditoria
from app.constants import TipoEventoWebhook

webhook_inbound_bp = Blueprint('webhook_inbound', __name__, url_prefix='/api/v1/webhook')


@webhook_inbound_bp.post('/agendamentos/<int:agendamento_id>/aprovar')
@limiter.limit(os.environ.get('RL_WEBHOOK_INBOUND', '20 per minute'))
def aprovar_via_automacao(agendamento_id):
    ag = (
        Agendamento.query
        .filter_by(id=agendamento_id)
        .with_for_update()
        .first()
    )
    if not ag:
        raise APIError('Agendamento não encontrado.', 404)

    cfg = BarbeariaWebhookConfig.query.filter_by(barbearia_id=ag.barbearia_id).first()
    if not cfg or not cfg.permite_auto_aprovacao or not cfg.webhook_secret:
        raise APIError('Aprovação automática não está habilitada para este estabelecimento.', 403)

    # Comparação em tempo constante — evita vazar quanto do secret já bateu
    # via timing (mesmo padrão que qualquer verificação de token/secret).
    secret_recebido = request.headers.get('X-Webhook-Secret', '')
    if not hmac.compare_digest(secret_recebido, cfg.webhook_secret):
        raise APIError('Secret inválido.', 401)

    aprovar_comprovante_pix(ag)
    commit_ou_falhar('webhook_inbound.aprovar_via_automacao')

    registrar_auditoria(
        usuario_id=None,
        barbearia_id=ag.barbearia_id,
        tipo_acao='edit',
        entidade='agendamento',
        entidade_id=ag.id,
        descricao='Comprovante PIX aprovado automaticamente via automação (n8n).',
    )

    disparar_webhook(ag.barbearia_id, TipoEventoWebhook.AGENDAMENTO_APROVADO, {
        'agendamento_id': ag.id, 'cliente_id': ag.cliente_id, 'barbeiro_id': ag.barbeiro_id,
        'data_hora': ag.data_hora.isoformat(), 'aprovado_por': 'automacao_n8n',
    })

    return jsonify({'mensagem': 'Agendamento aprovado automaticamente.', 'id': ag.id, 'status': ag.status}), 200
