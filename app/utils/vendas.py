"""
Núcleo de criação/cancelamento de Venda avulsa de produto (Script 18).
Compartilhado entre gestor/vendas.py e barbeiro/vendas.py — mesma lógica,
só muda quem pode ser `barbeiro_id` (gestor escolhe; barbeiro é ele mesmo).
"""
from app.extensions import db
from app.exceptions import APIError
from app.constants import MetodoPagamentoVenda, StatusVenda, TipoMovimentacaoEstoque
from app.utils import estoque as estoque_service
from app.utils.estoque import calcular_comissao_venda


def criar_venda_core(barbearia_id: int, usuario_registro_id: int, itens: list,
                      barbeiro_id: int = None, cliente_id: int = None,
                      cliente_nome_livre: str = None, metodo_pagamento: str = None):
    """
    itens: [{'produto_id': int, 'quantidade': int}, ...]
    Valida estoque via serviço central (com lock), calcula total e comissão
    do barbeiro (se houver), grava Venda + VendaItem + MovimentacaoEstoque
    (saida_venda) tudo na mesma transação. Levanta APIError em qualquer
    violação (produto inexistente, estoque insuficiente, etc.) — quem
    chama decide se comita ou propaga.
    """
    from app.models import Venda, VendaItem, Produto, Barbeiro, Cliente

    if not itens:
        raise APIError('Informe ao menos um item para a venda.', 422)
    if metodo_pagamento not in MetodoPagamentoVenda.TODOS:
        raise APIError(
            f'"metodo_pagamento" deve ser um de: {", ".join(sorted(MetodoPagamentoVenda.TODOS))}.', 422
        )
    if cliente_id and cliente_nome_livre:
        raise APIError('Informe "cliente_id" OU "cliente_nome_livre", não os dois.', 422)

    if cliente_id is not None:
        if not Cliente.query.filter_by(id=cliente_id, barbearia_id=barbearia_id).first():
            raise APIError('Cliente não encontrado.', 404)

    barbeiro = None
    if barbeiro_id is not None:
        barbeiro = Barbeiro.query.filter_by(id=barbeiro_id, barbearia_id=barbearia_id, ativo=True).first()
        if not barbeiro:
            raise APIError('Profissional vendedor não encontrado ou inativo.', 404)

    venda = Venda(
        barbearia_id=barbearia_id,
        cliente_id=cliente_id,
        cliente_nome_livre=(cliente_nome_livre or '').strip() or None,
        barbeiro_id=barbeiro_id,
        usuario_registro_id=usuario_registro_id,
        metodo_pagamento=metodo_pagamento,
        status=StatusVenda.CONCLUIDA,
        valor_total=0,
    )
    db.session.add(venda)
    db.session.flush()  # precisa do venda.id pra referenciar nos itens/movimentações

    valor_total = 0.0
    for item in itens:
        produto_id = item.get('produto_id')
        quantidade = item.get('quantidade')
        if not isinstance(produto_id, int):
            raise APIError('"produto_id" de cada item deve ser um inteiro.', 422)
        if not isinstance(quantidade, int) or quantidade <= 0:
            raise APIError('"quantidade" de cada item deve ser um inteiro positivo.', 422)

        produto = Produto.query.filter_by(id=produto_id, barbearia_id=barbearia_id, ativo=True).first()
        if not produto:
            raise APIError(f'Produto id={produto_id} não encontrado ou inativo.', 404)

        preco_unitario = float(produto.preco)
        subtotal = round(preco_unitario * quantidade, 2)
        comissao = calcular_comissao_venda(barbeiro, subtotal) if barbeiro else 0.0

        # Saída de estoque com lock atômico — 422 se não houver quantidade suficiente.
        estoque_service.registrar_saida(
            produto_id, barbearia_id, quantidade, usuario_registro_id,
            motivo=f'Venda #{venda.id}', tipo=TipoMovimentacaoEstoque.SAIDA_VENDA,
            referencia_venda_id=venda.id,
        )

        db.session.add(VendaItem(
            venda_id=venda.id,
            produto_id=produto.id,
            quantidade=quantidade,
            preco_unitario=preco_unitario,
            custo_unitario_snapshot=float(produto.custo_unitario or 0),
            comissao_valor=comissao,
        ))
        valor_total += subtotal

    venda.valor_total = round(valor_total, 2)
    return venda


def cancelar_venda_core(venda, usuario_id: int):
    """Devolve o estoque de cada item (entrada, motivo 'cancelamento venda')
    e marca a venda como cancelada. `venda` já deve estar travada
    (.with_for_update()) por quem chamou."""
    from app.models import VendaItem

    if venda.status == StatusVenda.CANCELADA:
        raise APIError('Esta venda já está cancelada.', 422)

    # Tarefa pede explicitamente: "movimenta 'entrada' motivo 'cancelamento venda'".
    itens = VendaItem.query.filter_by(venda_id=venda.id).all()
    for item in itens:
        estoque_service.registrar_entrada(
            item.produto_id, venda.barbearia_id, item.quantidade, usuario_id,
            motivo='cancelamento venda',
            tipo=TipoMovimentacaoEstoque.ENTRADA,
            referencia_venda_id=venda.id,
        )

    venda.status = StatusVenda.CANCELADA
