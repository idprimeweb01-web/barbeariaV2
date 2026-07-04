from datetime import time
from flask import Blueprint, request, g, jsonify
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import Barbeiro, Usuario, Servico, BarbeiroServico, ConfiguracaoAgenda, PausaBarbeiro
from app.exceptions import APIError
from app.decorators.auth import gestor_required
from app.labels import L
from app.utils import normalizar_telefone
from app.utils.auditoria import registrar_auditoria
from app.utils.auth import revogar_todos_tokens

profissionais_bp = Blueprint('gestor_profissionais', __name__, url_prefix='/api/v1/gestor')


def _barbearia_id_atual():
    if g.barbearia_id:
        return g.barbearia_id
    raise APIError('Sem barbearia ativa no contexto.', 403)


def _fmt_barbeiro(b):
    u   = b.usuario
    cfg = b.configuracao_agenda
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
        'barbeiro_id':               b.id,
        'configuracao': {
            'horario_abertura':          cfg.horario_abertura.strftime('%H:%M') if cfg and cfg.horario_abertura else None,
            'horario_fechamento':        cfg.horario_fechamento.strftime('%H:%M') if cfg and cfg.horario_fechamento else None,
            'intervalo_minutos':         cfg.intervalo_minutos if cfg else 30,
            'loja_aberta':               cfg.loja_aberta if cfg else False,
            'permite_horario_barbeiro':  cfg.permite_horario_barbeiro if cfg else False,
        } if cfg else None,
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
        if not ativo:
            revogar_todos_tokens(u, 'usuario_desativado')
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


# ── Agenda: horário e pausas recorrentes ─────────────────────────────────────

def _fmt_config(cfg):
    if not cfg:
        return None
    return {
        'id':                        cfg.id,
        'horario_abertura':          cfg.horario_abertura.strftime('%H:%M') if cfg.horario_abertura else None,
        'horario_fechamento':        cfg.horario_fechamento.strftime('%H:%M') if cfg.horario_fechamento else None,
        'intervalo_minutos':         cfg.intervalo_minutos,
        'loja_aberta':               cfg.loja_aberta,
        'permite_horario_barbeiro':  cfg.permite_horario_barbeiro,
    }


def _fmt_pausa(p):
    return {
        'id':          p.id,
        'hora_inicio': p.hora_inicio.strftime('%H:%M') if p.hora_inicio else None,
        'hora_fim':    p.hora_fim.strftime('%H:%M') if p.hora_fim else None,
        'descricao':   p.descricao,
    }


@profissionais_bp.get('/barbeiros/<int:barbeiro_id>/agenda')
@gestor_required
def get_agenda(barbeiro_id):
    barbearia_id = _barbearia_id_atual()
    _get_barbeiro(barbeiro_id, barbearia_id)
    config = ConfiguracaoAgenda.query.filter_by(barbeiro_id=barbeiro_id).first()
    pausas = (PausaBarbeiro.query
              .filter_by(barbeiro_id=barbeiro_id)
              .order_by(PausaBarbeiro.hora_inicio)
              .all())
    return jsonify({'config': _fmt_config(config), 'pausas': [_fmt_pausa(p) for p in pausas]}), 200


@profissionais_bp.put('/barbeiros/<int:barbeiro_id>/agenda')
@gestor_required
def put_agenda(barbeiro_id):
    barbearia_id = _barbearia_id_atual()
    _get_barbeiro(barbeiro_id, barbearia_id)
    dados = request.get_json(silent=True) or {}

    config = ConfiguracaoAgenda.query.filter_by(barbeiro_id=barbeiro_id).first()
    if not config:
        config = ConfiguracaoAgenda(
            barbearia_id=barbearia_id, barbeiro_id=barbeiro_id,
            horario_abertura=time(8, 0), horario_fechamento=time(18, 0),
            intervalo_minutos=30,
        )
        db.session.add(config)

    if 'horario_abertura' in dados:
        try:
            config.horario_abertura = time.fromisoformat(dados['horario_abertura'])
        except Exception:
            raise APIError('"horario_abertura" inválido. Use HH:MM.')
    if 'horario_fechamento' in dados:
        try:
            config.horario_fechamento = time.fromisoformat(dados['horario_fechamento'])
        except Exception:
            raise APIError('"horario_fechamento" inválido. Use HH:MM.')
    if 'intervalo_minutos' in dados:
        try:
            v = int(dados['intervalo_minutos'])
        except Exception:
            raise APIError('"intervalo_minutos" deve ser um inteiro.')
        if v < 5:
            raise APIError('"intervalo_minutos" deve ser no mínimo 5.')
        config.intervalo_minutos = v
    if 'loja_aberta' in dados:
        config.loja_aberta = bool(dados['loja_aberta'])
    if 'permite_horario_barbeiro' in dados:
        config.permite_horario_barbeiro = bool(dados['permite_horario_barbeiro'])

    db.session.commit()
    return jsonify({'config': _fmt_config(config)}), 200


@profissionais_bp.post('/barbeiros/<int:barbeiro_id>/agenda/pausas')
@gestor_required
def criar_pausa(barbeiro_id):
    barbearia_id = _barbearia_id_atual()
    _get_barbeiro(barbeiro_id, barbearia_id)
    dados = request.get_json(silent=True) or {}

    ini_str = (dados.get('hora_inicio') or '').strip()
    fim_str = (dados.get('hora_fim') or '').strip()
    if not ini_str or not fim_str:
        raise APIError('"hora_inicio" e "hora_fim" são obrigatórios.')
    try:
        hora_ini = time.fromisoformat(ini_str)
        hora_fim = time.fromisoformat(fim_str)
    except Exception:
        raise APIError('"hora_inicio" e "hora_fim" devem estar no formato HH:MM.')

    if hora_fim <= hora_ini:
        raise APIError('"hora_fim" deve ser depois de "hora_inicio".')

    config = ConfiguracaoAgenda.query.filter_by(barbeiro_id=barbeiro_id).first()
    if config:
        if hora_ini < config.horario_abertura or hora_fim > config.horario_fechamento:
            raise APIError('A pausa deve estar dentro do horário de trabalho do funcionário.')

    for p in PausaBarbeiro.query.filter_by(barbeiro_id=barbeiro_id).all():
        if p.hora_inicio < hora_fim and p.hora_fim > hora_ini:
            descr = p.descricao or f'{p.hora_inicio.strftime("%H:%M")}–{p.hora_fim.strftime("%H:%M")}'
            raise APIError(f'Conflito com a pausa "{descr}" já cadastrada.')

    pausa = PausaBarbeiro(
        barbearia_id=barbearia_id, barbeiro_id=barbeiro_id,
        hora_inicio=hora_ini, hora_fim=hora_fim,
        descricao=(dados.get('descricao') or '').strip() or None,
    )
    db.session.add(pausa)
    db.session.commit()
    return jsonify({'pausa': _fmt_pausa(pausa)}), 201


@profissionais_bp.delete('/barbeiros/<int:barbeiro_id>/agenda/pausas/<int:pausa_id>')
@gestor_required
def deletar_pausa(barbeiro_id, pausa_id):
    barbearia_id = _barbearia_id_atual()
    _get_barbeiro(barbeiro_id, barbearia_id)
    pausa = PausaBarbeiro.query.filter_by(
        id=pausa_id, barbeiro_id=barbeiro_id, barbearia_id=barbearia_id
    ).first()
    if not pausa:
        raise APIError('Pausa não encontrada.', 404)
    db.session.delete(pausa)
    db.session.commit()
    return jsonify({'mensagem': 'Pausa removida.'}), 200
