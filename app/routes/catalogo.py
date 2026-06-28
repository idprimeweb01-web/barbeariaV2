from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from app import db
from app.models import Usuario, Servico, BarbeiroServico, Barbeiro, Produto
from app.utils import get_barbearia_atual, registrar_auditoria
from app.routes.auth import gestor_required, barbeiro_required

catalogo = Blueprint('catalogo', __name__)


def _erro(msg, code=400):
    return jsonify({'erro': msg}), code


# Aliases locais para clareza semântica
admin_required          = gestor_required
barbeiro_ou_admin_required = barbeiro_required


def _fmt_servico(s):
    return {
        'id': s.id, 'nome': s.nome, 'descricao': s.descricao,
        'duracao_minutos': s.duracao_minutos, 'preco': float(s.preco),
        'foto': s.foto, 'ativo': s.ativo,
    }


def _fmt_produto(p, admin=False):
    d = {
        'id': p.id, 'nome': p.nome, 'categoria': p.categoria,
        'preco': float(p.preco), 'quantidade_estoque': p.quantidade_estoque,
        'foto': p.foto,
    }
    if admin:
        d['ativo']     = p.ativo
        d['criado_em'] = p.criado_em.isoformat() if p.criado_em else None
    return d


def _validar_preco(valor):
    try:
        v = float(valor)
        if v < 0:
            raise ValueError
        return v, None
    except (TypeError, ValueError):
        return None, '"preco" deve ser um número positivo.'


# ── SERVIÇOS ───────────────────────────────────────────────────────────────────

@catalogo.get('/servicos')
@barbeiro_ou_admin_required
def listar_servicos():
    barbearia_id = get_barbearia_atual()
    servicos = Servico.query.filter_by(
        ativo=True, barbearia_id=barbearia_id
    ).order_by(Servico.nome).all()
    return jsonify([_fmt_servico(s) for s in servicos])


@catalogo.post('/servicos')
@admin_required
def criar_servico():
    barbearia_id = get_barbearia_atual()
    dados = request.get_json(silent=True)
    if not dados:
        return _erro('Corpo da requisição inválido ou ausente.')

    nome      = (dados.get('nome') or '').strip()
    descricao = (dados.get('descricao') or '').strip() or None
    duracao   = dados.get('duracao_minutos')
    preco_raw = dados.get('preco')

    if not nome:
        return _erro('O campo "nome" é obrigatório.')
    if duracao is None:
        return _erro('O campo "duracao_minutos" é obrigatório.')
    if not isinstance(duracao, int) or duracao < 1:
        return _erro('"duracao_minutos" deve ser um inteiro maior que 0.')
    if preco_raw is None:
        return _erro('O campo "preco" é obrigatório.')
    preco, err = _validar_preco(preco_raw)
    if err:
        return _erro(err)

    servico = Servico(
        barbearia_id=barbearia_id, nome=nome, descricao=descricao,
        duracao_minutos=duracao, preco=preco,
    )
    db.session.add(servico)
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'create', 'servico', servico.id,
                         f'Criou serviço "{nome}".')
    return jsonify({'mensagem': 'Serviço criado com sucesso.', 'servico': _fmt_servico(servico)}), 201


@catalogo.put('/servicos/<int:servico_id>')
@admin_required
def editar_servico(servico_id):
    barbearia_id = get_barbearia_atual()
    servico = Servico.query.filter_by(id=servico_id, barbearia_id=barbearia_id).first()
    if not servico:
        return _erro('Serviço não encontrado.', 404)

    dados = request.get_json(silent=True) or {}
    if 'nome' in dados:
        nome = (dados['nome'] or '').strip()
        if not nome:
            return _erro('"nome" não pode ser vazio.')
        servico.nome = nome
    if 'descricao' in dados:
        servico.descricao = (dados['descricao'] or '').strip() or None
    if 'duracao_minutos' in dados:
        d = dados['duracao_minutos']
        if not isinstance(d, int) or d < 1:
            return _erro('"duracao_minutos" deve ser um inteiro maior que 0.')
        servico.duracao_minutos = d
    if 'preco' in dados:
        preco, err = _validar_preco(dados['preco'])
        if err:
            return _erro(err)
        servico.preco = preco

    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'edit', 'servico', servico.id,
                         f'Editou serviço "{servico.nome}".')
    return jsonify({'mensagem': 'Serviço atualizado com sucesso.', 'servico': _fmt_servico(servico)})


@catalogo.delete('/servicos/<int:servico_id>')
@admin_required
def desativar_servico(servico_id):
    barbearia_id = get_barbearia_atual()
    servico = Servico.query.filter_by(id=servico_id, barbearia_id=barbearia_id).first()
    if not servico:
        return _erro('Serviço não encontrado.', 404)
    if not servico.ativo:
        return _erro('Serviço já está inativo.')
    servico.ativo = False
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'delete', 'servico', servico_id,
                         f'Desativou serviço "{servico.nome}".')
    return jsonify({'mensagem': 'Serviço desativado com sucesso.', 'id': servico_id})


@catalogo.post('/servicos/<int:servico_id>/barbeiros/<int:barbeiro_id>')
@admin_required
def vincular_servico_barbeiro(servico_id, barbeiro_id):
    barbearia_id = get_barbearia_atual()
    servico  = Servico.query.filter_by(id=servico_id, barbearia_id=barbearia_id, ativo=True).first()
    if not servico:
        return _erro('Serviço não encontrado ou inativo.', 404)
    barbeiro = Barbeiro.query.filter_by(id=barbeiro_id, barbearia_id=barbearia_id, ativo=True).first()
    if not barbeiro:
        return _erro('Barbeiro não encontrado ou inativo.', 404)
    if BarbeiroServico.query.filter_by(barbeiro_id=barbeiro_id, servico_id=servico_id).first():
        return _erro('Este serviço já está vinculado a este barbeiro.', 409)

    db.session.add(BarbeiroServico(barbeiro_id=barbeiro_id, servico_id=servico_id))
    db.session.commit()
    usuario = db.session.get(Usuario, barbeiro.usuario_id)
    return jsonify({
        'mensagem': 'Serviço vinculado ao barbeiro com sucesso.',
        'barbeiro': usuario.nome if usuario else None,
        'servico':  servico.nome,
    }), 201


@catalogo.delete('/servicos/<int:servico_id>/barbeiros/<int:barbeiro_id>')
@admin_required
def desvincular_servico_barbeiro(servico_id, barbeiro_id):
    barbearia_id = get_barbearia_atual()
    # Garante que o serviço pertence a esta barbearia
    servico = Servico.query.filter_by(id=servico_id, barbearia_id=barbearia_id).first()
    if not servico:
        return _erro('Serviço não encontrado.', 404)
    vinculo = BarbeiroServico.query.filter_by(servico_id=servico_id, barbeiro_id=barbeiro_id).first()
    if not vinculo:
        return _erro('Vínculo não encontrado.', 404)
    db.session.delete(vinculo)
    db.session.commit()
    return jsonify({'mensagem': 'Serviço desvinculado do barbeiro com sucesso.'})


# ── PRODUTOS ───────────────────────────────────────────────────────────────────

@catalogo.get('/produtos')
@barbeiro_ou_admin_required
def listar_produtos():
    barbearia_id = get_barbearia_atual()
    produtos = Produto.query.filter(
        Produto.barbearia_id == barbearia_id,
        Produto.ativo        == True,
        Produto.quantidade_estoque > 0,
    ).order_by(Produto.nome).all()
    return jsonify([_fmt_produto(p) for p in produtos])


@catalogo.get('/admin/produtos')
@barbeiro_ou_admin_required
def listar_todos_produtos():
    barbearia_id = get_barbearia_atual()
    produtos = Produto.query.filter_by(
        barbearia_id=barbearia_id
    ).order_by(Produto.nome).all()
    return jsonify([_fmt_produto(p, admin=True) for p in produtos])


@catalogo.post('/produtos')
@admin_required
def criar_produto():
    barbearia_id = get_barbearia_atual()
    dados = request.get_json(silent=True)
    if not dados:
        return _erro('Corpo da requisição inválido ou ausente.')

    nome      = (dados.get('nome') or '').strip()
    categoria = (dados.get('categoria') or '').strip() or None
    preco_raw = dados.get('preco')
    estoque   = dados.get('quantidade_estoque', 0)

    if not nome:
        return _erro('O campo "nome" é obrigatório.')
    if preco_raw is None:
        return _erro('O campo "preco" é obrigatório.')
    preco, err = _validar_preco(preco_raw)
    if err:
        return _erro(err)
    if not isinstance(estoque, int) or estoque < 0:
        return _erro('"quantidade_estoque" deve ser um inteiro maior ou igual a 0.')

    produto = Produto(
        barbearia_id=barbearia_id, nome=nome, categoria=categoria,
        preco=preco, quantidade_estoque=estoque, ativo=estoque > 0,
    )
    db.session.add(produto)
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'create', 'produto', produto.id,
                         f'Criou produto "{nome}".')
    return jsonify({'mensagem': 'Produto criado com sucesso.', 'produto': _fmt_produto(produto, admin=True)}), 201


@catalogo.put('/produtos/<int:produto_id>')
@admin_required
def editar_produto(produto_id):
    barbearia_id = get_barbearia_atual()
    produto = Produto.query.filter_by(id=produto_id, barbearia_id=barbearia_id).first()
    if not produto:
        return _erro('Produto não encontrado.', 404)

    dados = request.get_json(silent=True) or {}
    if 'nome' in dados:
        nome = (dados['nome'] or '').strip()
        if not nome:
            return _erro('"nome" não pode ser vazio.')
        produto.nome = nome
    if 'categoria' in dados:
        produto.categoria = (dados['categoria'] or '').strip() or None
    if 'preco' in dados:
        preco, err = _validar_preco(dados['preco'])
        if err:
            return _erro(err)
        produto.preco = preco

    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'edit', 'produto', produto.id,
                         f'Editou produto "{produto.nome}".')
    return jsonify({'mensagem': 'Produto atualizado com sucesso.', 'produto': _fmt_produto(produto, admin=True)})


@catalogo.delete('/produtos/<int:produto_id>')
@admin_required
def desativar_produto(produto_id):
    barbearia_id = get_barbearia_atual()
    produto = Produto.query.filter_by(id=produto_id, barbearia_id=barbearia_id).first()
    if not produto:
        return _erro('Produto não encontrado.', 404)
    if not produto.ativo:
        return _erro('Produto já está inativo.')
    produto.ativo = False
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'delete', 'produto', produto_id,
                         f'Desativou produto "{produto.nome}".')
    return jsonify({'mensagem': 'Produto desativado com sucesso.', 'id': produto_id})


@catalogo.put('/admin/produtos/<int:produto_id>')
@admin_required
def editar_produto_admin(produto_id):
    barbearia_id = get_barbearia_atual()
    produto = Produto.query.filter_by(id=produto_id, barbearia_id=barbearia_id).first()
    if not produto:
        return _erro('Produto não encontrado.', 404)
    dados = request.get_json(silent=True) or {}
    if 'nome' in dados:
        nome = (dados['nome'] or '').strip()
        if not nome: return _erro('"nome" não pode ser vazio.')
        produto.nome = nome
    if 'categoria' in dados:
        produto.categoria = (dados['categoria'] or '').strip() or None
    if 'preco' in dados:
        preco, err = _validar_preco(dados['preco'])
        if err: return _erro(err)
        produto.preco = preco
    if 'quantidade_estoque' in dados:
        q = dados['quantidade_estoque']
        if not isinstance(q, int) or q < 0:
            return _erro('"quantidade_estoque" deve ser inteiro >= 0.')
        produto.quantidade_estoque = q
        if q == 0: produto.ativo = False
        elif not produto.ativo: produto.ativo = True
    if 'ativo' in dados:
        produto.ativo = bool(dados['ativo'])
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'edit', 'produto', produto.id,
                         f'Editou produto "{produto.nome}" (admin).')
    return jsonify({'mensagem': 'Produto atualizado.', 'produto': _fmt_produto(produto, admin=True)})


@catalogo.post('/admin/produtos')
@admin_required
def criar_produto_admin():
    barbearia_id = get_barbearia_atual()
    dados = request.get_json(silent=True)
    if not dados: return _erro('Corpo da requisição inválido ou ausente.')
    nome      = (dados.get('nome') or '').strip()
    categoria = (dados.get('categoria') or '').strip() or None
    preco_raw = dados.get('preco')
    estoque   = dados.get('quantidade_estoque', 0)
    if not nome: return _erro('O campo "nome" é obrigatório.')
    if preco_raw is None: return _erro('O campo "preco" é obrigatório.')
    preco, err = _validar_preco(preco_raw)
    if err: return _erro(err)
    if not isinstance(estoque, int) or estoque < 0:
        return _erro('"quantidade_estoque" deve ser inteiro >= 0.')
    produto = Produto(
        barbearia_id=barbearia_id, nome=nome, categoria=categoria,
        preco=preco, quantidade_estoque=estoque, ativo=estoque > 0,
    )
    db.session.add(produto)
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'create', 'produto', produto.id,
                         f'Criou produto "{nome}" (admin).')
    return jsonify({'mensagem': 'Produto criado.', 'produto': _fmt_produto(produto, admin=True)}), 201


@catalogo.delete('/admin/produtos/<int:produto_id>')
@admin_required
def desativar_produto_admin(produto_id):
    barbearia_id = get_barbearia_atual()
    produto = Produto.query.filter_by(id=produto_id, barbearia_id=barbearia_id).first()
    if not produto: return _erro('Produto não encontrado.', 404)
    if not produto.ativo: return _erro('Produto já está inativo.')
    produto.ativo = False
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'delete', 'produto', produto_id,
                         f'Desativou produto "{produto.nome}" (admin).')
    return jsonify({'mensagem': 'Produto desativado.', 'id': produto_id})


@catalogo.put('/produtos/<int:produto_id>/estoque')
@admin_required
def ajustar_estoque(produto_id):
    barbearia_id = get_barbearia_atual()
    produto = Produto.query.filter_by(id=produto_id, barbearia_id=barbearia_id).first()
    if not produto:
        return _erro('Produto não encontrado.', 404)

    dados = request.get_json(silent=True)
    if not dados or 'quantidade' not in dados:
        return _erro('O campo "quantidade" é obrigatório (positivo para adicionar, negativo para remover).')
    qtd = dados['quantidade']
    if not isinstance(qtd, int):
        return _erro('"quantidade" deve ser um número inteiro.')

    novo_estoque = produto.quantidade_estoque + qtd
    if novo_estoque < 0:
        return _erro(f'Estoque insuficiente. Estoque atual: {produto.quantidade_estoque}.')

    estava_zerado = produto.quantidade_estoque == 0
    produto.quantidade_estoque = novo_estoque
    aviso = None
    if novo_estoque == 0:
        produto.ativo = False
        aviso = 'Estoque zerado. Produto desativado automaticamente.'
    elif estava_zerado and novo_estoque > 0:
        produto.ativo = True
        aviso = 'Estoque reabastecido. Produto reativado automaticamente.'

    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'edit', 'produto', produto.id,
                         f'Ajustou estoque de "{produto.nome}" ({"+" if qtd >= 0 else ""}{qtd}).')
    resp = {'mensagem': 'Estoque ajustado com sucesso.', 'produto': _fmt_produto(produto, admin=True)}
    if aviso:
        resp['aviso'] = aviso
    return jsonify(resp)
