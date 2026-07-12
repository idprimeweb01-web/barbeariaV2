import datetime as dt
from flask import Blueprint, g, jsonify
from app.models import SolicitacaoSenha, Usuario
from app.decorators.auth import gestor_required

gestor_solicitacoes_senha_bp = Blueprint(
    'gestor_solicitacoes_senha', __name__, url_prefix='/api/v1/gestor/solicitacoes-senha'
)


# ── GET /api/v1/gestor/solicitacoes-senha ─────────────────────────────────────
# Pedidos de reset de senha de CLIENTES desta barbearia, ainda pendentes e não
# expirados — o gestor repassa o código por WhatsApp (ver Bos.wa em bos.js).

@gestor_solicitacoes_senha_bp.get('')
@gestor_required
def listar_solicitacoes():
    agora = dt.datetime.utcnow()
    solicitacoes = (
        SolicitacaoSenha.query
        .join(Usuario, SolicitacaoSenha.usuario_id == Usuario.id)
        .filter(
            SolicitacaoSenha.barbearia_id == g.barbearia_id,
            SolicitacaoSenha.status == 'pendente',
            SolicitacaoSenha.expira_em > agora,
            Usuario.perfil == 'cliente',
        )
        .order_by(SolicitacaoSenha.criado_em.desc())
        .all()
    )
    usuario_ids = {s.usuario_id for s in solicitacoes}
    usuarios = {u.id: u for u in Usuario.query.filter(Usuario.id.in_(usuario_ids)).all()} if usuario_ids else {}

    return jsonify([
        {
            'id':          s.id,
            'nome':        usuarios[s.usuario_id].nome if s.usuario_id in usuarios else None,
            'telefone':    usuarios[s.usuario_id].telefone if s.usuario_id in usuarios else None,
            'codigo':      s.codigo_novo,
            'criado_em':   s.criado_em.isoformat() if s.criado_em else None,
            'expira_em':   s.expira_em.isoformat() if s.expira_em else None,
        }
        for s in solicitacoes
    ]), 200
