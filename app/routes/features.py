import json
from functools import wraps
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from app import db
from app.models import (
    FeatureBarbearia, ClientePlanoSolicitacao, ClientePlano, ClientePlanoUso,
    Plano, PlanoServico, Servico, Usuario, ClienteVip, Cliente, Barbearia, VipNivel,
)
from app.routes.auth import gestor_required, super_admin_required
from app.utils import get_barbearia_atual, incrementar_nivel_vip, registrar_auditoria, limite_para_fora

features = Blueprint('features', __name__, url_prefix='/api/features')

NOMES_NIVEL_VIP = ['Sem nível', 'Bronze', 'Prata', 'Ouro', 'Platina', 'Diamante']


def _nome_nivel_vip(nivel):
    if nivel <= 0:
        return NOMES_NIVEL_VIP[0]
    if nivel < len(NOMES_NIVEL_VIP):
        return NOMES_NIVEL_VIP[nivel]
    return f'Nível {nivel}'


FLAGS_VALIDAS = {
    'planos', 'relatorios_avancados', 'vip_brindes', 'agendamento_login',
    'historico_cliente', 'cupons', 'fila_espera', 'comissao',
    'notificacoes', 'pix_integrado',
}


def _erro(msg, code=400):
    return jsonify({'erro': msg}), code


def cliente_required(fn):
    """Apenas usuários com perfil 'cliente'."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        usuario = db.session.get(Usuario, int(get_jwt_identity()))
        if not usuario or not usuario.ativo or usuario.perfil != 'cliente':
            return _erro('Acesso restrito a clientes.', 403)
        return fn(*args, **kwargs)
    return wrapper


def _get_or_create_features(barbearia_id):
    feat = FeatureBarbearia.query.filter_by(barbearia_id=barbearia_id).first()
    if not feat:
        feat = FeatureBarbearia(barbearia_id=barbearia_id)
        db.session.add(feat)
        db.session.commit()
    return feat


def _fmt_features(feat):
    return {nome: getattr(feat, nome) for nome in sorted(FLAGS_VALIDAS)}


# ============================================================================
# FEATURE FLAGS
# ============================================================================

# ── GET /api/features/barbearia/<id>/list ──────────────────────────────────
# Apenas super_admin: gerencia features de qualquer barbearia da plataforma.

@features.get('/barbearia/<int:barbearia_id>/list')
@super_admin_required
def listar_features(barbearia_id):
    if not db.session.get(Barbearia, barbearia_id):
        return _erro('Barbearia não encontrada.', 404)
    feat = _get_or_create_features(barbearia_id)
    return jsonify(_fmt_features(feat)), 200


# ── GET /api/features/minha-barbearia ──────────────────────────────────────
# Gestor/super_admin: features da própria barbearia (para condicionar a UI).

@features.get('/minha-barbearia')
@gestor_required
def minhas_features():
    feat = _get_or_create_features(get_barbearia_atual())
    return jsonify(_fmt_features(feat)), 200


# ── PUT /api/features/barbearia/<id>/<nome>/toggle ─────────────────────────
# Apenas super_admin: gerencia features de qualquer barbearia da plataforma.

@features.put('/barbearia/<int:barbearia_id>/<nome>/toggle')
@super_admin_required
def toggle_feature(barbearia_id, nome):
    if nome not in FLAGS_VALIDAS:
        return _erro(f'Feature inválida. Use: {", ".join(sorted(FLAGS_VALIDAS))}.')
    if not db.session.get(Barbearia, barbearia_id):
        return _erro('Barbearia não encontrada.', 404)

    feat = _get_or_create_features(barbearia_id)
    setattr(feat, nome, not getattr(feat, nome))
    feat.atualizado_em = datetime.utcnow()
    db.session.commit()

    registrar_auditoria(
        int(get_jwt_identity()), barbearia_id, 'edit', 'feature', feat.id,
        f"{'Ativou' if getattr(feat, nome) else 'Desativou'} feature \"{nome}\".",
    )

    return jsonify({
        'nome': nome,
        'ativo': getattr(feat, nome),
        'mensagem': f"Feature {'ativada' if getattr(feat, nome) else 'desativada'}.",
    }), 200


# ============================================================================
# PIX — aprovação de solicitações de plano
# ============================================================================

# ── GET /api/features/pix/pendentes ────────────────────────────────────────

@features.get('/pix/pendentes')
@gestor_required
def pix_pendentes():
    barbearia_id = get_barbearia_atual()
    rows = (
        db.session.query(ClientePlanoSolicitacao, Cliente, Plano)
        .join(Cliente, ClientePlanoSolicitacao.cliente_id == Cliente.id)
        .join(Plano, ClientePlanoSolicitacao.plano_id == Plano.id)
        .filter(
            ClientePlanoSolicitacao.barbearia_id == barbearia_id,
            ClientePlanoSolicitacao.status == 'pendente',
        )
        .order_by(ClientePlanoSolicitacao.criado_em)
        .all()
    )

    return jsonify([
        {
            'id': s.id,
            'cliente_id': s.cliente_id,
            'cliente_nome': c.nome,
            'plano_id': s.plano_id,
            'plano_nome': p.nome,
            'valor': float(s.valor),
            'comprovante_url': s.comprovante_url,
            'metodo_pagamento': s.metodo_pagamento,
            'criado_em': s.criado_em.isoformat() if s.criado_em else None,
        }
        for s, c, p in rows
    ]), 200


# ── POST /api/features/pix/<id>/aprovar ────────────────────────────────────

@features.post('/pix/<int:solicitacao_id>/aprovar')
@gestor_required
def aprovar_pix(solicitacao_id):
    barbearia_id = get_barbearia_atual()
    solicitacao = ClientePlanoSolicitacao.query.filter_by(
        id=solicitacao_id, barbearia_id=barbearia_id,
    ).first()
    if not solicitacao:
        return _erro('Solicitação não encontrada.', 404)
    if solicitacao.status != 'pendente':
        return _erro('Esta solicitação já foi respondida.')

    solicitacao.status = 'aprovado'
    solicitacao.aprovado_em = datetime.utcnow()

    cliente_plano = ClientePlano.query.filter_by(
        cliente_id=solicitacao.cliente_id, plano_id=solicitacao.plano_id,
    ).first()
    if cliente_plano:
        cliente_plano.ativo = True
        cliente_plano.data_fim = None
    else:
        cliente_plano = ClientePlano(
            cliente_id=solicitacao.cliente_id,
            plano_id=solicitacao.plano_id,
            barbeiro_id=solicitacao.barbeiro_id,
            barbearia_id=solicitacao.barbearia_id,
            data_inicio=date.today(),
            ativo=True,
        )
        db.session.add(cliente_plano)

    db.session.commit()

    incrementar_nivel_vip(solicitacao.cliente_id, barbearia_id)
    registrar_auditoria(
        int(get_jwt_identity()), barbearia_id, 'edit', 'plano_solicitacao', solicitacao.id,
        f'Aprovou solicitação de plano #{solicitacao.id} (PIX).',
    )

    return jsonify({'mensagem': 'Solicitação aprovada.', 'solicitacao_id': solicitacao_id}), 200


# ── POST /api/features/pix/<id>/rejeitar ───────────────────────────────────

@features.post('/pix/<int:solicitacao_id>/rejeitar')
@gestor_required
def rejeitar_pix(solicitacao_id):
    barbearia_id = get_barbearia_atual()
    solicitacao = ClientePlanoSolicitacao.query.filter_by(
        id=solicitacao_id, barbearia_id=barbearia_id,
    ).first()
    if not solicitacao:
        return _erro('Solicitação não encontrada.', 404)
    if solicitacao.status != 'pendente':
        return _erro('Esta solicitação já foi respondida.')

    dados = request.get_json(silent=True) or {}
    motivo = (dados.get('motivo_rejeicao') or '').strip() or 'Sem motivo informado'

    solicitacao.status = 'rejeitado'
    solicitacao.motivo_rejeicao = motivo
    solicitacao.aprovado_em = datetime.utcnow()

    db.session.commit()

    registrar_auditoria(
        int(get_jwt_identity()), barbearia_id, 'edit', 'plano_solicitacao', solicitacao.id,
        f'Rejeitou solicitação de plano #{solicitacao.id} (PIX). Motivo: {motivo}',
    )

    return jsonify({
        'mensagem': 'Solicitação rejeitada.',
        'solicitacao_id': solicitacao_id,
        'motivo': motivo,
    }), 200


# ============================================================================
# PERFIL DO CLIENTE — seções condicionais a features ativas
# ============================================================================

# ── GET /api/features/cliente/profile ──────────────────────────────────────

@features.get('/cliente/profile')
@cliente_required
def cliente_profile():
    usuario = db.session.get(Usuario, int(get_jwt_identity()))
    cliente = usuario.cliente
    if not cliente:
        return _erro('Cadastro de cliente não encontrado para este usuário.', 404)

    barbearia_id = cliente.barbearia_id
    feat = FeatureBarbearia.query.filter_by(barbearia_id=barbearia_id).first()

    secoes_disponiveis = {
        'planos':       bool(feat and feat.planos),
        'vip':          bool(feat and feat.vip_brindes),
        'pix':          bool(feat and feat.pix_integrado),
        'notificacoes': bool(feat and feat.notificacoes),
    }

    plano_ativo = None
    if feat and feat.planos:
        cliente_plano = ClientePlano.query.filter_by(
            cliente_id=cliente.id, barbearia_id=barbearia_id, ativo=True,
        ).first()
        if cliente_plano:
            plano = db.session.get(Plano, cliente_plano.plano_id)
            vinculos = PlanoServico.query.filter_by(plano_id=cliente_plano.plano_id, ativo=True).all() if plano else []
            janela_30d = date.today() - timedelta(days=30)
            servicos_fmt = []
            for v in vinculos:
                sv = db.session.get(Servico, v.servico_id)
                ja_usou = ClientePlanoUso.query.filter(
                    ClientePlanoUso.cliente_plano_id == cliente_plano.id,
                    ClientePlanoUso.servico_id == v.servico_id,
                    ClientePlanoUso.usado == True,
                    ClientePlanoUso.data_uso >= janela_30d,
                ).count()
                servicos_fmt.append({
                    'id': v.servico_id,
                    'nome': sv.nome if sv else '—',
                    'limite_mensal': limite_para_fora(v.limite_uso_mensal),
                    'ja_usou': ja_usou,
                })
            plano_ativo = {
                'id': cliente_plano.id,
                'nome_plano': plano.nome if plano else None,
                'preco': float(plano.preco_mensal) if plano else None,
                'data_inicio': cliente_plano.data_inicio.isoformat() if cliente_plano.data_inicio else None,
                'data_fim': cliente_plano.data_fim.isoformat() if cliente_plano.data_fim else None,
                'servicos': servicos_fmt,
            }

    vip = None
    if feat and feat.vip_brindes:
        cliente_vip = ClienteVip.query.filter_by(
            cliente_id=cliente.id, barbearia_id=barbearia_id,
        ).first()
        if cliente_vip:
            try:
                brindes = json.loads(cliente_vip.brindes_resgatados or '[]')
            except (TypeError, ValueError):
                brindes = []
            nivel = cliente_vip.nivel_vip_atual or 0
            nivel_atual_cat = VipNivel.query.filter_by(barbearia_id=barbearia_id, nivel=nivel).first()
            proximo_cat = VipNivel.query.filter_by(barbearia_id=barbearia_id, nivel=nivel + 1).first()
            vip = {
                'nivel_atual': nivel,
                'nivel_nome': _nome_nivel_vip(nivel),
                'brinde_atual': (nivel_atual_cat.brinde_descricao if nivel_atual_cat and nivel_atual_cat.modo_brinde_ativo else None),
                'proximo_nivel': {
                    'numero': nivel + 1,
                    'nome': _nome_nivel_vip(nivel + 1),
                    'brinde': proximo_cat.brinde_descricao if proximo_cat else None,
                } if proximo_cat else None,
                'brindes_resgatados': brindes,
                'proxima_renovacao': cliente_vip.data_proxima_renovacao.isoformat()
                    if cliente_vip.data_proxima_renovacao else None,
            }

    return jsonify({
        'secoes_disponiveis': secoes_disponiveis,
        'plano_ativo': plano_ativo,
        'vip': vip,
    }), 200
