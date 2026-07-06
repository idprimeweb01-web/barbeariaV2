import os
from flask import Blueprint, request, g, jsonify
from app.extensions import db, limiter
from app.models import (
    Barbearia, Plano, PlanoServico, Servico, Barbeiro,
    ClientePlanoSolicitacao, Cliente,
)
from app.exceptions import APIError
from app.utils.planos import PLANO_LIMITE_ILIMITADO, limite_para_fora
from app.utils.telefone import normalizar_telefone
from app.labels import L
from app.utils.db import commit_ou_falhar
from app.constants import StatusSolicitacaoPlano

pub_planos_bp = Blueprint('pub_planos', __name__)


def _get_barbearia_ou_404(slug: str) -> Barbearia:
    b = Barbearia.query.filter_by(slug=slug, ativo=True).first()
    if not b:
        raise APIError(f'{L("tenant")} não encontrada.', 404)
    return b


def _fmt_plano_pub(p):
    servicos = PlanoServico.query.filter_by(plano_id=p.id, ativo=True).all()
    return {
        'id':            p.id,
        'nome':          p.nome,
        'descricao':     p.descricao,
        'preco_mensal':  float(p.preco_mensal),
        'barbeiro_id':   p.barbeiro_id,
        'is_plano_aberto': p.barbeiro_id is None,
        'servicos': [
            {
                'servico_id':        ps.servico_id,
                'nome':              (db.session.get(Servico, ps.servico_id).nome
                                      if db.session.get(Servico, ps.servico_id) else None),
                'limite_uso_mensal': limite_para_fora(ps.limite_uso_mensal),
                'ilimitado':         ps.limite_uso_mensal == PLANO_LIMITE_ILIMITADO,
                'dias_expiracao':    ps.dias_expiracao,
            }
            for ps in servicos
        ],
    }


# ── GET /pub/<slug>/planos ────────────────────────────────────────────────────

@pub_planos_bp.get('/pub/<string:slug>/planos')
def listar_planos_pub(slug):
    """Lista planos ativos disponíveis para assinatura."""
    b = _get_barbearia_ou_404(slug)
    barbeiro_id = request.args.get('barbeiro_id', type=int)

    q = Plano.query.filter_by(barbearia_id=b.id, ativo=True)
    if barbeiro_id is not None:
        # Filtra planos abertos (barbeiro_id=NULL) OU vinculados a este barbeiro
        q = q.filter(
            db.or_(Plano.barbeiro_id.is_(None), Plano.barbeiro_id == barbeiro_id)
        )

    planos = q.order_by(Plano.nome).all()
    return jsonify([_fmt_plano_pub(p) for p in planos]), 200


# ── POST /pub/<slug>/planos/<id>/solicitar ───────────────────────────────────
# Cria ClientePlanoSolicitacao com status=pendente.
# Ativação só acontece após aprovação do gestor (PIX manual ou outro método).

@pub_planos_bp.post('/pub/<string:slug>/planos/<int:plano_id>/solicitar')
@limiter.limit(os.environ.get('RL_PLANO_SOLICITAR', '5 per minute'))
def solicitar_assinatura(slug, plano_id):
    b = _get_barbearia_ou_404(slug)
    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    # ── Identificar o cliente ─────────────────────────────────────────────────
    cliente_id = None
    if g.user_id:
        from app.models import Usuario
        usr = db.session.get(Usuario, g.user_id)
        if usr and usr.barbearia_id == b.id:
            cli = Cliente.query.filter_by(barbearia_id=b.id, usuario_id=usr.id).first()
            if cli:
                cliente_id = cli.id

    # Fallback: quick-booking por telefone
    if cliente_id is None:
        tel_raw = (dados.get('telefone') or '').strip()
        if not tel_raw:
            raise APIError(
                'Informe seu telefone para solicitar um plano sem login, '
                'ou faça login antes de solicitar.'
            )
        tel_norm, tel_erro = normalizar_telefone(tel_raw)
        if tel_erro:
            raise APIError(tel_erro)
        cli = Cliente.query.filter_by(barbearia_id=b.id, telefone=tel_norm).first()
        if not cli:
            raise APIError(
                'Cliente não encontrado. Faça um agendamento primeiro ou '
                'entre em contato com a barbearia para criar seu cadastro.'
            )
        cliente_id = cli.id

    # ── Validar o plano ───────────────────────────────────────────────────────
    plano = Plano.query.filter_by(id=plano_id, barbearia_id=b.id, ativo=True).first()
    if not plano:
        raise APIError(f'{L("plano")} não encontrado ou inativo.', 404)

    # Plano vinculado: validar barbeiro informado
    barbeiro_id = dados.get('barbeiro_id')
    if plano.barbeiro_id is not None:
        if barbeiro_id is None:
            barbeiro_id = plano.barbeiro_id
        elif barbeiro_id != plano.barbeiro_id:
            raise APIError(
                f'Este {L("plano").lower()} é vinculado ao {L("profissional").lower()} '
                f'id={plano.barbeiro_id}.'
            )
    else:
        # Plano aberto: barbeiro_id na solicitação é opcional (pode ser None)
        if barbeiro_id is not None:
            br = Barbeiro.query.filter_by(id=barbeiro_id, barbearia_id=b.id, ativo=True).first()
            if not br:
                raise APIError(f'{L("profissional")} não encontrado.', 404)

    # ── Verificar solicitação duplicada pendente ───────────────────────────────
    pendente = ClientePlanoSolicitacao.query.filter_by(
        barbearia_id=b.id, cliente_id=cliente_id,
        plano_id=plano_id, status=StatusSolicitacaoPlano.PENDENTE,
    ).first()
    if pendente:
        raise APIError(
            f'Você já tem uma solicitação pendente para este {L("plano").lower()}.',
            409
        )

    # ── Criar solicitação ─────────────────────────────────────────────────────
    metodo = (dados.get('metodo_pagamento') or 'pix').lower()
    if metodo not in ('pix', 'dinheiro', 'cartao'):
        metodo = 'pix'

    sol = ClientePlanoSolicitacao(
        barbearia_id=b.id,
        cliente_id=cliente_id,
        plano_id=plano_id,
        barbeiro_id=barbeiro_id,
        valor=plano.preco_mensal,
        metodo_pagamento=metodo,
        status=StatusSolicitacaoPlano.PENDENTE,
    )
    db.session.add(sol)
    commit_ou_falhar('pub.planos.solicitar_assinatura')

    resposta = {
        'mensagem': f'Solicitação de {L("plano").lower()} enviada. Aguarde a aprovação.',
        'solicitacao_id': sol.id,
        'plano': plano.nome,
        'valor': float(sol.valor),
        'metodo_pagamento': sol.metodo_pagamento,
        'status': StatusSolicitacaoPlano.PENDENTE,
    }

    # Gerar código PIX se método for pix e barbearia tiver chave configurada
    if metodo == 'pix' and b.chave_pix:
        from app.utils.pix import gerar_pix_copia_cola
        emv = gerar_pix_copia_cola(
            chave=b.chave_pix,
            nome_titular=b.pix_nome_titular or b.nome,
            cidade=b.pix_cidade or 'CIDADE',
            valor=float(sol.valor),
            txid=f'PLANO{sol.id:06d}',
        )
        resposta['pix_copia_cola'] = emv
        resposta['pix_info'] = (
            f'Envie R$ {float(sol.valor):.2f} via PIX e aguarde a ativação pelo gestor.'
        )

    return jsonify(resposta), 201
