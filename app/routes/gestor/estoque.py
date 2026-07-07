from flask import Blueprint, request, g, jsonify
from app.extensions import db
from app.models import Produto, MovimentacaoEstoque, Usuario
from app.exceptions import APIError
from app.decorators.auth import gestor_required
from app.utils.features import feature_required
from app.utils.db import commit_ou_falhar
from app.constants import TipoMovimentacaoEstoque
from app.utils import estoque as estoque_service

gestor_estoque_bp = Blueprint('gestor_estoque', __name__, url_prefix='/api/v1/gestor/estoque')


def _fmt_movimentacao(m, usuarios_map=None):
    usr = usuarios_map.get(m.usuario_id) if usuarios_map is not None else db.session.get(Usuario, m.usuario_id)
    return {
        'id':                        m.id,
        'produto_id':                m.produto_id,
        'tipo':                      m.tipo,
        'quantidade':                m.quantidade,
        'quantidade_apos':           m.quantidade_apos,
        'motivo':                    m.motivo,
        'usuario_id':                m.usuario_id,
        'usuario_nome':              usr.nome if usr else None,
        'referencia_venda_id':       m.referencia_venda_id,
        'referencia_atendimento_id': m.referencia_atendimento_id,
        'criado_em':                 m.criado_em.isoformat() if m.criado_em else None,
    }


# ── POST /api/v1/gestor/estoque/movimentar ───────────────────────────────────

@gestor_estoque_bp.post('/movimentar')
@gestor_required
@feature_required('produtos_venda')
def movimentar_estoque():
    bid = g.barbearia_id
    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    produto_id = dados.get('produto_id')
    tipo       = (dados.get('tipo') or '').strip()
    quantidade = dados.get('quantidade')
    motivo     = (dados.get('motivo') or '').strip()

    if not isinstance(produto_id, int):
        raise APIError('"produto_id" é obrigatório e deve ser um inteiro.')
    if tipo not in TipoMovimentacaoEstoque.TODOS:
        raise APIError(f'"tipo" deve ser um de: {", ".join(sorted(TipoMovimentacaoEstoque.TODOS))}.')
    if not isinstance(quantidade, int) or quantidade == 0:
        raise APIError('"quantidade" deve ser um inteiro diferente de zero.')
    if not motivo:
        raise APIError('"motivo" é obrigatório.')

    if tipo == TipoMovimentacaoEstoque.AJUSTE:
        # Único tipo bidirecional — sinal decide entrada ou saída (ver
        # app.utils.estoque.ajustar_estoque).
        produto = estoque_service.ajustar_estoque(produto_id, bid, quantidade, g.user_id, motivo)
    elif tipo == TipoMovimentacaoEstoque.ENTRADA:
        if quantidade < 0:
            raise APIError('"quantidade" deve ser positiva para entrada.', 422)
        produto = estoque_service.registrar_entrada(produto_id, bid, quantidade, g.user_id, motivo, tipo=tipo)
    else:  # saida_venda, saida_uso
        if quantidade < 0:
            raise APIError('"quantidade" deve ser positiva (magnitude) para saída.', 422)
        produto = estoque_service.registrar_saida(produto_id, bid, quantidade, g.user_id, motivo, tipo=tipo)

    commit_ou_falhar('gestor.estoque.movimentar_estoque')
    return jsonify({
        'produto_id':       produto.id,
        'quantidade_atual': produto.quantidade_estoque,
    }), 201


# ── GET /api/v1/gestor/estoque/movimentacoes ─────────────────────────────────

@gestor_estoque_bp.get('/movimentacoes')
@gestor_required
def listar_movimentacoes():
    bid = g.barbearia_id
    q = MovimentacaoEstoque.query.filter_by(barbearia_id=bid)

    produto_id = request.args.get('produto_id', type=int)
    if produto_id:
        q = q.filter_by(produto_id=produto_id)

    try:
        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 50))))
    except ValueError:
        raise APIError('"page" e "per_page" devem ser inteiros.', 422)

    paginado = q.order_by(MovimentacaoEstoque.criado_em.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    usuario_ids = {m.usuario_id for m in paginado.items}
    usuarios_map = {u.id: u for u in Usuario.query.filter(Usuario.id.in_(usuario_ids)).all()} if usuario_ids else {}

    return jsonify({
        'dados':    [_fmt_movimentacao(m, usuarios_map) for m in paginado.items],
        'page':     paginado.page,
        'per_page': paginado.per_page,
        'total':    paginado.total,
        'pages':    paginado.pages,
    }), 200
