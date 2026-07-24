"""Dúvidas do Cliente / Suporte — lado do cliente. Abre ticket (com
categoria, prioridade sugerida e, opcionalmente, um funcionário específico
pra direcionar), conversa em thread com até 3 imagens por mensagem, e
avalia a satisfação depois que o ticket é concluído. Núcleo de criação de
mensagem compartilhado com gestor/barbeiro/admin em app/utils/duvidas.py."""
import os
from flask import Blueprint, request, g, jsonify
from app.extensions import db, limiter
from app.models import Cliente, ClienteDuvida, ClienteDuvidaMensagem, Barbeiro
from app.exceptions import APIError
from app.decorators.auth import cliente_required
from app.utils.features import feature_required
from app.utils.db import commit_ou_falhar
from app.utils.webhooks import disparar_webhook
from app.utils.comprovante_link import gerar_link_comprovante
from app.utils.duvidas import (
    criar_mensagem, registrar_evento, resolver_direcionamento,
    notificar_responsaveis, notificar_admins,
)
from app.constants import (
    StatusClienteDuvida, AutorTipoDuvida, TipoEventoWebhook,
    CategoriaDuvida, PrioridadeDuvida, TipoEventoDuvida,
)

cliente_duvidas_bp = Blueprint('cliente_duvidas', __name__, url_prefix='/api/v1/cliente')


def _cliente_ou_404():
    cli = Cliente.query.filter_by(usuario_id=g.user_id, barbearia_id=g.barbearia_id).first()
    if not cli:
        raise APIError('Perfil de cliente não encontrado.', 404)
    return cli


def _duvida_ou_404(duvida_id, cliente_id):
    d = ClienteDuvida.query.filter_by(
        id=duvida_id, barbearia_id=g.barbearia_id, cliente_id=cliente_id
    ).first()
    if not d:
        raise APIError('Dúvida não encontrada.', 404)
    return d


def _fmt_mensagem(m):
    return {
        'id':         m.id,
        'autor_tipo': m.autor_tipo,
        'texto':      m.texto,
        'imagens':    [gerar_link_comprovante('duvida_msg', img.id, img.barbearia_id) for img in m.imagens],
        'criado_em':  m.criado_em.isoformat() if m.criado_em else None,
    }


def _fmt_preview(d, ultima=None):
    preview = None
    if ultima:
        preview = ultima.texto[:120] if ultima.texto else ('📷 Imagem' if ultima.imagens else None)
    return {
        'id':                      d.id,
        'assunto':                 d.assunto,
        'categoria':               d.categoria,
        'prioridade':              d.prioridade,
        'status':                  d.status,
        'nao_lida_cliente':        d.nao_lida_cliente,
        'ultima_mensagem_em':      d.ultima_mensagem_em.isoformat() if d.ultima_mensagem_em else None,
        'ultima_mensagem_autor_tipo': ultima.autor_tipo if ultima else None,
        'ultima_mensagem_preview': preview,
        'nota_satisfacao':         d.nota_satisfacao,
        'criado_em':               d.criado_em.isoformat() if d.criado_em else None,
    }


def _mapa_ultimas_mensagens(duvida_ids):
    if not duvida_ids:
        return {}
    msgs = (
        ClienteDuvidaMensagem.query
        .filter(ClienteDuvidaMensagem.duvida_id.in_(duvida_ids))
        .order_by(ClienteDuvidaMensagem.id.desc())
        .all()
    )
    mapa = {}
    for m in msgs:
        mapa.setdefault(m.duvida_id, m)  # ordenado desc → 1ª ocorrência é a mais recente
    return mapa


# ── GET /api/v1/cliente/duvidas ───────────────────────────────────────────────

@cliente_duvidas_bp.get('/duvidas')
@cliente_required
@feature_required('duvidas_cliente')
def listar_duvidas():
    cli = _cliente_ou_404()
    try:
        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(50, max(1, int(request.args.get('per_page', 20))))
    except ValueError:
        raise APIError('"page" e "per_page" devem ser inteiros.', 422)

    paginado = (
        ClienteDuvida.query
        .filter_by(barbearia_id=g.barbearia_id, cliente_id=cli.id)
        .order_by(ClienteDuvida.ultima_mensagem_em.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    ultimas = _mapa_ultimas_mensagens([d.id for d in paginado.items])

    return jsonify({
        'dados':    [_fmt_preview(d, ultimas.get(d.id)) for d in paginado.items],
        'page':     paginado.page,
        'per_page': paginado.per_page,
        'total':    paginado.total,
        'pages':    paginado.pages,
    }), 200


# ── GET /api/v1/cliente/duvidas/funcionarios ──────────────────────────────────
# Lista pra alimentar o seletor "Direcionar para" na abertura do ticket.
# categoria='erro' ignora a escolha (ver resolver_direcionamento) — a tela
# já avisa isso, mas o filtro aqui é só leitura, não precisa saber disso.

@cliente_duvidas_bp.get('/duvidas/funcionarios')
@cliente_required
@feature_required('duvidas_cliente')
def listar_funcionarios_duvida():
    from app.models import Usuario
    barbeiros = (
        Barbeiro.query
        .filter_by(barbearia_id=g.barbearia_id, ativo=True)
        .join(Usuario, Usuario.id == Barbeiro.usuario_id)
        .order_by(Usuario.nome)
        .all()
    )
    return jsonify([{'id': br.id, 'nome': br.usuario.nome} for br in barbeiros]), 200


# ── POST /api/v1/cliente/duvidas ──────────────────────────────────────────────
# multipart: assunto (opcional) + texto (opcional) + imagens[] (até 3,
# opcionais) + categoria (opcional, default 'duvida') + prioridade
# (opcional, default 'normal', sugestão de quem abre) + barbeiro_id
# (opcional — id de Barbeiro, não de Usuario; "quero falar com").

@cliente_duvidas_bp.post('/duvidas')
@limiter.limit(os.environ.get('RL_DUVIDA', '5 per minute'))
@cliente_required
@feature_required('duvidas_cliente')
def criar_duvida():
    cli = _cliente_ou_404()
    assunto = (request.form.get('assunto') or '').strip()[:150] or None
    texto   = request.form.get('texto')
    arquivos = request.files.getlist('imagens')

    categoria = (request.form.get('categoria') or CategoriaDuvida.DUVIDA).strip().lower()
    if categoria not in CategoriaDuvida.TODOS:
        raise APIError(f'"categoria" inválida: "{categoria}".', 422)

    prioridade = (request.form.get('prioridade') or PrioridadeDuvida.NORMAL).strip().lower()
    if prioridade not in PrioridadeDuvida.TODOS:
        raise APIError(f'"prioridade" inválida: "{prioridade}".', 422)

    barbeiro_id_raw = request.form.get('barbeiro_id')
    usuario_id_escolhido = None
    if barbeiro_id_raw:
        try:
            barbeiro_id = int(barbeiro_id_raw)
        except ValueError:
            raise APIError('"barbeiro_id" deve ser um inteiro.', 422)
        br = Barbeiro.query.filter_by(id=barbeiro_id, barbearia_id=g.barbearia_id, ativo=True).first()
        if br:
            usuario_id_escolhido = br.usuario_id

    direcionado_tipo, direcionado_usuario_id = resolver_direcionamento(
        g.barbearia_id, categoria, usuario_id_escolhido,
    )

    duvida = ClienteDuvida(
        barbearia_id=g.barbearia_id,
        cliente_id=cli.id,
        aberta_por_usuario_id=g.user_id,
        assunto=assunto,
        categoria=categoria,
        prioridade=prioridade,
        status=StatusClienteDuvida.PENDENTE,
        direcionado_para_tipo=direcionado_tipo,
        direcionado_para_usuario_id=direcionado_usuario_id,
        nao_lida_gestor=True,
    )
    db.session.add(duvida)
    db.session.flush()

    msg = criar_mensagem(
        duvida=duvida, barbearia_id=g.barbearia_id,
        autor_usuario_id=g.user_id, autor_tipo=AutorTipoDuvida.CLIENTE,
        texto=texto, arquivos_imagem=arquivos,
    )

    commit_ou_falhar('cliente.duvidas.criar_duvida')

    resumo = assunto or (texto or '').strip()[:80] or 'sem assunto'
    notificar_responsaveis(duvida, 'Nova dúvida recebida', f'{cli.nome}: "{resumo}"')

    disparar_webhook(g.barbearia_id, TipoEventoWebhook.DUVIDA_CRIADA, {
        'duvida_id': duvida.id, 'cliente_id': cli.id, 'assunto': duvida.assunto,
        'categoria': duvida.categoria, 'prioridade': duvida.prioridade,
    })
    if prioridade == PrioridadeDuvida.URGENTE:
        disparar_webhook(g.barbearia_id, TipoEventoWebhook.DUVIDA_URGENTE, {
            'duvida_id': duvida.id, 'cliente_id': cli.id, 'assunto': duvida.assunto,
        })

    return jsonify({'mensagem': 'Dúvida enviada.', 'duvida_id': duvida.id, 'mensagem_id': msg.id}), 201


# ── GET /api/v1/cliente/duvidas/<id> ──────────────────────────────────────────

@cliente_duvidas_bp.get('/duvidas/<int:duvida_id>')
@cliente_required
@feature_required('duvidas_cliente')
def detalhar_duvida(duvida_id):
    cli = _cliente_ou_404()
    d = _duvida_ou_404(duvida_id, cli.id)

    mensagens = (
        ClienteDuvidaMensagem.query
        .filter_by(duvida_id=d.id)
        .order_by(ClienteDuvidaMensagem.id)
        .all()
    )

    if d.nao_lida_cliente:
        d.nao_lida_cliente = False
        commit_ou_falhar('cliente.duvidas.marcar_lida')

    return jsonify({
        'id':               d.id,
        'assunto':          d.assunto,
        'categoria':        d.categoria,
        'prioridade':       d.prioridade,
        'status':           d.status,
        'nota_satisfacao':  d.nota_satisfacao,
        'comentario_satisfacao': d.comentario_satisfacao,
        'criado_em':        d.criado_em.isoformat() if d.criado_em else None,
        'mensagens':        [_fmt_mensagem(m) for m in mensagens],
    }), 200


# ── POST /api/v1/cliente/duvidas/<id>/mensagens ───────────────────────────────

@cliente_duvidas_bp.post('/duvidas/<int:duvida_id>/mensagens')
@limiter.limit(os.environ.get('RL_DUVIDA', '5 per minute'))
@cliente_required
@feature_required('duvidas_cliente')
def responder_duvida(duvida_id):
    cli = _cliente_ou_404()
    d = _duvida_ou_404(duvida_id, cli.id)

    if d.status == StatusClienteDuvida.CANCELADA:
        raise APIError('Este ticket foi cancelado e não aceita novas mensagens.', 422)

    status_antes = d.status
    texto    = request.form.get('texto')
    arquivos = request.files.getlist('imagens')

    msg = criar_mensagem(
        duvida=d, barbearia_id=g.barbearia_id,
        autor_usuario_id=g.user_id, autor_tipo=AutorTipoDuvida.CLIENTE,
        texto=texto, arquivos_imagem=arquivos,
    )
    d.nao_lida_gestor = True
    reabriu = status_antes == StatusClienteDuvida.CONCLUIDA and d.status == StatusClienteDuvida.PENDENTE

    commit_ou_falhar('cliente.duvidas.responder_duvida')

    if reabriu:
        notificar_responsaveis(d, 'Ticket reaberto pelo cliente', f'{cli.nome} respondeu um ticket já concluído — reaberto automaticamente.')
    else:
        resumo = (texto or '').strip()[:80] or 'Nova mensagem'
        notificar_responsaveis(d, 'Nova mensagem do cliente', f'{cli.nome}: "{resumo}"')

    disparar_webhook(g.barbearia_id, TipoEventoWebhook.DUVIDA_NOVA_MENSAGEM, {
        'duvida_id': d.id, 'cliente_id': cli.id, 'autor_tipo': AutorTipoDuvida.CLIENTE,
    })

    return jsonify({'mensagem': 'Mensagem enviada.', 'mensagem_id': msg.id}), 201


# ── PUT /api/v1/cliente/duvidas/<id>/fechar ───────────────────────────────────
# O cliente marca o PRÓPRIO ticket como resolvido (situação -> concluida).
# Cancelamento é ação exclusiva de gestor/barbeiro/admin (ver gestor/duvidas.py).

@cliente_duvidas_bp.put('/duvidas/<int:duvida_id>/fechar')
@cliente_required
@feature_required('duvidas_cliente')
def fechar_duvida(duvida_id):
    cli = _cliente_ou_404()
    d = _duvida_ou_404(duvida_id, cli.id)
    if d.status != StatusClienteDuvida.PENDENTE:
        raise APIError('Este ticket já está encerrado.', 422)

    status_anterior = d.status
    d.status = StatusClienteDuvida.CONCLUIDA
    registrar_evento(
        duvida=d, tipo=TipoEventoDuvida.SITUACAO_ALTERADA,
        valor_anterior=status_anterior, valor_novo=d.status, autor_usuario_id=g.user_id,
    )
    commit_ou_falhar('cliente.duvidas.fechar_duvida')
    return jsonify({'mensagem': 'Dúvida encerrada.'}), 200


# ── POST /api/v1/cliente/duvidas/<id>/satisfacao ──────────────────────────────
# CSAT opcional, uma única vez, só depois de concluida.

@cliente_duvidas_bp.post('/duvidas/<int:duvida_id>/satisfacao')
@cliente_required
@feature_required('duvidas_cliente')
def avaliar_satisfacao(duvida_id):
    cli = _cliente_ou_404()
    d = _duvida_ou_404(duvida_id, cli.id)

    if d.status != StatusClienteDuvida.CONCLUIDA:
        raise APIError('Só é possível avaliar um ticket já concluído.', 422)
    if d.nota_satisfacao is not None:
        raise APIError('Este ticket já foi avaliado.', 422)

    dados = request.get_json(silent=True) or {}
    nota = dados.get('nota')
    if not isinstance(nota, int) or nota < 1 or nota > 5:
        raise APIError('"nota" deve ser um inteiro de 1 a 5.', 422)

    d.nota_satisfacao = nota
    d.comentario_satisfacao = (dados.get('comentario') or '').strip()[:500] or None
    commit_ou_falhar('cliente.duvidas.avaliar_satisfacao')

    # CSAT baixo é sinal de qualidade ruim no atendimento — alerta quem
    # cuidou do ticket (gestor/barbeiro) ou o admin, se foi encaminhado.
    if nota <= 2:
        texto_alerta = f'{cli.nome} avaliou o atendimento com nota {nota}/5' + (
            f': "{d.comentario_satisfacao}"' if d.comentario_satisfacao else '.'
        )
        if d.encaminhado_admin:
            notificar_admins(d, 'CSAT baixo — atenção', texto_alerta)
        else:
            notificar_responsaveis(d, 'CSAT baixo — atenção', texto_alerta)

    return jsonify({'mensagem': 'Obrigado pela avaliação!'}), 200
