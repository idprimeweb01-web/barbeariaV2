import os
import cloudinary
import cloudinary.uploader
from flask import Blueprint, request, g, jsonify, current_app
from app.extensions import db, limiter
from app.models import (
    Barbearia, Plano, PlanoServico, Servico, Barbeiro,
    ClientePlanoSolicitacao, ClientePlano, Cliente, Usuario,
)
from app.exceptions import APIError
from app.utils.features import feature_ativa
from app.utils.planos import PLANO_LIMITE_ILIMITADO, limite_para_fora
from app.utils.telefone import normalizar_telefone
from app.labels import L
from app.utils.db import commit_ou_falhar
from app.utils.notificacoes import notificar
from app.constants import StatusSolicitacaoPlano
from app.routes.pub.agendamento import _TIPOS_COMPROVANTE, _MAX_BYTES_COMP, _validar_magic_bytes

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


# ── GET /api/v1/pub/<slug>/planos ─────────────────────────────────────────────

@pub_planos_bp.get('/api/v1/pub/<string:slug>/planos')
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


# ── POST /api/v1/pub/<slug>/planos/<id>/solicitar ────────────────────────────
# Cria ClientePlanoSolicitacao com status=pendente.
# Ativação só acontece após aprovação do gestor (PIX manual ou outro método).

@pub_planos_bp.post('/api/v1/pub/<string:slug>/planos/<int:plano_id>/solicitar')
@limiter.limit(os.environ.get('RL_PLANO_SOLICITAR', '5 per minute'))
def solicitar_assinatura(slug, plano_id):
    b = _get_barbearia_ou_404(slug)
    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    # ── Identificar o cliente ─────────────────────────────────────────────────
    cliente_id = None
    if g.user_id:
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

    # Checagem preventiva de capacidade — evita solicitação inútil de um plano
    # já cheio. Não é a garantia final (isso é no aprovar_solicitacao, com
    # lock); aqui é só custo evitado pro cliente e pro gestor.
    if plano.max_assinaturas is not None:
        assinantes_ativos = ClientePlano.query.filter_by(plano_id=plano.id, ativo=True).count()
        if assinantes_ativos >= plano.max_assinaturas:
            raise APIError(f'Este {L("plano").lower()} atingiu o limite de assinantes.', 403)

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

    if metodo == 'pix' and not feature_ativa(b.id, 'pix_integrado'):
        raise APIError('PIX não está disponível para este estabelecimento.', 403)

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

    cli_notif = db.session.get(Cliente, cliente_id)
    gestores = Usuario.query.filter_by(barbearia_id=b.id, perfil='gestor', ativo=True).all()
    for gestor in gestores:
        notificar(
            barbearia_id=b.id, usuario_id=gestor.id, tipo='plano_solicitado',
            titulo='Nova solicitação de plano',
            mensagem=f'{cli_notif.nome if cli_notif else "Cliente"} solicitou o plano "{plano.nome}".',
            link='/gestor/planos', canal='in_app',
        )

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
        resposta['chave_pix'] = b.chave_pix
        resposta['pix_nome_titular'] = b.pix_nome_titular or b.nome
        resposta['pix_info'] = (
            f'Envie R$ {float(sol.valor):.2f} via PIX e aguarde a ativação pelo gestor.'
        )

    return jsonify(resposta), 201


# ── POST /api/v1/pub/<slug>/planos/solicitacoes/<id>/comprovante ─────────────
# Mesmo padrão do comprovante de agendamento (pub/agendamento.py) — o campo
# comprovante_url já existia no model ClientePlanoSolicitacao desde sempre,
# mas nenhum endpoint jamais escreveu nele (achado em teste manual: cliente
# solicitava plano via PIX e não tinha como enviar comprovante nenhum).

@pub_planos_bp.post('/api/v1/pub/<string:slug>/planos/solicitacoes/<int:solicitacao_id>/comprovante')
@limiter.limit(os.environ.get('RL_COMPROVANTE', '3 per minute'))
def upload_comprovante_plano(slug, solicitacao_id):
    b = _get_barbearia_ou_404(slug)

    sol = ClientePlanoSolicitacao.query.filter_by(id=solicitacao_id, barbearia_id=b.id).first()
    if not sol:
        raise APIError('Solicitação não encontrada.', 404)

    if sol.metodo_pagamento != 'pix':
        raise APIError('Esta solicitação não é via PIX.', 400)
    if sol.status != StatusSolicitacaoPlano.PENDENTE:
        raise APIError('Não é possível enviar comprovante para esta solicitação.', 422)

    if 'arquivo' not in request.files:
        raise APIError('Campo "arquivo" é obrigatório.', 400)

    arq = request.files['arquivo']
    if not arq.filename:
        raise APIError('Nenhum arquivo enviado.', 400)
    if arq.mimetype not in _TIPOS_COMPROVANTE:
        raise APIError('Tipo não permitido. Use JPEG ou PNG.', 400)
    arq.seek(0, 2)
    if arq.tell() > _MAX_BYTES_COMP:
        raise APIError('Arquivo muito grande. Máximo 5 MB.', 400)
    arq.seek(0)
    _validar_magic_bytes(arq)

    from datetime import datetime as _dt
    now  = _dt.utcnow()
    folder    = f'barbearia/{b.id}/comprovantes_plano/{now.strftime("%Y")}/{now.strftime("%m")}'
    public_id = f'plano_sol_{solicitacao_id}'

    try:
        resultado = cloudinary.uploader.upload(
            arq.stream,
            folder=folder,
            public_id=public_id,
            overwrite=True,
            unique_filename=False,
            invalidate=True,
            resource_type='image',
        )
    except Exception as exc:
        current_app.logger.error(f'Cloudinary: falha ao enviar comprovante (solicitacao {solicitacao_id}): {exc}', exc_info=True)
        raise APIError('Erro ao enviar comprovante. Tente novamente.', 502)

    url = resultado.get('secure_url')
    if not url:
        raise APIError('Cloudinary não retornou URL.', 502)

    sol.comprovante_url = url
    commit_ou_falhar('pub.planos.upload_comprovante_plano')

    return jsonify({'mensagem': 'Comprovante enviado com sucesso.', 'url': url}), 200
