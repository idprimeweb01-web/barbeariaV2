from flask import Blueprint, g, jsonify, request
from app.extensions import db
from app.models import AuditoriaLog, Usuario
from app.exceptions import APIError
from app.decorators.auth import gestor_required

gestor_auditoria_bp = Blueprint('gestor_auditoria', __name__, url_prefix='/api/v1/gestor')


@gestor_auditoria_bp.get('/auditoria')
@gestor_required
def listar_auditoria():
    """
    Lista registros de auditoria desta barbearia.

    Query params:
      tipo_acao  — filtra por tipo (ex.: edicao, notificacao)
      entidade   — filtra por entidade (ex.: barbeiro, agendamento)
      de / ate   — filtro de data YYYY-MM-DD
      page       — página (default: 1)
      per_page   — registros por página (default: 50, max: 200)
    """
    q = AuditoriaLog.query.filter_by(barbearia_id=g.barbearia_id)

    tipo = request.args.get('tipo_acao')
    if tipo:
        q = q.filter(AuditoriaLog.tipo_acao == tipo)

    entidade = request.args.get('entidade')
    if entidade:
        q = q.filter(AuditoriaLog.entidade == entidade)

    de_str  = request.args.get('de')
    ate_str = request.args.get('ate')
    try:
        if de_str:
            from datetime import date
            de = date.fromisoformat(de_str)
            q = q.filter(db.func.date(AuditoriaLog.criado_em) >= de)
        if ate_str:
            from datetime import date
            ate = date.fromisoformat(ate_str)
            q = q.filter(db.func.date(AuditoriaLog.criado_em) <= ate)
    except ValueError:
        raise APIError('Parâmetros "de" e "ate" devem estar no formato YYYY-MM-DD.', 422)

    try:
        page     = max(1, int(request.args.get('page',     1)))
        per_page = min(200, max(1, int(request.args.get('per_page', 50))))
    except ValueError:
        raise APIError('"page" e "per_page" devem ser inteiros.', 422)

    paginado = q.order_by(AuditoriaLog.criado_em.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    def _fmt(log):
        u = db.session.get(Usuario, log.usuario_id) if log.usuario_id else None
        return {
            'id':         log.id,
            'tipo_acao':  log.tipo_acao,
            'entidade':   log.entidade,
            'entidade_id': log.entidade_id,
            'descricao':  log.descricao,
            'usuario':    u.nome if u else None,
            'criado_em':  log.criado_em.strftime('%d/%m/%Y %H:%M') if log.criado_em else None,
        }

    return jsonify({
        'total':     paginado.total,
        'page':      paginado.page,
        'per_page':  paginado.per_page,
        'pages':     paginado.pages,
        'registros': [_fmt(l) for l in paginado.items],
    }), 200
