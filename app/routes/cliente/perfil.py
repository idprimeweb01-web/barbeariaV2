from flask import Blueprint, request, g, jsonify
from app.extensions import db
from app.models import Cliente, Usuario, ClienteVip, VipNivel
from app.exceptions import APIError
from app.decorators.auth import cliente_required
from app.utils import normalizar_telefone
from app.utils.db import commit_ou_falhar

cliente_perfil_bp = Blueprint('cliente_perfil', __name__, url_prefix='/api/v1/cliente')


def _get_cliente_e_usuario():
    usr = db.session.get(Usuario, g.user_id)
    cli = Cliente.query.filter_by(usuario_id=g.user_id, barbearia_id=g.barbearia_id).first()
    if not usr or not cli:
        raise APIError('Perfil de cliente não encontrado.', 404)
    return cli, usr


# ── GET /api/v1/cliente/perfil ────────────────────────────────────────────────

@cliente_perfil_bp.get('/perfil')
@cliente_required
def obter_perfil():
    cli, _usr = _get_cliente_e_usuario()
    return jsonify({
        'nome':     cli.nome,
        'telefone': cli.telefone,
        'email':    cli.email,
        'foto':     cli.foto,
    }), 200


# ── PATCH /api/v1/cliente/perfil ──────────────────────────────────────────────

@cliente_perfil_bp.patch('/perfil')
@cliente_required
def editar_perfil():
    cli, usr = _get_cliente_e_usuario()
    dados = request.get_json(silent=True) or {}

    if 'nome' in dados:
        nome = (dados.get('nome') or '').strip()
        if not nome:
            raise APIError('"nome" não pode ser vazio.')
        cli.nome = nome
        usr.nome = nome

    if 'telefone' in dados:
        tel_norm, tel_erro = normalizar_telefone(dados.get('telefone') or '')
        if tel_erro:
            raise APIError(f'Telefone: {tel_erro}')
        existente = Cliente.query.filter_by(barbearia_id=g.barbearia_id, telefone=tel_norm).first()
        if existente and existente.id != cli.id:
            raise APIError('Já existe um cliente com este telefone.', 409)
        cli.telefone = tel_norm
        usr.telefone = tel_norm

    if 'email' in dados:
        email = (dados.get('email') or '').strip().lower() or None
        cli.email = email
        usr.email = email

    commit_ou_falhar('cliente.perfil.editar_perfil')
    return jsonify({
        'nome':     cli.nome,
        'telefone': cli.telefone,
        'email':    cli.email,
        'foto':     cli.foto,
    }), 200


# ── GET /api/v1/cliente/vip ───────────────────────────────────────────────────

@cliente_perfil_bp.get('/vip')
@cliente_required
def status_vip():
    cli, _usr = _get_cliente_e_usuario()
    cv = ClienteVip.query.filter_by(cliente_id=cli.id, barbearia_id=g.barbearia_id).first()
    nivel_atual = cv.nivel_vip_atual if cv else 0

    nivel_info = None
    if nivel_atual > 0:
        vn = VipNivel.query.filter_by(
            barbearia_id=g.barbearia_id, nivel=nivel_atual, ativo=True
        ).first()
        if vn:
            nivel_info = {
                'nivel':            vn.nivel,
                'brinde_descricao': vn.brinde_descricao,
                'tipo_brinde':      vn.tipo_brinde,
                'valor_desconto':   float(vn.valor_desconto) if vn.valor_desconto is not None else None,
            }

    return jsonify({
        'nivel_vip_atual':        nivel_atual,
        'nivel_info':             nivel_info,
        'data_proxima_renovacao': cv.data_proxima_renovacao.isoformat() if cv and cv.data_proxima_renovacao else None,
    }), 200
