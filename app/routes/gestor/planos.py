from flask import Blueprint, request, g, jsonify
from app.extensions import db
from app.models import (
    Plano, PlanoServico, Servico, ClientePlano, ClientePlanoSolicitacao,
    ClientePlanoUso, Barbearia, Cliente, Barbeiro,
)
from app.exceptions import APIError
from app.decorators.auth import gestor_required
from app.utils.planos import PLANO_LIMITE_ILIMITADO, limite_para_fora
from app.utils.tz import hoje_brasilia, naive_brasilia
from app.labels import L

planos_bp = Blueprint('gestor_planos', __name__, url_prefix='/api/v1/gestor')


def _fmt_plano(p, com_servicos=False):
    d = {
        'id':            p.id,
        'barbearia_id':  p.barbearia_id,
        'nome':          p.nome,
        'descricao':     p.descricao,
        'preco_mensal':  float(p.preco_mensal),
        'barbeiro_id':   p.barbeiro_id,
        'is_plano_aberto': p.barbeiro_id is None,
        'ativo':         p.ativo,
        'criado_em':     p.criado_em.isoformat() if p.criado_em else None,
    }
    if com_servicos:
        servicos = PlanoServico.query.filter_by(plano_id=p.id).all()
        d['servicos'] = [
            {
                'servico_id':       ps.servico_id,
                'nome':             (db.session.get(Servico, ps.servico_id) or {}).nome if db.session.get(Servico, ps.servico_id) else None,
                'limite_uso_mensal': limite_para_fora(ps.limite_uso_mensal),
                'ilimitado':        ps.limite_uso_mensal == PLANO_LIMITE_ILIMITADO,
                'dias_expiracao':   ps.dias_expiracao,
                'ativo':            ps.ativo,
            }
            for ps in servicos
        ]
    return d


def _get_plano_ou_404(plano_id, barbearia_id):
    p = Plano.query.filter_by(id=plano_id, barbearia_id=barbearia_id).first()
    if not p:
        raise APIError(f'{L("plano")} não encontrado.', 404)
    return p


# ── GET /api/v1/gestor/planos ─────────────────────────────────────────────────

@planos_bp.get('/planos')
@gestor_required
def listar_planos():
    q = Plano.query.filter_by(barbearia_id=g.barbearia_id)
    ativo = request.args.get('ativo')
    if ativo == 'true':
        q = q.filter_by(ativo=True)
    elif ativo == 'false':
        q = q.filter_by(ativo=False)
    return jsonify([_fmt_plano(p, com_servicos=True) for p in q.order_by(Plano.nome).all()]), 200


# ── POST /api/v1/gestor/planos ────────────────────────────────────────────────

@planos_bp.post('/planos')
@gestor_required
def criar_plano():
    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    nome = (dados.get('nome') or '').strip()
    if not nome:
        raise APIError('"nome" é obrigatório.')

    preco = dados.get('preco_mensal')
    try:
        preco = float(preco)
        assert preco >= 0
    except (TypeError, ValueError, AssertionError):
        raise APIError('"preco_mensal" deve ser um número não-negativo.')

    barbeiro_id = dados.get('barbeiro_id')  # null = plano aberto
    if barbeiro_id is not None:
        br = Barbeiro.query.filter_by(id=barbeiro_id, barbearia_id=g.barbearia_id, ativo=True).first()
        if not br:
            raise APIError(f'{L("profissional")} id={barbeiro_id} não encontrado.', 404)

    p = Plano(
        barbearia_id=g.barbearia_id,
        nome=nome,
        descricao=(dados.get('descricao') or '').strip() or None,
        preco_mensal=preco,
        barbeiro_id=barbeiro_id,
        ativo=True,
    )
    db.session.add(p)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise APIError(f'Erro ao salvar {L("plano").lower()}. Tente novamente.', 500)
    return jsonify(_fmt_plano(p, com_servicos=True)), 201


# ── GET /api/v1/gestor/planos/<id> ───────────────────────────────────────────

@planos_bp.get('/planos/<int:plano_id>')
@gestor_required
def detalhar_plano(plano_id):
    p = _get_plano_ou_404(plano_id, g.barbearia_id)
    return jsonify(_fmt_plano(p, com_servicos=True)), 200


# ── PATCH /api/v1/gestor/planos/<id> ─────────────────────────────────────────

@planos_bp.patch('/planos/<int:plano_id>')
@gestor_required
def editar_plano(plano_id):
    p = _get_plano_ou_404(plano_id, g.barbearia_id)
    dados = request.get_json(silent=True) or {}

    if 'nome' in dados:
        nome = (dados['nome'] or '').strip()
        if not nome:
            raise APIError('"nome" não pode ser vazio.')
        p.nome = nome
    if 'descricao' in dados:
        p.descricao = (dados['descricao'] or '').strip() or None
    if 'preco_mensal' in dados:
        try:
            p.preco_mensal = float(dados['preco_mensal'])
            assert p.preco_mensal >= 0
        except (TypeError, ValueError, AssertionError):
            raise APIError('"preco_mensal" inválido.')
    if 'ativo' in dados:
        p.ativo = bool(dados['ativo'])

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise APIError(f'Erro ao salvar {L("plano").lower()}. Tente novamente.', 500)
    return jsonify(_fmt_plano(p, com_servicos=True)), 200


# ── DELETE /api/v1/gestor/planos/<id> (soft delete) ──────────────────────────

@planos_bp.delete('/planos/<int:plano_id>')
@gestor_required
def desativar_plano(plano_id):
    p = _get_plano_ou_404(plano_id, g.barbearia_id)
    p.ativo = False
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise APIError(f'Erro ao desativar {L("plano").lower()}. Tente novamente.', 500)
    return jsonify({'mensagem': f'{L("plano")} desativado.', 'id': plano_id}), 200


# ── POST /api/v1/gestor/planos/<id>/servicos ─────────────────────────────────

@planos_bp.post('/planos/<int:plano_id>/servicos')
@gestor_required
def adicionar_servico_plano(plano_id):
    p = _get_plano_ou_404(plano_id, g.barbearia_id)
    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    servico_id = dados.get('servico_id')
    if not isinstance(servico_id, int):
        raise APIError('"servico_id" é obrigatório.')

    s = Servico.query.filter_by(id=servico_id, barbearia_id=g.barbearia_id, ativo=True).first()
    if not s:
        raise APIError(f'{L("servico")} não encontrado ou inativo.', 404)

    existente = PlanoServico.query.filter_by(plano_id=plano_id, servico_id=servico_id).first()
    if existente:
        raise APIError(f'{L("servico")} já está incluído neste {L("plano").lower()}.', 409)

    limite_raw = dados.get('limite_uso_mensal')
    if limite_raw is None or str(limite_raw).lower() in ('ilimitado', 'null', ''):
        limite = PLANO_LIMITE_ILIMITADO
    else:
        try:
            limite = int(limite_raw)
            assert limite > 0
        except (ValueError, AssertionError):
            raise APIError('"limite_uso_mensal" deve ser um inteiro positivo ou null (ilimitado).')

    dias = dados.get('dias_expiracao', 30)
    if not isinstance(dias, int) or dias <= 0:
        raise APIError('"dias_expiracao" deve ser um inteiro positivo.')

    ps = PlanoServico(
        plano_id=plano_id, servico_id=servico_id,
        limite_uso_mensal=limite,
        dias_expiracao=dias, ativo=True,
    )
    db.session.add(ps)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise APIError(f'Erro ao salvar {L("servico").lower()} do {L("plano").lower()}. Tente novamente.', 500)

    return jsonify({
        'mensagem': f'{L("servico")} adicionado ao {L("plano").lower()}.',
        'servico_id': servico_id,
        'nome': s.nome,
        'limite_uso_mensal': limite_para_fora(limite),
        'ilimitado': limite == PLANO_LIMITE_ILIMITADO,
    }), 201


# ── DELETE /api/v1/gestor/planos/<id>/servicos/<sid> ─────────────────────────

@planos_bp.delete('/planos/<int:plano_id>/servicos/<int:servico_id>')
@gestor_required
def remover_servico_plano(plano_id, servico_id):
    _get_plano_ou_404(plano_id, g.barbearia_id)
    ps = PlanoServico.query.filter_by(plano_id=plano_id, servico_id=servico_id).first()
    if not ps:
        raise APIError(f'{L("servico")} não encontrado neste {L("plano").lower()}.', 404)
    db.session.delete(ps)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise APIError(f'Erro ao remover {L("servico").lower()} do {L("plano").lower()}. Tente novamente.', 500)
    return jsonify({'mensagem': f'{L("servico")} removido do {L("plano").lower()}.'}), 200


# ── GET /api/v1/gestor/planos/<id>/assinaturas ────────────────────────────────

@planos_bp.get('/planos/<int:plano_id>/assinaturas')
@gestor_required
def listar_assinaturas(plano_id):
    _get_plano_ou_404(plano_id, g.barbearia_id)
    assinaturas = ClientePlano.query.filter_by(plano_id=plano_id, barbearia_id=g.barbearia_id).all()
    resultado = []
    for cp in assinaturas:
        cli = db.session.get(Cliente, cp.cliente_id)
        resultado.append({
            'id':          cp.id,
            'cliente':     {'id': cli.id, 'nome': cli.nome, 'telefone': cli.telefone} if cli else None,
            'data_inicio': cp.data_inicio.isoformat() if cp.data_inicio else None,
            'data_fim':    cp.data_fim.isoformat() if cp.data_fim else None,
            'barbeiro_id': cp.barbeiro_id,
            'ativo':       cp.ativo,
        })
    return jsonify(resultado), 200


# ── GET /api/v1/gestor/planos/solicitacoes ────────────────────────────────────

@planos_bp.get('/planos/solicitacoes')
@gestor_required
def listar_solicitacoes():
    q = ClientePlanoSolicitacao.query.filter_by(barbearia_id=g.barbearia_id)
    status_f = request.args.get('status', 'pendente')
    if status_f:
        q = q.filter_by(status=status_f)
    solic = q.order_by(ClientePlanoSolicitacao.criado_em.desc()).all()
    return jsonify([_fmt_solicitacao(s) for s in solic]), 200


def _fmt_solicitacao(s):
    cli = db.session.get(Cliente, s.cliente_id)
    p = db.session.get(Plano, s.plano_id)
    return {
        'id':               s.id,
        'status':           s.status,
        'valor':            float(s.valor),
        'metodo_pagamento': s.metodo_pagamento,
        'criado_em':        s.criado_em.isoformat() if s.criado_em else None,
        'aprovado_em':      s.aprovado_em.isoformat() if s.aprovado_em else None,
        'motivo_rejeicao':  s.motivo_rejeicao,
        'cliente':          {'id': cli.id, 'nome': cli.nome} if cli else None,
        'plano':            {'id': p.id, 'nome': p.nome} if p else None,
        'barbeiro_id':      s.barbeiro_id,
    }


# ── PUT /api/v1/gestor/planos/solicitacoes/<id>/aprovar ──────────────────────
# PIX de plano NUNCA ativa automaticamente — exige aprovação do gestor.

@planos_bp.put('/planos/solicitacoes/<int:sol_id>/aprovar')
@gestor_required
def aprovar_solicitacao(sol_id):
    sol = ClientePlanoSolicitacao.query.filter_by(
        id=sol_id, barbearia_id=g.barbearia_id
    ).first()
    if not sol:
        raise APIError('Solicitação não encontrada.', 404)
    if sol.status != 'pendente':
        raise APIError(f'Solicitação já foi {sol.status}.')

    p = db.session.get(Plano, sol.plano_id)
    if not p or not p.ativo:
        raise APIError(f'{L("plano")} não está mais ativo.', 422)

    hoje = hoje_brasilia()
    data_fim = None
    # Calcula data_fim como hoje + dias_expiracao do primeiro PlanoServico, ou 30 dias
    ps = PlanoServico.query.filter_by(plano_id=sol.plano_id, ativo=True).first()
    if ps:
        from datetime import timedelta
        data_fim = hoje + timedelta(days=ps.dias_expiracao)

    cp = ClientePlano(
        barbearia_id=g.barbearia_id,
        cliente_id=sol.cliente_id,
        plano_id=sol.plano_id,
        barbeiro_id=sol.barbeiro_id,
        data_inicio=hoje,
        data_fim=data_fim,
        ativo=True,
    )
    db.session.add(cp)

    sol.status = 'aprovado'
    sol.aprovado_em = naive_brasilia()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise APIError('Erro ao aprovar solicitação. Tente novamente.', 500)

    return jsonify({
        'mensagem': f'{L("plano")} ativado para o cliente.',
        'cliente_plano_id': cp.id,
        'data_inicio': hoje.isoformat(),
        'data_fim': data_fim.isoformat() if data_fim else None,
    }), 200


# ── PUT /api/v1/gestor/planos/solicitacoes/<id>/rejeitar ─────────────────────

@planos_bp.put('/planos/solicitacoes/<int:sol_id>/rejeitar')
@gestor_required
def rejeitar_solicitacao(sol_id):
    sol = ClientePlanoSolicitacao.query.filter_by(
        id=sol_id, barbearia_id=g.barbearia_id
    ).first()
    if not sol:
        raise APIError('Solicitação não encontrada.', 404)
    if sol.status != 'pendente':
        raise APIError(f'Solicitação já foi {sol.status}.')

    dados = request.get_json(silent=True) or {}
    sol.status = 'rejeitado'
    sol.motivo_rejeicao = (dados.get('motivo') or '').strip() or 'Rejeitado pelo gestor.'
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise APIError('Erro ao rejeitar solicitação. Tente novamente.', 500)

    return jsonify({'mensagem': 'Solicitação rejeitada.', 'id': sol_id}), 200
