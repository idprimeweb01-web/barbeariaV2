from flask import Blueprint, request, g, jsonify
from app.models import Barbeiro, VendaItem, Produto
from app.exceptions import APIError
from app.decorators.auth import barbeiro_required
from app.utils.features import feature_required
from app.utils.db import commit_ou_falhar
from app.utils.vendas import criar_venda_core

barbeiro_vendas_bp = Blueprint('barbeiro_vendas', __name__, url_prefix='/api/v1/barbeiro/vendas')


def _get_barbeiro(user_id, barbearia_id):
    b = Barbeiro.query.filter_by(usuario_id=user_id, barbearia_id=barbearia_id, ativo=True).first()
    if not b:
        raise APIError('Profissional não encontrado.', 404)
    return b


def _fmt_venda_simples(v):
    itens = VendaItem.query.filter_by(venda_id=v.id).all()
    produto_ids = {it.produto_id for it in itens}
    produtos_map = {p.id: p for p in Produto.query.filter(Produto.id.in_(produto_ids)).all()} if produto_ids else {}
    return {
        'id':               v.id,
        'metodo_pagamento': v.metodo_pagamento,
        'status':           v.status,
        'valor_total':      float(v.valor_total),
        'criado_em':        v.criado_em.isoformat() if v.criado_em else None,
        'itens': [
            {
                'produto_id':   it.produto_id,
                'produto_nome': produtos_map.get(it.produto_id).nome if produtos_map.get(it.produto_id) else None,
                'quantidade':   it.quantidade,
                'subtotal':     round(float(it.preco_unitario) * it.quantidade, 2),
            }
            for it in itens
        ],
    }


# ── POST /api/v1/barbeiro/vendas ─────────────────────────────────────────────
# Mesmo payload do gestor, mas o vendedor é sempre o próprio barbeiro logado
# (barbeiro_id não é aceito do request — evita um barbeiro registrar venda
# em nome de outro).

@barbeiro_vendas_bp.post('')
@barbeiro_required
@feature_required('produtos_venda')
def criar_venda_barbeiro():
    b = _get_barbeiro(g.user_id, g.barbearia_id)
    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    venda = criar_venda_core(
        barbearia_id=g.barbearia_id,
        usuario_registro_id=g.user_id,
        itens=dados.get('itens') or [],
        barbeiro_id=b.id,
        cliente_id=dados.get('cliente_id'),
        cliente_nome_livre=dados.get('cliente_nome_livre'),
        metodo_pagamento=(dados.get('metodo_pagamento') or '').strip().lower(),
    )
    commit_ou_falhar('barbeiro.vendas.criar_venda_barbeiro')
    return jsonify(_fmt_venda_simples(venda)), 201
