"""
Integração com Evolution API (gateway self-hosted de WhatsApp, rodando junto
do n8n em .claude/n8n/docker-compose.yml) — usada pelo bot de agendamento via
WhatsApp. Cada barbearia tem sua própria "instância" (1 número conectado via
QR code); é o nome dessa instância que o n8n usa pra identificar de qual
barbearia veio a mensagem (ver Barbearia.whatsapp_instance_id e
app/routes/pub/whatsapp.py).

Endpoints seguem o contrato da Evolution API v2 (github.com/EvolutionAPI/evolution-api).
Sem SDK oficial — é tudo HTTP puro. Se a versão rodando divergir, confira o
Swagger em {EVOLUTION_API_URL}/docs e ajuste os paths aqui.
"""
import os
import logging
import requests

logger = logging.getLogger(__name__)

TIMEOUT_SEGUNDOS = 15


class EvolutionNaoConfigurado(Exception):
    pass


def _config() -> tuple[str, str]:
    url = os.environ.get('EVOLUTION_API_URL')
    api_key = os.environ.get('EVOLUTION_API_KEY')
    if not url or not api_key:
        raise EvolutionNaoConfigurado('EVOLUTION_API_URL / EVOLUTION_API_KEY não configurados no ambiente.')
    return url.rstrip('/'), api_key


def _headers(api_key: str) -> dict:
    return {'apikey': api_key, 'Content-Type': 'application/json'}


def criar_instancia(instance_name: str, webhook_url: str) -> dict:
    """Cria a instância já com o webhook configurado — é ele que o n8n vai
    ouvir pras mensagens recebidas dessa barbearia especificamente.

    O header X-Webhook-Secret autentica essas chamadas no n8n (node "Webhook
    - Evolution Inbound", credencial Header Auth) — sem ele, qualquer um que
    descobrisse a URL do webhook conseguiria forjar mensagem pro bot."""
    url, api_key = _config()
    webhook_secret = os.environ.get('N8N_BOT_WEBHOOK_SECRET')
    webhook_config = {'url': webhook_url, 'events': ['MESSAGES_UPSERT']}
    if webhook_secret:
        webhook_config['headers'] = {'X-Webhook-Secret': webhook_secret}
    resp = requests.post(
        f'{url}/instance/create',
        headers=_headers(api_key),
        json={
            'instanceName': instance_name,
            'qrcode': True,
            'integration': 'WHATSAPP-BAILEYS',
            'webhook': webhook_config,
        },
        timeout=TIMEOUT_SEGUNDOS,
    )
    resp.raise_for_status()
    return resp.json()


def obter_qrcode(instance_name: str) -> dict:
    """QR code (base64) pra parear o número — só é válido enquanto a
    instância não estiver com status 'open' (já conectada)."""
    url, api_key = _config()
    resp = requests.get(
        f'{url}/instance/connect/{instance_name}',
        headers=_headers(api_key),
        timeout=TIMEOUT_SEGUNDOS,
    )
    resp.raise_for_status()
    return resp.json()


def status_conexao(instance_name: str) -> str:
    """'open' (conectado) | 'connecting' | 'close' (desconectado/inexistente)."""
    url, api_key = _config()
    resp = requests.get(
        f'{url}/instance/connectionState/{instance_name}',
        headers=_headers(api_key),
        timeout=TIMEOUT_SEGUNDOS,
    )
    if resp.status_code == 404:
        return 'close'
    resp.raise_for_status()
    dados = resp.json()
    return (dados.get('instance') or {}).get('state', 'close')


def desconectar_instancia(instance_name: str) -> None:
    """Logout do número, sem apagar a instância — dá pra reconectar
    escaneando o QR de novo depois, sem perder a configuração de webhook."""
    url, api_key = _config()
    resp = requests.delete(
        f'{url}/instance/logout/{instance_name}',
        headers=_headers(api_key),
        timeout=TIMEOUT_SEGUNDOS,
    )
    resp.raise_for_status()


def excluir_instancia(instance_name: str) -> None:
    """Remove a instância por completo da Evolution API (não só desconecta)."""
    url, api_key = _config()
    resp = requests.delete(
        f'{url}/instance/delete/{instance_name}',
        headers=_headers(api_key),
        timeout=TIMEOUT_SEGUNDOS,
    )
    resp.raise_for_status()
