from flask import Blueprint, g, jsonify, request
from app.extensions import db
from app.models import Notificacao, Cliente
from app.exceptions import APIError
from app.decorators.auth import cliente_required
from app.utils.db import commit_ou_falhar

cliente_notif_bp = Blueprint('cliente_notificacoes', __name__, url_prefix='/api/v1/cliente')


def _cliente_ou_404():
    cli = Cliente.query.filter_by(usuario_id=g.user_id, barbearia_id=g.barbearia_id).first()
    if not cli:
        raise APIError('Perfil de cliente não encontrado.', 404)
    return cli


# ── GET /notificacoes ─────────────────────────────────────────────────────────

@cliente_notif_bp.get('/notificacoes')
@cliente_required
def listar_notificacoes():
    """
    Lista notificações do cliente autenticado (canal in_app).

    Query params:
      apenas_nao_lidas — '1' para filtrar só não-lidas
      page             — página (default: 1)
      per_page         — por página (default: 20, max: 100)
    """
    cli = _cliente_ou_404()

    try:
        page     = max(1, int(request.args.get('page',     1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 20))))
    except ValueError:
        raise APIError('"page" e "per_page" devem ser inteiros.', 422)

    q = Notificacao.query.filter_by(
        barbearia_id=g.barbearia_id,
        usuario_id=g.user_id,
        canal='in_app',
    )

    if request.args.get('apenas_nao_lidas') == '1':
        q = q.filter_by(lida=False)

    paginado = q.order_by(Notificacao.criado_em.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    nao_lidas = Notificacao.query.filter_by(
        barbearia_id=g.barbearia_id,
        usuario_id=g.user_id,
        canal='in_app',
        lida=False,
    ).count()

    return jsonify({
        'nao_lidas':  nao_lidas,
        'total':      paginado.total,
        'page':       paginado.page,
        'pages':      paginado.pages,
        'notificacoes': [_fmt(n) for n in paginado.items],
    }), 200


# ── GET /notificacoes/contador ────────────────────────────────────────────────

@cliente_notif_bp.get('/notificacoes/contador')
@cliente_required
def contador_notificacoes():
    """Retorna apenas o número de notificações não-lidas. Útil para badges na UI."""
    _cliente_ou_404()
    nao_lidas = Notificacao.query.filter_by(
        barbearia_id=g.barbearia_id,
        usuario_id=g.user_id,
        canal='in_app',
        lida=False,
    ).count()
    return jsonify({'nao_lidas': nao_lidas}), 200


# ── PATCH /notificacoes/<id>/lida ─────────────────────────────────────────────

@cliente_notif_bp.patch('/notificacoes/<int:notif_id>/lida')
@cliente_required
def marcar_lida(notif_id):
    """Marca uma notificação específica como lida."""
    _cliente_ou_404()
    n = Notificacao.query.filter_by(
        id=notif_id,
        barbearia_id=g.barbearia_id,
        usuario_id=g.user_id,
    ).first()
    if not n:
        raise APIError('Notificação não encontrada.', 404)
    n.lida = True
    commit_ou_falhar('cliente.notificacoes.marcar_lida')
    return jsonify(_fmt(n)), 200


# ── POST /notificacoes/marcar-todas-lidas ─────────────────────────────────────

@cliente_notif_bp.post('/notificacoes/marcar-todas-lidas')
@cliente_required
def marcar_todas_lidas():
    """Marca todas as notificações não-lidas do cliente como lidas."""
    _cliente_ou_404()
    atualizados = (
        Notificacao.query
        .filter_by(
            barbearia_id=g.barbearia_id,
            usuario_id=g.user_id,
            canal='in_app',
            lida=False,
        )
        .update({'lida': True})
    )
    commit_ou_falhar('cliente.notificacoes.marcar_todas_lidas')
    return jsonify({'marcadas_lidas': atualizados}), 200


# ── Formato ───────────────────────────────────────────────────────────────────

def _fmt(n: Notificacao) -> dict:
    return {
        'id':             n.id,
        'tipo':           n.tipo,
        'titulo':         n.titulo,
        'corpo':          n.corpo,
        'lida':           n.lida,
        'agendamento_id': n.agendamento_id,
        'criado_em':      n.criado_em.strftime('%d/%m/%Y %H:%M') if n.criado_em else None,
    }
