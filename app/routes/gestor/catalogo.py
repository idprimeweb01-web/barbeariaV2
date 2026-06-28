from flask import Blueprint, request, g, jsonify
from app.extensions import db
from app.models import Servico, Produto
from app.exceptions import APIError
from app.decorators.auth import gestor_required
from app.labels import L

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


def _fmt_produto(p):
    return {
        'id':                    p.id,
        'barbearia_id':          p.barbearia_id,
        'nome':                  p.nome,
        'categoria':             p.categoria,
        'preco':                 float(p.preco),
        'quantidade_estoque':    p.quantidade_estoque,
        'quantidade_reservada':  p.quantidade_reservada,
        'quantidade_disponivel': p.quantidade_estoque - p.quantidade_reservada,
        'foto':                  p.foto,
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
    db.session.commit()
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

    db.session.commit()
    return jsonify(_fmt_servico(s)), 200


@catalogo_bp.delete('/servicos/<int:servico_id>')
@gestor_required
def desativar_servico(servico_id):
    s = Servico.query_tenant().filter_by(id=servico_id).first()
    if not s:
        raise APIError(f'{L("servico")} não encontrado.', 404)
    s.ativo = False
    db.session.commit()
    return jsonify({'mensagem': f'{L("servico")} desativado.'}), 200


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
    return jsonify([_fmt_produto(p) for p in q.order_by(Produto.nome).all()]), 200


@catalogo_bp.post('/produtos')
@gestor_required
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

    p = Produto(
        barbearia_id=_barbearia_id_atual(),
        nome=nome,
        categoria=(dados.get('categoria') or '').strip() or None,
        preco=preco,
        quantidade_estoque=qtd,
        quantidade_reservada=0,
        ativo=True,
    )
    db.session.add(p)
    db.session.commit()
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
    if 'preco' in dados:
        try:
            pr = float(dados['preco'])
            assert pr >= 0
        except (TypeError, ValueError, AssertionError):
            raise APIError('"preco" deve ser um número não-negativo.')
        p.preco = pr
    if 'ativo' in dados:
        p.ativo = bool(dados['ativo'])

    db.session.commit()
    return jsonify(_fmt_produto(p)), 200


@catalogo_bp.delete('/produtos/<int:produto_id>')
@gestor_required
def desativar_produto(produto_id):
    p = Produto.query_tenant().filter_by(id=produto_id).first()
    if not p:
        raise APIError(f'{L("produto")} não encontrado.', 404)
    p.ativo = False
    db.session.commit()
    return jsonify({'mensagem': f'{L("produto")} desativado.'}), 200


@catalogo_bp.post('/produtos/<int:produto_id>/ajustar-estoque')
@gestor_required
def ajustar_estoque(produto_id):
    p = Produto.query_tenant().filter_by(id=produto_id).first()
    if not p:
        raise APIError(f'{L("produto")} não encontrado.', 404)

    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    delta = dados.get('delta')
    if not isinstance(delta, int):
        raise APIError('"delta" deve ser um inteiro (positivo para entrada, negativo para saída).')

    anterior = p.quantidade_estoque
    novo     = anterior + delta
    if novo < 0:
        raise APIError(
            f'Estoque insuficiente. Atual: {anterior}, ajuste solicitado: {delta}.'
        )

    p.quantidade_estoque = novo
    db.session.commit()
    return jsonify({
        'produto_id':         p.id,
        'quantidade_anterior': anterior,
        'delta':              delta,
        'quantidade_atual':   novo,
    }), 200
