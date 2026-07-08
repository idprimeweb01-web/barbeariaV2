import os
import cloudinary
import cloudinary.uploader
from flask import Blueprint, request, g, jsonify
from app.extensions import db
from app.models import Servico, Produto, CategoriaProduto, MovimentacaoEstoque
from app.exceptions import APIError
from app.decorators.auth import gestor_required
from app.utils.features import feature_required
from app.utils.imagem import validar_upload_imagem
from app.utils import estoque as estoque_service
from app.labels import L
from app.utils.db import commit_ou_falhar

catalogo_bp = Blueprint('gestor_catalogo', __name__, url_prefix='/api/v1/gestor')


def _barbearia_id_atual():
    if g.barbearia_id:
        return g.barbearia_id
    raise APIError('Sem barbearia ativa no contexto.', 403)


def _fmt_servico(s):
    return {
        'id':               s.id,
        'barbearia_id':     s.barbearia_id,
        'nome':             s.nome,
        'descricao':        s.descricao,
        'duracao_minutos':  s.duracao_minutos,
        'preco':            float(s.preco),
        'foto':             s.foto,
        'ativo':            s.ativo,
    }


def _fmt_categoria(c):
    return {'id': c.id, 'nome': c.nome, 'ativo': c.ativo}


def _fmt_produto(p, categorias_map=None):
    """categorias_map: dict opcional {id: CategoriaProduto} pré-carregado em
    lote pela listagem (evita N+1 quando categoria_id está presente)."""
    categoria_nome = None
    if p.categoria_id:
        cat = categorias_map.get(p.categoria_id) if categorias_map is not None else db.session.get(CategoriaProduto, p.categoria_id)
        categoria_nome = cat.nome if cat else None

    custo = float(p.custo_unitario or 0)
    preco = float(p.preco)
    return {
        'id':                    p.id,
        'barbearia_id':          p.barbearia_id,
        'nome':                  p.nome,
        'categoria':             p.categoria,
        'categoria_id':          p.categoria_id,
        'categoria_nome':        categoria_nome,
        'marca':                 p.marca,
        'preco':                 preco,
        'custo_unitario':        custo,
        'margem':                round(preco - custo, 2),
        'codigo_barras':         p.codigo_barras,
        'quantidade_estoque':    p.quantidade_estoque,
        'quantidade_reservada':  p.quantidade_reservada,
        'quantidade_disponivel': p.quantidade_disponivel,
        'estoque_minimo':        p.estoque_minimo,
        'estoque_baixo':         p.quantidade_estoque <= p.estoque_minimo,
        'foto':                  p.foto,
        'foto_url':              p.foto_url,
        'ativo':                 p.ativo,
        'criado_em':             p.criado_em.isoformat() if p.criado_em else None,
    }


# ── Serviços ──────────────────────────────────────────────────────────────────

@catalogo_bp.get('/servicos')
@gestor_required
def listar_servicos():
    q = Servico.query_tenant()
    ativo = request.args.get('ativo')
    if ativo == 'true':
        q = q.filter_by(ativo=True)
    elif ativo == 'false':
        q = q.filter_by(ativo=False)
    return jsonify([_fmt_servico(s) for s in q.order_by(Servico.nome).all()]), 200


@catalogo_bp.post('/servicos')
@gestor_required
def criar_servico():
    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    nome    = (dados.get('nome') or '').strip()
    duracao = dados.get('duracao_minutos')
    preco   = dados.get('preco')

    if not nome:
        raise APIError('"nome" é obrigatório.')
    if not isinstance(duracao, int) or duracao <= 0:
        raise APIError('"duracao_minutos" deve ser um inteiro positivo.')
    try:
        preco = float(preco)
        assert preco >= 0
    except (TypeError, ValueError, AssertionError):
        raise APIError('"preco" deve ser um número não-negativo.')

    s = Servico(
        barbearia_id=_barbearia_id_atual(),
        nome=nome,
        descricao=(dados.get('descricao') or '').strip() or None,
        duracao_minutos=duracao,
        preco=preco,
        ativo=True,
    )
    db.session.add(s)
    commit_ou_falhar('gestor.catalogo.criar_servico')
    return jsonify(_fmt_servico(s)), 201


@catalogo_bp.get('/servicos/<int:servico_id>')
@gestor_required
def detalhar_servico(servico_id):
    s = Servico.query_tenant().filter_by(id=servico_id).first()
    if not s:
        raise APIError(f'{L("servico")} não encontrado.', 404)
    return jsonify(_fmt_servico(s)), 200


@catalogo_bp.patch('/servicos/<int:servico_id>')
@gestor_required
def editar_servico(servico_id):
    s = Servico.query_tenant().filter_by(id=servico_id).first()
    if not s:
        raise APIError(f'{L("servico")} não encontrado.', 404)

    dados = request.get_json(silent=True) or {}

    if 'nome' in dados:
        nome = (dados['nome'] or '').strip()
        if not nome:
            raise APIError('"nome" não pode ser vazio.')
        s.nome = nome
    if 'descricao' in dados:
        s.descricao = (dados['descricao'] or '').strip() or None
    if 'duracao_minutos' in dados:
        dur = dados['duracao_minutos']
        if not isinstance(dur, int) or dur <= 0:
            raise APIError('"duracao_minutos" deve ser um inteiro positivo.')
        s.duracao_minutos = dur
    if 'preco' in dados:
        try:
            p = float(dados['preco'])
            assert p >= 0
        except (TypeError, ValueError, AssertionError):
            raise APIError('"preco" deve ser um número não-negativo.')
        s.preco = p
    if 'ativo' in dados:
        s.ativo = bool(dados['ativo'])

    commit_ou_falhar('gestor.catalogo.editar_servico')
    return jsonify(_fmt_servico(s)), 200


@catalogo_bp.delete('/servicos/<int:servico_id>')
@gestor_required
def desativar_servico(servico_id):
    s = Servico.query_tenant().filter_by(id=servico_id).first()
    if not s:
        raise APIError(f'{L("servico")} não encontrado.', 404)
    s.ativo = False
    commit_ou_falhar('gestor.catalogo.desativar_servico')
    return jsonify({'mensagem': f'{L("servico")} desativado.'}), 200


# ── Categorias de produto (Script 18) ─────────────────────────────────────────

@catalogo_bp.get('/produtos/categorias')
@gestor_required
def listar_categorias_produto():
    q = CategoriaProduto.query_tenant()
    ativo = request.args.get('ativo')
    if ativo == 'true':
        q = q.filter_by(ativo=True)
    elif ativo == 'false':
        q = q.filter_by(ativo=False)
    return jsonify([_fmt_categoria(c) for c in q.order_by(CategoriaProduto.nome).all()]), 200


@catalogo_bp.post('/produtos/categorias')
@gestor_required
@feature_required('produtos_venda')
def criar_categoria_produto():
    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')
    nome = (dados.get('nome') or '').strip()
    if not nome:
        raise APIError('"nome" é obrigatório.')

    bid = _barbearia_id_atual()
    if CategoriaProduto.query.filter_by(barbearia_id=bid, nome=nome).first():
        raise APIError('Já existe uma categoria com este nome.', 409)

    c = CategoriaProduto(barbearia_id=bid, nome=nome, ativo=True)
    db.session.add(c)
    commit_ou_falhar('gestor.catalogo.criar_categoria_produto')
    return jsonify(_fmt_categoria(c)), 201


@catalogo_bp.patch('/produtos/categorias/<int:categoria_id>')
@gestor_required
@feature_required('produtos_venda')
def editar_categoria_produto(categoria_id):
    c = CategoriaProduto.query_tenant().filter_by(id=categoria_id).first()
    if not c:
        raise APIError('Categoria não encontrada.', 404)
    dados = request.get_json(silent=True) or {}
    if 'nome' in dados:
        nome = (dados['nome'] or '').strip()
        if not nome:
            raise APIError('"nome" não pode ser vazio.')
        dup = CategoriaProduto.query.filter_by(barbearia_id=c.barbearia_id, nome=nome).first()
        if dup and dup.id != c.id:
            raise APIError('Já existe uma categoria com este nome.', 409)
        c.nome = nome
    if 'ativo' in dados:
        c.ativo = bool(dados['ativo'])
    commit_ou_falhar('gestor.catalogo.editar_categoria_produto')
    return jsonify(_fmt_categoria(c)), 200


@catalogo_bp.delete('/produtos/categorias/<int:categoria_id>')
@gestor_required
@feature_required('produtos_venda')
def desativar_categoria_produto(categoria_id):
    c = CategoriaProduto.query_tenant().filter_by(id=categoria_id).first()
    if not c:
        raise APIError('Categoria não encontrada.', 404)
    c.ativo = False
    commit_ou_falhar('gestor.catalogo.desativar_categoria_produto')
    return jsonify({'mensagem': 'Categoria desativada.'}), 200


# ── Produtos ──────────────────────────────────────────────────────────────────

@catalogo_bp.get('/produtos')
@gestor_required
def listar_produtos():
    q = Produto.query_tenant()
    ativo = request.args.get('ativo')
    if ativo == 'true':
        q = q.filter_by(ativo=True)
    elif ativo == 'false':
        q = q.filter_by(ativo=False)
    categoria = request.args.get('categoria')
    if categoria:
        q = q.filter_by(categoria=categoria)
    produtos = q.order_by(Produto.nome).all()

    categoria_ids = {p.categoria_id for p in produtos if p.categoria_id}
    categorias_map = {c.id: c for c in CategoriaProduto.query.filter(
        CategoriaProduto.id.in_(categoria_ids)).all()} if categoria_ids else {}

    return jsonify([_fmt_produto(p, categorias_map) for p in produtos]), 200


@catalogo_bp.post('/produtos')
@gestor_required
@feature_required('produtos_venda')
def criar_produto():
    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    nome  = (dados.get('nome') or '').strip()
    preco = dados.get('preco')

    if not nome:
        raise APIError('"nome" é obrigatório.')
    try:
        preco = float(preco)
        assert preco >= 0
    except (TypeError, ValueError, AssertionError):
        raise APIError('"preco" deve ser um número não-negativo.')

    qtd = dados.get('quantidade_estoque', 0)
    if not isinstance(qtd, int) or qtd < 0:
        raise APIError('"quantidade_estoque" deve ser um inteiro não-negativo.')

    bid = _barbearia_id_atual()

    categoria_id = dados.get('categoria_id')
    if categoria_id is not None:
        if not CategoriaProduto.query.filter_by(id=categoria_id, barbearia_id=bid).first():
            raise APIError('Categoria não encontrada.', 404)

    custo_unitario = dados.get('custo_unitario', 0)
    try:
        custo_unitario = float(custo_unitario or 0)
        assert custo_unitario >= 0
    except (TypeError, ValueError, AssertionError):
        raise APIError('"custo_unitario" deve ser um número não-negativo.')

    estoque_minimo = dados.get('estoque_minimo', 0)
    if not isinstance(estoque_minimo, int) or estoque_minimo < 0:
        raise APIError('"estoque_minimo" deve ser um inteiro não-negativo.')

    p = Produto(
        barbearia_id=bid,
        nome=nome,
        categoria=(dados.get('categoria') or '').strip() or None,
        categoria_id=categoria_id,
        marca=(dados.get('marca') or '').strip() or None,
        preco=preco,
        custo_unitario=custo_unitario,
        codigo_barras=(dados.get('codigo_barras') or '').strip() or None,
        # quantidade_estoque nasce em 0 — o estoque inicial (abaixo) é quem
        # grava o valor real via registrar_entrada(). Gravar `qtd` aqui E
        # somar `qtd` de novo em registrar_entrada() duplicava o estoque
        # inicial (achado no Script 20/release v1.1.0).
        quantidade_estoque=0,
        quantidade_reservada=0,
        estoque_minimo=estoque_minimo,
        ativo=True,
    )
    db.session.add(p)
    commit_ou_falhar('gestor.catalogo.criar_produto')

    if qtd > 0:
        estoque_service.registrar_entrada(
            p.id, bid, qtd, g.user_id, 'Estoque inicial no cadastro do produto',
        )
        commit_ou_falhar('gestor.catalogo.criar_produto.estoque_inicial')

    return jsonify(_fmt_produto(p)), 201


@catalogo_bp.get('/produtos/<int:produto_id>')
@gestor_required
def detalhar_produto(produto_id):
    p = Produto.query_tenant().filter_by(id=produto_id).first()
    if not p:
        raise APIError(f'{L("produto")} não encontrado.', 404)
    return jsonify(_fmt_produto(p)), 200


@catalogo_bp.patch('/produtos/<int:produto_id>')
@gestor_required
def editar_produto(produto_id):
    p = Produto.query_tenant().filter_by(id=produto_id).first()
    if not p:
        raise APIError(f'{L("produto")} não encontrado.', 404)

    dados = request.get_json(silent=True) or {}

    if 'nome' in dados:
        nome = (dados['nome'] or '').strip()
        if not nome:
            raise APIError('"nome" não pode ser vazio.')
        p.nome = nome
    if 'categoria' in dados:
        p.categoria = (dados['categoria'] or '').strip() or None
    if 'categoria_id' in dados:
        categoria_id = dados['categoria_id']
        if categoria_id is not None and not CategoriaProduto.query.filter_by(
            id=categoria_id, barbearia_id=p.barbearia_id
        ).first():
            raise APIError('Categoria não encontrada.', 404)
        p.categoria_id = categoria_id
    if 'marca' in dados:
        p.marca = (dados['marca'] or '').strip() or None
    if 'codigo_barras' in dados:
        p.codigo_barras = (dados['codigo_barras'] or '').strip() or None
    if 'preco' in dados:
        try:
            pr = float(dados['preco'])
            assert pr >= 0
        except (TypeError, ValueError, AssertionError):
            raise APIError('"preco" deve ser um número não-negativo.')
        p.preco = pr
    if 'custo_unitario' in dados:
        try:
            cu = float(dados['custo_unitario'] or 0)
            assert cu >= 0
        except (TypeError, ValueError, AssertionError):
            raise APIError('"custo_unitario" deve ser um número não-negativo.')
        p.custo_unitario = cu
    if 'estoque_minimo' in dados:
        em = dados['estoque_minimo']
        if not isinstance(em, int) or em < 0:
            raise APIError('"estoque_minimo" deve ser um inteiro não-negativo.')
        p.estoque_minimo = em
    if 'ativo' in dados:
        p.ativo = bool(dados['ativo'])

    commit_ou_falhar('gestor.catalogo.editar_produto')
    return jsonify(_fmt_produto(p)), 200


@catalogo_bp.delete('/produtos/<int:produto_id>')
@gestor_required
def desativar_produto(produto_id):
    p = Produto.query_tenant().filter_by(id=produto_id).first()
    if not p:
        raise APIError(f'{L("produto")} não encontrado.', 404)
    p.ativo = False
    commit_ou_falhar('gestor.catalogo.desativar_produto')
    return jsonify({'mensagem': f'{L("produto")} desativado.'}), 200


@catalogo_bp.post('/produtos/<int:produto_id>/ajustar-estoque')
@gestor_required
@feature_required('produtos_venda')
def ajustar_estoque(produto_id):
    bid = _barbearia_id_atual()
    p = Produto.query_tenant().filter_by(id=produto_id).first()
    if not p:
        raise APIError(f'{L("produto")} não encontrado.', 404)

    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    # Aceita "quantidade" (nome usado pelo frontend) ou "delta" (nome
    # histórico da rota) — mesma coisa, corrige a inconsistência pré-existente
    # entre o JS e a API sem quebrar quem já mandava "delta".
    delta = dados.get('quantidade', dados.get('delta'))
    if not isinstance(delta, int) or delta == 0:
        raise APIError('"quantidade" deve ser um inteiro diferente de zero (positivo para entrada, negativo para saída).')

    anterior = p.quantidade_estoque
    motivo = (dados.get('motivo') or 'Ajuste manual de estoque').strip()

    estoque_service.ajustar_estoque(p.id, bid, delta, g.user_id, motivo)
    commit_ou_falhar('gestor.catalogo.ajustar_estoque')

    db.session.refresh(p)
    return jsonify({
        'produto_id':          p.id,
        'quantidade_anterior': anterior,
        'delta':               delta,
        'quantidade_atual':    p.quantidade_estoque,
    }), 200


# ── Foto do produto (Cloudinary) ───────────────────────────────────────────────

@catalogo_bp.post('/produtos/<int:produto_id>/foto')
@gestor_required
def upload_foto_produto(produto_id):
    bid = _barbearia_id_atual()
    p = Produto.query_tenant().filter_by(id=produto_id).first()
    if not p:
        raise APIError(f'{L("produto")} não encontrado.', 404)

    if 'arquivo' not in request.files:
        raise APIError('Campo "arquivo" é obrigatório.')
    arq = request.files['arquivo']
    validar_upload_imagem(arq)

    try:
        resultado = cloudinary.uploader.upload(
            arq.stream,
            folder=f'barberos/produtos/{bid}',
            public_id=f'produto_{p.id}',
            overwrite=True,
            unique_filename=False,
            invalidate=True,
            resource_type='image',
        )
    except Exception as exc:
        raise APIError(f'Cloudinary: {exc}', 502)

    url = resultado.get('secure_url')
    if not url:
        raise APIError('Cloudinary não retornou a URL da imagem.', 502)

    p.foto_url = url
    commit_ou_falhar('gestor.catalogo.upload_foto_produto')
    return jsonify({'foto_url': url}), 200
