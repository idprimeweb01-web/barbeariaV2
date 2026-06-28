import csv
import io
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, Response
from app import db
from app.models import AuditoriaLog, Usuario, Barbearia
from app.routes.auth import super_admin_required

auditoria = Blueprint('auditoria', __name__, url_prefix='/api/auditoria')

POR_PAGINA = 20


def _query_filtrada():
    dias = request.args.get('dias', 30, type=int)
    filtro = (request.args.get('filtro') or '').strip().lower()

    desde = datetime.utcnow() - timedelta(days=dias)
    q = (
        db.session.query(AuditoriaLog, Usuario, Barbearia)
        .outerjoin(Usuario, AuditoriaLog.usuario_id == Usuario.id)
        .outerjoin(Barbearia, AuditoriaLog.barbearia_id == Barbearia.id)
        .filter(AuditoriaLog.criado_em >= desde)
    )
    if filtro:
        q = q.filter(
            db.or_(
                Usuario.nome.ilike(f'%{filtro}%'),
                AuditoriaLog.descricao.ilike(f'%{filtro}%'),
                AuditoriaLog.entidade.ilike(f'%{filtro}%'),
            )
        )
    return q.order_by(AuditoriaLog.criado_em.desc())


def _fmt_log(log, usuario, barbearia):
    return {
        'id': log.id,
        'data_hora': log.criado_em.isoformat() if log.criado_em else None,
        'usuario_nome': usuario.nome if usuario else 'Sistema',
        'usuario_tipo': usuario.perfil if usuario else None,
        'barbearia_nome': barbearia.nome if barbearia else None,
        'acao': log.descricao,
        'tipo': log.tipo_acao,
        'entidade': log.entidade,
    }


# ── GET /api/auditoria/logs ──────────────────────────────────────────────────────

@auditoria.get('/logs')
@super_admin_required
def listar_logs():
    pagina = request.args.get('pagina', 1, type=int)
    if pagina < 1:
        pagina = 1

    q = _query_filtrada()
    total = q.count()
    rows = q.offset((pagina - 1) * POR_PAGINA).limit(POR_PAGINA).all()

    return jsonify({
        'logs': [_fmt_log(log, u, b) for log, u, b in rows],
        'total': total,
        'pagina': pagina,
        'total_paginas': max(1, (total + POR_PAGINA - 1) // POR_PAGINA),
    })


# ── POST /api/auditoria/exportar ─────────────────────────────────────────────────

@auditoria.post('/exportar')
@super_admin_required
def exportar_logs():
    rows = _query_filtrada().limit(5000).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['Data/Hora', 'Usuário', 'Perfil', 'Barbearia', 'Tipo', 'Entidade', 'Ação'])
    for log, u, b in rows:
        writer.writerow([
            log.criado_em.isoformat() if log.criado_em else '',
            u.nome if u else 'Sistema',
            u.perfil if u else '',
            b.nome if b else '',
            log.tipo_acao,
            log.entidade,
            log.descricao,
        ])

    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=auditoria.csv'},
    )
