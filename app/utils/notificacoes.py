"""
Sistema de notificações multi-canal.

Arquitetura de plug-in:
  - A GERAÇÃO de notificações (quem, quando, o quê) não muda ao adicionar canais.
  - Adicionar e-mail ou web_push = registrar função em _DESPACHANTES — sem tocar schedulers ou rotas.

Canal 'in_app': entregue agora — salva em tabela Notificacao, lida/não-lida via API.
Canal 'email':  stub pronto — plugar serviço (SendGrid, Mailgun) aqui.
Canal 'web_push': stub pronto — plugar FCM/Vapid aqui.
"""
import logging

logger = logging.getLogger(__name__)


# ── Registry de despachantes ───────────────────────────────────────────────────

def _despachar_in_app(notif):
    """Canal in_app: o próprio registro na tabela já é a entrega. Marca enviada=True."""
    notif.enviada = True


def _despachar_email(notif):
    """
    Canal e-mail — stub.
    TODO: buscar Usuario.email, chamar SendGrid/Mailgun com notif.titulo + notif.corpo.
    Nenhuma configuração de serviço de e-mail definida neste sprint.
    """
    logger.debug('Email stub: usuario_id=%s titulo=%r (sem envio real)', notif.usuario_id, notif.titulo)
    # notif.enviada permanece False — indica que entrega real não ocorreu


def _despachar_web_push(notif):
    """
    Canal web_push — stub.
    TODO: buscar subscription do usuário, chamar FCM ou biblioteca Vapid.
    Sem chaves de push configuradas neste sprint.
    """
    logger.debug('WebPush stub: usuario_id=%s titulo=%r (sem envio real)', notif.usuario_id, notif.titulo)
    # notif.enviada permanece False


# Registro: canal → função despachante.
# Para ativar e-mail no futuro: substituir _despachar_email pela implementação real.
_DESPACHANTES: dict = {
    'in_app':   _despachar_in_app,
    'email':    _despachar_email,
    'web_push': _despachar_web_push,
}


# ── API pública ───────────────────────────────────────────────────────────────
# notificar() é o ÚNICO ponto de criação de Notificacao no sistema — todo
# gatilho de negócio (agendamento, plano, compra, dúvida/suporte, estoque,
# reset de senha etc.) chama esta função em vez de instanciar Notificacao
# diretamente, pra manter uma única superfície pra despacho multi-canal,
# link navegável e log de falha consistente.

def notificar(
    *,
    usuario_id: int,
    barbearia_id: int,
    tipo: str,
    titulo: str,
    mensagem: str,
    link: str | None = None,
    canal: str = 'in_app',
    agendamento_id: int | None = None,
) -> None:
    """
    Cria uma notificação e a despacha pelo canal solicitado.
    Nunca levanta exceção — falha de notificação não cancela a operação principal.

    Canais aceitos: 'in_app', 'email', 'web_push'.
    link: path relativo (ex: '/gestor/agenda?agendamento_id=42') pra onde a
    notificação deve levar ao ser clicada — None se não houver destino.
    """
    if canal not in _DESPACHANTES:
        logger.warning('Canal de notificação desconhecido: %r (ignorado)', canal)
        return

    try:
        from app.extensions import db
        from app.models import Notificacao

        notif = Notificacao(
            barbearia_id=barbearia_id,
            usuario_id=usuario_id,
            agendamento_id=agendamento_id,
            tipo=tipo,
            canal=canal,
            titulo=titulo,
            corpo=mensagem,
            link=link,
            lida=False,
            enviada=False,
        )
        db.session.add(notif)
        db.session.flush()  # gera o id antes de despachar

        _DESPACHANTES[canal](notif)

        db.session.commit()

    except Exception:
        try:
            from app.extensions import db
            db.session.rollback()
        except Exception:
            pass
        logger.exception(
            'Falha ao criar notificação: usuario=%s barbearia=%s tipo=%s canal=%s',
            usuario_id, barbearia_id, tipo, canal,
        )


def notificar_cliente(barbearia_id: int, cliente_id: int, descricao: str, link: str | None = None) -> None:
    """
    Atalho legado usado pela rota de agendamento público.
    Substitui o stub de AuditoriaLog — agora grava em Notificacao.
    """
    try:
        from app.extensions import db
        from app.models import Cliente
        cli = db.session.get(Cliente, cliente_id)
        if not cli:
            return
        usuario_id = cli.usuario_id
    except Exception:
        logger.exception('notificar_cliente: erro ao buscar cliente_id=%s', cliente_id)
        return

    notificar(
        barbearia_id=barbearia_id,
        usuario_id=usuario_id,
        tipo='confirmacao',
        titulo='Agendamento confirmado',
        mensagem=descricao,
        link=link,
        canal='in_app',
    )
