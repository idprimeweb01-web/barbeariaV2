from flask import Blueprint, request, g, jsonify
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import Barbeiro, Usuario, Servico, BarbeiroServico
from app.exceptions import APIError
from app.decorators.auth import gestor_required
from app.labels import L
from app.utils import normalizar_telefone
from app.utils.auditoria import registrar_auditoria

profissionais_bp = Blueprint('gestor_profissionais', __name__, url_prefix='/api/v1/gestor')


def _barbearia_id_atual():
    if g.barbearia_id:
        return g.barbearia_id
    raise APIError('Sem barbearia ativa no contexto.', 403)


def _fmt_barbeiro(b):
    u = b.usuario
    return {
        'id':                        b.id,
        'usuario_id':                b.usuario_id,
        'barbearia_id':              b.barbearia_id,
        'nome':                      u.nome if u else None,
        'email':                     u.email if u else None,
        'telefone':                  u.telefone if u else None,
        'foto_perfil_url':           u.foto_perfil_url if u else None,
        'foto':                      b.foto,
        'bio':                       b.bio,
        'comissao_percentual':       float(b.comissao_percentual),
        'comissao_plano_percentual': float(b.comissao_plano_percentual),
        'ativo':                     b.ativo,
    }


def _get_barbeiro(barbeiro_id, barbearia_id):
    b = (
        db.session.query(Barbeiro)
        .filter_by(id=barbeiro_id, barbearia_id=barbearia_id)
        .first()
    )
    if not b:
        raise APIError(f'{L("profissional")} não encontrado.', 404)
    return b


# ── GET /api/v1/gestor/barbeiros ──────────────────────────────────────────────

@profissionais_bp.get('/barbeiros')
@gestor_required
def listar_barbeiros():
    barbearia_id = _barbearia_id_atual()
    q = Barbeiro.query.filter_by(barbearia_id=barbearia_id)
    ativo = request.args.get('ativo')
    if ativo == 'true':
        q = q.filter_by(ativo=True)
    elif ativo == 'false':
        q = q.filter_by(ativo=False)
    barbeiros = q.join(Usuario).order_by(Usuario.nome).all()
    return jsonify([_fmt_barbeiro(b) for b in barbeiros]), 200


# ── POST /api/v1/gestor/barbeiros ─────────────────────────────────────────────

@profissionais_bp.post('/barbeiros')
@gestor_required
def criar_barbeiro():
    barbearia_id = _barbearia_id_atual()
    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    nome   = (dados.get('nome') or '').strip()
    email  = (dados.get('email') or '').strip().lower() or None
    tel    = (dados.get('telefone') or '').strip()
    senha  = dados.get('senha') or ''

    if not nome:
        raise APIError('"nome" é obrigatório.')
    if not tel:
        raise APIError('"telefone" é obrigatório.')
    if len(senha) < 6:
        raise APIError('"senha" deve ter no mínimo 6 caracteres.')

    tel_norm, tel_erro = normalizar_telefone(tel)
    if tel_erro:
        raise APIError(tel_erro)

    if email and Usuario.query.filter_by(email=email).first():
        raise APIError(f'Email "{email}" já está em uso.', 409)

    comissao       = float(dados.get('comissao_percentual', 0) or 0)
    comissao_plano = float(dados.get('comissao_plano_percentual', 0) or 0)

    usuario = Usuario(
        barbearia_id=barbearia_id,
        nome=nome,
        email=email,
        telefone=tel_norm,
        senha=generate_password_hash(senha),
        perfil='barbeiro',
        ativo=True,
    )
    db.session.add(usuario)
    db.session.flush()

    barbeiro = Barbeiro(
        barbearia_id=barbearia_id,
        usuario_id=usuario.id,
        bio=(dados.get('bio') or '').strip() or None,
        comissao_percentual=comissao,
        comissao_plano_percentual=comissao_plano,
        ativo=True,
    )
    db.session.add(barbeiro)
    db.session.commit()

    return jsonify(_fmt_barbeiro(barbeiro)), 201


# ── GET /api/v1/gestor/barbeiros/<id> ────────────────────────────────────────

@profissionais_bp.get('/barbeiros/<int:barbeiro_id>')
@gestor_required
def detalhar_barbeiro(barbeiro_id):
    barbearia_id = _barbearia_id_atual()
    b = _get_barbeiro(barbeiro_id, barbearia_id)

    servicos = (
        db.session.query(Servico)
        .join(BarbeiroServico, BarbeiroServico.servico_id == Servico.id)
        .filter(BarbeiroServico.barbeiro_id == barbeiro_id)
        .order_by(Servico.nome)
        .all()
    )

    return jsonify({
        **_fmt_barbeiro(b),
        'servicos': [
            {'id': s.id, 'nome': s.nome, 'duracao_minutos': s.duracao_minutos, 'preco': float(s.preco)}
            for s in servicos
        ],
    }), 200


# ── PATCH /api/v1/gestor/barbeiros/<id> ──────────────────────────────────────

@profissionais_bp.patch('/barbeiros/<int:barbeiro_id>')
@gestor_required
def editar_barbeiro(barbeiro_id):
    barbearia_id = _barbearia_id_atual()
    b = _get_barbeiro(barbeiro_id, barbearia_id)
    u = b.usuario

    dados = request.get_json(silent=True) or {}

    if 'nome' in dados:
        nome = (dados['nome'] or '').strip()
        if not nome:
            raise APIError('"nome" não pode ser vazio.')
        u.nome = nome
    if 'bio' in dados:
        b.bio = (dados['bio'] or '').strip() or None
    # Captura valores anteriores para auditoria antes de sobrescrever
    auditoria_mudancas = []
    if 'comissao_percentual' in dados:
        antigo = float(b.comissao_percentual)
        novo   = float(dados['comissao_percentual'] or 0)
        b.comissao_percentual = novo
        if antigo != novo:
            auditoria_mudancas.append(
                f'comissao_percentual: {antigo}% → {novo}%'
            )
    if 'comissao_plano_percentual' in dados:
        antigo = float(b.comissao_plano_percentual)
        novo   = float(dados['comissao_plano_percentual'] or 0)
        b.comissao_plano_percentual = novo
        if antigo != novo:
            auditoria_mudancas.append(
                f'comissao_plano_percentual: {antigo}% → {novo}%'
            )
    if 'ativo' in dados:
        ativo = bool(dados['ativo'])
        b.ativo = ativo
        u.ativo = ativo
        auditoria_mudancas.append(f'ativo: {"ativado" if ativo else "desativado"}')

    db.session.commit()

    # Registra auditoria APÓS commit — falha de log não reverte a operação
    for descricao in auditoria_mudancas:
        registrar_auditoria(
            usuario_id=g.user_id,
            barbearia_id=barbearia_id,
            tipo_acao='edicao',
            entidade='barbeiro',
            entidade_id=b.id,
            descricao=descricao,
        )

    return jsonify(_fmt_barbeiro(b)), 200


# ── Atribuição de serviços ao profissional ───────────────────────────────────

@profissionais_bp.post('/barbeiros/<int:barbeiro_id>/servicos')
@gestor_required
def atribuir_servico(barbeiro_id):
    barbearia_id = _barbearia_id_atual()
    b = _get_barbeiro(barbeiro_id, barbearia_id)

    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    servico_id = dados.get('servico_id')
    if not isinstance(servico_id, int):
        raise APIError('"servico_id" é obrigatório e deve ser um inteiro.')

    s = Servico.query.filter_by(id=servico_id, barbearia_id=barbearia_id, ativo=True).first()
    if not s:
        raise APIError(f'{L("servico")} não encontrado ou inativo.', 404)

    existente = BarbeiroServico.query.filter_by(
        barbeiro_id=barbeiro_id, servico_id=servico_id
    ).first()
    if existente:
        raise APIError(f'{L("profissional")} já oferece este {L("servico").lower()}.', 409)

    db.session.add(BarbeiroServico(barbeiro_id=barbeiro_id, servico_id=servico_id))
    db.session.commit()

    return jsonify({
        'mensagem': f'{L("servico")} atribuído ao {L("profissional").lower()}.',
        'barbeiro_id': barbeiro_id,
        'servico_id':  servico_id,
        'servico_nome': s.nome,
    }), 201


@profissionais_bp.delete('/barbeiros/<int:barbeiro_id>/servicos/<int:servico_id>')
@gestor_required
def remover_servico(barbeiro_id, servico_id):
    barbearia_id = _barbearia_id_atual()
    _get_barbeiro(barbeiro_id, barbearia_id)

    bs = BarbeiroServico.query.filter_by(
        barbeiro_id=barbeiro_id, servico_id=servico_id
    ).first()
    if not bs:
        raise APIError('Atribuição não encontrada.', 404)

    db.session.delete(bs)
    db.session.commit()
    return jsonify({'mensagem': f'{L("servico")} removido do {L("profissional").lower()}.'}), 200
