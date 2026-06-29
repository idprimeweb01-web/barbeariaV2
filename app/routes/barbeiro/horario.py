from datetime import time
from flask import Blueprint, request, g, jsonify
from app.extensions import db
from app.models import Barbeiro, ConfiguracaoAgenda, PausaBarbeiro
from app.exceptions import APIError
from app.decorators.auth import barbeiro_required

barbeiro_horario_bp = Blueprint('barbeiro_horario', __name__, url_prefix='/api/v1/barbeiro')


def _get_barbeiro(user_id, barbearia_id):
    b = Barbeiro.query.filter_by(usuario_id=user_id, barbearia_id=barbearia_id, ativo=True).first()
    if not b:
        raise APIError('Profissional não encontrado.', 404)
    return b


def _fmt_config(cfg):
    if not cfg:
        return None
    return {
        'horario_abertura':   cfg.horario_abertura.strftime('%H:%M') if cfg.horario_abertura else None,
        'horario_fechamento': cfg.horario_fechamento.strftime('%H:%M') if cfg.horario_fechamento else None,
        'intervalo_minutos':  cfg.intervalo_minutos,
        'loja_aberta':        cfg.loja_aberta,
    }


def _fmt_pausa(p):
    return {
        'id':          p.id,
        'hora_inicio': p.hora_inicio.strftime('%H:%M') if p.hora_inicio else None,
        'hora_fim':    p.hora_fim.strftime('%H:%M') if p.hora_fim else None,
        'descricao':   p.descricao,
    }


# ── GET /api/v1/barbeiro/horario ──────────────────────────────────────────────

@barbeiro_horario_bp.get('/horario')
@barbeiro_required
def get_horario():
    b      = _get_barbeiro(g.user_id, g.barbearia_id)
    cfg    = ConfiguracaoAgenda.query.filter_by(barbeiro_id=b.id).first()
    pausas = (PausaBarbeiro.query
              .filter_by(barbeiro_id=b.id)
              .order_by(PausaBarbeiro.hora_inicio).all())
    return jsonify({'config': _fmt_config(cfg), 'pausas': [_fmt_pausa(p) for p in pausas]}), 200


# ── PATCH /api/v1/barbeiro/horario ───────────────────────────────────────────

@barbeiro_horario_bp.patch('/horario')
@barbeiro_required
def atualizar_horario():
    b     = _get_barbeiro(g.user_id, g.barbearia_id)
    dados = request.get_json(silent=True) or {}

    cfg = ConfiguracaoAgenda.query.filter_by(barbeiro_id=b.id).first()
    if not cfg:
        cfg = ConfiguracaoAgenda(
            barbearia_id=g.barbearia_id, barbeiro_id=b.id,
            horario_abertura=time(8, 0), horario_fechamento=time(18, 0),
            intervalo_minutos=30,
        )
        db.session.add(cfg)

    if 'horario_abertura' in dados:
        try:
            cfg.horario_abertura = time.fromisoformat(dados['horario_abertura'])
        except Exception:
            raise APIError('"horario_abertura" inválido. Use HH:MM.', 422)
    if 'horario_fechamento' in dados:
        try:
            cfg.horario_fechamento = time.fromisoformat(dados['horario_fechamento'])
        except Exception:
            raise APIError('"horario_fechamento" inválido. Use HH:MM.', 422)
    if 'intervalo_minutos' in dados:
        try:
            v = int(dados['intervalo_minutos'])
        except Exception:
            raise APIError('"intervalo_minutos" deve ser inteiro.', 422)
        if v < 5:
            raise APIError('"intervalo_minutos" mínimo é 5.', 422)
        cfg.intervalo_minutos = v
    if 'loja_aberta' in dados:
        cfg.loja_aberta = bool(dados['loja_aberta'])

    db.session.commit()
    return jsonify({'config': _fmt_config(cfg)}), 200


# ── POST /api/v1/barbeiro/pausas ─────────────────────────────────────────────

@barbeiro_horario_bp.post('/pausas')
@barbeiro_required
def criar_pausa():
    b     = _get_barbeiro(g.user_id, g.barbearia_id)
    dados = request.get_json(silent=True) or {}

    ini_str = (dados.get('hora_inicio') or '').strip()
    fim_str = (dados.get('hora_fim') or '').strip()
    if not ini_str or not fim_str:
        raise APIError('"hora_inicio" e "hora_fim" são obrigatórios.', 422)
    try:
        hora_ini = time.fromisoformat(ini_str)
        hora_fim = time.fromisoformat(fim_str)
    except Exception:
        raise APIError('"hora_inicio" e "hora_fim" devem ser HH:MM.', 422)
    if hora_fim <= hora_ini:
        raise APIError('"hora_fim" deve ser após "hora_inicio".', 422)

    for p in PausaBarbeiro.query.filter_by(barbeiro_id=b.id).all():
        if p.hora_inicio < hora_fim and p.hora_fim > hora_ini:
            descr = p.descricao or f'{p.hora_inicio.strftime("%H:%M")}–{p.hora_fim.strftime("%H:%M")}'
            raise APIError(f'Conflito com pausa "{descr}" já cadastrada.', 409)

    pausa = PausaBarbeiro(
        barbearia_id=g.barbearia_id, barbeiro_id=b.id,
        hora_inicio=hora_ini, hora_fim=hora_fim,
        descricao=(dados.get('descricao') or '').strip() or None,
    )
    db.session.add(pausa)
    db.session.commit()
    return jsonify({'pausa': _fmt_pausa(pausa)}), 201


# ── PATCH /api/v1/barbeiro/pausas/<id> ───────────────────────────────────────

@barbeiro_horario_bp.patch('/pausas/<int:pausa_id>')
@barbeiro_required
def editar_pausa(pausa_id):
    b     = _get_barbeiro(g.user_id, g.barbearia_id)
    pausa = PausaBarbeiro.query.filter_by(
        id=pausa_id, barbeiro_id=b.id, barbearia_id=g.barbearia_id
    ).first()
    if not pausa:
        raise APIError('Pausa não encontrada.', 404)

    dados = request.get_json(silent=True) or {}
    ini_str = (dados.get('hora_inicio') or '').strip()
    fim_str = (dados.get('hora_fim') or '').strip()
    if not ini_str or not fim_str:
        raise APIError('"hora_inicio" e "hora_fim" são obrigatórios.', 422)
    try:
        hora_ini = time.fromisoformat(ini_str)
        hora_fim = time.fromisoformat(fim_str)
    except Exception:
        raise APIError('"hora_inicio" e "hora_fim" devem ser HH:MM.', 422)
    if hora_fim <= hora_ini:
        raise APIError('"hora_fim" deve ser após "hora_inicio".', 422)

    for p in PausaBarbeiro.query.filter_by(barbeiro_id=b.id).all():
        if p.id == pausa_id:
            continue
        if p.hora_inicio < hora_fim and p.hora_fim > hora_ini:
            descr = p.descricao or f'{p.hora_inicio.strftime("%H:%M")}–{p.hora_fim.strftime("%H:%M")}'
            raise APIError(f'Conflito com pausa "{descr}" já cadastrada.', 409)

    pausa.hora_inicio = hora_ini
    pausa.hora_fim    = hora_fim
    pausa.descricao   = (dados.get('descricao') or '').strip() or None
    db.session.commit()
    return jsonify({'pausa': _fmt_pausa(pausa)}), 200


# ── DELETE /api/v1/barbeiro/pausas/<id> ──────────────────────────────────────

@barbeiro_horario_bp.delete('/pausas/<int:pausa_id>')
@barbeiro_required
def deletar_pausa(pausa_id):
    b     = _get_barbeiro(g.user_id, g.barbearia_id)
    pausa = PausaBarbeiro.query.filter_by(
        id=pausa_id, barbeiro_id=b.id, barbearia_id=g.barbearia_id
    ).first()
    if not pausa:
        raise APIError('Pausa não encontrada.', 404)
    db.session.delete(pausa)
    db.session.commit()
    return jsonify({'mensagem': 'Pausa removida.'}), 200
