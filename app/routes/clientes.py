from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import func
from app import db
from app.models import Usuario, Agendamento, Servico, Barbeiro, Cliente
from app.utils import normalizar_telefone, get_barbearia_atual, registrar_auditoria
from app.routes.auth import barbeiro_required

clientes = Blueprint('clientes', __name__)


def _erro(msg, code=400):
    return jsonify({'erro': msg}), code


def _fmt_cliente(c, ultima=None, total=0):
    return {
        'id':            c.id,
        'nome':          c.nome,
        'telefone':      c.telefone,
        'email':         c.email,
        'foto':          c.foto,
        'observacoes':   c.observacoes,
        'ativo':         c.ativo,
        'criado_em':     c.criado_em.isoformat() if c.criado_em else None,
        'ultima_visita': ultima.isoformat() if ultima else None,
        'total_visitas': total,
    }


# ── GET /clientes ──────────────────────────────────────────────────────────────

@clientes.get('/clientes')
@barbeiro_required
def listar_clientes():
    barbearia_id = get_barbearia_atual()
    q = request.args.get('q', '').strip()

    base = db.session.query(
        Cliente,
        func.max(Agendamento.data_hora).label('ultima_visita'),
        func.count(Agendamento.id).label('total_visitas'),
    ).outerjoin(
        Agendamento,
        (Agendamento.cliente_id == Cliente.id) & (Agendamento.status == 'concluido'),
    ).filter(
        Cliente.barbearia_id == barbearia_id,
        Cliente.ativo == True,
    )
    if q:
        base = base.filter(
            (Cliente.nome.ilike(f'%{q}%')) | (Cliente.telefone.contains(q))
        )
    rows = base.group_by(Cliente.id).order_by(Cliente.nome).all()

    return jsonify([_fmt_cliente(c, ultima, total) for c, ultima, total in rows])


# ── GET /clientes/<id>/perfil ──────────────────────────────────────────────────

@clientes.get('/clientes/<int:cliente_id>/perfil')
@barbeiro_required
def perfil_cliente(cliente_id):
    barbearia_id = get_barbearia_atual()
    cliente = Cliente.query.filter_by(id=cliente_id, barbearia_id=barbearia_id).first()
    if not cliente:
        return _erro('Cliente não encontrado.', 404)

    historico_rows = (
        db.session.query(Agendamento, Servico, Barbeiro, Usuario)
        .join(Servico,  Agendamento.servico_id  == Servico.id)
        .join(Barbeiro, Agendamento.barbeiro_id  == Barbeiro.id)
        .join(Usuario,  Barbeiro.usuario_id      == Usuario.id)
        .filter(
            Agendamento.cliente_id   == cliente_id,
            Agendamento.barbearia_id == barbearia_id,
            Agendamento.status       == 'concluido',
        )
        .order_by(Agendamento.data_hora.desc())
        .limit(10).all()
    )

    historico = [
        {
            'data':     ag.data_hora.isoformat(),
            'servico':  sv.nome,
            'barbeiro': u.nome,
            'valor':    float(sv.preco),
        }
        for ag, sv, b, u in historico_rows
    ]

    servico_mais_feito = (
        db.session.query(Servico.nome, func.count(Agendamento.id).label('qtd'))
        .join(Agendamento, Agendamento.servico_id == Servico.id)
        .filter(
            Agendamento.cliente_id   == cliente_id,
            Agendamento.barbearia_id == barbearia_id,
            Agendamento.status       == 'concluido',
        )
        .group_by(Servico.nome)
        .order_by(func.count(Agendamento.id).desc())
        .first()
    )

    total_visitas = (
        db.session.query(func.count(Agendamento.id))
        .filter(
            Agendamento.cliente_id   == cliente_id,
            Agendamento.barbearia_id == barbearia_id,
            Agendamento.status       == 'concluido',
        )
        .scalar() or 0
    )

    total_gasto = (
        db.session.query(func.sum(Servico.preco))
        .join(Agendamento, Agendamento.servico_id == Servico.id)
        .filter(
            Agendamento.cliente_id   == cliente_id,
            Agendamento.barbearia_id == barbearia_id,
            Agendamento.status       == 'concluido',
        )
        .scalar()
    )

    ultima_visita = (
        db.session.query(func.max(Agendamento.data_hora))
        .filter(
            Agendamento.cliente_id   == cliente_id,
            Agendamento.barbearia_id == barbearia_id,
            Agendamento.status       == 'concluido',
        )
        .scalar()
    )

    return jsonify({
        'dados_pessoais': {
            'id':          cliente.id,
            'nome':        cliente.nome,
            'telefone':    cliente.telefone,
            'email':       cliente.email,
            'foto':        cliente.foto,
            'observacoes': cliente.observacoes,
            'ativo':       cliente.ativo,
        },
        'historico':          historico,
        'servico_mais_feito': servico_mais_feito[0] if servico_mais_feito else None,
        'total_visitas':      total_visitas,
        'total_gasto':        float(total_gasto) if total_gasto else 0.0,
        'ultima_visita':      ultima_visita.isoformat() if ultima_visita else None,
    })


# ── POST /clientes ─────────────────────────────────────────────────────────────

@clientes.post('/clientes')
@barbeiro_required
def criar_cliente():
    barbearia_id = get_barbearia_atual()
    dados = request.get_json(silent=True)
    if not dados:
        return _erro('Corpo da requisição inválido ou ausente.')

    nome         = (dados.get('nome') or '').strip()
    telefone_raw = (dados.get('telefone') or '').strip()
    email_raw    = (dados.get('email') or '').strip().lower()

    if not nome:
        return _erro('O campo "nome" é obrigatório.')
    if not telefone_raw:
        return _erro('O campo "telefone" é obrigatório.')
    if email_raw and '@' not in email_raw:
        return _erro('E-mail inválido.')

    telefone, tel_erro = normalizar_telefone(telefone_raw)
    if tel_erro:
        return _erro(tel_erro)

    if Cliente.query.filter_by(telefone=telefone, barbearia_id=barbearia_id, ativo=True).first():
        return _erro('Já existe um cliente ativo com este telefone.', 409)

    cliente = Cliente(
        barbearia_id=barbearia_id,
        nome=nome,
        telefone=telefone,
        email=email_raw or None,
        observacoes=(dados.get('observacoes') or '').strip() or None,
    )
    db.session.add(cliente)
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'create', 'cliente', cliente.id,
                         f'Criou cliente "{nome}".')

    return jsonify({
        'mensagem': 'Cliente criado com sucesso.',
        'cliente':  _fmt_cliente(cliente),
    }), 201


# ── PUT /clientes/<id> ─────────────────────────────────────────────────────────

@clientes.put('/clientes/<int:cliente_id>')
@barbeiro_required
def editar_cliente(cliente_id):
    barbearia_id = get_barbearia_atual()
    cliente = Cliente.query.filter_by(id=cliente_id, barbearia_id=barbearia_id).first()
    if not cliente:
        return _erro('Cliente não encontrado.', 404)

    dados = request.get_json(silent=True) or {}

    if 'nome' in dados:
        nome = (dados['nome'] or '').strip()
        if not nome:
            return _erro('"nome" não pode ser vazio.')
        cliente.nome = nome
    if 'email' in dados:
        e = (dados['email'] or '').strip().lower()
        if e and '@' not in e:
            return _erro('E-mail inválido.')
        cliente.email = e or None
    if 'observacoes' in dados:
        cliente.observacoes = (dados['observacoes'] or '').strip() or None
    if 'foto' in dados:
        cliente.foto = (dados['foto'] or '').strip() or None

    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'edit', 'cliente', cliente.id,
                         f'Editou cliente "{cliente.nome}".')
    return jsonify({'mensagem': 'Cliente atualizado com sucesso.', 'cliente': _fmt_cliente(cliente)})


# ── DELETE /clientes/<id>  (soft delete) ───────────────────────────────────────

@clientes.delete('/clientes/<int:cliente_id>')
@barbeiro_required
def deletar_cliente(cliente_id):
    barbearia_id = get_barbearia_atual()
    cliente = Cliente.query.filter_by(id=cliente_id, barbearia_id=barbearia_id).first()
    if not cliente:
        return _erro('Cliente não encontrado.', 404)
    cliente.ativo = False
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'delete', 'cliente', cliente_id,
                         f'Removeu cliente "{cliente.nome}".')
    return jsonify({'mensagem': 'Cliente removido.', 'id': cliente_id})
