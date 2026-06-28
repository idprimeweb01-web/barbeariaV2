from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from app import db
from app.models import (
    Plano, PlanoServico, Servico, Barbeiro, Usuario,
    ClientePlano, ClientePlanoSolicitacao, PlanoBarbeiro,
)
from app.utils import get_barbearia_atual, registrar_auditoria, limite_para_fora, limite_para_dentro
from app.routes.auth import gestor_required

planos = Blueprint('planos', __name__, url_prefix='/api/planos')


def _erro(msg, code=400):
    return jsonify({'erro': msg}), code


_limite_para_fora = limite_para_fora
_limite_para_dentro = limite_para_dentro


def _fmt_plano(p):
    vinculos = PlanoServico.query.filter_by(plano_id=p.id).all()
    servico_ids = [v.servico_id for v in vinculos]
    servicos_map = {s.id: s for s in Servico.query.filter(Servico.id.in_(servico_ids)).all()} if servico_ids else {}
    validade_dias = vinculos[0].dias_expiracao if vinculos else None
    total_clientes = ClientePlano.query.filter_by(plano_id=p.id, ativo=True).count()
    vinculos_barbeiro = PlanoBarbeiro.query.filter_by(plano_id=p.id).all()
    barbeiros_ids = [v.barbeiro_id for v in vinculos_barbeiro]

    return {
        'id':            p.id,
        'nome':          p.nome,
        'descricao':     p.descricao,
        'preco_mensal':  float(p.preco_mensal),
        'validade_dias': validade_dias,
        'servicos': [
            {
                'id': v.servico_id,
                'nome': servicos_map[v.servico_id].nome if v.servico_id in servicos_map else '—',
                'limite_mensal': _limite_para_fora(v.limite_uso_mensal),
            }
            for v in vinculos
        ],
        'servicos_ids':  servico_ids,
        'barbeiros_ids': barbeiros_ids,
        'total_clientes': total_clientes,
        'ativo':         p.ativo,
        'criado_em':     p.criado_em.isoformat() if p.criado_em else None,
    }


def _sincronizar_servicos(plano_id, servicos, dias_expiracao):
    """`servicos` é uma lista de {id, limite_mensal} ou, por compatibilidade, de ints (ids)."""
    PlanoServico.query.filter_by(plano_id=plano_id).delete()
    for item in servicos:
        if isinstance(item, dict):
            sid = item.get('id')
            limite = _limite_para_dentro(item.get('limite_mensal'))
        else:
            sid = item
            limite = ILIMITADO
        db.session.add(PlanoServico(
            plano_id=plano_id,
            servico_id=sid,
            limite_uso_mensal=limite,
            dias_expiracao=dias_expiracao,
        ))


# ── GET /api/planos/listar ──────────────────────────────────────────────────────

@planos.get('/listar')
@gestor_required
def listar_planos():
    barbearia_id = get_barbearia_atual()
    rows = Plano.query.filter_by(barbearia_id=barbearia_id).order_by(Plano.nome).all()
    return jsonify([_fmt_plano(p) for p in rows])


# ── POST /api/planos/criar ──────────────────────────────────────────────────────

@planos.post('/criar')
@gestor_required
def criar_plano():
    barbearia_id = get_barbearia_atual()
    dados = request.get_json(silent=True)
    if not dados:
        return _erro('Corpo da requisição inválido ou ausente.')

    nome           = (dados.get('nome') or '').strip()
    preco_mensal   = dados.get('preco_mensal')
    validade_dias  = dados.get('validade_dias')
    servicos_in    = dados.get('servicos')
    if servicos_in is None:
        servicos_in = [{'id': sid, 'limite_mensal': None} for sid in (dados.get('servicos_ids') or [])]
    ativo          = bool(dados.get('ativo', True))

    if not nome:
        return _erro('"nome" é obrigatório.')
    try:
        preco_mensal = float(preco_mensal)
        if preco_mensal < 0:
            raise ValueError
    except (TypeError, ValueError):
        return _erro('"preco_mensal" deve ser um número positivo.')
    try:
        validade_dias = int(validade_dias)
        if validade_dias < 1:
            raise ValueError
    except (TypeError, ValueError):
        return _erro('"validade_dias" deve ser um número inteiro positivo.')

    barbeiro = Barbeiro.query.filter_by(barbearia_id=barbearia_id, ativo=True).first()
    if not barbeiro:
        return _erro('Cadastre ao menos um barbeiro ativo antes de criar planos.')

    plano = Plano(
        barbearia_id=barbearia_id,
        barbeiro_id=barbeiro.id,
        nome=nome,
        descricao=(dados.get('descricao') or '').strip() or None,
        preco_mensal=preco_mensal,
        ativo=ativo,
    )
    db.session.add(plano)
    db.session.flush()

    ids_validos = {
        s.id for s in Servico.query.filter(
            Servico.id.in_([item.get('id') for item in servicos_in]), Servico.barbearia_id == barbearia_id,
        ).all()
    }
    servicos_validos = [item for item in servicos_in if item.get('id') in ids_validos]
    _sincronizar_servicos(plano.id, servicos_validos, validade_dias)

    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'create', 'plano', plano.id,
                         f'Criou plano "{plano.nome}".')
    return jsonify({'mensagem': 'Plano criado.', 'plano': _fmt_plano(plano)}), 201


# ── PUT /api/planos/<id> ─────────────────────────────────────────────────────────

@planos.put('/<int:plano_id>')
@gestor_required
def editar_plano(plano_id):
    barbearia_id = get_barbearia_atual()
    plano = Plano.query.filter_by(id=plano_id, barbearia_id=barbearia_id).first()
    if not plano:
        return _erro('Plano não encontrado.', 404)

    dados = request.get_json(silent=True) or {}

    if 'nome' in dados:
        nome = (dados['nome'] or '').strip()
        if not nome:
            return _erro('"nome" não pode ser vazio.')
        plano.nome = nome
    if 'descricao' in dados:
        plano.descricao = (dados['descricao'] or '').strip() or None
    if 'preco_mensal' in dados:
        try:
            preco = float(dados['preco_mensal'])
            if preco < 0:
                raise ValueError
        except (TypeError, ValueError):
            return _erro('"preco_mensal" deve ser um número positivo.')
        plano.preco_mensal = preco
    if 'ativo' in dados:
        plano.ativo = bool(dados['ativo'])

    if 'servicos' in dados or 'servicos_ids' in dados or 'validade_dias' in dados:
        vinculo_atual = PlanoServico.query.filter_by(plano_id=plano.id).first()
        validade_dias = dados.get('validade_dias', vinculo_atual.dias_expiracao if vinculo_atual else None)
        try:
            validade_dias = int(validade_dias)
            if validade_dias < 1:
                raise ValueError
        except (TypeError, ValueError):
            return _erro('"validade_dias" deve ser um número inteiro positivo.')

        servicos_in = dados.get('servicos')
        if servicos_in is None:
            servicos_ids = dados.get('servicos_ids')
            if servicos_ids is None:
                servicos_in = [
                    {'id': v.servico_id, 'limite_mensal': _limite_para_fora(v.limite_uso_mensal)}
                    for v in PlanoServico.query.filter_by(plano_id=plano.id).all()
                ]
            else:
                servicos_in = [{'id': sid, 'limite_mensal': None} for sid in servicos_ids]

        ids_validos = {
            s.id for s in Servico.query.filter(
                Servico.id.in_([item.get('id') for item in servicos_in]), Servico.barbearia_id == barbearia_id,
            ).all()
        }
        servicos_validos = [item for item in servicos_in if item.get('id') in ids_validos]
        _sincronizar_servicos(plano.id, servicos_validos, validade_dias)

    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'edit', 'plano', plano.id,
                         f'Editou plano "{plano.nome}".')
    return jsonify({'mensagem': 'Plano atualizado.', 'plano': _fmt_plano(plano)})


# ── DELETE /api/planos/<id> ──────────────────────────────────────────────────────

@planos.delete('/<int:plano_id>')
@gestor_required
def deletar_plano(plano_id):
    barbearia_id = get_barbearia_atual()
    plano = Plano.query.filter_by(id=plano_id, barbearia_id=barbearia_id).first()
    if not plano:
        return _erro('Plano não encontrado.', 404)

    if ClientePlano.query.filter_by(plano_id=plano.id).first():
        return _erro('Este plano já teve clientes vinculados. Inative-o em vez de deletar.', 409)
    if ClientePlanoSolicitacao.query.filter_by(plano_id=plano.id).first():
        return _erro('Este plano possui solicitações de pagamento (PIX). Inative-o em vez de deletar.', 409)

    nome_plano = plano.nome
    PlanoServico.query.filter_by(plano_id=plano.id).delete()
    PlanoBarbeiro.query.filter_by(plano_id=plano.id).delete()
    db.session.delete(plano)
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'delete', 'plano', plano_id,
                         f'Deletou plano "{nome_plano}".')
    return jsonify({'mensagem': 'Plano deletado.', 'id': plano_id})


# ── POST /api/planos/<id>/vincular-barbeiro ──────────────────────────────────────

@planos.post('/<int:plano_id>/vincular-barbeiro')
@gestor_required
def vincular_barbeiro(plano_id):
    barbearia_id = get_barbearia_atual()
    plano = Plano.query.filter_by(id=plano_id, barbearia_id=barbearia_id).first()
    if not plano:
        return _erro('Plano não encontrado.', 404)

    dados = request.get_json(silent=True) or {}
    barbeiro_id = dados.get('barbeiro_id')
    barbeiro = Barbeiro.query.filter_by(id=barbeiro_id, barbearia_id=barbearia_id, ativo=True).first()
    if not barbeiro:
        return _erro('Barbeiro não encontrado.', 404)

    if PlanoBarbeiro.query.filter_by(plano_id=plano_id, barbeiro_id=barbeiro_id).first():
        return _erro('Este barbeiro já atende este plano.', 409)

    db.session.add(PlanoBarbeiro(plano_id=plano_id, barbeiro_id=barbeiro_id, barbearia_id=barbearia_id))
    db.session.commit()
    return jsonify({'mensagem': 'Barbeiro vinculado ao plano.'}), 201


# ── DELETE /api/planos/<id>/desvincular-barbeiro/<barbeiro_id> ───────────────────

@planos.delete('/<int:plano_id>/desvincular-barbeiro/<int:barbeiro_id>')
@gestor_required
def desvincular_barbeiro(plano_id, barbeiro_id):
    barbearia_id = get_barbearia_atual()
    vinculo = PlanoBarbeiro.query.filter_by(
        plano_id=plano_id, barbeiro_id=barbeiro_id, barbearia_id=barbearia_id,
    ).first()
    if not vinculo:
        return _erro('Vínculo não encontrado.', 404)

    db.session.delete(vinculo)
    db.session.commit()
    return jsonify({'mensagem': 'Barbeiro desvinculado do plano.'})
