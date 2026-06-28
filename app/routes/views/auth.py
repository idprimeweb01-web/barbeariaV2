from datetime import timedelta
from functools import wraps
from flask import (
    Blueprint, request, session, redirect, url_for,
    render_template, jsonify, make_response,
)
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    verify_jwt_in_request, get_jwt_identity,
)
from werkzeug.security import check_password_hash
from app.extensions import db
from app.models import Usuario

views_bp = Blueprint('views', __name__)

_PERFIL_REDIRECT = {
    'super_admin': '/super/',
    'gestor':      '/gestor/',
    'barbeiro':    '/barbeiro/',
}

_COOKIE_OPTS = dict(httponly=True, samesite='Lax', path='/')


def session_required(*perfis):
    """Guard para rotas de tela (não-API). Redireciona para /entrar se não autenticado."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('views.entrar'))
            if perfis and session.get('perfil') not in perfis:
                return redirect(url_for('views.entrar'))
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ── GET /entrar ───────────────────────────────────────────────────────────────

@views_bp.get('/entrar')
def entrar():
    if 'user_id' in session:
        perfil = session.get('perfil', '')
        return redirect(_PERFIL_REDIRECT.get(perfil, '/entrar'))
    return render_template('staff/login.html')


# ── POST /entrar ──────────────────────────────────────────────────────────────

@views_bp.post('/entrar')
def entrar_post():
    dados = request.get_json(silent=True) or {}
    email  = (dados.get('email') or '').strip().lower()
    senha  = dados.get('senha') or ''
    lembrar = bool(dados.get('lembrar'))

    if not email or not senha:
        return jsonify({'erro': 'E-mail e senha são obrigatórios.'}), 400

    usuario = Usuario.query.filter_by(email=email).first()

    if not usuario or not usuario.senha or not check_password_hash(usuario.senha, senha):
        return jsonify({'erro': 'Credenciais inválidas.'}), 401

    if not usuario.ativo:
        return jsonify({'erro': 'Conta desativada. Entre em contato com o suporte.'}), 403

    if usuario.perfil == 'cliente':
        return jsonify({
            'erro': (
                'Esta entrada é para a equipe. '
                'Clientes acessam pelo link do estabelecimento.'
            )
        }), 403

    if usuario.perfil not in _PERFIL_REDIRECT:
        return jsonify({'erro': 'Perfil não reconhecido.'}), 403

    access_token  = create_access_token(identity=str(usuario.id))
    refresh_token = create_refresh_token(identity=str(usuario.id))

    resp = make_response(
        jsonify({'ok': True, 'redirect': _PERFIL_REDIRECT[usuario.perfil]}),
        200,
    )

    # Access token: 15 min (alinhado com JWT_ACCESS_TOKEN_EXPIRES)
    resp.set_cookie('bos_at', access_token, max_age=15 * 60, **_COOKIE_OPTS)
    # Refresh token: 30 dias se "lembrar", cookie de sessão caso contrário
    rt_max_age = 30 * 24 * 3600 if lembrar else None
    resp.set_cookie('bos_rt', refresh_token, max_age=rt_max_age, **_COOKIE_OPTS)

    session.permanent = lembrar
    session['user_id']      = usuario.id
    session['nome']         = usuario.nome
    session['perfil']       = usuario.perfil
    session['barbearia_id'] = usuario.barbearia_id

    return resp


# ── POST /entrar/renovar ──────────────────────────────────────────────────────

@views_bp.post('/entrar/renovar')
def renovar():
    """
    Renova o access token (bos_at) usando o refresh token (bos_rt).
    Chamado automaticamente por bos.js quando recebe 401.
    """
    try:
        verify_jwt_in_request(refresh=True, locations=['cookies'])
        uid     = get_jwt_identity()
        usuario = db.session.get(Usuario, int(uid))
        if not usuario or not usuario.ativo:
            return jsonify({'erro': 'Sessão inválida.'}), 401

        new_at = create_access_token(identity=str(uid))
        resp   = make_response(jsonify({'ok': True}), 200)
        resp.set_cookie('bos_at', new_at, max_age=15 * 60, **_COOKIE_OPTS)

        session['user_id']      = usuario.id
        session['nome']         = usuario.nome
        session['perfil']       = usuario.perfil
        session['barbearia_id'] = usuario.barbearia_id

        return resp
    except Exception:
        return jsonify({'erro': 'Sessão expirada. Faça login novamente.'}), 401


# ── POST /sair ────────────────────────────────────────────────────────────────

@views_bp.post('/sair')
def sair():
    session.clear()
    resp = make_response(jsonify({'ok': True}), 200)
    resp.delete_cookie('bos_at', path='/')
    resp.delete_cookie('bos_rt', path='/')
    return resp


# ── Áreas placeholder ─────────────────────────────────────────────────────────

@views_bp.get('/gestor/')
@views_bp.get('/gestor')
@session_required('gestor', 'super_admin')
def area_gestor():
    return render_template('staff/placeholder.html',
        area='do Gestor',
        nome=session.get('nome', ''),
        perfil=session.get('perfil', ''),
    )


@views_bp.get('/super/')
@views_bp.get('/super')
@session_required('super_admin')
def area_super():
    return render_template('staff/placeholder.html',
        area='do Administrador',
        nome=session.get('nome', ''),
        perfil=session.get('perfil', ''),
    )


@views_bp.get('/barbeiro/')
@views_bp.get('/barbeiro')
@session_required('barbeiro', 'super_admin')
def area_barbeiro():
    return render_template('staff/placeholder.html',
        area='do Funcionário',
        nome=session.get('nome', ''),
        perfil=session.get('perfil', ''),
    )
