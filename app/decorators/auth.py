from functools import wraps
from flask import g
from app.exceptions import APIError


def _require(perfis, *, allow_super=True, check_tenant_ativo=False):
    allowed = set(perfis)
    if allow_super:
        allowed.add('super_admin')

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if getattr(g, 'user_id', None) is None:
                raise APIError('Autenticação necessária.', 401)
            if g.perfil not in allowed:
                raise APIError('Acesso não autorizado.', 403)
            # Guard de tenant ativo: super_admin nunca é bloqueado por isso.
            if check_tenant_ativo and g.perfil != 'super_admin':
                from app.extensions import db
                from app.models import Barbearia
                b = db.session.get(Barbearia, g.barbearia_id) if g.barbearia_id else None
                if not b or not b.ativo:
                    raise APIError('Este estabelecimento está desativado.', 403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def cliente_required(fn):
    """Apenas perfil 'cliente'. super_admin não bypassa."""
    return _require(['cliente'], allow_super=False)(fn)


def barbeiro_required(fn):
    """Perfil 'barbeiro' ou 'super_admin'."""
    return _require(['barbeiro'], check_tenant_ativo=True)(fn)


def gestor_required(fn):
    """Perfil 'gestor' ou 'super_admin'."""
    return _require(['gestor'], check_tenant_ativo=True)(fn)


def super_required(fn):
    """Apenas 'super_admin'."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if getattr(g, 'user_id', None) is None:
            raise APIError('Autenticação necessária.', 401)
        if g.perfil != 'super_admin':
            raise APIError('Acesso restrito a super administradores.', 403)
        return fn(*args, **kwargs)
    return wrapper
