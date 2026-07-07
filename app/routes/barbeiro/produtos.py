"""
Leitura de catálogo de produtos pro barbeiro (Script 18) — só GET, nenhuma
escrita. Criado porque app/templates/barbeiro/produtos.html chamava
`api.produtos.listar()`, um objeto JS que nunca existiu em lugar nenhum do
projeto (mesmo bug encontrado em vip.html no Script 15) — a tela nunca
funcionou de fato. Corrigido para usar Bos (cliente real) + este endpoint,
que também serve para popular a busca de produto no modal de venda.
"""
from flask import Blueprint, g, jsonify
from app.models import Produto, CategoriaProduto, FeatureMetadata, FeatureBarbearia
from app.decorators.auth import barbeiro_required

barbeiro_produtos_bp = Blueprint('barbeiro_produtos', __name__, url_prefix='/api/v1/barbeiro')


@barbeiro_produtos_bp.get('/features')
@barbeiro_required
def listar_features_barbeiro():
    """Mesmo formato de GET /api/v1/gestor/features — não existia equivalente
    pro barbeiro (a sidebar dele nunca gateou nada por feature antes do
    Script 18). Usado pra esconder o botão 'Vender produto' quando a feature
    'produtos_venda' estiver desligada."""
    todas = FeatureMetadata.query.order_by(FeatureMetadata.nome).all()
    flags = {
        fb.feature_id: fb.ativo
        for fb in FeatureBarbearia.query.filter_by(barbearia_id=g.barbearia_id).all()
    }
    return jsonify([
        {'nome': fm.nome, 'descricao': fm.descricao, 'ativo': flags.get(fm.id, False)}
        for fm in todas
    ]), 200


@barbeiro_produtos_bp.get('/produtos')
@barbeiro_required
def listar_produtos_barbeiro():
    produtos = Produto.query_tenant().filter_by(ativo=True).order_by(Produto.nome).all()
    categoria_ids = {p.categoria_id for p in produtos if p.categoria_id}
    categorias_map = {c.id: c for c in CategoriaProduto.query.filter(
        CategoriaProduto.id.in_(categoria_ids)).all()} if categoria_ids else {}

    return jsonify([
        {
            'id':                 p.id,
            'nome':                p.nome,
            'categoria':           categorias_map.get(p.categoria_id).nome if p.categoria_id and categorias_map.get(p.categoria_id) else p.categoria,
            'preco':               float(p.preco),
            'codigo_barras':       p.codigo_barras,
            'quantidade_estoque':  p.quantidade_estoque,
            'ativo':               p.ativo,
        }
        for p in produtos
    ]), 200
