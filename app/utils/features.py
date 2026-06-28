from functools import wraps
from flask import g
from app.exceptions import APIError


def feature_ativa(barbearia_id: int, nome: str) -> bool:
    """Retorna True se a feature está ativa para a barbearia. False se inexistente ou desligada."""
    from app.extensions import db
    from app.models import FeatureMetadata, FeatureBarbearia
    meta = FeatureMetadata.query.filter_by(nome=nome).first()
    if not meta:
        return False
    fb = FeatureBarbearia.query.filter_by(
        barbearia_id=barbearia_id, feature_id=meta.id, ativo=True
    ).first()
    return fb is not None


def feature_required(nome: str):
    """Decorator: bloqueia a rota com 403 se a feature não estiver ativa para g.barbearia_id."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not feature_ativa(g.barbearia_id, nome):
                raise APIError(
                    f'Feature "{nome}" não está ativa para esta barbearia.',
                    403,
                )
            return f(*args, **kwargs)
        return wrapper
    return decorator
