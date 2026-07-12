from datetime import datetime
from flask import Blueprint, request, g, jsonify
from app.extensions import db
from app.models import Venda, VendaItem, Produto, Cliente, Barbeiro, Usuario
from app.exceptions import APIError
from app.decorators.auth import gestor_required
from app.utils.features import feature_required
from app.utils.db import commit_ou_falhar
from app.utils.vendas import criar_venda_core, cancelar_venda_core
from app.utils.webhooks import disparar_webhook
from app.constants import StatusVenda, TipoEventoWebhook

gestor_vendas_bp = Blueprint('gestor_vendas', __name__, url_prefix='/api/v1/gestor/vendas')


def _fmt_venda(v, clientes=None, barbeiros_usr=None):
    itens = VendaItem.query.filter_by(venda_id=v.id).all()
    produto_ids = {it.produto_id for it in itens}
    produtos_map = {p.id: p for p in Produto.query.filter(Produto.id.in_(produto_ids)).all()} if produto_ids else {}

    cliente_nome = v.cliente_nome_livre
    if v.cliente_id:
        cli = clientes.get(v.cliente_id) if clientes is not None else db.session.get(Cliente, v.cliente_id)
        cliente_nome = cli.nome if cli else cliente_nome

    barbeiro_nome = None
    if v.barbeiro_id:
        if barbeiros_usr is not None:
            barbeiro_nome = barbeiros_usr.get(v.barbeiro_id)
        else:
            barb = db.session.get(Barbeiro, v.barbeiro_id)
            usr = db.session.get(Usuario, barb.usuario_id) if barb else None
            barbeiro_nome = usr.nome if usr else None

    return {
        'id':               v.id,
        'cliente_id':       v.cliente_id,
        'cliente_nome':     cliente_nome,
        'barbeiro_id':      v.barbeiro_id,
        'barbeiro_nome':    barbeiro_nome,
        'metodo_pagamento': v.metodo_pagamento,
        'status':           v.status,
        'valor_total':      float(v.valor_total),
        'criado_em':        v.criado_em.isoformat() if v.criado_em else None,
        'itens': [
            {
                'produto_id':     it.produto_id,
                'produto_nome':   produtos_map.get(it.produto_id).nome if produtos_map.get(it.produto_id) else None,
                'quantidade':     it.quantidade,
                'preco_unitario': float(it.preco_unitario),
                'subtotal':       round(float(it.preco_unitario) * it.quantidade, 2),
                'comissao_valor': float(it.comissao_valor),
            }
            for it in itens
        ],
    }


# ── POST /api/v1/gestor/vendas ────────────────────────────────────────────────

@gestor_vendas_bp.post('')
@gestor_required
@feature_required('produtos_venda')
def criar_venda():
    bid = g.barbearia_id
    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    venda = criar_venda_core(
        barbearia_id=bid,
        usuario_registro_id=g.user_id,
        itens=dados.get('itens') or [],
        barbeiro_id=dados.get('barbeiro_id'),
        cliente_id=dados.get('cliente_id'),
        cliente_nome_livre=dados.get('cliente_nome_livre'),
        metodo_pagamento=(dados.get('metodo_pagamento') or '').strip().lower(),
    )
    commit_ou_falhar('gestor.vendas.criar_venda')

    disparar_webhook(bid, TipoEventoWebhook.VENDA_CONCLUIDA, {
        'venda_id': venda.id, 'cliente_id': venda.cliente_id, 'barbeiro_id': venda.barbeiro_id,
        'valor_total': float(venda.valor_total), 'metodo_pagamento': venda.metodo_pagamento,
    })

    return jsonify(_fmt_venda(venda)), 201


# ── GET /api/v1/gestor/vendas?data=&page= ────────────────────────────────────

@gestor_vendas_bp.get('')
@gestor_required
def listar_vendas():
    bid = g.barbearia_id
    q = Venda.query.filter_by(barbearia_id=bid)

    data_f = request.args.get('data')
    if data_f:
        try:
            dia = datetime.strptime(data_f, '%Y-%m-%d').date()
        except ValueError:
            raise APIError('"data" inválida. Use YYYY-MM-DD.', 422)
        q = q.filter(db.func.date(Venda.criado_em) == dia)

    try:
        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 50))))
    except ValueError:
        raise APIError('"page" e "per_page" devem ser inteiros.', 422)

    paginado = q.order_by(Venda.criado_em.desc()).paginate(page=page, per_page=per_page, error_out=False)

    vendas = paginado.items
    cliente_ids = {v.cliente_id for v in vendas if v.cliente_id}
    clientes = {c.id: c for c in Cliente.query.filter(Cliente.id.in_(cliente_ids)).all()} if cliente_ids else {}

    barbeiro_ids = {v.barbeiro_id for v in vendas if v.barbeiro_id}
    barbeiros_usr = {}
    if barbeiro_ids:
        barbeiros = {b.id: b for b in Barbeiro.query.filter(Barbeiro.id.in_(barbeiro_ids)).all()}
        usuarios = {u.id: u for u in Usuario.query.filter(
            Usuario.id.in_({b.usuario_id for b in barbeiros.values()})).all()}
        barbeiros_usr = {
            bid_: (usuarios.get(b.usuario_id).nome if usuarios.get(b.usuario_id) else None)
            for bid_, b in barbeiros.items()
        }

    return jsonify({
        'dados':    [_fmt_venda(v, clientes, barbeiros_usr) for v in vendas],
        'page':     paginado.page,
        'per_page': paginado.per_page,
        'total':    paginado.total,
        'pages':    paginado.pages,
    }), 200


# ── POST /api/v1/gestor/vendas/<id>/cancelar ─────────────────────────────────

@gestor_vendas_bp.post('/<int:venda_id>/cancelar')
@gestor_required
@feature_required('produtos_venda')
def cancelar_venda(venda_id):
    bid = g.barbearia_id
    venda = (
        Venda.query
        .filter_by(id=venda_id, barbearia_id=bid)
        .with_for_update()
        .first()
    )
    if not venda:
        raise APIError('Venda não encontrada.', 404)

    cancelar_venda_core(venda, g.user_id)
    commit_ou_falhar('gestor.vendas.cancelar_venda')
    return jsonify({'mensagem': 'Venda cancelada. Estoque devolvido.', 'id': venda.id}), 200
