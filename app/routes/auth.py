from flask import Blueprint, request, g, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity,
)
from werkzeug.security import check_password_hash, generate_password_hash
from app.extensions import db
from app.models import Usuario
from app.exceptions import APIError

auth_bp = Blueprint('auth', __name__, url_prefix='/api/v1/auth')


def _fmt_usuario(u):
    return {
        'id':              u.id,
        'nome':            u.nome,
        'email':           u.email,
        'perfil':          u.perfil,
        'barbearia_id':    u.barbearia_id,
        'foto_perfil_url': u.foto_perfil_url,
    }


# ── POST /api/v1/auth/login ────────────────────────────────────────────────────

@auth_bp.post('/login')
def login():
    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    email = (dados.get('email') or '').strip().lower()
    senha = dados.get('senha') or ''

    if not email or not senha:
        raise APIError('Email e senha são obrigatórios.')

    usuario = Usuario.query.filter_by(email=email).first()
    if not usuario or not usuario.senha or not check_password_hash(usuario.senha, senha):
        raise APIError('Credenciais inválidas.', 401)
    if not usuario.ativo:
        raise APIError('Conta desativada. Entre em contato com o suporte.', 403)

    access_token  = create_access_token(identity=str(usuario.id))
    refresh_token = create_refresh_token(identity=str(usuario.id))

    return jsonify({
        'access_token':  access_token,
        'refresh_token': refresh_token,
        'usuario':       _fmt_usuario(usuario),
    }), 200


# ── POST /api/v1/auth/refresh ─────────────────────────────────────────────────

@auth_bp.post('/refresh')
@jwt_required(refresh=True)
def refresh():
    uid     = get_jwt_identity()
    usuario = db.session.get(Usuario, int(uid))
    if not usuario or not usuario.ativo:
        raise APIError('Usuário não encontrado ou inativo.', 401)

    return jsonify({
        'access_token': create_access_token(identity=str(usuario.id)),
    }), 200


# ── GET /api/v1/auth/me ───────────────────────────────────────────────────────

@auth_bp.get('/me')
def me():
    if g.user_id is None:
        raise APIError('Autenticação necessária.', 401)

    usuario = db.session.get(Usuario, g.user_id)
    if not usuario or not usuario.ativo:
        raise APIError('Usuário não encontrado.', 404)

    return jsonify(_fmt_usuario(usuario)), 200


# ── POST /api/v1/auth/trocar-senha ────────────────────────────────────────────

@auth_bp.post('/trocar-senha')
def trocar_senha():
    if g.user_id is None:
        raise APIError('Autenticação necessária.', 401)

    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    senha_atual = dados.get('senha_atual') or ''
    senha_nova  = dados.get('senha_nova')  or ''

    if not senha_atual or not senha_nova:
        raise APIError('Os campos "senha_atual" e "senha_nova" são obrigatórios.')
    if len(senha_nova) < 6:
        raise APIError('A nova senha deve ter no mínimo 6 caracteres.')

    usuario = db.session.get(Usuario, g.user_id)
    if not usuario or not usuario.senha:
        raise APIError('Usuário não encontrado.', 404)
    if not check_password_hash(usuario.senha, senha_atual):
        raise APIError('Senha atual incorreta.', 403)

    usuario.senha = generate_password_hash(senha_nova)
    db.session.commit()

    return jsonify({'mensagem': 'Senha alterada com sucesso.'}), 200
