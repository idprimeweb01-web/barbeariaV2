from datetime import date
from flask import Blueprint, request, g, jsonify
from app.extensions import db
from app.models import Cupom
from app.exceptions import APIError
from app.decorators.auth import gestor_required
from app.utils.features import feature_required
from app.utils.tz import hoje_brasilia

cupons_bp = Blueprint('gestor_cupons', __name__, url_prefix='/api/v1/gestor')

_TIPOS = {'percentual', 'valor_fixo'}


def _fmt_cupom(c):
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
        'ativo':                  c.ativo,
        'expirado':               c.data_expiracao < hoje_brasilia(),
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

    if Cupom.query.filter_by(barbearia_id=g.barbearia_id, codigo=codigo).first():
        raise APIError(f'Já existe um cupom com o código "{codigo}".', 409)

    c = Cupom(
        barbearia_id=g.barbearia_id,
        nome=nome,
        codigo=codigo,
        tipo_desconto=tipo,
        valor_desconto=valor,
        data_expiracao=data_exp,
        quantidade_maxima_usos=qtd_max,
        ativo=dados.get('ativo', True) if isinstance(dados.get('ativo', True), bool) else True,
    )
    db.session.add(c)
    db.session.commit()
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

    if 'ativo' in dados and isinstance(dados.get('ativo'), bool):
        c.ativo = dados['ativo']

    db.session.commit()
    return jsonify(_fmt_cupom(c)), 200


@cupons_bp.delete('/cupons/<int:cupom_id>')
@gestor_required
@feature_required('cupons')
def excluir_cupom(cupom_id):
    c = Cupom.query_tenant().filter_by(id=cupom_id).first()
    if not c:
        raise APIError('Cupom não encontrado.', 404)
    c.ativo = False
    db.session.commit()
    return jsonify({'mensagem': 'Cupom desativado.'}), 200
