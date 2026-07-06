from flask import Blueprint, g, jsonify
from app.extensions import db
from app.models import FeatureMetadata, FeatureBarbearia
from app.decorators.auth import gestor_required
from app.utils.features import feature_ativa, feature_required
from app.exceptions import APIError
from app.labels import L
from app.constants import StatusAgendamento

gestor_features_bp = Blueprint('gestor_features', __name__, url_prefix='/api/v1/gestor')


@gestor_features_bp.get('/features')
@gestor_required
def listar_features():
    """Lista todas as features da plataforma com status ativo/inativo para esta barbearia."""
    todas = FeatureMetadata.query.order_by(FeatureMetadata.nome).all()
    flags = {
        fb.feature_id: fb.ativo
        for fb in FeatureBarbearia.query.filter_by(barbearia_id=g.barbearia_id).all()
    }
    return jsonify([
        {
            'nome':    fm.nome,
            'descricao': fm.descricao,
            'ativo':   flags.get(fm.id, False),
        }
        for fm in todas
    ]), 200


# Endpoint de exemplo gateado por feature — demonstra o decorator feature_required.
# Retorna 403 se 'historico_cliente' não estiver ativa para esta barbearia.
@gestor_features_bp.get('/historico-cliente/resumo')
@gestor_required
@feature_required('historico_cliente')
def historico_cliente_resumo():
    """Resumo de histórico por cliente. Exige feature 'historico_cliente' ativa."""
    from app.models import Cliente, Agendamento
    from sqlalchemy import func

    top = (
        db.session.query(
            Agendamento.cliente_id,
            func.count(Agendamento.id).label('total'),
            func.sum(Agendamento.valor_total).label('gasto'),
        )
        .filter(
            Agendamento.barbearia_id == g.barbearia_id,
            Agendamento.status.in_([StatusAgendamento.AGENDADO, StatusAgendamento.CONCLUIDO]),
        )
        .group_by(Agendamento.cliente_id)
        .order_by(func.count(Agendamento.id).desc())
        .limit(10)
        .all()
    )
    resultado = []
    for row in top:
        cli = db.session.get(Cliente, row.cliente_id)
        resultado.append({
            L('cliente').lower(): cli.nome if cli else None,
            'total_' + L('agendamento').lower() + 's': row.total,
            'total_gasto': float(row.gasto or 0),
        })
    return jsonify({
        'top_' + L('cliente').lower() + 's': resultado,
        'rotulos': {'cliente': L('cliente'), 'agendamento': L('agendamento')},
    }), 200
