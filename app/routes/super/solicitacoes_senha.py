import datetime as dt
from flask import Blueprint, jsonify
from app.models import SolicitacaoSenha, Usuario, Barbearia
from app.decorators.auth import super_required

super_solicitacoes_senha_bp = Blueprint(
    'super_solicitacoes_senha', __name__, url_prefix='/api/v1/super/solicitacoes-senha'
)


# ── GET /api/v1/super/solicitacoes-senha ──────────────────────────────────────
# Pedidos de reset de senha de GESTOR/BARBEIRO (staff), pendentes e não
# expirados, cross-tenant — o super repassa o código por WhatsApp.

@super_solicitacoes_senha_bp.get('')
@super_required
def listar_solicitacoes():
    agora = dt.datetime.utcnow()
    solicitacoes = (
        SolicitacaoSenha.query
        .join(Usuario, SolicitacaoSenha.usuario_id == Usuario.id)
        .filter(
            SolicitacaoSenha.status == 'pendente',
            SolicitacaoSenha.expira_em > agora,
            Usuario.perfil.in_(['gestor', 'barbeiro']),
        )
        .order_by(SolicitacaoSenha.criado_em.desc())
        .all()
    )
    usuario_ids = {s.usuario_id for s in solicitacoes}
    usuarios = {u.id: u for u in Usuario.query.filter(Usuario.id.in_(usuario_ids)).all()} if usuario_ids else {}
    barbearia_ids = {u.barbearia_id for u in usuarios.values() if u.barbearia_id}
    barbearias = {b.id: b for b in Barbearia.query.filter(Barbearia.id.in_(barbearia_ids)).all()} if barbearia_ids else {}

    resultado = []
    for s in solicitacoes:
        u = usuarios.get(s.usuario_id)
        if not u:
            continue
        b = barbearias.get(u.barbearia_id)
        resultado.append({
            'id':          s.id,
            'nome':        u.nome,
            'telefone':    u.telefone,
            'perfil':      u.perfil,
            'barbearia':   b.nome if b else None,
            'codigo':      s.codigo_novo,
            'criado_em':   s.criado_em.isoformat() if s.criado_em else None,
            'expira_em':   s.expira_em.isoformat() if s.expira_em else None,
        })
    return jsonify(resultado), 200
