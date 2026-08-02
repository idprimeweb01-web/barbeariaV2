from datetime import date
from flask import Blueprint, request, g, jsonify
from app.extensions import db
from app.models import Cupom, CupomServico, CupomProduto, CupomUso, Servico, Produto, Cliente
from app.exceptions import APIError
from app.decorators.auth import gestor_required
from app.utils.features import feature_required
from app.utils.tz import hoje_brasilia
from app.utils.db import commit_ou_falhar
from app.utils.auditoria import registrar_auditoria

cupons_bp = Blueprint('gestor_cupons', __name__, url_prefix='/api/v1/gestor')

_TIPOS = {'percentual', 'valor_fixo'}
_MODOS = {'nenhum', 'todos', 'selecionar'}


def _resolver_modo(dados, chave_modo, chave_ids, model, barbearia_id, nome_recurso):
    """Lê '{chave_modo}' ('nenhum'|'todos'|'selecionar') + '{chave_ids}' do
    payload e retorna (veio_no_payload, aplica_todos, ids_validados).
    'nenhum' = cupom não cobre nada dessa dimensão (comportamento padrão).
    'todos'  = cobre qualquer item dessa dimensão, presente ou futuro.
    'selecionar' = cobre só os ids informados em '{chave_ids}'."""
    if chave_modo not in dados:
        return False, None, None

    modo = dados.get(chave_modo)
    if modo not in _MODOS:
        raise APIError(f'"{chave_modo}" deve ser "nenhum", "todos" ou "selecionar".', 422)

    if modo != 'selecionar':
        return True, (modo == 'todos'), []

    ids = dados.get(chave_ids) or []
    if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
        raise APIError(f'"{chave_ids}" deve ser uma lista de inteiros.', 422)
    if not ids:
        raise APIError(f'Selecione ao menos um {nome_recurso}, ou mude o modo pra "nenhum"/"todos".', 422)
    encontrados = {r.id for r in model.query.filter(
        model.id.in_(ids), model.barbearia_id == barbearia_id
    ).all()}
    faltando = set(ids) - encontrados
    if faltando:
        raise APIError(f'{nome_recurso.capitalize()}(s) não encontrado(s): {sorted(faltando)}.', 404)
    return True, False, ids


def _fmt_cupom(c):
    servicos = (
        db.session.query(Servico)
        .join(CupomServico, CupomServico.servico_id == Servico.id)
        .filter(CupomServico.cupom_id == c.id)
        .all()
    )
    produtos = (
        db.session.query(Produto)
        .join(CupomProduto, CupomProduto.produto_id == Produto.id)
        .filter(CupomProduto.cupom_id == c.id)
        .all()
    )
    servicos_modo = 'todos' if c.aplica_todos_servicos else ('selecionar' if servicos else 'nenhum')
    produtos_modo = 'todos' if c.aplica_todos_produtos else ('selecionar' if produtos else 'nenhum')
    return {
        'id':                     c.id,
        'barbearia_id':           c.barbearia_id,
        'nome':                   c.nome,
        'codigo':                 c.codigo,
        'tipo_desconto':          c.tipo_desconto,
        'valor_desconto':         float(c.valor_desconto),
        'data_expiracao':         c.data_expiracao.isoformat(),
        'quantidade_maxima_usos': c.quantidade_maxima_usos,
        'quantidade_usos':        c.quantidade_usos,
        'limite_uso_por_cliente': c.limite_uso_por_cliente,
        'ativo':                  c.ativo,
        'expirado':               c.data_expiracao < hoje_brasilia(),
        'servicos_modo':          servicos_modo,
        'servicos':               [{'id': s.id, 'nome': s.nome} for s in servicos],
        'produtos_modo':          produtos_modo,
        'produtos':               [{'id': p.id, 'nome': p.nome} for p in produtos],
    }


@cupons_bp.get('/cupons')
@gestor_required
@feature_required('cupons')
def listar_cupons():
    q = Cupom.query_tenant()
    ativo = request.args.get('ativo')
    if ativo == 'true':
        q = q.filter_by(ativo=True)
    elif ativo == 'false':
        q = q.filter_by(ativo=False)

    try:
        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 50))))
    except ValueError:
        raise APIError('"page" e "per_page" devem ser inteiros.', 422)

    paginado = q.order_by(Cupom.criado_em.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'dados':    [_fmt_cupom(c) for c in paginado.items],
        'page':     paginado.page,
        'per_page': paginado.per_page,
        'total':    paginado.total,
        'pages':    paginado.pages,
    }), 200


@cupons_bp.post('/cupons')
@gestor_required
@feature_required('cupons')
def criar_cupom():
    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    nome = (dados.get('nome') or '').strip()
    if not nome:
        raise APIError('"nome" é obrigatório.')

    codigo = (dados.get('codigo') or '').strip().upper()
    if not codigo:
        raise APIError('"codigo" é obrigatório.')

    tipo = (dados.get('tipo_desconto') or '').strip().lower()
    if tipo not in _TIPOS:
        raise APIError('"tipo_desconto" deve ser "percentual" ou "valor_fixo".')

    try:
        valor = float(dados.get('valor_desconto'))
        assert valor > 0
    except (TypeError, ValueError, AssertionError):
        raise APIError('"valor_desconto" deve ser um número positivo.')
    if tipo == 'percentual' and valor > 100:
        raise APIError('"valor_desconto" percentual não pode ser maior que 100.')

    data_exp_str = (dados.get('data_expiracao') or '').strip()
    if not data_exp_str:
        raise APIError('"data_expiracao" é obrigatório (YYYY-MM-DD).')
    try:
        data_exp = date.fromisoformat(data_exp_str)
    except ValueError:
        raise APIError('"data_expiracao" inválido. Use YYYY-MM-DD.')

    qtd_max = dados.get('quantidade_maxima_usos')
    if qtd_max is not None:
        try:
            qtd_max = int(qtd_max)
            assert qtd_max > 0
        except (TypeError, ValueError, AssertionError):
            raise APIError('"quantidade_maxima_usos" deve ser um inteiro positivo (ou omitido).')

    limite_cliente = dados.get('limite_uso_por_cliente')
    if limite_cliente is not None:
        try:
            limite_cliente = int(limite_cliente)
            assert limite_cliente > 0
        except (TypeError, ValueError, AssertionError):
            raise APIError('"limite_uso_por_cliente" deve ser um inteiro positivo (ou omitido).')

    if Cupom.query.filter_by(barbearia_id=g.barbearia_id, codigo=codigo).first():
        raise APIError(f'Já existe um cupom com o código "{codigo}".', 409)

    _, aplica_todos_servicos, servico_ids = _resolver_modo(
        dados, 'servicos_modo', 'servico_ids', Servico, g.barbearia_id, 'serviço')
    _, aplica_todos_produtos, produto_ids = _resolver_modo(
        dados, 'produtos_modo', 'produto_ids', Produto, g.barbearia_id, 'produto')

    c = Cupom(
        barbearia_id=g.barbearia_id,
        nome=nome,
        codigo=codigo,
        tipo_desconto=tipo,
        valor_desconto=valor,
        data_expiracao=data_exp,
        quantidade_maxima_usos=qtd_max,
        limite_uso_por_cliente=limite_cliente,
        ativo=dados.get('ativo', True) if isinstance(dados.get('ativo', True), bool) else True,
        aplica_todos_servicos=bool(aplica_todos_servicos),
        aplica_todos_produtos=bool(aplica_todos_produtos),
    )
    db.session.add(c)
    db.session.flush()

    for sid in (servico_ids or []):
        db.session.add(CupomServico(cupom_id=c.id, servico_id=sid))
    for pid in (produto_ids or []):
        db.session.add(CupomProduto(cupom_id=c.id, produto_id=pid))

    commit_ou_falhar('gestor.cupons.criar_cupom')
    registrar_auditoria(g.user_id, g.barbearia_id, 'create', 'cupom', c.id,
                         f'Criou o cupom "{c.codigo}" ({valor}{"%" if tipo == "percentual" else " R$"} de desconto).')
    return jsonify(_fmt_cupom(c)), 201


@cupons_bp.patch('/cupons/<int:cupom_id>')
@gestor_required
@feature_required('cupons')
def editar_cupom(cupom_id):
    c = Cupom.query_tenant().filter_by(id=cupom_id).first()
    if not c:
        raise APIError('Cupom não encontrado.', 404)

    dados = request.get_json(silent=True) or {}

    if 'nome' in dados:
        nome = (dados.get('nome') or '').strip()
        if not nome:
            raise APIError('"nome" não pode ser vazio.')
        c.nome = nome

    if 'codigo' in dados:
        codigo = (dados.get('codigo') or '').strip().upper()
        if not codigo:
            raise APIError('"codigo" não pode ser vazio.')
        existente = Cupom.query.filter_by(barbearia_id=g.barbearia_id, codigo=codigo).first()
        if existente and existente.id != c.id:
            raise APIError(f'Já existe um cupom com o código "{codigo}".', 409)
        c.codigo = codigo

    if 'tipo_desconto' in dados:
        tipo = (dados.get('tipo_desconto') or '').strip().lower()
        if tipo not in _TIPOS:
            raise APIError('"tipo_desconto" deve ser "percentual" ou "valor_fixo".')
        c.tipo_desconto = tipo

    if 'valor_desconto' in dados:
        try:
            valor = float(dados.get('valor_desconto'))
            assert valor > 0
        except (TypeError, ValueError, AssertionError):
            raise APIError('"valor_desconto" deve ser um número positivo.')
        if c.tipo_desconto == 'percentual' and valor > 100:
            raise APIError('"valor_desconto" percentual não pode ser maior que 100.')
        c.valor_desconto = valor

    if 'data_expiracao' in dados:
        try:
            c.data_expiracao = date.fromisoformat((dados.get('data_expiracao') or '').strip())
        except ValueError:
            raise APIError('"data_expiracao" inválido. Use YYYY-MM-DD.')

    if 'quantidade_maxima_usos' in dados:
        qtd_max = dados.get('quantidade_maxima_usos')
        if qtd_max is not None:
            try:
                qtd_max = int(qtd_max)
                assert qtd_max > 0
            except (TypeError, ValueError, AssertionError):
                raise APIError('"quantidade_maxima_usos" deve ser um inteiro positivo (ou nulo).')
        c.quantidade_maxima_usos = qtd_max

    if 'limite_uso_por_cliente' in dados:
        limite_cliente = dados.get('limite_uso_por_cliente')
        if limite_cliente is not None:
            try:
                limite_cliente = int(limite_cliente)
                assert limite_cliente > 0
            except (TypeError, ValueError, AssertionError):
                raise APIError('"limite_uso_por_cliente" deve ser um inteiro positivo (ou nulo).')
        c.limite_uso_por_cliente = limite_cliente

    if 'ativo' in dados and isinstance(dados.get('ativo'), bool):
        c.ativo = dados['ativo']

    tem_servicos, aplica_todos_servicos, servico_ids = _resolver_modo(
        dados, 'servicos_modo', 'servico_ids', Servico, g.barbearia_id, 'serviço')
    if tem_servicos:
        c.aplica_todos_servicos = aplica_todos_servicos
        CupomServico.query.filter_by(cupom_id=c.id).delete()
        for sid in servico_ids:
            db.session.add(CupomServico(cupom_id=c.id, servico_id=sid))

    tem_produtos, aplica_todos_produtos, produto_ids = _resolver_modo(
        dados, 'produtos_modo', 'produto_ids', Produto, g.barbearia_id, 'produto')
    if tem_produtos:
        c.aplica_todos_produtos = aplica_todos_produtos
        CupomProduto.query.filter_by(cupom_id=c.id).delete()
        for pid in produto_ids:
            db.session.add(CupomProduto(cupom_id=c.id, produto_id=pid))

    commit_ou_falhar('gestor.cupons.editar_cupom')
    registrar_auditoria(g.user_id, g.barbearia_id, 'edit', 'cupom', c.id, f'Editou o cupom "{c.codigo}".')
    return jsonify(_fmt_cupom(c)), 200


@cupons_bp.get('/cupons/<int:cupom_id>/uso')
@gestor_required
@feature_required('cupons')
def relatorio_uso_cupom(cupom_id):
    """Relatório completo de uso: quem usou, quando, quanto foi descontado —
    o que a tabela `usos` alimenta na tela de editar/remover cupom."""
    c = Cupom.query_tenant().filter_by(id=cupom_id).first()
    if not c:
        raise APIError('Cupom não encontrado.', 404)

    usos = (
        CupomUso.query
        .filter_by(cupom_id=c.id, barbearia_id=g.barbearia_id)
        .order_by(CupomUso.criado_em.desc())
        .all()
    )
    cliente_ids = {u.cliente_id for u in usos if u.cliente_id}
    clientes = {cli.id: cli for cli in Cliente.query.filter(Cliente.id.in_(cliente_ids)).all()} if cliente_ids else {}

    usos_fmt = [
        {
            'cliente_nome':   clientes[u.cliente_id].nome if u.cliente_id in clientes else 'Cliente sem cadastro',
            'agendamento_id': u.agendamento_id,
            'venda_id':       u.venda_id,
            'valor_original': float(u.valor_original),
            'valor_desconto': float(u.valor_desconto),
            'valor_final':    float(u.valor_final),
            'criado_em':      u.criado_em.isoformat() if u.criado_em else None,
        }
        for u in usos
    ]

    restantes = (c.quantidade_maxima_usos - c.quantidade_usos) if c.quantidade_maxima_usos is not None else None

    return jsonify({
        'cupom':                  _fmt_cupom(c),
        'usos_restantes':         max(restantes, 0) if restantes is not None else None,
        'valor_total_descontado': float(round(sum(u.valor_desconto for u in usos), 2)),
        'usos':                   usos_fmt,
    }), 200


@cupons_bp.delete('/cupons/<int:cupom_id>')
@gestor_required
@feature_required('cupons')
def excluir_cupom(cupom_id):
    c = Cupom.query_tenant().filter_by(id=cupom_id).first()
    if not c:
        raise APIError('Cupom não encontrado.', 404)
    c.ativo = False
    commit_ou_falhar('gestor.cupons.excluir_cupom')
    registrar_auditoria(g.user_id, g.barbearia_id, 'delete', 'cupom', c.id, f'Desativou o cupom "{c.codigo}".')
    return jsonify({'mensagem': 'Cupom desativado.'}), 200
