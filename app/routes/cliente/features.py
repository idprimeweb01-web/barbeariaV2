from flask import Blueprint, g, jsonify
from app.models import FeatureMetadata, FeatureBarbearia
from app.decorators.auth import cliente_required

cliente_features_bp = Blueprint('cliente_features', __name__, url_prefix='/api/v1/cliente')


@cliente_features_bp.get('/features')
@cliente_required
def listar_features():
    """Mesmo formato de GET /api/v1/gestor/features e /api/v1/barbeiro/features —
    não existia equivalente pro cliente (SPA React nunca consultou feature
    flags). Usado pra esconder seções da SPA (ex: Planos, Benefícios/VIP)
    quando a feature correspondente estiver desligada."""
    todas = FeatureMetadata.query.order_by(FeatureMetadata.nome).all()
    flags = {
        fb.feature_id: fb.ativo
        for fb in FeatureBarbearia.query.filter_by(barbearia_id=g.barbearia_id).all()
    }
    return jsonify([
        {'nome': fm.nome, 'descricao': fm.descricao, 'ativo': flags.get(fm.id, False)}
        for fm in todas
    ]), 200
