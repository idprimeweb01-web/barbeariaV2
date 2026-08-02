"""Loja do cliente: ver produtos e pedir compra — vira uma Venda de verdade
(com baixa de estoque) só quando o gestor aprova, mesmo modelo de
solicitação usado pelas assinaturas de plano (ver cliente/planos.py)."""
import os
import cloudinary
import cloudinary.uploader
from flask import Blueprint, request, g, jsonify, current_app
from app.extensions import db, limiter
from app.models import (
    Produto, Cliente, SolicitacaoCompraProduto, SolicitacaoCompraItem,
)
from app.exceptions import APIError
from app.decorators.auth import cliente_required
from app.utils.features import feature_required, feature_ativa
from app.utils.cupons import validar_cupom
from app.utils.db import commit_ou_falhar
from app.utils.notificacoes import notificar
from app.constants import StatusSolicitacaoCompra
from app.routes.pub.agendamento import _TIPOS_COMPROVANTE, _MAX_BYTES_COMP, _validar_magic_bytes

cliente_produtos_bp = Blueprint('cliente_produtos', __name__, url_prefix='/api/v1/cliente')


def _get_cliente_ou_404(user_id, barbearia_id):
    from app.models import Usuario
    usr = db.session.get(Usuario, user_id)
    if not usr:
        raise APIError('Usuário não encontrado.', 404)
    cli = Cliente.query.filter_by(barbearia_id=barbearia_id, usuario_id=usr.id).first()
    if not cli:
        raise APIError('Perfil de cliente não encontrado nesta barbearia.', 404)
    return cli


def _fmt_produto(p):
    return {
        'id':                    p.id,
        'nome':                  p.nome,
        'preco':                 float(p.preco),
        'foto_url':              p.foto_url,
        'quantidade_disponivel': p.quantidade_disponivel,
    }


# ── GET /api/v1/cliente/produtos ──────────────────────────────────────────────

@cliente_produtos_bp.get('/produtos')
@cliente_required
@feature_required('produtos_venda')
def listar_produtos():
    produtos = (
        Produto.query_tenant()
        .filter_by(ativo=True)
        .order_by(Produto.nome)
        .all()
    )
    return jsonify([_fmt_produto(p) for p in produtos]), 200


def _fmt_solicitacao(s, itens_map=None, produtos_map=None):
    itens = itens_map.get(s.id, []) if itens_map is not None else (
        SolicitacaoCompraItem.query.filter_by(solicitacao_id=s.id).all()
    )
    return {
        'id':               s.id,
        'valor_original':   float(s.valor_original),
        'valor_desconto':   float(s.valor_desconto),
        'valor_total':      float(s.valor_total),
        'cupom_codigo':     s.cupom_codigo,
        'metodo_pagamento': s.metodo_pagamento,
        'status':           s.status,
        'motivo_rejeicao':  s.motivo_rejeicao,
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


# ── GET /api/v1/cliente/compras ───────────────────────────────────────────────

@cliente_produtos_bp.get('/compras')
@cliente_required
@feature_required('produtos_venda')
def listar_compras():
    cli = _get_cliente_ou_404(g.user_id, g.barbearia_id)
    sols = (
        SolicitacaoCompraProduto.query
        .filter_by(barbearia_id=g.barbearia_id, cliente_id=cli.id)
        .order_by(SolicitacaoCompraProduto.criado_em.desc())
        .all()
    )
    if not sols:
        return jsonify([]), 200

    itens_todos = SolicitacaoCompraItem.query.filter(
        SolicitacaoCompraItem.solicitacao_id.in_([s.id for s in sols])
    ).all()
    itens_map = {}
    for it in itens_todos:
        itens_map.setdefault(it.solicitacao_id, []).append(it)
    produtos_map = {p.id: p for p in Produto.query.filter(
        Produto.id.in_({it.produto_id for it in itens_todos})
    ).all()} if itens_todos else {}

    return jsonify([_fmt_solicitacao(s, itens_map, produtos_map) for s in sols]), 200


# ── POST /api/v1/cliente/compras ──────────────────────────────────────────────

@cliente_produtos_bp.post('/compras')
@limiter.limit(os.environ.get('RL_COMPRA_SOLICITAR', '10 per minute'))
@cliente_required
@feature_required('produtos_venda')
def criar_compra():
    cli = _get_cliente_ou_404(g.user_id, g.barbearia_id)
    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    itens_req = dados.get('itens') or []
    if not itens_req:
        raise APIError('Adicione ao menos um produto ao pedido.', 422)

    metodo = (dados.get('metodo_pagamento') or 'pix').strip().lower()
    if metodo not in ('pix', 'dinheiro', 'cartao'):
        raise APIError('"metodo_pagamento" deve ser pix, dinheiro ou cartao.', 422)
    if metodo == 'pix' and not feature_ativa(g.barbearia_id, 'pix_integrado'):
        raise APIError('PIX não está disponível para este estabelecimento.', 403)

    itens_montados = []
    subtotal = 0.0
    for item in itens_req:
        produto_id = item.get('produto_id')
        quantidade = item.get('quantidade')
        if not isinstance(produto_id, int):
            raise APIError('"produto_id" de cada item deve ser um inteiro.', 422)
        if not isinstance(quantidade, int) or quantidade <= 0:
            raise APIError('"quantidade" de cada item deve ser um inteiro positivo.', 422)

        produto = Produto.query.filter_by(id=produto_id, barbearia_id=g.barbearia_id, ativo=True).first()
        if not produto:
            raise APIError(f'Produto id={produto_id} não encontrado ou indisponível.', 404)
        if produto.quantidade_disponivel < quantidade:
            raise APIError(f'"{produto.nome}" tem apenas {produto.quantidade_disponivel} unidade(s) disponível(is).', 422)

        preco = float(produto.preco)
        subtotal += preco * quantidade
        itens_montados.append({'produto': produto, 'quantidade': quantidade, 'preco': preco})

    cupom_codigo = (dados.get('cupom_codigo') or '').strip() or None
    valor_desconto = 0.0
    if cupom_codigo:
        itens_cupom = [{'tipo': 'produto', 'ref_id': i['produto'].id, 'valor': i['preco'] * i['quantidade']} for i in itens_montados]
        _, valor_desconto = validar_cupom(g.barbearia_id, cupom_codigo, itens_cupom, cliente_id=cli.id)

    valor_total = round(subtotal - valor_desconto, 2)

    sol = SolicitacaoCompraProduto(
        barbearia_id=g.barbearia_id,
        cliente_id=cli.id,
        valor_original=round(subtotal, 2),
        valor_desconto=round(valor_desconto, 2),
        valor_total=valor_total,
        cupom_codigo=cupom_codigo,
        metodo_pagamento=metodo,
        status=StatusSolicitacaoCompra.PENDENTE,
    )
    db.session.add(sol)
    db.session.flush()

    for item in itens_montados:
        db.session.add(SolicitacaoCompraItem(
            solicitacao_id=sol.id,
            produto_id=item['produto'].id,
            quantidade=item['quantidade'],
            preco_unitario=item['preco'],
        ))

    commit_ou_falhar('cliente.produtos.criar_compra')

    from app.models import Usuario
    gestores = Usuario.query.filter_by(barbearia_id=g.barbearia_id, perfil='gestor', ativo=True).all()
    for gestor in gestores:
        notificar(
            barbearia_id=g.barbearia_id, usuario_id=gestor.id, tipo='compra_solicitada',
            titulo='Novo pedido de produto',
            mensagem=f'{cli.nome} pediu {len(itens_montados)} item(ns) — R$ {valor_total:.2f}.',
            link='/gestor/compras-produto', canal='in_app',
        )

    resposta = {
        'mensagem': 'Pedido enviado. Aguarde a aprovação do estabelecimento.',
        'solicitacao_id': sol.id,
        'valor_original': float(sol.valor_original),
        'valor_desconto': float(sol.valor_desconto),
        'valor_total':    float(sol.valor_total),
        'status': StatusSolicitacaoCompra.PENDENTE,
    }

    if metodo == 'pix':
        from app.models import Barbearia
        b = db.session.get(Barbearia, g.barbearia_id)
        if b and b.chave_pix:
            from app.utils.pix import gerar_pix_copia_cola
            emv = gerar_pix_copia_cola(
                chave=b.chave_pix,
                nome_titular=b.pix_nome_titular or b.nome,
                cidade=b.pix_cidade or 'CIDADE',
                valor=valor_total,
                txid=f'COMPRA{sol.id:06d}',
            )
            resposta['pix_copia_cola'] = emv
            resposta['chave_pix'] = b.chave_pix
            resposta['pix_nome_titular'] = b.pix_nome_titular or b.nome
            resposta['pix_info'] = f'Envie R$ {valor_total:.2f} via PIX e envie o comprovante.'

    return jsonify(resposta), 201


# ── POST /api/v1/cliente/compras/<id>/comprovante ────────────────────────────

@cliente_produtos_bp.post('/compras/<int:solicitacao_id>/comprovante')
@limiter.limit(os.environ.get('RL_COMPROVANTE', '3 per minute'))
@cliente_required
@feature_required('produtos_venda')
def upload_comprovante_compra(solicitacao_id):
    cli = _get_cliente_ou_404(g.user_id, g.barbearia_id)
    sol = SolicitacaoCompraProduto.query.filter_by(
        id=solicitacao_id, barbearia_id=g.barbearia_id, cliente_id=cli.id
    ).first()
    if not sol:
        raise APIError('Pedido não encontrado.', 404)
    if sol.metodo_pagamento != 'pix':
        raise APIError('Este pedido não é via PIX.', 400)
    if sol.status != StatusSolicitacaoCompra.PENDENTE:
        raise APIError('Não é possível enviar comprovante para este pedido.', 422)

    if 'arquivo' not in request.files:
        raise APIError('Campo "arquivo" é obrigatório.', 400)
    arq = request.files['arquivo']
    if not arq.filename:
        raise APIError('Nenhum arquivo enviado.', 400)
    if arq.mimetype not in _TIPOS_COMPROVANTE:
        raise APIError('Tipo não permitido. Use JPEG ou PNG.', 400)
    arq.seek(0, 2)
    if arq.tell() > _MAX_BYTES_COMP:
        raise APIError('Arquivo muito grande. Máximo 5 MB.', 400)
    arq.seek(0)
    _validar_magic_bytes(arq)

    from datetime import datetime as _dt
    now = _dt.utcnow()
    folder = f'barbearia/{g.barbearia_id}/comprovantes_compra/{now.strftime("%Y")}/{now.strftime("%m")}'
    public_id = f'compra_{solicitacao_id}'

    try:
        resultado = cloudinary.uploader.upload(
            arq.stream, folder=folder, public_id=public_id,
            overwrite=True, unique_filename=False, invalidate=True, resource_type='image',
        )
    except Exception as exc:
        current_app.logger.error(f'Cloudinary: falha ao enviar comprovante (compra {solicitacao_id}): {exc}', exc_info=True)
        raise APIError('Erro ao enviar comprovante. Tente novamente.', 502)

    url = resultado.get('secure_url')
    if not url:
        raise APIError('Cloudinary não retornou URL.', 502)

    sol.comprovante_url = url
    commit_ou_falhar('cliente.produtos.upload_comprovante_compra')

    return jsonify({'mensagem': 'Comprovante enviado com sucesso.', 'url': url}), 200
