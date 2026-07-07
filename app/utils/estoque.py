"""
Serviço central de movimentação de estoque (Script 18/Bloco 6.4).

TODO fluxo que altera Produto.quantidade_estoque deve passar por aqui —
nunca escrever direto na coluna (inclusive o caixa/atendimento, refatorado
para usar este serviço). Toda movimentação gera uma linha de
MovimentacaoEstoque para auditoria (quantidade sempre positiva/magnitude —
ver app.constants.TipoMovimentacaoEstoque para a decisão de semântica).

Padrão de lock: mesmo UPDATE atômico com guard de linha afetada usado em
incrementar_uso_cupom/decrementar_uso_cupom (Script 07) — evita o TOCTOU
entre "checar se tem estoque" e "decrementar", mesmo sob concorrência real.
"""
from sqlalchemy import text
from app.extensions import db
from app.exceptions import APIError
from app.constants import TipoMovimentacaoEstoque


def _get_produto_ou_404(produto_id: int, barbearia_id: int):
    from app.models import Produto
    produto = Produto.query.filter_by(id=produto_id, barbearia_id=barbearia_id).first()
    if not produto:
        raise APIError('Produto não encontrado.', 404)
    return produto


def _registrar_movimentacao(produto, tipo, quantidade, usuario_id, motivo,
                             referencia_venda_id=None, referencia_atendimento_id=None):
    from app.models import MovimentacaoEstoque
    db.session.add(MovimentacaoEstoque(
        barbearia_id=produto.barbearia_id,
        produto_id=produto.id,
        tipo=tipo,
        quantidade=quantidade,
        quantidade_apos=produto.quantidade_estoque,
        motivo=motivo,
        usuario_id=usuario_id,
        referencia_venda_id=referencia_venda_id,
        referencia_atendimento_id=referencia_atendimento_id,
    ))


def registrar_entrada(produto_id: int, barbearia_id: int, quantidade: int, usuario_id: int,
                       motivo: str, tipo: str = TipoMovimentacaoEstoque.ENTRADA,
                       referencia_venda_id: int = None, referencia_atendimento_id: int = None):
    """Soma ao estoque. Sem guard de limite superior (entrada sempre cabe).
    `quantidade` é a magnitude (sempre positiva) — quem chama já resolveu o sinal."""
    if not isinstance(quantidade, int) or quantidade <= 0:
        raise APIError('Quantidade deve ser um inteiro maior que zero.', 422)

    produto = _get_produto_ou_404(produto_id, barbearia_id)

    db.session.execute(text('''
        UPDATE produtos SET quantidade_estoque = quantidade_estoque + :q
        WHERE id = :id AND barbearia_id = :bk
    '''), {'q': quantidade, 'id': produto_id, 'bk': barbearia_id})
    db.session.refresh(produto)

    _registrar_movimentacao(produto, tipo, quantidade, usuario_id, motivo,
                             referencia_venda_id, referencia_atendimento_id)
    return produto


def registrar_saida(produto_id: int, barbearia_id: int, quantidade: int, usuario_id: int,
                     motivo: str, tipo: str = TipoMovimentacaoEstoque.SAIDA_USO,
                     referencia_venda_id: int = None, referencia_atendimento_id: int = None):
    """
    UPDATE atômico com guard (padrão Script 07): só decrementa se o estoque
    atual for suficiente — fecha a corrida entre 2 vendas simultâneas do
    último item. rowcount 0 => 422 'Estoque insuficiente'.
    """
    if not isinstance(quantidade, int) or quantidade <= 0:
        raise APIError('Quantidade deve ser um inteiro maior que zero.', 422)

    produto = _get_produto_ou_404(produto_id, barbearia_id)
    nome = produto.nome

    result = db.session.execute(text('''
        UPDATE produtos SET quantidade_estoque = quantidade_estoque - :q
        WHERE id = :id AND barbearia_id = :bk AND quantidade_estoque >= :q
    '''), {'q': quantidade, 'id': produto_id, 'bk': barbearia_id})

    if result.rowcount == 0:
        raise APIError(f'Estoque insuficiente de "{nome}".', 422)

    db.session.refresh(produto)
    _registrar_movimentacao(produto, tipo, quantidade, usuario_id, motivo,
                             referencia_venda_id, referencia_atendimento_id)
    return produto


def ajustar_estoque(produto_id: int, barbearia_id: int, delta: int, usuario_id: int, motivo: str):
    """
    Endpoint de correção manual de inventário (quebra, perda, contagem
    física) — `delta` pode ser positivo ou negativo (é a ÚNICA via que
    aceita sinal explícito). Internamente grava sempre a magnitude (abs)
    na MovimentacaoEstoque com tipo='ajuste', e decide a direção chamando
    registrar_entrada (delta > 0) ou registrar_saida (delta < 0).
    """
    if not isinstance(delta, int) or delta == 0:
        raise APIError('"quantidade" deve ser um inteiro diferente de zero.', 422)

    if delta > 0:
        return registrar_entrada(produto_id, barbearia_id, delta, usuario_id, motivo,
                                  tipo=TipoMovimentacaoEstoque.AJUSTE)
    return registrar_saida(produto_id, barbearia_id, abs(delta), usuario_id, motivo,
                            tipo=TipoMovimentacaoEstoque.AJUSTE)


def calcular_comissao_venda(barbeiro, valor_item: float) -> float:
    """
    Comissão de venda de produto pro barbeiro que vendeu. Isolada em função
    própria (pedido explícito da tarefa) para, no futuro, suportar comissão
    configurável por produto sem precisar tocar nos endpoints de venda —
    hoje usa só Barbeiro.comissao_percentual (mesmo campo já usado na
    comissão de atendimento/agendamento).
    """
    if not barbeiro:
        return 0.0
    return round(float(valor_item) * float(barbeiro.comissao_percentual) / 100, 2)
