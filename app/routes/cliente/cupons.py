import os
from flask import Blueprint, request, g, jsonify
from app.exceptions import APIError
from app.decorators.auth import cliente_required
from app.extensions import limiter
from app.models import Cliente
from app.utils.cupons import validar_cupom

cliente_cupons_bp = Blueprint('cliente_cupons', __name__, url_prefix='/api/v1/cliente')


@cliente_cupons_bp.post('/cupons/validar')
@limiter.limit(os.environ.get('RL_CUPOM_VALIDAR', '20 per minute'))
@cliente_required
def validar_cupom_cliente():
    dados = request.get_json(silent=True) or {}

    codigo = (dados.get('codigo') or '').strip()
    if not codigo:
        raise APIError('"codigo" é obrigatório.')

    try:
        subtotal = float(dados.get('subtotal'))
        assert subtotal >= 0
    except (TypeError, ValueError, AssertionError):
        raise APIError('"subtotal" é obrigatório e deve ser um número não negativo.')

    # itens: [{'tipo': 'servico'|'produto', 'ref_id': int, 'valor': float}, ...] —
    # se o chamador só souber o subtotal (uso simplificado), cai num item único
    # sem tipo, que só bate com cupons sem nenhuma restrição.
    itens = dados.get('itens')
    if not itens:
        itens = [{'tipo': None, 'ref_id': None, 'valor': subtotal}]

    cli = Cliente.query.filter_by(barbearia_id=g.barbearia_id, usuario_id=g.user_id).first()
    cupom, desconto = validar_cupom(g.barbearia_id, codigo, itens, cliente_id=(cli.id if cli else None))

    return jsonify({
        'cupom_id':       cupom.id,
        'codigo':         cupom.codigo,
        'nome':           cupom.nome,
        'subtotal':       round(subtotal, 2),
        'valor_desconto': desconto,
        'valor_final':    round(subtotal - desconto, 2),
    }), 200
