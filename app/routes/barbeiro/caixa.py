"""
Caixa diária do barbeiro (v1.2) — abre na 1ª venda do dia, acumula itens,
fecha manualmente (ou automaticamente ao abrir a próxima, ver PATCH /fechar).
Preço sempre resolvido server-side de Produto.preco — nunca aceito do
client, mesmo padrão de app/utils/vendas.py:criar_venda_core.
"""
from flask import Blueprint, request, g, jsonify
from app.models import Barbeiro, Produto, BarbeiroCaixa, ItemCaixa
from app.exceptions import APIError
from app.decorators.auth import barbeiro_required
from app.utils.features import feature_required
from app.utils.db import commit_ou_falhar
from app.utils.tz import hoje_brasilia
from app.utils import pdv_caixa as pdv_service
from app.constants import MetodoPagamentoVenda

barbeiro_caixa_bp = Blueprint('barbeiro_caixa', __name__, url_prefix='/api/v1/barbeiro/caixa')


def _get_barbeiro(user_id, barbearia_id):
    b = Barbeiro.query.filter_by(usuario_id=user_id, barbearia_id=barbearia_id, ativo=True).first()
    if not b:
        raise APIError('Profissional não encontrado.', 404)
    return b


def _get_caixa_do_barbeiro(caixa_id, barbeiro_id, barbearia_id):
    """Toda operação sobre uma caixa exige que ela pertença ao barbeiro logado —
    sem isso, um barbeiro poderia mexer na caixa de outro só sabendo o id."""
    caixa = BarbeiroCaixa.query.filter_by(id=caixa_id, barbearia_id=barbearia_id).first()
    if not caixa:
        raise APIError('Caixa não encontrado.', 404)
    if caixa.barbeiro_id != barbeiro_id:
        raise APIError('Caixa não encontrado.', 404)  # 404, não 403 — não confirma existência a terceiros
    return caixa


def _fmt_caixa(caixa, itens=None):
    if itens is None:
        itens = ItemCaixa.query.filter_by(caixa_id=caixa.id).order_by(ItemCaixa.criado_em).all()
    produto_ids = {i.produto_id for i in itens}
    produtos_map = {p.id: p for p in Produto.query.filter(Produto.id.in_(produto_ids)).all()} if produto_ids else {}
    return {
        'id':         caixa.id,
        'barbeiro_id': caixa.barbeiro_id,
        'data':       caixa.data.isoformat(),
        'aberto_em':  caixa.aberto_em.isoformat() if caixa.aberto_em else None,
        'fechado_em': caixa.fechado_em.isoformat() if caixa.fechado_em else None,
        'total':      float(caixa.total),
        'itens': [
            {
                'id':                  i.id,
                'produto_id':          i.produto_id,
                'produto_nome':        produtos_map.get(i.produto_id).nome if produtos_map.get(i.produto_id) else None,
                'quantidade':          i.quantidade,
                'preco':               float(i.preco),
                'desconto_percentual': float(i.desconto_percentual),
                'subtotal':            i.subtotal,
                'total':               i.total,
                'forma_pagamento':     i.forma_pagamento,
                'agendamento_id':      i.agendamento_id,
                'criado_em':           i.criado_em.isoformat() if i.criado_em else None,
            }
            for i in itens
        ],
    }


# ── GET /api/v1/barbeiro/caixa ────────────────────────────────────────────────
# ?data=YYYY-MM-DD (opcional, default hoje)

@barbeiro_caixa_bp.get('')
@barbeiro_required
def ver_caixa():
    barbeiro = _get_barbeiro(g.user_id, g.barbearia_id)

    data_str = request.args.get('data')
    if data_str:
        try:
            from datetime import date
            data = date.fromisoformat(data_str)
        except ValueError:
            raise APIError('"data" inválida. Use YYYY-MM-DD.', 422)
    else:
        data = hoje_brasilia()

    caixa = BarbeiroCaixa.query.filter_by(
        barbeiro_id=barbeiro.id, barbearia_id=g.barbearia_id, data=data
    ).first()
    if not caixa:
        return jsonify(None), 200

    return jsonify(_fmt_caixa(caixa)), 200


# ── POST /api/v1/barbeiro/caixa ───────────────────────────────────────────────
# Abre a caixa de hoje. Idempotente — chamar de novo no mesmo dia devolve a
# mesma caixa (200), não cria duplicata (uq_barbeiro_caixa_data garante isso
# mesmo sob concorrência).

@barbeiro_caixa_bp.post('')
@barbeiro_required
def abrir_caixa_endpoint():
    barbeiro = _get_barbeiro(g.user_id, g.barbearia_id)
    hoje = hoje_brasilia()

    ja_existia = BarbeiroCaixa.query.filter_by(
        barbeiro_id=barbeiro.id, barbearia_id=g.barbearia_id, data=hoje
    ).first() is not None

    caixa = pdv_service.abrir_caixa(barbeiro.id, g.barbearia_id, hoje)
    commit_ou_falhar('barbeiro.caixa.abrir_caixa_endpoint')

    return jsonify(_fmt_caixa(caixa)), (200 if ja_existia else 201)


# ── POST /api/v1/barbeiro/caixa/<id>/itens ────────────────────────────────────

@barbeiro_caixa_bp.post('/<int:caixa_id>/itens')
@barbeiro_required
@feature_required('produtos_venda')
def adicionar_item(caixa_id):
    barbeiro = _get_barbeiro(g.user_id, g.barbearia_id)
    _get_caixa_do_barbeiro(caixa_id, barbeiro.id, g.barbearia_id)

    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    produto_id = dados.get('produto_id')
    quantidade = dados.get('quantidade')
    desconto_percentual = dados.get('desconto_percentual', 0)
    forma_pagamento = (dados.get('forma_pagamento') or '').strip().lower()
    agendamento_id = dados.get('agendamento_id')

    if not isinstance(produto_id, int):
        raise APIError('"produto_id" é obrigatório e deve ser um inteiro.', 422)
    if not isinstance(quantidade, int) or quantidade <= 0:
        raise APIError('"quantidade" deve ser um inteiro positivo.', 422)
    try:
        desconto_percentual = float(desconto_percentual)
        assert 0 <= desconto_percentual <= 100
    except (TypeError, ValueError, AssertionError):
        raise APIError('"desconto_percentual" deve ser um número entre 0 e 100.', 422)
    if forma_pagamento not in MetodoPagamentoVenda.TODOS:
        raise APIError(
            f'"forma_pagamento" deve ser um de: {", ".join(sorted(MetodoPagamentoVenda.TODOS))}.', 422
        )
    if agendamento_id is not None and not isinstance(agendamento_id, int):
        raise APIError('"agendamento_id" deve ser um inteiro (ou omitido).', 422)

    # Preço SEMPRE resolvido do produto — nunca aceito do client (mesmo
    # motivo de app/utils/vendas.py:criar_venda_core).
    produto = Produto.query.filter_by(id=produto_id, barbearia_id=g.barbearia_id, ativo=True).first()
    if not produto:
        raise APIError('Produto não encontrado ou inativo.', 404)

    item = pdv_service.adicionar_item_caixa(
        caixa_id=caixa_id, produto_id=produto_id, barbearia_id=g.barbearia_id,
        usuario_id=g.user_id, quantidade=quantidade, preco=float(produto.preco),
        desconto_percentual=desconto_percentual, forma_pagamento=forma_pagamento,
        agendamento_id=agendamento_id,
    )
    commit_ou_falhar('barbeiro.caixa.adicionar_item')

    return jsonify(_fmt_caixa(item.caixa)), 201


# ── DELETE /api/v1/barbeiro/caixa/itens/<id> ──────────────────────────────────

@barbeiro_caixa_bp.delete('/itens/<int:item_id>')
@barbeiro_required
@feature_required('produtos_venda')
def remover_item(item_id):
    barbeiro = _get_barbeiro(g.user_id, g.barbearia_id)

    item = ItemCaixa.query.filter_by(id=item_id, barbearia_id=g.barbearia_id).first()
    if not item:
        raise APIError('Item não encontrado.', 404)
    _get_caixa_do_barbeiro(item.caixa_id, barbeiro.id, g.barbearia_id)

    pdv_service.remover_item_caixa(item_id, g.barbearia_id, g.user_id)
    commit_ou_falhar('barbeiro.caixa.remover_item')

    return jsonify({'mensagem': 'Item removido.', 'id': item_id}), 200


# ── PATCH /api/v1/barbeiro/caixa/<id>/fechar ──────────────────────────────────

@barbeiro_caixa_bp.patch('/<int:caixa_id>/fechar')
@barbeiro_required
def fechar_caixa_endpoint(caixa_id):
    barbeiro = _get_barbeiro(g.user_id, g.barbearia_id)
    _get_caixa_do_barbeiro(caixa_id, barbeiro.id, g.barbearia_id)

    caixa = pdv_service.fechar_caixa(caixa_id, g.barbearia_id)
    commit_ou_falhar('barbeiro.caixa.fechar_caixa_endpoint')

    return jsonify(_fmt_caixa(caixa)), 200
