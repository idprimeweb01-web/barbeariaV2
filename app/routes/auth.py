import os
from flask import Blueprint, request, g, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity,
)
from werkzeug.security import check_password_hash, generate_password_hash
from app.extensions import db, limiter
from app.models import Usuario
from app.exceptions import APIError
from app.utils.auth import revogar_todos_tokens
from app.utils.db import commit_ou_falhar
from app.utils.reset_senha import gerar_codigo_recuperacao, validar_codigo_recuperacao

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
    revogar_todos_tokens(usuario, 'troca_senha')
    commit_ou_falhar('auth.trocar_senha')

    return jsonify({'mensagem': 'Senha alterada com sucesso.'}), 200


# ── POST /api/v1/auth/solicitar-reset-senha ───────────────────────────────────
# Sem login. Resposta é SEMPRE a mesma mensagem genérica, exista o e-mail ou
# não — não confirmar/negar existência de conta (evita enumeração de e-mails).

@auth_bp.post('/solicitar-reset-senha')
@limiter.limit(os.environ.get('RL_RESET_SENHA', '5 per minute'))
def solicitar_reset_senha():
    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    email = (dados.get('email') or '').strip().lower()
    if not email:
        raise APIError('"email" é obrigatório.')

    gerar_codigo_recuperacao(email)
    commit_ou_falhar('auth.solicitar_reset_senha')

    return jsonify({
        'mensagem': 'Se este e-mail estiver cadastrado, um código de recuperação '
                     'foi enviado para quem pode te ajudar a redefinir a senha.',
    }), 200


# ── POST /api/v1/auth/confirmar-reset-senha ───────────────────────────────────
# Sem login (o usuário perdeu a senha — é o ponto do fluxo). Token+código
# validam a identidade; sucesso já devolve tokens novos (auto-login).

@auth_bp.post('/confirmar-reset-senha')
@limiter.limit(os.environ.get('RL_RESET_SENHA', '5 per minute'))
def confirmar_reset_senha():
    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    token  = (dados.get('token') or '').strip()
    codigo = (dados.get('codigo') or '').strip()
    if not token or not codigo:
        raise APIError('Os campos "token" e "codigo" são obrigatórios.')

    usuario = validar_codigo_recuperacao(token, codigo)
    commit_ou_falhar('auth.confirmar_reset_senha')

    return jsonify({
        'mensagem':      'Senha redefinida com sucesso.',
        'access_token':  create_access_token(identity=str(usuario.id)),
        'refresh_token': create_refresh_token(identity=str(usuario.id)),
        'usuario':       _fmt_usuario(usuario),
    }), 200
