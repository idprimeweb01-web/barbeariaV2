"""
Helper de commit protegido — Bloco 3.1.

Substitui `db.session.commit()` nu (sem try/except) espalhado pelas rotas.
Qualquer falha de banco no commit deixava a sessão suja e virava 500 sem
nenhum log — impossível diagnosticar em produção.
"""
import logging
from app.extensions import db
from app.exceptions import APIError

logger = logging.getLogger(__name__)


def commit_ou_falhar(contexto: str, mensagem_usuario: str = 'Erro ao salvar. Tente novamente.'):
    """Faz commit da sessão; em caso de erro, rollback + log com contexto +
    APIError genérico (500) para o cliente — nunca stack trace exposta."""
    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error('commit falhou em %s: %s', contexto, exc, exc_info=True)
        raise APIError(mensagem_usuario, 500)
