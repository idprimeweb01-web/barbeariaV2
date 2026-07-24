"""Dúvidas do Cliente / Suporte — lado gestor + barbeiro (mesma rota, mesmo
padrão já usado em GET /api/v1/gestor/barbearia/tema: gestor tem visão
completa da barbearia, barbeiro só vê os tickets direcionados a ele mesmo
— ver _query_tenant_ou_barbeiro). Núcleo de criação de mensagem
compartilhado em app/utils/duvidas.py. Admin (cross-tenant) fica em
app/routes/super/duvidas.py."""
from collections import OrderedDict
from datetime import date
from flask import Blueprint, request, g, jsonify, send_file
from app.extensions import db
from app.models import ClienteDuvida, ClienteDuvidaMensagem, ClienteDuvidaEvento, Cliente, Barbearia
from app.exceptions import APIError
from app.decorators.auth import _require
from app.utils.features import feature_required
from app.utils.db import commit_ou_falhar
from app.utils.tz import hoje_brasilia, limites_utc_do_dia_brasilia
from app.utils.webhooks import disparar_webhook
from app.utils.comprovante_link import gerar_link_comprovante
from app.utils.notificacoes import notificar
from app.utils.auditoria import registrar_auditoria
from app.utils.duvidas import (
    criar_mensagem, registrar_evento, query_precisa_resposta,
    ordenar_por_prioridade_e_recencia, notificar_admins,
)
from app.utils.relatorio import gerar_excel
from app.constants import (
    StatusClienteDuvida, AutorTipoDuvida, TipoEventoWebhook,
    CategoriaDuvida, PrioridadeDuvida, TipoEventoDuvida,
)

gestor_duvidas_bp = Blueprint('gestor_duvidas', __name__, url_prefix='/api/v1/gestor')

_STAFF_REQUIRED = _require(['gestor', 'barbeiro'], check_tenant_ativo=True)

_COLUNAS_EXCEL = OrderedDict([
    ('cliente',    {'label': 'Cliente'}),
    ('assunto',    {'label': 'Assunto'}),
    ('categoria',  {'label': 'Categoria'}),
    ('prioridade', {'label': 'Prioridade'}),
    ('status',     {'label': 'Situação'}),
    ('mensagens',  {'label': 'Nº Mensagens'}),
    ('aberta_em',  {'label': 'Aberta em'}),
    ('ultima_em',  {'label': 'Última mensagem em'}),
    ('nota',       {'label': 'Nota CSAT'}),
    ('link',       {'label': 'Link da conversa'}),
])


# ── Escopo por perfil: gestor vê tudo da barbearia; barbeiro só o que foi
# direcionado a ele mesmo (mesma ideia de isolamento, um nível abaixo). ────

def _query_tenant_ou_barbeiro():
    q = ClienteDuvida.query.filter_by(barbearia_id=g.barbearia_id)
    if g.perfil == 'barbeiro':
        q = q.filter(ClienteDuvida.direcionado_para_usuario_id == g.user_id)
    return q


def _get_duvida_ou_404(duvida_id):
    d = _query_tenant_ou_barbeiro().filter(ClienteDuvida.id == duvida_id).first()
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


def _fmt_evento(ev, usuarios_map=None):
    autor = usuarios_map.get(ev.autor_usuario_id) if usuarios_map and ev.autor_usuario_id else None
    return {
        'id':             ev.id,
        'tipo':           ev.tipo,
        'valor_anterior': ev.valor_anterior,
        'valor_novo':     ev.valor_novo,
        'autor':          autor.nome if autor else None,
        'criado_em':      ev.criado_em.isoformat() if ev.criado_em else None,
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
        mapa.setdefault(m.duvida_id, m)
    return mapa


def _parse_filtros():
    """Comum a listar_duvidas e exportar_excel."""
    status_f = request.args.get('status')
    if status_f and status_f not in StatusClienteDuvida.TODOS:
        raise APIError(f'Status inválido: "{status_f}".', 422)

    categorias_f = [c for c in (request.args.get('categoria') or '').split(',') if c]
    invalidas = set(categorias_f) - CategoriaDuvida.TODOS
    if invalidas:
        raise APIError(f'Categoria(s) inválida(s): {", ".join(sorted(invalidas))}.', 422)

    prioridades_f = [p for p in (request.args.get('prioridade') or '').split(',') if p]
    invalidas = set(prioridades_f) - PrioridadeDuvida.TODOS
    if invalidas:
        raise APIError(f'Prioridade(s) inválida(s): {", ".join(sorted(invalidas))}.', 422)

    de_str  = request.args.get('de',  hoje_brasilia().replace(day=1).isoformat())
    ate_str = request.args.get('ate', hoje_brasilia().isoformat())
    try:
        de  = date.fromisoformat(de_str)
        ate = date.fromisoformat(ate_str)
    except ValueError:
        raise APIError('Parâmetros "de" e "ate" devem estar no formato YYYY-MM-DD.', 422)
    if de > ate:
        raise APIError('"de" não pode ser posterior a "ate".', 422)

    precisa_resposta = request.args.get('precisa_resposta') == '1'
    q_busca = (request.args.get('q') or '').strip()

    return status_f, categorias_f, prioridades_f, de, ate, precisa_resposta, q_busca


def _query_filtrada(status_f, categorias_f, prioridades_f, de, ate, precisa_resposta, q_busca):
    if precisa_resposta:
        q = query_precisa_resposta(g.barbearia_id)
        if g.perfil == 'barbeiro':
            q = q.filter(ClienteDuvida.direcionado_para_usuario_id == g.user_id)
    else:
        q = _query_tenant_ou_barbeiro()

    inicio_utc, fim_utc = limites_utc_do_dia_brasilia(de, ate)
    q = q.filter(
        ClienteDuvida.criado_em >= inicio_utc,
        ClienteDuvida.criado_em <= fim_utc,
    )
    if status_f:
        q = q.filter(ClienteDuvida.status == status_f)
    if categorias_f:
        q = q.filter(ClienteDuvida.categoria.in_(categorias_f))
    if prioridades_f:
        q = q.filter(ClienteDuvida.prioridade.in_(prioridades_f))
    if q_busca:
        termo = f'%{q_busca}%'
        ids_por_mensagem = (
            db.session.query(ClienteDuvidaMensagem.duvida_id)
            .filter(ClienteDuvidaMensagem.barbearia_id == g.barbearia_id, ClienteDuvidaMensagem.texto.ilike(termo))
        )
        q = q.filter(db.or_(ClienteDuvida.assunto.ilike(termo), ClienteDuvida.id.in_(ids_por_mensagem)))
    return q


# ── GET /api/v1/gestor/duvidas ────────────────────────────────────────────────

@gestor_duvidas_bp.get('/duvidas')
@_STAFF_REQUIRED
@feature_required('duvidas_cliente')
def listar_duvidas():
    status_f, categorias_f, prioridades_f, de, ate, precisa_resposta, q_busca = _parse_filtros()

    try:
        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 20))))
    except ValueError:
        raise APIError('"page" e "per_page" devem ser inteiros.', 422)

    q = _query_filtrada(status_f, categorias_f, prioridades_f, de, ate, precisa_resposta, q_busca)
    q = ordenar_por_prioridade_e_recencia(q, ClienteDuvida.prioridade, ClienteDuvida.ultima_mensagem_em)
    paginado = q.paginate(page=page, per_page=per_page, error_out=False)

    itens = paginado.items
    clientes = {
        c.id: c for c in Cliente.query.filter(
            Cliente.id.in_({d.cliente_id for d in itens})
        ).all()
    } if itens else {}
    ultimas = _mapa_ultimas_mensagens([d.id for d in itens])

    def _fmt(d):
        cli = clientes.get(d.cliente_id)
        ultima = ultimas.get(d.id)
        preview = None
        if ultima:
            preview = ultima.texto[:120] if ultima.texto else ('📷 Imagem' if ultima.imagens else None)
        return {
            'id':                      d.id,
            'cliente':                 {'id': cli.id, 'nome': cli.nome, 'telefone': cli.telefone} if cli else None,
            'assunto':                 d.assunto,
            'categoria':               d.categoria,
            'prioridade':              d.prioridade,
            'status':                  d.status,
            'direcionado_para_tipo':   d.direcionado_para_tipo,
            'nao_lida_gestor':         d.nao_lida_gestor,
            'precisa_resposta':        bool(
                d.status == StatusClienteDuvida.PENDENTE
                and ultima and ultima.autor_tipo == AutorTipoDuvida.CLIENTE
            ),
            'ultima_mensagem_em':      d.ultima_mensagem_em.isoformat() if d.ultima_mensagem_em else None,
            'ultima_mensagem_autor_tipo': ultima.autor_tipo if ultima else None,
            'ultima_mensagem_preview': preview,
            'nota_satisfacao':         d.nota_satisfacao,
            'criado_em':               d.criado_em.isoformat() if d.criado_em else None,
        }

    return jsonify({
        'dados':    [_fmt(d) for d in itens],
        'page':     paginado.page,
        'per_page': paginado.per_page,
        'total':    paginado.total,
        'pages':    paginado.pages,
    }), 200


# ── GET /api/v1/gestor/duvidas/<id> ───────────────────────────────────────────

@gestor_duvidas_bp.get('/duvidas/<int:duvida_id>')
@_STAFF_REQUIRED
@feature_required('duvidas_cliente')
def detalhar_duvida(duvida_id):
    d = _get_duvida_ou_404(duvida_id)
    cli = db.session.get(Cliente, d.cliente_id)

    mensagens = (
        ClienteDuvidaMensagem.query
        .filter_by(duvida_id=d.id)
        .order_by(ClienteDuvidaMensagem.id)
        .all()
    )
    eventos = (
        ClienteDuvidaEvento.query
        .filter_by(duvida_id=d.id)
        .order_by(ClienteDuvidaEvento.criado_em.desc())
        .all()
    )
    from app.models import Usuario
    autor_ids = {e.autor_usuario_id for e in eventos if e.autor_usuario_id}
    usuarios_map = {u.id: u for u in Usuario.query.filter(Usuario.id.in_(autor_ids)).all()} if autor_ids else {}

    if d.nao_lida_gestor:
        d.nao_lida_gestor = False
        commit_ou_falhar('gestor.duvidas.marcar_lida')

    return jsonify({
        'id':                    d.id,
        'cliente':               {'id': cli.id, 'nome': cli.nome, 'telefone': cli.telefone} if cli else None,
        'assunto':               d.assunto,
        'categoria':             d.categoria,
        'prioridade':            d.prioridade,
        'status':                d.status,
        'direcionado_para_tipo': d.direcionado_para_tipo,
        'atribuido_a_usuario_id': d.atribuido_a_usuario_id,
        'encaminhado_admin':     d.encaminhado_admin,
        'nota_satisfacao':       d.nota_satisfacao,
        'comentario_satisfacao': d.comentario_satisfacao,
        'criado_em':             d.criado_em.isoformat() if d.criado_em else None,
        'mensagens':             [_fmt_mensagem(m) for m in mensagens],
        'timeline':              [_fmt_evento(e, usuarios_map) for e in eventos],
    }), 200


# ── POST /api/v1/gestor/duvidas/<id>/mensagens ────────────────────────────────

@gestor_duvidas_bp.post('/duvidas/<int:duvida_id>/mensagens')
@_STAFF_REQUIRED
@feature_required('duvidas_cliente')
def responder_duvida(duvida_id):
    d = _get_duvida_ou_404(duvida_id)
    if d.status == StatusClienteDuvida.CANCELADA:
        raise APIError('Este ticket foi cancelado e não aceita novas mensagens.', 422)

    texto    = request.form.get('texto')
    arquivos = request.files.getlist('imagens')
    autor_tipo = AutorTipoDuvida.BARBEIRO if g.perfil == 'barbeiro' else AutorTipoDuvida.GESTOR

    msg = criar_mensagem(
        duvida=d, barbearia_id=g.barbearia_id,
        autor_usuario_id=g.user_id, autor_tipo=autor_tipo,
        texto=texto, arquivos_imagem=arquivos,
    )
    d.nao_lida_cliente = True

    commit_ou_falhar('gestor.duvidas.responder_duvida')

    cli = db.session.get(Cliente, d.cliente_id)
    if cli and cli.usuario_id:
        notificar(
            barbearia_id=g.barbearia_id,
            usuario_id=cli.usuario_id,
            tipo='duvida_respondida',
            titulo='Sua dúvida foi respondida',
            mensagem=d.assunto or 'Você recebeu uma nova resposta na sua dúvida.',
            link=f'/cliente/duvidas?id={d.id}',
            canal='in_app',
        )

    registrar_auditoria(
        g.user_id, g.barbearia_id, 'edit', 'cliente_duvida', d.id,
        f'Respondeu a dúvida #{d.id}.',
    )

    disparar_webhook(g.barbearia_id, TipoEventoWebhook.DUVIDA_NOVA_MENSAGEM, {
        'duvida_id': d.id, 'cliente_id': d.cliente_id, 'autor_tipo': autor_tipo,
    })

    return jsonify({'mensagem': 'Resposta enviada.', 'mensagem_id': msg.id}), 201


# ── PATCH /api/v1/gestor/duvidas/<id>/categoria ───────────────────────────────
# Editável a qualquer momento — se virar 'erro', reforça o direcionamento
# pra fila do gestor (mesma regra da abertura, ver resolver_direcionamento).

@gestor_duvidas_bp.patch('/duvidas/<int:duvida_id>/categoria')
@_STAFF_REQUIRED
@feature_required('duvidas_cliente')
def alterar_categoria(duvida_id):
    d = _get_duvida_ou_404(duvida_id)
    dados = request.get_json(silent=True) or {}
    categoria = (dados.get('categoria') or '').strip().lower()
    if categoria not in CategoriaDuvida.TODOS:
        raise APIError(f'"categoria" inválida: "{categoria}".', 422)

    if categoria == d.categoria:
        return jsonify({'mensagem': 'Categoria inalterada.', 'categoria': d.categoria}), 200

    anterior = d.categoria
    d.categoria = categoria
    if categoria == CategoriaDuvida.ERRO:
        d.direcionado_para_tipo = 'gestor'
        d.direcionado_para_usuario_id = None
    registrar_evento(
        duvida=d, tipo=TipoEventoDuvida.CATEGORIA_ALTERADA,
        valor_anterior=anterior, valor_novo=categoria, autor_usuario_id=g.user_id,
    )
    commit_ou_falhar('gestor.duvidas.alterar_categoria')
    return jsonify({'mensagem': 'Categoria atualizada.', 'categoria': d.categoria}), 200


# ── PATCH /api/v1/gestor/duvidas/<id>/prioridade ──────────────────────────────

@gestor_duvidas_bp.patch('/duvidas/<int:duvida_id>/prioridade')
@_STAFF_REQUIRED
@feature_required('duvidas_cliente')
def alterar_prioridade(duvida_id):
    d = _get_duvida_ou_404(duvida_id)
    dados = request.get_json(silent=True) or {}
    prioridade = (dados.get('prioridade') or '').strip().lower()
    if prioridade not in PrioridadeDuvida.TODOS:
        raise APIError(f'"prioridade" inválida: "{prioridade}".', 422)

    if prioridade == d.prioridade:
        return jsonify({'mensagem': 'Prioridade inalterada.', 'prioridade': d.prioridade}), 200

    anterior = d.prioridade
    d.prioridade = prioridade
    registrar_evento(
        duvida=d, tipo=TipoEventoDuvida.PRIORIDADE_ALTERADA,
        valor_anterior=anterior, valor_novo=prioridade, autor_usuario_id=g.user_id,
    )
    commit_ou_falhar('gestor.duvidas.alterar_prioridade')

    if prioridade == PrioridadeDuvida.URGENTE:
        disparar_webhook(g.barbearia_id, TipoEventoWebhook.DUVIDA_URGENTE, {
            'duvida_id': d.id, 'cliente_id': d.cliente_id, 'assunto': d.assunto,
        })

    return jsonify({'mensagem': 'Prioridade atualizada.', 'prioridade': d.prioridade}), 200


# ── PUT /api/v1/gestor/duvidas/<id>/concluir ──────────────────────────────────

@gestor_duvidas_bp.put('/duvidas/<int:duvida_id>/concluir')
@_STAFF_REQUIRED
@feature_required('duvidas_cliente')
def concluir_duvida(duvida_id):
    d = _get_duvida_ou_404(duvida_id)
    if d.status != StatusClienteDuvida.PENDENTE:
        raise APIError('Só é possível concluir um ticket pendente.', 422)

    anterior = d.status
    d.status = StatusClienteDuvida.CONCLUIDA
    registrar_evento(
        duvida=d, tipo=TipoEventoDuvida.SITUACAO_ALTERADA,
        valor_anterior=anterior, valor_novo=d.status, autor_usuario_id=g.user_id,
    )
    commit_ou_falhar('gestor.duvidas.concluir_duvida')
    registrar_auditoria(g.user_id, g.barbearia_id, 'edit', 'cliente_duvida', d.id, f'Concluiu a dúvida #{d.id}.')
    return jsonify({'mensagem': 'Dúvida concluída.'}), 200


# ── PUT /api/v1/gestor/duvidas/<id>/cancelar ──────────────────────────────────
# Único jeito de chegar em 'cancelada' — cliente não pode. Não reabre sozinho.

@gestor_duvidas_bp.put('/duvidas/<int:duvida_id>/cancelar')
@_STAFF_REQUIRED
@feature_required('duvidas_cliente')
def cancelar_duvida(duvida_id):
    d = _get_duvida_ou_404(duvida_id)
    if d.status == StatusClienteDuvida.CANCELADA:
        raise APIError('Este ticket já está cancelado.', 422)

    anterior = d.status
    d.status = StatusClienteDuvida.CANCELADA
    registrar_evento(
        duvida=d, tipo=TipoEventoDuvida.SITUACAO_ALTERADA,
        valor_anterior=anterior, valor_novo=d.status, autor_usuario_id=g.user_id,
    )
    commit_ou_falhar('gestor.duvidas.cancelar_duvida')
    registrar_auditoria(g.user_id, g.barbearia_id, 'edit', 'cliente_duvida', d.id, f'Cancelou a dúvida #{d.id}.')
    return jsonify({'mensagem': 'Dúvida cancelada.'}), 200


# ── PUT /api/v1/gestor/duvidas/<id>/encaminhar-admin ──────────────────────────
# Destaca o ticket pra fila do admin (que já enxerga tudo — isso é só um
# realce/filtro, ver app/routes/super/duvidas.py). Útil quando gestor/
# barbeiro não conseguem resolver sozinhos e querem sinalizar pro suporte
# da plataforma.

@gestor_duvidas_bp.put('/duvidas/<int:duvida_id>/encaminhar-admin')
@_STAFF_REQUIRED
@feature_required('duvidas_cliente')
def encaminhar_admin(duvida_id):
    d = _get_duvida_ou_404(duvida_id)
    if d.encaminhado_admin:
        return jsonify({'mensagem': 'Este ticket já está encaminhado ao admin.'}), 200

    d.encaminhado_admin = True
    registrar_evento(
        duvida=d, tipo=TipoEventoDuvida.DIRECIONADO_ADMIN,
        valor_anterior=None, valor_novo='admin', autor_usuario_id=g.user_id,
    )
    commit_ou_falhar('gestor.duvidas.encaminhar_admin')
    registrar_auditoria(g.user_id, g.barbearia_id, 'edit', 'cliente_duvida', d.id, f'Encaminhou a dúvida #{d.id} pro suporte da plataforma.')
    notificar_admins(d, 'Ticket encaminhado pelo estabelecimento', f'Assunto: "{d.assunto or "sem assunto"}"')
    return jsonify({'mensagem': 'Ticket encaminhado ao suporte da plataforma.'}), 200


# ── GET /api/v1/gestor/duvidas/excel ──────────────────────────────────────────

@gestor_duvidas_bp.get('/duvidas/excel')
@_STAFF_REQUIRED
@feature_required('duvidas_cliente')
def exportar_excel():
    """Exporta metadados das threads filtradas (imagem não entra no xlsx —
    só um link pra abrir a conversa na tela)."""
    status_f, categorias_f, prioridades_f, de, ate, precisa_resposta, q_busca = _parse_filtros()
    duvidas = _query_filtrada(status_f, categorias_f, prioridades_f, de, ate, precisa_resposta, q_busca).order_by(
        ClienteDuvida.criado_em.desc()
    ).all()

    clientes = {
        c.id: c for c in Cliente.query.filter(
            Cliente.id.in_({d.cliente_id for d in duvidas})
        ).all()
    } if duvidas else {}
    contagem_msgs = dict(
        db.session.query(
            ClienteDuvidaMensagem.duvida_id, db.func.count(ClienteDuvidaMensagem.id)
        )
        .filter(ClienteDuvidaMensagem.duvida_id.in_([d.id for d in duvidas]))
        .group_by(ClienteDuvidaMensagem.duvida_id)
        .all()
    ) if duvidas else {}

    _STATUS_LABEL = {'pendente': 'Pendente', 'concluida': 'Concluída', 'cancelada': 'Cancelada'}
    base_url = request.host_url.rstrip('/')
    dados = [{
        'cliente':    clientes.get(d.cliente_id).nome if clientes.get(d.cliente_id) else '—',
        'assunto':    d.assunto or '—',
        'categoria':  d.categoria,
        'prioridade': d.prioridade,
        'status':     _STATUS_LABEL.get(d.status, d.status),
        'mensagens':  contagem_msgs.get(d.id, 0),
        'aberta_em':  d.criado_em.strftime('%d/%m/%Y %H:%M') if d.criado_em else '—',
        'ultima_em':  d.ultima_mensagem_em.strftime('%d/%m/%Y %H:%M') if d.ultima_mensagem_em else '—',
        'nota':       d.nota_satisfacao if d.nota_satisfacao is not None else '—',
        'link':       f'{base_url}/gestor/duvidas-cliente?id={d.id}',
    } for d in duvidas]

    barbearia = db.session.get(Barbearia, g.barbearia_id)
    nome_barbearia = (barbearia.nome_exibicao or barbearia.nome) if barbearia else 'Barbearia'
    periodo = f'{de.strftime("%d/%m/%Y")} a {ate.strftime("%d/%m/%Y")}'

    buf = gerar_excel(
        dados, list(_COLUNAS_EXCEL.keys()), nome_barbearia, periodo,
        titulo=f'Dúvidas do Cliente — {periodo}',
        colunas_catalogo=_COLUNAS_EXCEL,
    )
    nome_arquivo = (
        f'duvidas_{nome_barbearia.lower().replace(" ", "_")}'
        f'_{de.isoformat()}_{ate.isoformat()}.xlsx'
    )
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=nome_arquivo,
    )
