"""Suporte (Dúvidas do Cliente) — fila cross-tenant do admin. Mesmo padrão
já usado em super/auditoria.py (vs gestor/auditoria.py) e
super/solicitacoes_senha.py (vs gestor/solicitacoes_senha.py): o admin
enxerga TODOS os tickets de TODAS as barbearias por padrão — não precisa
de nenhum "encaminhamento" pra aparecer aqui. `encaminhado_admin` é só um
realce/filtro (setado pelo gestor/barbeiro, ver gestor/duvidas.py) pra
destacar tickets que pediram ajuda da plataforma explicitamente.
Núcleo de criação de mensagem compartilhado em app/utils/duvidas.py."""
from collections import OrderedDict
from datetime import date
from flask import Blueprint, request, g, jsonify, send_file
from app.extensions import db
from app.models import (
    ClienteDuvida, ClienteDuvidaMensagem, ClienteDuvidaEvento,
    Cliente, Barbearia, Usuario,
)
from app.exceptions import APIError
from app.decorators.auth import super_required
from app.utils.db import commit_ou_falhar
from app.utils.tz import hoje_brasilia, limites_utc_do_dia_brasilia
from app.utils.webhooks import disparar_webhook
from app.utils.comprovante_link import gerar_link_comprovante
from app.utils.notificacoes import notificar
from app.utils.auditoria import registrar_auditoria
from app.utils.duvidas import (
    criar_mensagem, registrar_evento, query_precisa_resposta,
    ordenar_por_prioridade_e_recencia, notificar_responsaveis,
)
from app.utils.relatorio import gerar_excel
from app.constants import (
    StatusClienteDuvida, AutorTipoDuvida, TipoEventoWebhook,
    CategoriaDuvida, PrioridadeDuvida, TipoEventoDuvida,
)

super_duvidas_bp = Blueprint('super_duvidas', __name__, url_prefix='/api/v1/super/duvidas')

_COLUNAS_EXCEL = OrderedDict([
    ('barbearia',  {'label': 'Barbearia'}),
    ('cliente',    {'label': 'Cliente'}),
    ('assunto',    {'label': 'Assunto'}),
    ('categoria',  {'label': 'Categoria'}),
    ('prioridade', {'label': 'Prioridade'}),
    ('status',     {'label': 'Situação'}),
    ('atribuido',  {'label': 'Atribuído a'}),
    ('mensagens',  {'label': 'Nº Mensagens'}),
    ('aberta_em',  {'label': 'Aberta em'}),
    ('ultima_em',  {'label': 'Última mensagem em'}),
    ('nota',       {'label': 'Nota CSAT'}),
    ('link',       {'label': 'Link da conversa'}),
])


def _get_duvida_ou_404(duvida_id):
    d = db.session.get(ClienteDuvida, duvida_id)
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
    encaminhado       = request.args.get('encaminhado') == '1'
    atribuido_f       = request.args.get('atribuido')  # 'me' | 'nenhum' | None
    q_busca = (request.args.get('q') or '').strip()

    return status_f, categorias_f, prioridades_f, de, ate, precisa_resposta, encaminhado, atribuido_f, q_busca


def _query_filtrada(status_f, categorias_f, prioridades_f, de, ate, precisa_resposta, encaminhado, atribuido_f, q_busca):
    q = query_precisa_resposta(None) if precisa_resposta else ClienteDuvida.query

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
    if encaminhado:
        q = q.filter(ClienteDuvida.encaminhado_admin.is_(True))
    if atribuido_f == 'me':
        q = q.filter(ClienteDuvida.atribuido_a_usuario_id == g.user_id)
    elif atribuido_f == 'nenhum':
        q = q.filter(ClienteDuvida.atribuido_a_usuario_id.is_(None))
    if q_busca:
        termo = f'%{q_busca}%'
        ids_por_mensagem = db.session.query(ClienteDuvidaMensagem.duvida_id).filter(
            ClienteDuvidaMensagem.texto.ilike(termo)
        )
        q = q.filter(db.or_(ClienteDuvida.assunto.ilike(termo), ClienteDuvida.id.in_(ids_por_mensagem)))
    return q


# ── GET /api/v1/super/duvidas ─────────────────────────────────────────────────

@super_duvidas_bp.get('')
@super_required
def listar_duvidas():
    status_f, categorias_f, prioridades_f, de, ate, precisa_resposta, encaminhado, atribuido_f, q_busca = _parse_filtros()

    try:
        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 20))))
    except ValueError:
        raise APIError('"page" e "per_page" devem ser inteiros.', 422)

    q = _query_filtrada(status_f, categorias_f, prioridades_f, de, ate, precisa_resposta, encaminhado, atribuido_f, q_busca)
    q = ordenar_por_prioridade_e_recencia(q, ClienteDuvida.prioridade, ClienteDuvida.ultima_mensagem_em)
    paginado = q.paginate(page=page, per_page=per_page, error_out=False)

    itens = paginado.items
    clientes = {
        c.id: c for c in Cliente.query.filter(Cliente.id.in_({d.cliente_id for d in itens})).all()
    } if itens else {}
    barbearias = {
        b.id: b for b in Barbearia.query.filter(Barbearia.id.in_({d.barbearia_id for d in itens})).all()
    } if itens else {}
    atribuidos_ids = {d.atribuido_a_usuario_id for d in itens if d.atribuido_a_usuario_id}
    atribuidos = {u.id: u for u in Usuario.query.filter(Usuario.id.in_(atribuidos_ids)).all()} if atribuidos_ids else {}
    ultimas = _mapa_ultimas_mensagens([d.id for d in itens])

    def _fmt(d):
        cli = clientes.get(d.cliente_id)
        bk = barbearias.get(d.barbearia_id)
        atrib = atribuidos.get(d.atribuido_a_usuario_id)
        ultima = ultimas.get(d.id)
        preview = None
        if ultima:
            preview = ultima.texto[:120] if ultima.texto else ('📷 Imagem' if ultima.imagens else None)
        return {
            'id':                      d.id,
            'barbearia':               {'id': bk.id, 'nome': bk.nome_exibicao or bk.nome} if bk else None,
            'cliente':                 {'id': cli.id, 'nome': cli.nome, 'telefone': cli.telefone} if cli else None,
            'assunto':                 d.assunto,
            'categoria':               d.categoria,
            'prioridade':              d.prioridade,
            'status':                  d.status,
            'encaminhado_admin':       d.encaminhado_admin,
            'atribuido_a':             {'id': atrib.id, 'nome': atrib.nome} if atrib else None,
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


# ── GET /api/v1/super/duvidas/<id> ────────────────────────────────────────────

@super_duvidas_bp.get('/<int:duvida_id>')
@super_required
def detalhar_duvida(duvida_id):
    d = _get_duvida_ou_404(duvida_id)
    cli = db.session.get(Cliente, d.cliente_id)
    bk = db.session.get(Barbearia, d.barbearia_id)

    mensagens = ClienteDuvidaMensagem.query.filter_by(duvida_id=d.id).order_by(ClienteDuvidaMensagem.id).all()
    eventos = ClienteDuvidaEvento.query.filter_by(duvida_id=d.id).order_by(ClienteDuvidaEvento.criado_em.desc()).all()
    autor_ids = {e.autor_usuario_id for e in eventos if e.autor_usuario_id}
    usuarios_map = {u.id: u for u in Usuario.query.filter(Usuario.id.in_(autor_ids)).all()} if autor_ids else {}

    return jsonify({
        'id':                    d.id,
        'barbearia':             {'id': bk.id, 'nome': bk.nome_exibicao or bk.nome} if bk else None,
        'cliente':               {'id': cli.id, 'nome': cli.nome, 'telefone': cli.telefone} if cli else None,
        'assunto':               d.assunto,
        'categoria':             d.categoria,
        'prioridade':            d.prioridade,
        'status':                d.status,
        'encaminhado_admin':     d.encaminhado_admin,
        'atribuido_a_usuario_id': d.atribuido_a_usuario_id,
        'nota_satisfacao':       d.nota_satisfacao,
        'comentario_satisfacao': d.comentario_satisfacao,
        'criado_em':             d.criado_em.isoformat() if d.criado_em else None,
        'mensagens':             [_fmt_mensagem(m) for m in mensagens],
        'timeline':              [_fmt_evento(e, usuarios_map) for e in eventos],
    }), 200


# ── POST /api/v1/super/duvidas/<id>/mensagens ─────────────────────────────────

@super_duvidas_bp.post('/<int:duvida_id>/mensagens')
@super_required
def responder_duvida(duvida_id):
    d = _get_duvida_ou_404(duvida_id)
    if d.status == StatusClienteDuvida.CANCELADA:
        raise APIError('Este ticket foi cancelado e não aceita novas mensagens.', 422)

    texto    = request.form.get('texto')
    arquivos = request.files.getlist('imagens')

    msg = criar_mensagem(
        duvida=d, barbearia_id=d.barbearia_id,
        autor_usuario_id=g.user_id, autor_tipo=AutorTipoDuvida.ADMIN,
        texto=texto, arquivos_imagem=arquivos,
    )
    d.nao_lida_cliente = True

    commit_ou_falhar('super.duvidas.responder_duvida')

    cli = db.session.get(Cliente, d.cliente_id)
    if cli and cli.usuario_id:
        notificar(
            barbearia_id=d.barbearia_id,
            usuario_id=cli.usuario_id,
            tipo='duvida_respondida',
            titulo='Sua dúvida foi respondida',
            mensagem=d.assunto or 'Você recebeu uma nova resposta na sua dúvida.',
            link=f'/cliente/duvidas?id={d.id}',
            canal='in_app',
        )

    # Além de notificar o cliente, avisa gestor/barbeiro que acompanham o
    # ticket — o admin respondeu no canal interno (item 4 do pedido).
    notificar_responsaveis(d, 'O suporte da plataforma respondeu', 'O admin respondeu no ticket de suporte.')

    registrar_auditoria(g.user_id, d.barbearia_id, 'edit', 'cliente_duvida', d.id, f'[admin] Respondeu a dúvida #{d.id}.')

    disparar_webhook(d.barbearia_id, TipoEventoWebhook.DUVIDA_NOVA_MENSAGEM, {
        'duvida_id': d.id, 'cliente_id': d.cliente_id, 'autor_tipo': AutorTipoDuvida.ADMIN,
    })

    return jsonify({'mensagem': 'Resposta enviada.', 'mensagem_id': msg.id}), 201


# ── PATCH /api/v1/super/duvidas/<id>/categoria ────────────────────────────────

@super_duvidas_bp.patch('/<int:duvida_id>/categoria')
@super_required
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
    commit_ou_falhar('super.duvidas.alterar_categoria')
    return jsonify({'mensagem': 'Categoria atualizada.', 'categoria': d.categoria}), 200


# ── PATCH /api/v1/super/duvidas/<id>/prioridade ───────────────────────────────

@super_duvidas_bp.patch('/<int:duvida_id>/prioridade')
@super_required
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
    commit_ou_falhar('super.duvidas.alterar_prioridade')

    if prioridade == PrioridadeDuvida.URGENTE:
        disparar_webhook(d.barbearia_id, TipoEventoWebhook.DUVIDA_URGENTE, {
            'duvida_id': d.id, 'cliente_id': d.cliente_id, 'assunto': d.assunto,
        })

    return jsonify({'mensagem': 'Prioridade atualizada.', 'prioridade': d.prioridade}), 200


# ── PUT /api/v1/super/duvidas/<id>/concluir | /cancelar ───────────────────────

@super_duvidas_bp.put('/<int:duvida_id>/concluir')
@super_required
def concluir_duvida(duvida_id):
    d = _get_duvida_ou_404(duvida_id)
    if d.status != StatusClienteDuvida.PENDENTE:
        raise APIError('Só é possível concluir um ticket pendente.', 422)
    anterior = d.status
    d.status = StatusClienteDuvida.CONCLUIDA
    registrar_evento(duvida=d, tipo=TipoEventoDuvida.SITUACAO_ALTERADA, valor_anterior=anterior, valor_novo=d.status, autor_usuario_id=g.user_id)
    commit_ou_falhar('super.duvidas.concluir_duvida')
    registrar_auditoria(g.user_id, d.barbearia_id, 'edit', 'cliente_duvida', d.id, f'[admin] Concluiu a dúvida #{d.id}.')
    return jsonify({'mensagem': 'Dúvida concluída.'}), 200


@super_duvidas_bp.put('/<int:duvida_id>/cancelar')
@super_required
def cancelar_duvida(duvida_id):
    d = _get_duvida_ou_404(duvida_id)
    if d.status == StatusClienteDuvida.CANCELADA:
        raise APIError('Este ticket já está cancelado.', 422)
    anterior = d.status
    d.status = StatusClienteDuvida.CANCELADA
    registrar_evento(duvida=d, tipo=TipoEventoDuvida.SITUACAO_ALTERADA, valor_anterior=anterior, valor_novo=d.status, autor_usuario_id=g.user_id)
    commit_ou_falhar('super.duvidas.cancelar_duvida')
    registrar_auditoria(g.user_id, d.barbearia_id, 'edit', 'cliente_duvida', d.id, f'[admin] Cancelou a dúvida #{d.id}.')
    return jsonify({'mensagem': 'Dúvida cancelada.'}), 200


# ── PUT /api/v1/super/duvidas/<id>/atribuir | /desatribuir ───────────────────

@super_duvidas_bp.put('/<int:duvida_id>/atribuir')
@super_required
def atribuir_duvida(duvida_id):
    d = _get_duvida_ou_404(duvida_id)
    anterior = d.atribuido_a_usuario_id
    d.atribuido_a_usuario_id = g.user_id
    registrar_evento(
        duvida=d, tipo=TipoEventoDuvida.ATRIBUIDO,
        valor_anterior=anterior, valor_novo=g.user_id, autor_usuario_id=g.user_id,
    )
    commit_ou_falhar('super.duvidas.atribuir_duvida')
    return jsonify({'mensagem': 'Ticket atribuído a você.', 'atribuido_a_usuario_id': d.atribuido_a_usuario_id}), 200


@super_duvidas_bp.put('/<int:duvida_id>/desatribuir')
@super_required
def desatribuir_duvida(duvida_id):
    d = _get_duvida_ou_404(duvida_id)
    anterior = d.atribuido_a_usuario_id
    d.atribuido_a_usuario_id = None
    registrar_evento(
        duvida=d, tipo=TipoEventoDuvida.ATRIBUIDO,
        valor_anterior=anterior, valor_novo=None, autor_usuario_id=g.user_id,
    )
    commit_ou_falhar('super.duvidas.desatribuir_duvida')
    return jsonify({'mensagem': 'Atribuição removida.'}), 200


# ── GET /api/v1/super/duvidas/excel ───────────────────────────────────────────

@super_duvidas_bp.get('/excel')
@super_required
def exportar_excel():
    status_f, categorias_f, prioridades_f, de, ate, precisa_resposta, encaminhado, atribuido_f, q_busca = _parse_filtros()
    duvidas = _query_filtrada(status_f, categorias_f, prioridades_f, de, ate, precisa_resposta, encaminhado, atribuido_f, q_busca).order_by(
        ClienteDuvida.criado_em.desc()
    ).all()

    clientes = {c.id: c for c in Cliente.query.filter(Cliente.id.in_({d.cliente_id for d in duvidas})).all()} if duvidas else {}
    barbearias = {b.id: b for b in Barbearia.query.filter(Barbearia.id.in_({d.barbearia_id for d in duvidas})).all()} if duvidas else {}
    atribuidos_ids = {d.atribuido_a_usuario_id for d in duvidas if d.atribuido_a_usuario_id}
    atribuidos = {u.id: u for u in Usuario.query.filter(Usuario.id.in_(atribuidos_ids)).all()} if atribuidos_ids else {}
    contagem_msgs = dict(
        db.session.query(ClienteDuvidaMensagem.duvida_id, db.func.count(ClienteDuvidaMensagem.id))
        .filter(ClienteDuvidaMensagem.duvida_id.in_([d.id for d in duvidas]))
        .group_by(ClienteDuvidaMensagem.duvida_id).all()
    ) if duvidas else {}

    _STATUS_LABEL = {'pendente': 'Pendente', 'concluida': 'Concluída', 'cancelada': 'Cancelada'}
    base_url = request.host_url.rstrip('/')
    dados = [{
        'barbearia':  (barbearias.get(d.barbearia_id).nome_exibicao or barbearias.get(d.barbearia_id).nome) if barbearias.get(d.barbearia_id) else '—',
        'cliente':    clientes.get(d.cliente_id).nome if clientes.get(d.cliente_id) else '—',
        'assunto':    d.assunto or '—',
        'categoria':  d.categoria,
        'prioridade': d.prioridade,
        'status':     _STATUS_LABEL.get(d.status, d.status),
        'atribuido':  atribuidos.get(d.atribuido_a_usuario_id).nome if atribuidos.get(d.atribuido_a_usuario_id) else '—',
        'mensagens':  contagem_msgs.get(d.id, 0),
        'aberta_em':  d.criado_em.strftime('%d/%m/%Y %H:%M') if d.criado_em else '—',
        'ultima_em':  d.ultima_mensagem_em.strftime('%d/%m/%Y %H:%M') if d.ultima_mensagem_em else '—',
        'nota':       d.nota_satisfacao if d.nota_satisfacao is not None else '—',
        'link':       f'{base_url}/super/duvidas?id={d.id}',
    } for d in duvidas]

    periodo = f'{de.strftime("%d/%m/%Y")} a {ate.strftime("%d/%m/%Y")}'
    buf = gerar_excel(
        dados, list(_COLUNAS_EXCEL.keys()), 'BarberOS — Suporte (todas as barbearias)', periodo,
        titulo=f'Suporte — {periodo}',
        colunas_catalogo=_COLUNAS_EXCEL,
    )
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'suporte_todas_barbearias_{de.isoformat()}_{ate.isoformat()}.xlsx',
    )
