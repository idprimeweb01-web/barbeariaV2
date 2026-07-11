from flask import Blueprint, request, g, jsonify
from app.extensions import db
from app.models import (
    Plano, PlanoServico, Servico, ClientePlano,
    ClientePlanoSolicitacao, ClientePlanoUso, Cliente,
)
from app.exceptions import APIError
from app.decorators.auth import cliente_required
from app.utils.planos import PLANO_LIMITE_ILIMITADO, limite_para_fora
from app.utils.tz import hoje_brasilia
from app.utils.db import commit_ou_falhar
from app.labels import L

cliente_planos_bp = Blueprint('cliente_planos', __name__, url_prefix='/api/v1/cliente')


def _get_cliente_ou_404(user_id, barbearia_id):
    """Retorna o Cliente do usuário autenticado nesta barbearia."""
    from app.models import Usuario
    usr = db.session.get(Usuario, user_id)
    if not usr:
        raise APIError('Usuário não encontrado.', 404)
    cli = Cliente.query.filter_by(barbearia_id=barbearia_id, usuario_id=usr.id).first()
    if not cli:
        raise APIError('Perfil de cliente não encontrado nesta barbearia.', 404)
    return cli


def _uso_mes_atual(cliente_plano_id, servico_id):
    hoje = hoje_brasilia()
    return ClientePlanoUso.query.filter(
        ClientePlanoUso.cliente_plano_id == cliente_plano_id,
        ClientePlanoUso.servico_id == servico_id,
        db.extract('year',  ClientePlanoUso.data_uso) == hoje.year,
        db.extract('month', ClientePlanoUso.data_uso) == hoje.month,
    ).count()


def _fmt_assinatura(cp, planos=None, servicos_por_plano=None, servicos_map=None, usos=None):
    """
    planos/servicos_por_plano/servicos_map/usos: lookups pré-carregados em
    lote (Bloco 5.1) — quando None (chamada de item único: detalhar), cai em
    query pontual por assinatura, aceitável fora de um loop.
    """
    plano = planos.get(cp.plano_id) if planos is not None else db.session.get(Plano, cp.plano_id)
    if servicos_por_plano is not None:
        servicos_plano = servicos_por_plano.get(cp.plano_id, [])
    else:
        servicos_plano = PlanoServico.query.filter_by(plano_id=cp.plano_id, ativo=True).all()

    servicos = []
    for ps in servicos_plano:
        svc = servicos_map.get(ps.servico_id) if servicos_map is not None else db.session.get(Servico, ps.servico_id)
        uso = usos.get((cp.id, ps.servico_id), 0) if usos is not None else _uso_mes_atual(cp.id, ps.servico_id)
        limite = limite_para_fora(ps.limite_uso_mensal)
        servicos.append({
            'servico_id':        ps.servico_id,
            'nome':              svc.nome if svc else None,
            'limite_uso_mensal': limite,
            'ilimitado':         ps.limite_uso_mensal == PLANO_LIMITE_ILIMITADO,
            'uso_mes_atual':     uso,
            'restante':          None if limite is None else max(0, limite - uso),
        })
    return {
        'id':          cp.id,
        'plano_id':    cp.plano_id,
        'plano_nome':  plano.nome if plano else None,
        'barbeiro_id': cp.barbeiro_id,
        'data_inicio': cp.data_inicio.isoformat() if cp.data_inicio else None,
        'data_fim':    cp.data_fim.isoformat() if cp.data_fim else None,
        'ativo':       cp.ativo,
        'servicos':    servicos,
    }


# ── GET /api/v1/cliente/planos ────────────────────────────────────────────────

@cliente_planos_bp.get('/planos')
@cliente_required
def listar_minhas_assinaturas():
    """Lista as assinaturas de plano ativas do cliente autenticado."""
    cli = _get_cliente_ou_404(g.user_id, g.barbearia_id)
    q = ClientePlano.query.filter_by(barbearia_id=g.barbearia_id, cliente_id=cli.id)
    ativo = request.args.get('ativo', 'true')
    if ativo == 'true':
        q = q.filter_by(ativo=True)
    elif ativo == 'false':
        q = q.filter_by(ativo=False)
    assinaturas = q.order_by(ClientePlano.criado_em.desc()).all()
    if not assinaturas:
        return jsonify([]), 200

    plano_ids = {cp.plano_id for cp in assinaturas}
    planos = {p.id: p for p in Plano.query.filter(Plano.id.in_(plano_ids)).all()}

    ps_rows = PlanoServico.query.filter(
        PlanoServico.plano_id.in_(plano_ids), PlanoServico.ativo == True
    ).all()
    servicos_por_plano = {}
    for ps in ps_rows:
        servicos_por_plano.setdefault(ps.plano_id, []).append(ps)
    servico_ids = {ps.servico_id for ps in ps_rows}
    servicos_map = {s.id: s for s in Servico.query.filter(Servico.id.in_(servico_ids)).all()} if servico_ids else {}

    hoje = hoje_brasilia()
    cp_ids = {cp.id for cp in assinaturas}
    uso_rows = ClientePlanoUso.query.filter(
        ClientePlanoUso.cliente_plano_id.in_(cp_ids),
        db.extract('year',  ClientePlanoUso.data_uso) == hoje.year,
        db.extract('month', ClientePlanoUso.data_uso) == hoje.month,
    ).all()
    usos = {}
    for u in uso_rows:
        key = (u.cliente_plano_id, u.servico_id)
        usos[key] = usos.get(key, 0) + 1

    return jsonify([
        _fmt_assinatura(cp, planos, servicos_por_plano, servicos_map, usos)
        for cp in assinaturas
    ]), 200


# ── GET /api/v1/cliente/planos/<id> ──────────────────────────────────────────

@cliente_planos_bp.get('/planos/<int:cp_id>')
@cliente_required
def detalhar_assinatura(cp_id):
    cli = _get_cliente_ou_404(g.user_id, g.barbearia_id)
    cp = ClientePlano.query.filter_by(
        id=cp_id, barbearia_id=g.barbearia_id, cliente_id=cli.id
    ).first()
    if not cp:
        raise APIError(f'{L("plano")} não encontrado.', 404)
    return jsonify(_fmt_assinatura(cp)), 200


# ── POST /api/v1/cliente/planos/<id>/cancelar ─────────────────────────────────
# Cancelamento = desativa a assinatura. Não há reembolso automático.

@cliente_planos_bp.post('/planos/<int:cp_id>/cancelar')
@cliente_required
def cancelar_assinatura(cp_id):
    cli = _get_cliente_ou_404(g.user_id, g.barbearia_id)
    cp = ClientePlano.query.filter_by(
        id=cp_id, barbearia_id=g.barbearia_id, cliente_id=cli.id
    ).first()
    if not cp:
        raise APIError(f'{L("plano")} não encontrado.', 404)
    if not cp.ativo:
        raise APIError(f'{L("plano")} já está inativo.')
    cp.ativo = False
    commit_ou_falhar(
        'cliente.planos.cancelar_assinatura',
        f'Erro ao salvar {L("plano")}. Tente novamente.',
    )

    # VIP leveling (v1.2) — abre a janela de tolerância pós-cancelamento.
    # Registrado após o commit principal: falha aqui não desfaz o cancelamento.
    from app.utils.vip_leveling import processar_evento_plano
    processar_evento_plano(cli.id, g.barbearia_id, 'cancelamento')
    commit_ou_falhar('cliente.planos.cancelar_assinatura.vip_leveling')

    return jsonify({'mensagem': f'{L("plano")} cancelado.', 'id': cp_id}), 200


# ── GET /api/v1/cliente/planos/solicitacoes ───────────────────────────────────

@cliente_planos_bp.get('/planos/solicitacoes')
@cliente_required
def listar_solicitacoes():
    cli = _get_cliente_ou_404(g.user_id, g.barbearia_id)
    solic = ClientePlanoSolicitacao.query.filter_by(
        barbearia_id=g.barbearia_id, cliente_id=cli.id
    ).order_by(ClientePlanoSolicitacao.criado_em.desc()).all()
    return jsonify([
        {
            'id':               s.id,
            'plano_id':         s.plano_id,
            'plano_nome':       (db.session.get(Plano, s.plano_id).nome
                                 if db.session.get(Plano, s.plano_id) else None),
            'valor':            float(s.valor),
            'metodo_pagamento': s.metodo_pagamento,
            'status':           s.status,
            'criado_em':        s.criado_em.isoformat() if s.criado_em else None,
            'aprovado_em':      s.aprovado_em.isoformat() if s.aprovado_em else None,
            'motivo_rejeicao':  s.motivo_rejeicao,
        }
        for s in solic
    ]), 200
