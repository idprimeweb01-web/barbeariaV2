import re
from flask import Blueprint, request, g, jsonify
from app.extensions import db
from app.models import BarbeariaWebhookConfig, WebhookLog
from app.exceptions import APIError
from app.decorators.auth import gestor_required
from app.utils.db import commit_ou_falhar
from app.utils.webhooks import testar_webhook
from app.constants import TipoEventoWebhook

gestor_webhook_bp = Blueprint('gestor_webhook', __name__, url_prefix='/api/v1/gestor/webhook')

# Validação simples de formato — não exige HTTPS pra permitir teste com
# n8n local/self-hosted em rede interna durante configuração inicial.
_URL_RE = re.compile(r'^https?://.+', re.I)


def _get_ou_criar_config(barbearia_id):
    config = BarbeariaWebhookConfig.query.filter_by(barbearia_id=barbearia_id).first()
    if not config:
        config = BarbeariaWebhookConfig(barbearia_id=barbearia_id, eventos_ativos=[])
        db.session.add(config)
    return config


def _fmt_config(config):
    return {
        'webhook_url':    config.webhook_url,
        'ativo':          config.ativo,
        'eventos_ativos': config.eventos_ativos or [],
        'eventos_disponiveis': sorted(TipoEventoWebhook.TODOS),
        'atualizado_em':  config.atualizado_em.isoformat() if config.atualizado_em else None,
    }


# ── GET /api/v1/gestor/webhook ────────────────────────────────────────────────

@gestor_webhook_bp.get('')
@gestor_required
def get_webhook():
    config = BarbeariaWebhookConfig.query.filter_by(barbearia_id=g.barbearia_id).first()
    if not config:
        return jsonify({
            'webhook_url': None, 'ativo': False, 'eventos_ativos': [],
            'eventos_disponiveis': sorted(TipoEventoWebhook.TODOS),
            'atualizado_em': None,
        }), 200
    return jsonify(_fmt_config(config)), 200


# ── PUT /api/v1/gestor/webhook ────────────────────────────────────────────────

@gestor_webhook_bp.put('')
@gestor_required
def salvar_webhook():
    dados = request.get_json(silent=True) or {}
    config = _get_ou_criar_config(g.barbearia_id)

    if 'webhook_url' in dados:
        url = (dados['webhook_url'] or '').strip()
        if url and not _URL_RE.match(url):
            raise APIError('"webhook_url" deve começar com http:// ou https://.', 422)
        config.webhook_url = url or None

    if 'eventos_ativos' in dados:
        eventos = dados['eventos_ativos']
        if not isinstance(eventos, list) or not all(isinstance(e, str) for e in eventos):
            raise APIError('"eventos_ativos" deve ser uma lista de strings.', 422)
        invalidos = set(eventos) - TipoEventoWebhook.TODOS
        if invalidos:
            raise APIError(f'Evento(s) desconhecido(s): {", ".join(sorted(invalidos))}.', 422)
        config.eventos_ativos = eventos

    if 'ativo' in dados:
        if not isinstance(dados['ativo'], bool):
            raise APIError('"ativo" deve ser booleano.', 422)
        if dados['ativo'] and not config.webhook_url:
            raise APIError('Configure uma "webhook_url" antes de ativar.', 422)
        config.ativo = dados['ativo']

    commit_ou_falhar('gestor.webhook.salvar_webhook')
    return jsonify({'mensagem': 'Webhook configurado com sucesso.', **_fmt_config(config)}), 200


# ── POST /api/v1/gestor/webhook/testar ────────────────────────────────────────
# Testa a URL informada no body — ou, se omitida, a já salva. Não grava
# WebhookLog (é validação manual do gestor, não um evento de negócio).

@gestor_webhook_bp.post('/testar')
@gestor_required
def testar():
    dados = request.get_json(silent=True) or {}
    url = (dados.get('webhook_url') or '').strip()

    if not url:
        config = BarbeariaWebhookConfig.query.filter_by(barbearia_id=g.barbearia_id).first()
        url = config.webhook_url if config else None

    if not url:
        raise APIError('Nenhuma "webhook_url" informada nem configurada.', 422)
    if not _URL_RE.match(url):
        raise APIError('"webhook_url" deve começar com http:// ou https://.', 422)

    resultado = testar_webhook(url)
    return jsonify(resultado), 200


# ── GET /api/v1/gestor/webhook/logs ───────────────────────────────────────────

@gestor_webhook_bp.get('/logs')
@gestor_required
def listar_logs():
    try:
        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 20))))
    except ValueError:
        raise APIError('"page" e "per_page" devem ser inteiros.', 422)

    paginado = (
        WebhookLog.query
        .filter_by(barbearia_id=g.barbearia_id)
        .order_by(WebhookLog.criado_em.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return jsonify({
        'dados': [
            {
                'id':            l.id,
                'tipo_evento':   l.tipo_evento,
                'http_status':   l.http_status,
                'sucesso':       l.sucesso,
                'erro_mensagem': l.erro_mensagem,
                'criado_em':     l.criado_em.isoformat() if l.criado_em else None,
            }
            for l in paginado.items
        ],
        'page':     paginado.page,
        'per_page': paginado.per_page,
        'total':    paginado.total,
        'pages':    paginado.pages,
    }), 200
