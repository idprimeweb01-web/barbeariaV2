"""Caixa de notificação in-app do admin (super_admin) — espelha exatamente
app/routes/barbeiro/notificacoes.py e app/routes/gestor/notificacoes.py.
Antes desta rota, o admin não tinha nenhuma caixa de notificação. Diferente
de gestor/barbeiro (tenant-scoped), o admin não tem barbearia_id fixo —
filtra só por usuario_id (a notificação em si já carrega o barbearia_id de
origem do evento, exibido no corpo/link quando relevante)."""
from flask import Blueprint, g, jsonify, request
from app.extensions import db
from app.models import Notificacao
from app.exceptions import APIError
from app.decorators.auth import super_required
from app.utils.db import commit_ou_falhar
from app.utils.tz import utc_naive_para_brasilia

super_notif_bp = Blueprint('super_notificacoes', __name__, url_prefix='/api/v1/super')


# ── GET /notificacoes ─────────────────────────────────────────────────────────

@super_notif_bp.get('/notificacoes')
@super_required
def listar_notificacoes():
    """
    Lista notificações do admin autenticado (canal in_app).

    Query params:
      apenas_nao_lidas — '1' para filtrar só não-lidas
      page             — página (default: 1)
      per_page         — por página (default: 20, max: 100)
    """
    try:
        page     = max(1, int(request.args.get('page',     1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 20))))
    except ValueError:
        raise APIError('"page" e "per_page" devem ser inteiros.', 422)

    q = Notificacao.query.filter_by(usuario_id=g.user_id, canal='in_app')

    if request.args.get('apenas_nao_lidas') == '1':
        q = q.filter_by(lida=False)

    paginado = q.order_by(Notificacao.criado_em.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    nao_lidas = Notificacao.query.filter_by(
        usuario_id=g.user_id, canal='in_app', lida=False,
    ).count()

    return jsonify({
        'nao_lidas':  nao_lidas,
        'total':      paginado.total,
        'page':       paginado.page,
        'pages':      paginado.pages,
        'notificacoes': [_fmt(n) for n in paginado.items],
    }), 200


# ── GET /notificacoes/contador ────────────────────────────────────────────────

@super_notif_bp.get('/notificacoes/contador')
@super_required
def contador_notificacoes():
    nao_lidas = Notificacao.query.filter_by(
        usuario_id=g.user_id, canal='in_app', lida=False,
    ).count()
    return jsonify({'nao_lidas': nao_lidas}), 200


# ── PATCH /notificacoes/<id>/lida ─────────────────────────────────────────────

@super_notif_bp.patch('/notificacoes/<int:notif_id>/lida')
@super_required
def marcar_lida(notif_id):
    n = Notificacao.query.filter_by(id=notif_id, usuario_id=g.user_id).first()
    if not n:
        raise APIError('Notificação não encontrada.', 404)
    n.lida = True
    commit_ou_falhar('super.notificacoes.marcar_lida')
    return jsonify(_fmt(n)), 200


# ── POST /notificacoes/marcar-todas-lidas ─────────────────────────────────────

@super_notif_bp.post('/notificacoes/marcar-todas-lidas')
@super_required
def marcar_todas_lidas():
    atualizados = (
        Notificacao.query
        .filter_by(usuario_id=g.user_id, canal='in_app', lida=False)
        .update({'lida': True})
    )
    commit_ou_falhar('super.notificacoes.marcar_todas_lidas')
    return jsonify({'marcadas_lidas': atualizados}), 200


def _fmt(n: Notificacao) -> dict:
    return {
        'id':             n.id,
        'tipo':           n.tipo,
        'titulo':         n.titulo,
        'corpo':          n.corpo,
        'link':           n.link,
        'lida':           n.lida,
        'agendamento_id': n.agendamento_id,
        'criado_em':      utc_naive_para_brasilia(n.criado_em).strftime('%d/%m/%Y %H:%M') if n.criado_em else None,
    }
