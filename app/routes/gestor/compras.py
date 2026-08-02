"""Aprovação de pedidos de compra de produto feitos pelo cliente no portal.
Aprovar gera uma Venda de verdade (baixa de estoque, comissão, cupom) via o
mesmo núcleo usado pelo PDV do gestor — ver app/utils/vendas.py."""
import logging

from flask import Blueprint, request, g, jsonify
from app.extensions import db
from app.models import SolicitacaoCompraProduto, SolicitacaoCompraItem, Cliente, Produto
from app.exceptions import APIError
from app.decorators.auth import gestor_required
from app.utils.features import feature_required
from app.utils.vendas import criar_venda_core
from app.utils.webhooks import disparar_webhook
from app.utils.tz import naive_brasilia
from app.utils.db import commit_ou_falhar
from app.utils.notificacoes import notificar
from app.utils.auditoria import registrar_auditoria
from app.utils.comprovante_link import gerar_link_comprovante
from app.constants import StatusSolicitacaoCompra, TipoEventoWebhook

logger = logging.getLogger(__name__)

gestor_compras_bp = Blueprint('gestor_compras', __name__, url_prefix='/api/v1/gestor/compras')


def _fmt_solicitacao(s, clientes=None, itens_map=None, produtos_map=None):
    cli = clientes.get(s.cliente_id) if clientes is not None else db.session.get(Cliente, s.cliente_id)
    itens = itens_map.get(s.id, []) if itens_map is not None else (
        SolicitacaoCompraItem.query.filter_by(solicitacao_id=s.id).all()
    )
    return {
        'id':               s.id,
        'cliente':          {'id': cli.id, 'nome': cli.nome, 'telefone': cli.telefone} if cli else None,
        'valor_original':   float(s.valor_original),
        'valor_desconto':   float(s.valor_desconto),
        'valor_total':      float(s.valor_total),
        'cupom_codigo':     s.cupom_codigo,
        'metodo_pagamento': s.metodo_pagamento,
        'status':           s.status,
        'motivo_rejeicao':  s.motivo_rejeicao,
        'comprovante_url':  gerar_link_comprovante('compra', s.id, s.barbearia_id) if s.comprovante_url else None,
        'criado_em':        s.criado_em.isoformat() if s.criado_em else None,
        'respondido_em':    s.respondido_em.isoformat() if s.respondido_em else None,
        'itens': [
            {
                'produto_id':     it.produto_id,
                'produto_nome':   (produtos_map.get(it.produto_id).nome if produtos_map is not None
                                    else (db.session.get(Produto, it.produto_id) or {}).nome),
                'quantidade':     it.quantidade,
                'preco_unitario': float(it.preco_unitario),
            }
            for it in itens
        ],
    }


# ── GET /api/v1/gestor/compras?status=pendente ───────────────────────────────

@gestor_compras_bp.get('')
@gestor_required
@feature_required('produtos_venda')
def listar_compras():
    status_f = request.args.get('status', StatusSolicitacaoCompra.PENDENTE)
    q = SolicitacaoCompraProduto.query.filter_by(barbearia_id=g.barbearia_id)
    if status_f:
        if status_f not in StatusSolicitacaoCompra.TODOS:
            raise APIError(f'Status inválido: "{status_f}".', 422)
        q = q.filter_by(status=status_f)

    sols = q.order_by(SolicitacaoCompraProduto.criado_em.desc()).all()
    if not sols:
        return jsonify([]), 200

    clientes = {c.id: c for c in Cliente.query.filter(
        Cliente.id.in_({s.cliente_id for s in sols})
    ).all()}
    itens_todos = SolicitacaoCompraItem.query.filter(
        SolicitacaoCompraItem.solicitacao_id.in_([s.id for s in sols])
    ).all()
    itens_map = {}
    for it in itens_todos:
        itens_map.setdefault(it.solicitacao_id, []).append(it)
    produtos_map = {p.id: p for p in Produto.query.filter(
        Produto.id.in_({it.produto_id for it in itens_todos})
    ).all()} if itens_todos else {}

    return jsonify([_fmt_solicitacao(s, clientes, itens_map, produtos_map) for s in sols]), 200


# ── POST /api/v1/gestor/compras/<id>/aprovar ─────────────────────────────────

@gestor_compras_bp.post('/<int:solicitacao_id>/aprovar')
@gestor_required
@feature_required('produtos_venda')
def aprovar_compra(solicitacao_id):
    sol = SolicitacaoCompraProduto.query.filter_by(
        id=solicitacao_id, barbearia_id=g.barbearia_id
    ).with_for_update().first()
    if not sol:
        raise APIError('Pedido não encontrado.', 404)
    if sol.status != StatusSolicitacaoCompra.PENDENTE:
        raise APIError('Este pedido já foi processado.', 409)

    itens = SolicitacaoCompraItem.query.filter_by(solicitacao_id=sol.id).all()
    venda = criar_venda_core(
        barbearia_id=g.barbearia_id,
        usuario_registro_id=g.user_id,
        itens=[{'produto_id': it.produto_id, 'quantidade': it.quantidade} for it in itens],
        cliente_id=sol.cliente_id,
        metodo_pagamento=sol.metodo_pagamento,
        cupom_codigo=sol.cupom_codigo,
        # Honra o preço/desconto congelados no pedido (o que o cliente já
        # pagou via PIX) em vez do preço atual do produto / cupom revalidado
        # do zero — ver PLANO_DE_ACAO.md achado C1.
        precos_congelados={it.produto_id: float(it.preco_unitario) for it in itens},
        valor_desconto_congelado=float(sol.valor_desconto),
    )

    if abs(float(venda.valor_total) - float(sol.valor_total)) > 0.01:
        logger.warning(
            'Venda aprovada com valor divergente do congelado na solicitação: '
            'solicitacao_id=%s valor_congelado=%.2f valor_venda=%.2f barbearia_id=%s',
            sol.id, float(sol.valor_total), float(venda.valor_total), g.barbearia_id,
        )

    sol.venda_id = venda.id
    sol.status = StatusSolicitacaoCompra.APROVADA
    sol.respondido_em = naive_brasilia()
    commit_ou_falhar('gestor.compras.aprovar_compra')

    disparar_webhook(g.barbearia_id, TipoEventoWebhook.VENDA_CONCLUIDA, {
        'venda_id': venda.id, 'cliente_id': venda.cliente_id, 'barbeiro_id': venda.barbeiro_id,
        'valor_total': float(venda.valor_total), 'metodo_pagamento': venda.metodo_pagamento,
        'origem': 'solicitacao_cliente',
    })

    cli_notif = db.session.get(Cliente, sol.cliente_id)
    if cli_notif and cli_notif.usuario_id:
        notificar(
            barbearia_id=g.barbearia_id, usuario_id=cli_notif.usuario_id, tipo='compra_aprovada',
            titulo='Pedido aprovado', mensagem=f'Seu pedido foi aprovado! Valor: R$ {float(venda.valor_total):.2f}.',
            link='/cliente/loja', canal='in_app',
        )

    registrar_auditoria(g.user_id, g.barbearia_id, 'edit', 'solicitacao_compra_produto', sol.id,
                         f'Aprovou pedido de compra #{sol.id} (venda #{venda.id}, R$ {float(venda.valor_total):.2f}).')

    return jsonify({'mensagem': 'Pedido aprovado. Venda registrada.', 'venda_id': venda.id}), 200


# ── POST /api/v1/gestor/compras/<id>/rejeitar ────────────────────────────────

@gestor_compras_bp.post('/<int:solicitacao_id>/rejeitar')
@gestor_required
@feature_required('produtos_venda')
def rejeitar_compra(solicitacao_id):
    sol = SolicitacaoCompraProduto.query.filter_by(
        id=solicitacao_id, barbearia_id=g.barbearia_id
    ).with_for_update().first()
    if not sol:
        raise APIError('Pedido não encontrado.', 404)
    if sol.status != StatusSolicitacaoCompra.PENDENTE:
        raise APIError('Este pedido já foi processado.', 409)

    dados = request.get_json(silent=True) or {}
    sol.status = StatusSolicitacaoCompra.REJEITADA
    sol.motivo_rejeicao = (dados.get('motivo') or '').strip() or None
    sol.respondido_em = naive_brasilia()
    commit_ou_falhar('gestor.compras.rejeitar_compra')

    cli_notif = db.session.get(Cliente, sol.cliente_id)
    if cli_notif and cli_notif.usuario_id:
        notificar(
            barbearia_id=g.barbearia_id, usuario_id=cli_notif.usuario_id, tipo='compra_rejeitada',
            titulo='Pedido rejeitado',
            mensagem='Seu pedido foi rejeitado.' + (f' Motivo: {sol.motivo_rejeicao}' if sol.motivo_rejeicao else ''),
            link='/cliente/loja', canal='in_app',
        )

    registrar_auditoria(g.user_id, g.barbearia_id, 'edit', 'solicitacao_compra_produto', sol.id,
                         f'Rejeitou pedido de compra #{sol.id}.' + (f' Motivo: {sol.motivo_rejeicao}' if sol.motivo_rejeicao else ''))

    return jsonify({'mensagem': 'Pedido rejeitado.'}), 200
