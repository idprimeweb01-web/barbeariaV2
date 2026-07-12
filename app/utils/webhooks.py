"""
Disparo de webhook n8n (v1.2/Frente 2).

Decisões registradas (perguntadas ao dono antes de implementar):
  - 1 URL única por barbearia, todos os eventos selecionados vão pra ela.
  - Sem assinatura HMAC nesta fase — a própria URL do n8n (opaca por padrão)
    já é o "segredo". Se um dia precisar de mais rigor, dá pra adicionar um
    header de assinatura aqui sem mudar a interface pública desta função.
  - Sem fila de retry — falha é só logada (mesmo padrão dos stubs de
    e-mail/web_push em app/utils/notificacoes.py). Síncrono, dentro do
    próprio request que gerou o evento.
"""
import logging
import requests
from app.extensions import db

logger = logging.getLogger(__name__)

TIMEOUT_SEGUNDOS = 5


def disparar_webhook(barbearia_id: int, tipo_evento: str, dados: dict) -> None:
    """Dispara o webhook da barbearia pro evento, se configurado e ativo.
    Nunca levanta exceção — falha de entrega não pode derrubar a operação
    de negócio que gerou o evento (mesmo contrato de criar_notificacao)."""
    from app.models import BarbeariaWebhookConfig

    try:
        config = BarbeariaWebhookConfig.query.filter_by(barbearia_id=barbearia_id).first()
        if not config or not config.ativo or not config.webhook_url:
            return
        if tipo_evento not in (config.eventos_ativos or []):
            return

        _enviar_e_logar(barbearia_id, config.webhook_url, tipo_evento, dados)
    except Exception:
        logger.exception(
            'Falha inesperada ao disparar webhook: barbearia=%s evento=%s',
            barbearia_id, tipo_evento,
        )


def _enviar_e_logar(barbearia_id: int, url: str, tipo_evento: str, dados: dict) -> None:
    from app.models import WebhookLog

    payload = {'evento': tipo_evento, 'barbearia_id': barbearia_id, 'dados': dados}
    log = WebhookLog(barbearia_id=barbearia_id, tipo_evento=tipo_evento, payload=payload, sucesso=False)

    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT_SEGUNDOS)
        log.http_status = resp.status_code
        log.sucesso = 200 <= resp.status_code < 300
        if not log.sucesso:
            log.erro_mensagem = f'HTTP {resp.status_code}'
    except requests.RequestException as exc:
        log.erro_mensagem = str(exc)[:500]

    try:
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception('Falha ao gravar WebhookLog: barbearia=%s evento=%s', barbearia_id, tipo_evento)


def testar_webhook(url: str) -> dict:
    """Chamada síncrona de teste — usada pelo botão "Testar" na tela de
    configuração, antes de qualquer WebhookLog existir pra essa URL.
    Não grava log (é só validação manual do gestor)."""
    payload = {'evento': 'teste', 'mensagem': 'Disparo de teste do BarberOS — se você recebeu isso, o webhook está funcionando.'}
    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT_SEGUNDOS)
        return {
            'sucesso': 200 <= resp.status_code < 300,
            'http_status': resp.status_code,
            'erro': None if resp.status_code < 300 else f'HTTP {resp.status_code}',
        }
    except requests.RequestException as exc:
        return {'sucesso': False, 'http_status': None, 'erro': str(exc)[:500]}
