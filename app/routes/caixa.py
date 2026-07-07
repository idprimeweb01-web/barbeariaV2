from datetime import datetime, timedelta, time as Time
from flask import Blueprint, request, jsonify, g
from app import db
from app.models import (
    Usuario, Barbeiro, Agendamento, AgendamentoServico, Atendimento, AtendimentoItem,
    Servico, Produto, Pagamento, Cliente, ReservaProduto,
)
from app.decorators.auth import barbeiro_required
from app.utils.db import commit_ou_falhar
from app.utils import estoque as estoque_service
from app.constants import StatusAgendamento, TipoMovimentacaoEstoque

caixa = Blueprint('caixa', __name__)


def _erro(msg, code=400):
    return jsonify({'erro': msg}), code


def _barbeiro_do_usuario(usuario_id, barbearia_id):
    return Barbeiro.query.filter_by(
        usuario_id=usuario_id, ativo=True, barbearia_id=barbearia_id
    ).first()


def _at_id_do_ag(agendamento_id, barbearia_id):
    at = Atendimento.query.filter_by(agendamento_id=agendamento_id, barbearia_id=barbearia_id).first()
    return at.id if at else None


def _pode_acessar(usuario, barbeiro, atendimento_barbeiro_id):
    if usuario.perfil in ('gestor', 'super_admin'):
        return True
    return barbeiro and atendimento_barbeiro_id == barbeiro.id


def _fmt_item(item):
    d = {
        'id': item.id, 'tipo': item.tipo,
        'quantidade': item.quantidade, 'preco_unitario': float(item.preco_unitario),
        'subtotal': round(float(item.preco_unitario) * item.quantidade, 2),
    }
    if item.tipo == 'servico' and item.servico_id:
        s = db.session.get(Servico, item.servico_id)
        d['servico_id'] = item.servico_id
        d['nome'] = s.nome if s else None
    elif item.tipo == 'produto' and item.produto_id:
        p = db.session.get(Produto, item.produto_id)
        d['produto_id'] = item.produto_id
        d['nome'] = p.nome if p else None
    return d


def _fmt_atendimento(at, itens):
    total_calc = round(sum(float(i.preco_unitario) * i.quantidade for i in itens), 2)
    return {
        'id':              at.id,
        'agendamento_id':  at.agendamento_id,
        'barbeiro_id':     at.barbeiro_id,
        'cliente_id':      at.cliente_id,
        'status_operacao': at.status_operacao,
        'total':           float(at.total) if at.total is not None else total_calc,
        'criado_em':       at.criado_em.isoformat() if at.criado_em else None,
        'itens':           [_fmt_item(i) for i in itens],
    }


# ── POST /atendimentos ─────────────────────────────────────────────────────────

@caixa.post('/atendimentos')
@barbeiro_required
def abrir_atendimento():
    uid          = g.user_id
    barbearia_id = g.barbearia_id
    usuario      = db.session.get(Usuario, uid)
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)

    dados = request.get_json(silent=True)
    if not dados:
        return _erro('Corpo da requisição inválido ou ausente.')

    agendamento_id = dados.get('agendamento_id')
    if not agendamento_id:
        return _erro('O campo "agendamento_id" é obrigatório.')

    ag = Agendamento.query.filter_by(id=agendamento_id, barbearia_id=barbearia_id).first()
    if not ag:
        return _erro('Agendamento não encontrado.', 404)
    if not _pode_acessar(usuario, barbeiro, ag.barbeiro_id):
        return _erro('Você não tem permissão para este agendamento.', 403)
    if ag.status != StatusAgendamento.AGENDADO:
        return _erro(f'Não é possível abrir atendimento para agendamento com status "{ag.status}".')
    if Atendimento.query.filter_by(agendamento_id=agendamento_id).first():
        return _erro('Já existe um atendimento para este agendamento.', 409)

    at = Atendimento(
        barbearia_id=barbearia_id,
        agendamento_id=agendamento_id,
        barbeiro_id=ag.barbeiro_id,
        cliente_id=ag.cliente_id,
        status_operacao='nao_efetuado',
    )
    db.session.add(at)
    db.session.flush()

    # Bug pré-existente corrigido (Script 18): Agendamento não tem mais
    # `servico_id` desde a v2 — os serviços agora vêm de AgendamentoServico
    # (pode ser mais de um por agendamento). Código morto nunca atualizado
    # pra esse schema; sem esta correção, abrir_atendimento nunca funcionaria.
    itens_ag = AgendamentoServico.query.filter_by(agendamento_id=ag.id).all()
    for item_ag in itens_ag:
        servico = db.session.get(Servico, item_ag.servico_id)
        if servico:
            db.session.add(AtendimentoItem(
                atendimento_id=at.id, tipo='servico',
                servico_id=servico.id, preco_unitario=item_ag.preco_unitario, quantidade=item_ag.quantidade,
            ))

    commit_ou_falhar('caixa.abrir_atendimento')
    itens = AtendimentoItem.query.filter_by(atendimento_id=at.id).all()
    return jsonify({'mensagem': 'Atendimento aberto com sucesso.', 'atendimento': _fmt_atendimento(at, itens)}), 201


# ── POST /atendimentos/<id>/itens ──────────────────────────────────────────────

@caixa.post('/atendimentos/<int:atendimento_id>/itens')
@barbeiro_required
def adicionar_item(atendimento_id):
    uid          = g.user_id
    barbearia_id = g.barbearia_id
    usuario      = db.session.get(Usuario, uid)
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)

    at = Atendimento.query.filter_by(id=atendimento_id, barbearia_id=barbearia_id).first()
    if not at:
        return _erro('Atendimento não encontrado.', 404)
    if not _pode_acessar(usuario, barbeiro, at.barbeiro_id):
        return _erro('Você não tem permissão para este atendimento.', 403)
    if at.status_operacao == 'efetuado':
        return _erro('Não é possível adicionar itens a um atendimento já efetuado.')

    dados = request.get_json(silent=True)
    if not dados:
        return _erro('Corpo da requisição inválido ou ausente.')

    tipo       = (dados.get('tipo') or '').strip().lower()
    quantidade = dados.get('quantidade', 1)

    if tipo not in ('servico', 'produto'):
        return _erro('O campo "tipo" deve ser "servico" ou "produto".')
    if not isinstance(quantidade, int) or quantidade < 1:
        return _erro('"quantidade" deve ser um inteiro maior que 0.')

    if tipo == 'servico':
        sid = dados.get('servico_id')
        if not sid:
            return _erro('O campo "servico_id" é obrigatório para tipo "servico".')
        servico = Servico.query.filter_by(id=sid, barbearia_id=barbearia_id, ativo=True).first()
        if not servico:
            return _erro('Serviço não encontrado ou inativo.', 404)
        item = AtendimentoItem(
            atendimento_id=atendimento_id, tipo='servico',
            servico_id=sid, preco_unitario=servico.preco, quantidade=quantidade,
        )
    else:
        pid = dados.get('produto_id')
        if not pid:
            return _erro('O campo "produto_id" é obrigatório para tipo "produto".')
        produto = Produto.query.filter_by(id=pid, barbearia_id=barbearia_id, ativo=True).first()
        if not produto:
            return _erro('Produto não encontrado ou inativo.', 404)
        if produto.quantidade_disponivel < quantidade:
            return _erro(f'Estoque insuficiente. Disponível: {produto.quantidade_disponivel} unidade(s).')
        item = AtendimentoItem(
            atendimento_id=atendimento_id, tipo='produto',
            produto_id=pid, preco_unitario=produto.preco, quantidade=quantidade,
        )

    db.session.add(item)
    commit_ou_falhar('caixa.adicionar_item')
    return jsonify({'mensagem': 'Item adicionado com sucesso.', 'item': _fmt_item(item)}), 201


# ── DELETE /atendimentos/<id>/itens/<item_id> ──────────────────────────────────

@caixa.delete('/atendimentos/<int:atendimento_id>/itens/<int:item_id>')
@barbeiro_required
def remover_item(atendimento_id, item_id):
    uid          = g.user_id
    barbearia_id = g.barbearia_id
    usuario      = db.session.get(Usuario, uid)
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)

    at = Atendimento.query.filter_by(id=atendimento_id, barbearia_id=barbearia_id).first()
    if not at:
        return _erro('Atendimento não encontrado.', 404)
    if not _pode_acessar(usuario, barbeiro, at.barbeiro_id):
        return _erro('Você não tem permissão para este atendimento.', 403)
    if at.status_operacao == 'efetuado':
        return _erro('Não é possível remover itens de um atendimento já efetuado.')

    item = db.session.get(AtendimentoItem, item_id)
    if not item or item.atendimento_id != atendimento_id:
        return _erro('Item não encontrado.', 404)

    db.session.delete(item)
    commit_ou_falhar('caixa.remover_item')
    return jsonify({'mensagem': 'Item removido com sucesso.', 'id': item_id})


# ── GET /atendimentos/<id> ─────────────────────────────────────────────────────

@caixa.get('/atendimentos/<int:atendimento_id>')
@barbeiro_required
def ver_atendimento(atendimento_id):
    uid          = g.user_id
    barbearia_id = g.barbearia_id
    usuario      = db.session.get(Usuario, uid)
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)

    at = Atendimento.query.filter_by(id=atendimento_id, barbearia_id=barbearia_id).first()
    if not at:
        return _erro('Atendimento não encontrado.', 404)
    if not _pode_acessar(usuario, barbeiro, at.barbeiro_id):
        return _erro('Você não tem permissão para este atendimento.', 403)

    itens = AtendimentoItem.query.filter_by(atendimento_id=atendimento_id).all()
    return jsonify(_fmt_atendimento(at, itens))


# ── PUT /atendimentos/<id>/efetuar ─────────────────────────────────────────────

@caixa.put('/atendimentos/<int:atendimento_id>/efetuar')
@barbeiro_required
def efetuar_atendimento(atendimento_id):
    uid          = g.user_id
    barbearia_id = g.barbearia_id
    usuario      = db.session.get(Usuario, uid)
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)

    at = Atendimento.query.filter_by(id=atendimento_id, barbearia_id=barbearia_id).first()
    if not at:
        return _erro('Atendimento não encontrado.', 404)
    if not _pode_acessar(usuario, barbeiro, at.barbeiro_id):
        return _erro('Você não tem permissão para este atendimento.', 403)
    if at.status_operacao == 'efetuado':
        return _erro('Este atendimento já foi efetuado.')

    dados = request.get_json(silent=True)
    if not dados:
        return _erro('Corpo da requisição inválido ou ausente.')

    formas_validas = {'pix', 'dinheiro', 'credito', 'debito'}
    forma = (dados.get('forma_pagamento') or '').strip().lower()
    if not forma:
        return _erro('O campo "forma_pagamento" é obrigatório.')
    if forma not in formas_validas:
        return _erro(f'Forma de pagamento inválida. Use: {", ".join(sorted(formas_validas))}.')

    itens = AtendimentoItem.query.filter_by(atendimento_id=atendimento_id).all()
    if not itens:
        return _erro('Não é possível efetuar um atendimento sem itens.')

    total  = round(sum(float(i.preco_unitario) * i.quantidade for i in itens), 2)
    avisos = []

    # Abate estoque dos itens vendidos — via serviço central (Script 18):
    # UPDATE atômico com guard (mesmo padrão de incrementar_uso_cupom), grava
    # MovimentacaoEstoque pra auditoria. Diferença de comportamento
    # INTENCIONAL vs. antes: se o estoque não for suficiente, agora levanta
    # 422 em vez de silenciosamente zerar (produto.quantidade_estoque =
    # max(0, ...)) — evita estoque negativo mascarado.
    for item in itens:
        if item.tipo == 'produto' and item.produto_id:
            produto = estoque_service.registrar_saida(
                item.produto_id, barbearia_id, item.quantidade, uid,
                motivo=f'Atendimento #{atendimento_id}',
                tipo=TipoMovimentacaoEstoque.SAIDA_USO,
                referencia_atendimento_id=atendimento_id,
            )
            if produto.quantidade_estoque == 0:
                produto.ativo = False
                avisos.append(f'Produto "{produto.nome}" zerou o estoque e foi desativado.')

    at.status_operacao = 'efetuado'
    at.total = total

    ag = db.session.get(Agendamento, at.agendamento_id)
    if ag:
        ag.status = StatusAgendamento.CONCLUIDO
        # Confirma reservas e abate estoque dos produtos reservados
        reservas = ReservaProduto.query.filter_by(
            agendamento_id=ag.id, status='reservado'
        ).all()
        for reserva in reservas:
            reserva.status = 'confirmado'
            produto_res = db.session.get(Produto, reserva.produto_id)
            if produto_res:
                produto_res.quantidade_reservada = max(0, (produto_res.quantidade_reservada or 0) - reserva.quantidade)
                produto_res = estoque_service.registrar_saida(
                    produto_res.id, barbearia_id, reserva.quantidade, uid,
                    motivo=f'Reserva confirmada — atendimento #{atendimento_id}',
                    tipo=TipoMovimentacaoEstoque.SAIDA_USO,
                    referencia_atendimento_id=atendimento_id,
                )
                if produto_res.quantidade_estoque == 0:
                    produto_res.ativo = False
                    avisos.append(f'Produto "{produto_res.nome}" zerou o estoque e foi desativado.')

    pagamento = Pagamento(
        atendimento_id=atendimento_id, forma_pagamento=forma, valor=total, status='aprovado',
    )
    db.session.add(pagamento)
    commit_ou_falhar('caixa.efetuar_atendimento')

    resp = {
        'mensagem':    'Atendimento efetuado com sucesso.',
        'atendimento': _fmt_atendimento(at, itens),
        'pagamento': {
            'id': pagamento.id, 'forma_pagamento': pagamento.forma_pagamento,
            'valor': float(pagamento.valor), 'status': pagamento.status,
        },
    }
    if avisos:
        resp['avisos'] = avisos
    return jsonify(resp)


# ── GET /atendimentos?data=YYYY-MM-DD ─────────────────────────────────────────

@caixa.get('/atendimentos')
@barbeiro_required
def listar_atendimentos():
    uid          = g.user_id
    barbearia_id = g.barbearia_id
    usuario      = db.session.get(Usuario, uid)
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)

    if usuario.perfil not in ('gestor', 'super_admin') and not barbeiro:
        return _erro('Perfil de barbeiro não encontrado.', 404)

    data_str = request.args.get('data', '').strip()
    if not data_str:
        return _erro('Parâmetro "data" é obrigatório (formato: YYYY-MM-DD).')
    try:
        data_dt = datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        return _erro('Formato de data inválido. Use YYYY-MM-DD.')

    inicio = datetime.combine(data_dt, Time(0, 0))
    fim    = inicio + timedelta(days=1)

    query = Atendimento.query.filter(
        Atendimento.barbearia_id == barbearia_id,
        Atendimento.criado_em    >= inicio,
        Atendimento.criado_em    < fim,
    )
    if usuario.perfil not in ('gestor', 'super_admin'):
        query = query.filter(Atendimento.barbeiro_id == barbeiro.id)

    atendimentos = query.order_by(Atendimento.criado_em).all()
    resultado = []
    for at in atendimentos:
        itens = AtendimentoItem.query.filter_by(atendimento_id=at.id).all()
        d = _fmt_atendimento(at, itens)
        cliente = db.session.get(Cliente, at.cliente_id) if at.cliente_id else None
        if cliente:
            d['cliente'] = {'id': cliente.id, 'nome': cliente.nome, 'telefone': cliente.telefone}
        resultado.append(d)

    return jsonify(resultado)


# ── POST /agendamentos/<id>/iniciar ───────────────────────────────────────────

@caixa.post('/agendamentos/<int:agendamento_id>/iniciar')
@barbeiro_required
def iniciar_atendimento(agendamento_id):
    uid          = g.user_id
    barbearia_id = g.barbearia_id
    usuario      = db.session.get(Usuario, uid)
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)

    ag = Agendamento.query.filter_by(id=agendamento_id, barbearia_id=barbearia_id).first()
    if not ag:
        return _erro('Agendamento não encontrado.', 404)
    if not _pode_acessar(usuario, barbeiro, ag.barbeiro_id):
        return _erro('Sem permissão para este agendamento.', 403)
    if ag.status not in (StatusAgendamento.AGENDADO,):
        return _erro(f'Agendamento com status "{ag.status}" não pode ser iniciado.')

    # Idempotente: se já existe atendimento, retorna
    at = Atendimento.query.filter_by(agendamento_id=agendamento_id).first()
    if at:
        itens = AtendimentoItem.query.filter_by(atendimento_id=at.id).all()
        return jsonify({'mensagem': 'Atendimento já iniciado.', 'atendimento': _fmt_atendimento(at, itens)})

    at = Atendimento(
        barbearia_id=barbearia_id,
        agendamento_id=agendamento_id,
        barbeiro_id=ag.barbeiro_id,
        cliente_id=ag.cliente_id,
        status_operacao='nao_efetuado',
    )
    db.session.add(at)
    db.session.flush()

    # Adiciona TODOS os serviços do agendamento (AgendamentoServico)
    ag_svs = AgendamentoServico.query.filter_by(agendamento_id=agendamento_id).all()
    if ag_svs:
        for ag_sv in ag_svs:
            db.session.add(AtendimentoItem(
                atendimento_id=at.id, tipo='servico',
                servico_id=ag_sv.servico_id,
                preco_unitario=ag_sv.preco_unitario,
                quantidade=ag_sv.quantidade,
            ))
    else:
        # Fallback: agendamentos criados antes do multi-serviço
        servico = db.session.get(Servico, ag.servico_id)
        if servico:
            db.session.add(AtendimentoItem(
                atendimento_id=at.id, tipo='servico',
                servico_id=servico.id, preco_unitario=servico.preco, quantidade=1,
            ))

    commit_ou_falhar('caixa.iniciar_atendimento')
    itens = AtendimentoItem.query.filter_by(atendimento_id=at.id).all()
    return jsonify({'mensagem': 'Atendimento iniciado.', 'atendimento': _fmt_atendimento(at, itens)}), 201


# ── GET /caixa/agendamento/<id> ───────────────────────────────────────────────

@caixa.get('/caixa/agendamento/<int:agendamento_id>')
@barbeiro_required
def dados_caixa(agendamento_id):
    uid          = g.user_id
    barbearia_id = g.barbearia_id
    usuario      = db.session.get(Usuario, uid)
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)

    ag = Agendamento.query.filter_by(id=agendamento_id, barbearia_id=barbearia_id).first()
    if not ag:
        return _erro('Agendamento não encontrado.', 404)
    if not _pode_acessar(usuario, barbeiro, ag.barbeiro_id):
        return _erro('Sem permissão.', 403)

    cliente = db.session.get(Cliente, ag.cliente_id)
    at      = Atendimento.query.filter_by(agendamento_id=agendamento_id).first()
    itens   = AtendimentoItem.query.filter_by(atendimento_id=at.id).all() if at else []

    # Todos os serviços agendados (AgendamentoServico)
    ag_svs = AgendamentoServico.query.filter_by(agendamento_id=agendamento_id).all()
    servicos_fmt = []
    for ag_sv in ag_svs:
        sv = db.session.get(Servico, ag_sv.servico_id)
        servicos_fmt.append({
            'nome':           sv.nome if sv else '—',
            'quantidade':     ag_sv.quantidade,
            'preco_unitario': float(ag_sv.preco_unitario),
            'subtotal':       round(float(ag_sv.preco_unitario) * ag_sv.quantidade, 2),
        })
    if not servicos_fmt and ag.servico_id:
        sv = db.session.get(Servico, ag.servico_id)
        if sv:
            servicos_fmt = [{'nome': sv.nome, 'quantidade': 1,
                             'preco_unitario': float(sv.preco), 'subtotal': float(sv.preco)}]

    # Produtos reservados no agendamento (ReservaProduto, status != cancelado)
    reservas = ReservaProduto.query.filter(
        ReservaProduto.agendamento_id == agendamento_id,
        ReservaProduto.status != 'cancelado',
    ).all()
    produtos_reservados_fmt = []
    for rp in reservas:
        pd = db.session.get(Produto, rp.produto_id)
        preco = float(pd.preco) if pd else 0.0
        produtos_reservados_fmt.append({
            'reserva_id':     rp.id,
            'produto_id':     rp.produto_id,
            'nome':           pd.nome if pd else '—',
            'quantidade':     rp.quantidade,
            'preco_unitario': preco,
            'subtotal':       round(preco * rp.quantidade, 2),
            'status':         rp.status,
        })

    return jsonify({
        'agendamento': {
            'id':              ag.id,
            'data_hora':       ag.data_hora.isoformat(),
            'duracao_minutos': ag.duracao_minutos,
            'status':          ag.status,
            'observacao':      ag.observacao,
        },
        'cliente': {
            'id':       cliente.id       if cliente else None,
            'nome':     cliente.nome     if cliente else '—',
            'telefone': cliente.telefone if cliente else '—',
            'foto':     cliente.foto     if cliente else None,
        },
        'servicos':            servicos_fmt,
        'produtos_reservados': produtos_reservados_fmt,
        'atendimento':         _fmt_atendimento(at, itens) if at else None,
    })
