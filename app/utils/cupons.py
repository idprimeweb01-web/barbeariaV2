from sqlalchemy import text
from app.extensions import db
from app.models import Cupom, CupomServico, CupomProduto, CupomUso
from app.exceptions import APIError
from app.utils.features import feature_ativa
from app.utils.tz import hoje_brasilia


def validar_cupom(barbearia_id: int, codigo: str, itens: list[dict],
                   cliente_id: int | None = None) -> tuple[Cupom, float]:
    """
    Valida um código de cupom para a barbearia e retorna (cupom, valor_desconto).
    Levanta APIError (422) com mensagem específica em qualquer condição inválida.

    itens: [{'tipo': 'servico'|'produto', 'ref_id': int, 'valor': float}, ...]
    — cada linha da compra atual, com `valor` = preço unitário × quantidade.
    O desconto é calculado só sobre a fatia elegível (serviços/produtos aos
    quais o cupom está vinculado) — nunca sobre o total do carrinho inteiro,
    a menos que o cupom não tenha nenhum vínculo (aí vale pra tudo).

    `cliente_id`: quando informado e o cupom tiver `limite_uso_por_cliente`
    setado, bloqueia se esse cliente já usou o cupom `limite_uso_por_cliente`
    vezes ou mais (conta TODO CupomUso, mesmo de agendamento/venda cancelado
    depois — ver comentário no model `Cupom`). Omitir (None) pula essa
    checagem — usado por chamadores que não têm cliente identificado (ex:
    venda avulsa com `cliente_nome_livre`).
    """
    if not feature_ativa(barbearia_id, 'cupons'):
        raise APIError('Cupons não estão disponíveis para esta barbearia.', 403)

    codigo_norm = (codigo or '').strip().upper()
    if not codigo_norm:
        raise APIError('Informe um código de cupom.', 422)

    cupom = Cupom.query.filter_by(barbearia_id=barbearia_id, codigo=codigo_norm).first()
    if not cupom:
        raise APIError('Cupom não encontrado.', 422)
    if not cupom.ativo:
        raise APIError('Este cupom não está mais ativo.', 422)
    if cupom.data_expiracao < hoje_brasilia():
        raise APIError('Este cupom expirou.', 422)
    if cupom.quantidade_maxima_usos is not None and cupom.quantidade_usos >= cupom.quantidade_maxima_usos:
        raise APIError('Este cupom atingiu o limite de utilizações.', 422)
    if cliente_id is not None and cupom.limite_uso_por_cliente is not None:
        usos_deste_cliente = CupomUso.query.filter_by(cupom_id=cupom.id, cliente_id=cliente_id).count()
        if usos_deste_cliente >= cupom.limite_uso_por_cliente:
            raise APIError('Você já atingiu o limite de uso deste cupom.', 422)

    subtotal_elegivel = _subtotal_elegivel(cupom, itens)
    if subtotal_elegivel <= 0:
        alvos = _descricao_alvos(cupom)
        raise APIError(f'Este cupom só vale para {alvos}.' if alvos else 'Este cupom não se aplica a nenhum item deste pedido.', 422)

    desconto = calcular_desconto(cupom, subtotal_elegivel)
    return cupom, desconto


def _subtotal_elegivel(cupom: Cupom, itens: list[dict]) -> float:
    """Soma só o valor das linhas do carrinho que o cupom cobre.

    Serviços e produtos são dimensões INDEPENDENTES — um cupom pode valer pra
    TODOS os serviços e, ao mesmo tempo, só um produto específico. Pra cada
    dimensão, o gestor escolhe um dos três modos (ver gestor/cupons.py):
      • aplica_todos_* = True         → cobre qualquer item dessa dimensão
      • existe linha em CupomServico/CupomProduto → cobre só os selecionados
      • nenhum dos dois (padrão)      → não cobre NADA dessa dimensão
    """
    servico_ids = {cs.servico_id for cs in CupomServico.query.filter_by(cupom_id=cupom.id).all()}
    produto_ids = {cp.produto_id for cp in CupomProduto.query.filter_by(cupom_id=cupom.id).all()}

    total = 0.0
    for i in itens:
        if i.get('tipo') == 'servico':
            if cupom.aplica_todos_servicos or i.get('ref_id') in servico_ids:
                total += i['valor']
        elif i.get('tipo') == 'produto':
            if cupom.aplica_todos_produtos or i.get('ref_id') in produto_ids:
                total += i['valor']
    return total


def _descricao_alvos(cupom: Cupom) -> str:
    """Monta 'todos os serviços e Shampoo Premium' etc. pra mensagem de erro."""
    from app.models import Servico, Produto
    partes = []

    if cupom.aplica_todos_servicos:
        partes.append('qualquer serviço')
    else:
        ids = [cs.servico_id for cs in CupomServico.query.filter_by(cupom_id=cupom.id).all()]
        if ids:
            nomes = [s.nome for s in Servico.query.filter(Servico.id.in_(ids)).all()]
            partes.append(' ou '.join(nomes) if len(nomes) == 1 else ', '.join(nomes[:-1]) + ' ou ' + nomes[-1])

    if cupom.aplica_todos_produtos:
        partes.append('qualquer produto')
    else:
        ids = [cp.produto_id for cp in CupomProduto.query.filter_by(cupom_id=cupom.id).all()]
        if ids:
            nomes = [p.nome for p in Produto.query.filter(Produto.id.in_(ids)).all()]
            partes.append(' ou '.join(nomes) if len(nomes) == 1 else ', '.join(nomes[:-1]) + ' ou ' + nomes[-1])

    return ' e '.join(partes)


def calcular_desconto(cupom: Cupom, subtotal: float) -> float:
    if cupom.tipo_desconto == 'percentual':
        valor = subtotal * float(cupom.valor_desconto) / 100
    else:
        valor = float(cupom.valor_desconto)
    return round(min(valor, subtotal), 2)


def incrementar_uso_cupom(cupom_id: int, barbearia_id: int):
    """UPDATE atômico — evita TOCTOU entre validar_cupom() (pré-check de UX)
    e o incremento de fato: duas requisições concorrentes usando o último uso
    disponível não podem, juntas, ultrapassar quantidade_maxima_usos."""
    result = db.session.execute(text('''
        UPDATE cupons SET quantidade_usos = quantidade_usos + 1
        WHERE id = :id AND barbearia_id = :bk
          AND (quantidade_maxima_usos IS NULL
               OR quantidade_usos < quantidade_maxima_usos)
    '''), {'id': cupom_id, 'bk': barbearia_id})
    if result.rowcount == 0:
        raise APIError('Cupom esgotado.', 422)


def decrementar_uso_cupom(cupom_id: int, barbearia_id: int):
    """UPDATE atômico — usado em cancelamento/rejeição. Não levanta erro se
    não houver linha pra decrementar (ex: contador já em zero)."""
    db.session.execute(text('''
        UPDATE cupons SET quantidade_usos = quantidade_usos - 1
        WHERE id = :id AND barbearia_id = :bk AND quantidade_usos > 0
    '''), {'id': cupom_id, 'bk': barbearia_id})


def registrar_uso_cupom(cupom_id: int, barbearia_id: int, valor_original: float, valor_desconto: float,
                         cliente_id: int | None = None, agendamento_id: int | None = None,
                         venda_id: int | None = None, honrado_fora_limite: bool = False):
    """Grava uma linha de histórico pra cada aplicação bem-sucedida de cupom —
    é o que alimenta o relatório de uso (quem usou, quando, quanto foi descontado).
    Chamar sempre junto com incrementar_uso_cupom(), na mesma transação — exceto
    no caso `honrado_fora_limite=True` (aprovação de compra já paga, cupom
    estourou nesse meio-tempo: o uso é registrado pra auditoria, mas o contador
    global de Cupom.quantidade_usos não é incrementado)."""
    db.session.add(CupomUso(
        barbearia_id=barbearia_id,
        cupom_id=cupom_id,
        cliente_id=cliente_id,
        agendamento_id=agendamento_id,
        venda_id=venda_id,
        valor_original=round(valor_original, 2),
        valor_desconto=round(valor_desconto, 2),
        valor_final=round(valor_original - valor_desconto, 2),
        honrado_fora_limite=honrado_fora_limite,
    ))
