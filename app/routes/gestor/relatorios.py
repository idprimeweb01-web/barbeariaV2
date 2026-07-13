from datetime import date
from flask import Blueprint, g, jsonify, request, send_file
from sqlalchemy import func
from app.extensions import db
from app.models import (
    Cliente, Agendamento, Venda, VendaItem, Produto,
    ItemCaixa, BarbeiroCaixa, Barbeiro, Usuario,
)
from app.exceptions import APIError
from app.decorators.auth import gestor_required
from app.labels import L
from app.utils.relatorio import (
    COLUNAS, COLUNAS_OBRIGATORIAS, validar_colunas,
    gerar_dados, gerar_excel, gerar_pdf,
)
from app.utils.tz import hoje_brasilia, naive_brasilia
from app.constants import StatusPagamento

gestor_relatorios_bp = Blueprint('gestor_relatorios', __name__, url_prefix='/api/v1/gestor')


def _parse_params():
    """Extrai e valida os query params comuns a todos os endpoints de relatório."""
    colunas_raw = request.args.get('colunas', '')
    if colunas_raw:
        colunas_solicitadas = [c.strip() for c in colunas_raw.split(',') if c.strip()]
    else:
        colunas_solicitadas = list(COLUNAS.keys())

    try:
        colunas = validar_colunas(colunas_solicitadas)
    except ValueError as exc:
        raise APIError(str(exc), 422)

    de_str  = request.args.get('de',  hoje_brasilia().replace(day=1).isoformat())
    ate_str = request.args.get('ate', hoje_brasilia().isoformat())
    try:
        de  = date.fromisoformat(de_str)
        ate = date.fromisoformat(ate_str)
    except ValueError:
        raise APIError('Parâmetros "de" e "ate" devem estar no formato YYYY-MM-DD.', 422)

    if de > ate:
        raise APIError('"de" não pode ser posterior a "ate".', 422)

    return colunas, de, ate


def _barbearia_nome() -> str:
    from app.models import Barbearia
    b = Barbearia.query.get(g.barbearia_id)
    return b.nome if b else 'Barbearia'


# ── JSON ──────────────────────────────────────────────────────────────────────

@gestor_relatorios_bp.get('/relatorios/agendamentos')
@gestor_required
def relatorio_agendamentos_json():
    """
    Retorna relatório de agendamentos em JSON.

    Query params:
      colunas  — lista separada por vírgula; padrão: todas as colunas.
                 Colunas obrigatórias não podem ser omitidas.
      de       — data inicial YYYY-MM-DD; padrão: primeiro dia do mês atual.
      ate      — data final   YYYY-MM-DD; padrão: hoje.
    """
    colunas, de, ate = _parse_params()
    dados = gerar_dados(g.barbearia_id, de, ate, colunas)

    receita_total = sum(float(l.get('valor_total', 0)) for l in dados) if 'valor_total' in colunas else None
    periodo = f'{de.strftime("%d/%m/%Y")} a {ate.strftime("%d/%m/%Y")}'

    return jsonify({
        'barbearia':    _barbearia_nome(),
        'periodo':      periodo,
        'gerado_em':    naive_brasilia().strftime('%d/%m/%Y %H:%M'),
        'colunas_ativas': colunas,
        'colunas_disponiveis': {
            k: {'label': v['label'], 'obrigatorio': v['obrigatorio']}
            for k, v in COLUNAS.items()
        },
        'total_registros': len(dados),
        'receita_total': round(receita_total, 2) if receita_total is not None else None,
        'dados': dados,
        'rotulos': {
            'agendamento':  L('agendamento'),
            'cliente':      L('cliente'),
            'servico':      L('servico'),
            'servicos':     L('servicos'),
            'profissional': L('profissional'),
            'receita':      L('receita'),
            'plano':        L('plano'),
        },
    }), 200


# ── Excel ─────────────────────────────────────────────────────────────────────

@gestor_relatorios_bp.get('/relatorios/agendamentos/excel')
@gestor_required
def relatorio_agendamentos_excel():
    """Exporta relatório de agendamentos em Excel (.xlsx)."""
    colunas, de, ate = _parse_params()
    dados = gerar_dados(g.barbearia_id, de, ate, colunas)
    nome_barbearia = _barbearia_nome()
    periodo = f'{de.strftime("%d/%m/%Y")} a {ate.strftime("%d/%m/%Y")}'

    buf = gerar_excel(dados, colunas, nome_barbearia, periodo)
    nome_arquivo = (
        f'relatorio_{nome_barbearia.lower().replace(" ", "_")}'
        f'_{de.isoformat()}_{ate.isoformat()}.xlsx'
    )
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=nome_arquivo,
    )


# ── PDF ───────────────────────────────────────────────────────────────────────

@gestor_relatorios_bp.get('/relatorios/agendamentos/pdf')
@gestor_required
def relatorio_agendamentos_pdf():
    """Exporta relatório de agendamentos em PDF. Cabeçalho com nome da barbearia e período."""
    colunas, de, ate = _parse_params()
    dados = gerar_dados(g.barbearia_id, de, ate, colunas)
    nome_barbearia = _barbearia_nome()
    periodo = f'{de.strftime("%d/%m/%Y")} a {ate.strftime("%d/%m/%Y")}'

    buf = gerar_pdf(dados, colunas, nome_barbearia, periodo)
    nome_arquivo = (
        f'relatorio_{nome_barbearia.lower().replace(" ", "_")}'
        f'_{de.isoformat()}_{ate.isoformat()}.pdf'
    )
    return send_file(
        buf,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=nome_arquivo,
    )


# ── Coluna schema ─────────────────────────────────────────────────────────────

@gestor_relatorios_bp.get('/relatorios/colunas')
@gestor_required
def listar_colunas():
    """Lista todas as colunas disponíveis com flag de obrigatoriedade."""
    return jsonify({
        'colunas': {
            k: {'label': v['label'], 'obrigatorio': v['obrigatorio']}
            for k, v in COLUNAS.items()
        },
        'obrigatorias': sorted(COLUNAS_OBRIGATORIAS),
    }), 200


# ── Dívidas por cliente ────────────────────────────────────────────────────────

@gestor_relatorios_bp.get('/relatorios/dividas')
@gestor_required
def relatorio_dividas():
    """Clientes com agendamentos de pagamento pendente (status_pagamento='pendente'),
    somados por cliente — usado pra cobrar quem ainda deve."""
    clientes_devedores = (
        db.session.query(
            Cliente.id, Cliente.nome,
            func.count(Agendamento.id).label('qtd_agendamentos'),
            func.sum(Agendamento.valor_total).label('valor_total'),
        )
        .join(Agendamento, Agendamento.cliente_id == Cliente.id)
        .filter(
            Agendamento.barbearia_id == g.barbearia_id,
            Agendamento.status_pagamento == StatusPagamento.PENDENTE,
        )
        .group_by(Cliente.id, Cliente.nome)
        .order_by(func.sum(Agendamento.valor_total).desc())
        .all()
    )

    return jsonify([
        {
            'cliente_id':       c.id,
            'nome':             c.nome,
            'qtd_agendamentos': c.qtd_agendamentos,
            'valor_devido':     float(c.valor_total),
        }
        for c in clientes_devedores
    ]), 200


# ── Produtos vendidos (Venda avulsa + venda pela caixa do barbeiro) ───────────
# São dois modelos de dados separados (ver app/models: Venda/VendaItem vs
# BarbeiroCaixa/ItemCaixa) que nunca se cruzam em nenhum outro lugar — este
# endpoint é o único ponto do sistema que soma os dois pra dar ao gestor uma
# visão completa de "o que foi vendido", não importa por qual tela.

@gestor_relatorios_bp.get('/relatorios/vendas-produtos')
@gestor_required
def relatorio_vendas_produtos():
    _, de, ate = _parse_params()

    produtos_map = {}   # produto_id -> {nome, quantidade, receita}
    por_forma = {'dinheiro': 0.0, 'cartao': 0.0, 'pix': 0.0}

    # ── Venda avulsa (gestor/PDV clássico) ────────────────────────────────────
    itens_venda = (
        db.session.query(VendaItem, Venda.metodo_pagamento)
        .join(Venda, VendaItem.venda_id == Venda.id)
        .filter(
            Venda.barbearia_id == g.barbearia_id,
            Venda.status == 'concluida',
            db.func.date(Venda.criado_em) >= de,
            db.func.date(Venda.criado_em) <= ate,
        )
        .all()
    )
    produto_ids = {vi.produto_id for vi, _ in itens_venda}

    # ── Venda pela caixa diária do barbeiro ───────────────────────────────────
    itens_caixa = (
        db.session.query(ItemCaixa)
        .join(BarbeiroCaixa, ItemCaixa.caixa_id == BarbeiroCaixa.id)
        .filter(
            ItemCaixa.barbearia_id == g.barbearia_id,
            BarbeiroCaixa.data >= de,
            BarbeiroCaixa.data <= ate,
        )
        .all()
    )
    produto_ids |= {i.produto_id for i in itens_caixa}

    produtos = {p.id: p for p in Produto.query.filter(Produto.id.in_(produto_ids)).all()} if produto_ids else {}

    for vi, metodo in itens_venda:
        p = produtos.get(vi.produto_id)
        nome = p.nome if p else f'Produto #{vi.produto_id}'
        entry = produtos_map.setdefault(vi.produto_id, {'nome': nome, 'quantidade': 0, 'receita': 0.0})
        receita_item = float(vi.preco_unitario) * vi.quantidade
        entry['quantidade'] += vi.quantidade
        entry['receita'] += receita_item
        if metodo in por_forma:
            por_forma[metodo] += receita_item

    for i in itens_caixa:
        p = produtos.get(i.produto_id)
        nome = p.nome if p else f'Produto #{i.produto_id}'
        entry = produtos_map.setdefault(i.produto_id, {'nome': nome, 'quantidade': 0, 'receita': 0.0})
        entry['quantidade'] += i.quantidade
        entry['receita'] += i.total
        if i.forma_pagamento in por_forma:
            por_forma[i.forma_pagamento] += i.total

    produtos_lista = sorted(
        [{'produto_id': pid, **v} for pid, v in produtos_map.items()],
        key=lambda x: x['quantidade'], reverse=True,
    )

    return jsonify({
        'periodo': f'{de.isoformat()} a {ate.isoformat()}',
        'produtos': produtos_lista,
        'por_forma_pagamento': {k: round(v, 2) for k, v in por_forma.items()},
        'faturamento_total': round(sum(por_forma.values()), 2),
    }), 200


# ── Caixa por barbeiro (produtos + recebimento de agendamento) ───────────────
# "Caixa" aqui é o conceito operacional (quanto cada barbeiro girou no dia),
# não a tabela BarbeiroCaixa sozinha — soma as duas origens de dinheiro que
# passam pela mão do barbeiro: venda de produto (ItemCaixa) e recebimento de
# atendimento pago no local (Agendamento.forma_pagamento_recebido).

@gestor_relatorios_bp.get('/relatorios/caixa')
@gestor_required
def relatorio_caixa():
    _, de, ate = _parse_params()

    def _zero():
        return {'dinheiro': 0.0, 'cartao': 0.0, 'pix': 0.0, 'total': 0.0}

    barbeiros = {
        b.id: b for b in Barbeiro.query.filter_by(barbearia_id=g.barbearia_id).all()
    }
    usuarios = {
        u.id: u for u in Usuario.query.filter(Usuario.id.in_(
            {b.usuario_id for b in barbeiros.values()}
        )).all()
    } if barbeiros else {}

    por_barbeiro = {
        bid: {
            'barbeiro_id': bid,
            'nome': usuarios.get(b.usuario_id).nome if usuarios.get(b.usuario_id) else '—',
            'produtos': _zero(),
            'atendimentos': _zero(),
        }
        for bid, b in barbeiros.items()
    }

    # ── Produtos (ItemCaixa) ──────────────────────────────────────────────────
    itens_caixa = (
        db.session.query(ItemCaixa, BarbeiroCaixa.barbeiro_id)
        .join(BarbeiroCaixa, ItemCaixa.caixa_id == BarbeiroCaixa.id)
        .filter(
            ItemCaixa.barbearia_id == g.barbearia_id,
            BarbeiroCaixa.data >= de,
            BarbeiroCaixa.data <= ate,
        )
        .all()
    )
    for item, bid in itens_caixa:
        alvo = por_barbeiro.get(bid)
        if not alvo or item.forma_pagamento not in alvo['produtos']:
            continue
        alvo['produtos'][item.forma_pagamento] += item.total
        alvo['produtos']['total'] += item.total

    # ── Atendimentos recebidos no local (Agendamento) ────────────────────────
    ags_pagos = Agendamento.query.filter(
        Agendamento.barbearia_id == g.barbearia_id,
        Agendamento.status_pagamento == StatusPagamento.PAGO,
        Agendamento.forma_pagamento_recebido.isnot(None),
        db.func.date(Agendamento.data_hora) >= de,
        db.func.date(Agendamento.data_hora) <= ate,
    ).all()
    for ag in ags_pagos:
        alvo = por_barbeiro.get(ag.barbeiro_id)
        if not alvo or ag.forma_pagamento_recebido not in alvo['atendimentos']:
            continue
        valor = float(ag.valor_total)
        alvo['atendimentos'][ag.forma_pagamento_recebido] += valor
        alvo['atendimentos']['total'] += valor

    consolidado_produtos = _zero()
    consolidado_atendimentos = _zero()
    for v in por_barbeiro.values():
        for k in consolidado_produtos:
            consolidado_produtos[k] += v['produtos'][k]
            consolidado_atendimentos[k] += v['atendimentos'][k]

    por_forma_geral = {
        forma: round(consolidado_produtos[forma] + consolidado_atendimentos[forma], 2)
        for forma in ('dinheiro', 'cartao', 'pix')
    }

    # Origem local/online: todo produto vendido pela caixa é presencial;
    # atendimento pago em 'pix' aqui é o recebido NO LOCAL via pix do
    # barbeiro (forma_pagamento_recebido), não o pix pago online antes —
    # esse já vem como 'pago' automaticamente e não passa por aqui.
    resultado = {
        'periodo': f'{de.isoformat()} a {ate.isoformat()}',
        'por_barbeiro': sorted(
            [v for v in por_barbeiro.values() if v['produtos']['total'] or v['atendimentos']['total']],
            key=lambda x: x['produtos']['total'] + x['atendimentos']['total'], reverse=True,
        ),
        'consolidado': {
            'produtos':     {k: round(v, 2) for k, v in consolidado_produtos.items()},
            'atendimentos': {k: round(v, 2) for k, v in consolidado_atendimentos.items()},
            'por_forma_pagamento': por_forma_geral,
            'total_geral': round(sum(por_forma_geral.values()), 2),
        },
    }
    return jsonify(resultado), 200
