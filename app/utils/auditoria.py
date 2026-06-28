import logging

logger = logging.getLogger(__name__)


def registrar_auditoria(usuario_id, barbearia_id, tipo_acao, entidade, entidade_id, descricao):
    """Grava entrada de auditoria. Nunca levanta exceção — falha de log não pode derrubar
    a operação principal. Ao contrário da v1, a exceção É logada (não suprimida silenciosamente)."""
    from app.extensions import db
    from app.models import AuditoriaLog
    try:
        db.session.add(AuditoriaLog(
            usuario_id=usuario_id,
            barbearia_id=barbearia_id,
            tipo_acao=tipo_acao,
            entidade=entidade,
            entidade_id=entidade_id,
            descricao=descricao,
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception(
            'Falha ao registrar auditoria: usuario=%s barbearia=%s %s %s id=%s',
            usuario_id, barbearia_id, tipo_acao, entidade, entidade_id,
        )
