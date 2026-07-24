"""Conexão da barbearia com o bot de agendamento via WhatsApp (Evolution API).

Cada barbearia tem sua própria "instância" (1 número de WhatsApp, pareado via
QR code). O nome da instância (Barbearia.whatsapp_instance_id) é o que o n8n
usa pra identificar de qual barbearia veio a mensagem do cliente — ver
.claude/n8n/workflows/barberos-bot-whatsapp.json."""
import os
import re
from flask import Blueprint, g, jsonify
from app.extensions import db
from app.models import Barbearia
from app.exceptions import APIError
from app.decorators.auth import gestor_required
from app.utils.db import commit_ou_falhar
from app.utils import evolution

gestor_whatsapp_bot_bp = Blueprint('gestor_whatsapp_bot', __name__, url_prefix='/api/v1/gestor/whatsapp-bot')


def _barbearia() -> Barbearia:
    barbearia = db.session.get(Barbearia, g.barbearia_id)
    if not barbearia:
        raise APIError('Barbearia não encontrada.', 404)
    return barbearia


def _instance_name(barbearia: Barbearia) -> str:
    # Nome legível e único (slug já é único) — evita caracteres que a
    # Evolution API não aceita no nome da instância.
    return f'barberos-{re.sub(r"[^a-z0-9-]", "-", barbearia.slug.lower())}'


# ── GET /api/v1/gestor/whatsapp-bot ───────────────────────────────────────────

@gestor_whatsapp_bot_bp.get('')
@gestor_required
def status():
    barbearia = _barbearia()
    if not barbearia.whatsapp_instance_id:
        return jsonify({'conectado': False, 'instance_id': None, 'status': 'nao_configurado'}), 200

    try:
        estado = evolution.status_conexao(barbearia.whatsapp_instance_id)
    except evolution.EvolutionNaoConfigurado as exc:
        raise APIError(str(exc), 503)
    except Exception:
        raise APIError('Não foi possível consultar o status da Evolution API. Ela está no ar?', 502)

    return jsonify({
        'conectado': estado == 'open',
        'instance_id': barbearia.whatsapp_instance_id,
        'status': estado,
    }), 200


# ── POST /api/v1/gestor/whatsapp-bot/conectar ─────────────────────────────────
# Cria a instância (se ainda não existir) e retorna o QR code pra escanear.

@gestor_whatsapp_bot_bp.post('/conectar')
@gestor_required
def conectar():
    barbearia = _barbearia()
    webhook_url = os.environ.get('N8N_BOT_WEBHOOK_URL')
    if not webhook_url:
        raise APIError('N8N_BOT_WEBHOOK_URL não configurado no servidor — avise o administrador.', 503)

    instance_name = barbearia.whatsapp_instance_id or _instance_name(barbearia)

    try:
        if not barbearia.whatsapp_instance_id:
            evolution.criar_instancia(instance_name, webhook_url)
            barbearia.whatsapp_instance_id = instance_name
            commit_ou_falhar('gestor.whatsapp_bot.conectar')
        qr = evolution.obter_qrcode(instance_name)
    except evolution.EvolutionNaoConfigurado as exc:
        raise APIError(str(exc), 503)
    except Exception:
        raise APIError('Não foi possível criar/conectar a instância na Evolution API.', 502)

    return jsonify({
        'instance_id': instance_name,
        'qrcode_base64': qr.get('base64') or qr.get('qrcode', {}).get('base64'),
        'pairing_code': qr.get('pairingCode'),
    }), 200


# ── POST /api/v1/gestor/whatsapp-bot/desconectar ──────────────────────────────
# Logout do número — mantém a instância (dá pra reconectar escaneando de novo).

@gestor_whatsapp_bot_bp.post('/desconectar')
@gestor_required
def desconectar():
    barbearia = _barbearia()
    if not barbearia.whatsapp_instance_id:
        raise APIError('Nenhuma instância conectada.', 422)

    try:
        evolution.desconectar_instancia(barbearia.whatsapp_instance_id)
    except evolution.EvolutionNaoConfigurado as exc:
        raise APIError(str(exc), 503)
    except Exception:
        raise APIError('Não foi possível desconectar na Evolution API.', 502)

    return jsonify({'mensagem': 'Número desconectado. Escaneie o QR code de novo pra reconectar.'}), 200


# ── DELETE /api/v1/gestor/whatsapp-bot ────────────────────────────────────────
# Remove a instância por completo — usar se quiser recomeçar do zero (ex:
# trocar de número).

@gestor_whatsapp_bot_bp.delete('')
@gestor_required
def excluir():
    barbearia = _barbearia()
    if not barbearia.whatsapp_instance_id:
        raise APIError('Nenhuma instância configurada.', 422)

    try:
        evolution.excluir_instancia(barbearia.whatsapp_instance_id)
    except evolution.EvolutionNaoConfigurado as exc:
        raise APIError(str(exc), 503)
    except Exception:
        raise APIError('Não foi possível excluir a instância na Evolution API.', 502)

    barbearia.whatsapp_instance_id = None
    commit_ou_falhar('gestor.whatsapp_bot.excluir')
    return jsonify({'mensagem': 'Instância removida. Você pode conectar um número novo quando quiser.'}), 200
