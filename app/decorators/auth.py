from functools import wraps
from flask import g
from app.exceptions import APIError


def _require(perfis, *, allow_super=True):
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
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def cliente_required(fn):
    """Apenas perfil 'cliente'. super_admin não bypassa."""
    return _require(['cliente'], allow_super=False)(fn)


def barbeiro_required(fn):
    """Perfil 'barbeiro' ou 'super_admin'."""
    return _require(['barbeiro'])(fn)


def gestor_required(fn):
    """Perfil 'gestor' ou 'super_admin'."""
    return _require(['gestor'])(fn)


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
