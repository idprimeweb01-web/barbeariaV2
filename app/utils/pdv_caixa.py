"""
Caixa diária do barbeiro (v1.2) — venda avulsa de produto fora do fluxo de
Venda/VendaItem (Script 18), acumulada por dia em vez de por transação.

Toda movimentação de estoque passa por app/utils/estoque.py (serviço central
já existente, com lock atômico e MovimentacaoEstoque de auditoria) — nunca
escrever direto em Produto.quantidade_estoque aqui.
"""
import datetime as dt

from app.extensions import db
from app.models import BarbeiroCaixa, ItemCaixa
from app.exceptions import APIError
from app.utils.tz import hoje_brasilia, naive_brasilia
from app.utils import estoque as estoque_service
from app.constants import TipoMovimentacaoEstoque


def abrir_caixa(barbeiro_id: int, barbearia_id: int, data: dt.date | None = None) -> BarbeiroCaixa:
    """Abre caixa do dia para o barbeiro. Idempotente — uq_barbeiro_caixa_data
    garante que uma 2ª chamada no mesmo dia devolve a caixa já existente."""
    if not data:
        data = hoje_brasilia()

    caixa = BarbeiroCaixa.query.filter_by(
        barbeiro_id=barbeiro_id, barbearia_id=barbearia_id, data=data
    ).first()

    if not caixa:
        caixa = BarbeiroCaixa(
            barbeiro_id=barbeiro_id,
            barbearia_id=barbearia_id,
            data=data,
        )
        db.session.add(caixa)
        db.session.flush()

    return caixa


def adicionar_item_caixa(
    caixa_id: int, produto_id: int, barbearia_id: int, usuario_id: int,
    quantidade: int, preco: float, desconto_percentual: float,
    forma_pagamento: str, agendamento_id: int | None = None,
) -> ItemCaixa:
    """Adiciona item à caixa e decrementa o estoque via serviço central —
    mesmo lock atômico usado em vendas avulsas (registrar_saida), evita
    2 caixas vendendo o último item do estoque ao mesmo tempo."""
    caixa = BarbeiroCaixa.query.filter_by(id=caixa_id, barbearia_id=barbearia_id).first()
    if not caixa:
        raise APIError('Caixa não encontrado.', 404)
    if caixa.fechado_em:
        raise APIError('Caixa já fechado.', 422)

    item = ItemCaixa(
        barbearia_id=barbearia_id,
        caixa_id=caixa_id,
        produto_id=produto_id,
        quantidade=quantidade,
        preco=preco,
        desconto_percentual=desconto_percentual,
        forma_pagamento=forma_pagamento,
        agendamento_id=agendamento_id,
    )
    db.session.add(item)
    db.session.flush()

    estoque_service.registrar_saida(
        produto_id, barbearia_id, quantidade, usuario_id,
        motivo=f'Venda avulsa — caixa #{caixa_id}',
        tipo=TipoMovimentacaoEstoque.SAIDA_VENDA,
    )

    caixa.total = float(caixa.total) + item.total
    return item


def remover_item_caixa(item_id: int, barbearia_id: int, usuario_id: int) -> None:
    """Remove item da caixa e devolve o estoque via serviço central."""
    item = ItemCaixa.query.filter_by(id=item_id, barbearia_id=barbearia_id).first()
    if not item:
        raise APIError('Item não encontrado.', 404)

    caixa = BarbeiroCaixa.query.filter_by(id=item.caixa_id, barbearia_id=barbearia_id).first()
    if caixa and caixa.fechado_em:
        raise APIError('Caixa já fechado.', 422)

    estoque_service.registrar_entrada(
        item.produto_id, barbearia_id, item.quantidade, usuario_id,
        motivo=f'Estorno — remoção de item da caixa #{item.caixa_id}',
        tipo=TipoMovimentacaoEstoque.ENTRADA,
    )

    if caixa:
        caixa.total = max(0.0, float(caixa.total) - item.total)

    db.session.delete(item)


def fechar_caixa(caixa_id: int, barbearia_id: int) -> BarbeiroCaixa:
    """Fecha a caixa do dia. Timestamp em horário de Brasília (DT-001) —
    fechado_em é exibido pro barbeiro/gestor, não é log interno."""
    caixa = BarbeiroCaixa.query.filter_by(id=caixa_id, barbearia_id=barbearia_id).first()
    if not caixa:
        raise APIError('Caixa não encontrado.', 404)
    if caixa.fechado_em:
        raise APIError('Caixa já fechado.', 422)

    caixa.fechado_em = naive_brasilia()
    return caixa
