import re
from flask import Blueprint, g, request, jsonify
from app.extensions import db
from app.models import Barbearia, BarbeariaCustomizacao
from app.exceptions import APIError
from app.decorators.auth import gestor_required
from app.utils.db import commit_ou_falhar

gestor_barbearia_bp = Blueprint('gestor_barbearia', __name__, url_prefix='/api/v1/gestor')


def _get_barbearia():
    b = db.session.get(Barbearia, g.barbearia_id)
    if not b:
        raise APIError('Barbearia não encontrada.', 404)
    return b


# ── GET /api/v1/gestor/barbearia/pix ─────────────────────────────────────────

@gestor_barbearia_bp.get('/barbearia/pix')
@gestor_required
def get_pix():
    b = _get_barbearia()
    return jsonify({
        'chave_pix':        b.chave_pix,
        'pix_nome_titular': b.pix_nome_titular,
        'pix_cidade':       b.pix_cidade,
        'pix_banco':        b.pix_banco,
    }), 200


# ── PATCH /api/v1/gestor/barbearia/pix ───────────────────────────────────────

@gestor_barbearia_bp.patch('/barbearia/pix')
@gestor_required
def salvar_pix():
    b    = _get_barbearia()
    dados = request.get_json(silent=True) or {}

    if 'chave_pix' in dados:
        v = (dados['chave_pix'] or '').strip()
        b.chave_pix = v or None
    if 'nome_titular' in dados:
        v = (dados['nome_titular'] or '').strip()[:25]
        b.pix_nome_titular = v or None
    if 'cidade' in dados:
        v = (dados['cidade'] or '').strip()[:15]
        b.pix_cidade = v or None
    if 'banco' in dados:
        v = (dados['banco'] or '').strip()
        b.pix_banco = v or None

    commit_ou_falhar('gestor.barbearia.salvar_pix')
    return jsonify({'mensagem': 'PIX configurado com sucesso.'}), 200


# ── POST /api/v1/gestor/barbearia/pix/testar ─────────────────────────────────

@gestor_barbearia_bp.post('/barbearia/pix/testar')
@gestor_required
def testar_pix():
    dados = request.get_json(silent=True) or {}
    chave = (dados.get('chave_pix') or '').strip()
    if not chave:
        raise APIError('"chave_pix" é obrigatório.')

    # Validação básica por tipo de chave PIX
    def _email(s):
        return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', s))

    def _cpf(s):
        digits = re.sub(r'\D', '', s)
        return len(digits) == 11

    def _cnpj(s):
        digits = re.sub(r'\D', '', s)
        return len(digits) == 14

    def _telefone(s):
        digits = re.sub(r'\D', '', s)
        return 10 <= len(digits) <= 13

    def _uuid(s):
        return bool(re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', s, re.I))

    if _email(chave):
        return jsonify({'valida': True, 'mensagem': 'Chave PIX do tipo e-mail parece válida.'}), 200
    if _cpf(chave):
        return jsonify({'valida': True, 'mensagem': 'Chave PIX do tipo CPF com 11 dígitos.'}), 200
    if _cnpj(chave):
        return jsonify({'valida': True, 'mensagem': 'Chave PIX do tipo CNPJ com 14 dígitos.'}), 200
    if _telefone(chave):
        return jsonify({'valida': True, 'mensagem': 'Chave PIX do tipo telefone parece válida.'}), 200
    if _uuid(chave):
        return jsonify({'valida': True, 'mensagem': 'Chave PIX aleatória (UUID) válida.'}), 200

    return jsonify({'valida': False, 'mensagem': 'Formato de chave PIX não reconhecido.'}), 200


# ── GET /api/v1/gestor/barbearia/tema ────────────────────────────────────────

@gestor_barbearia_bp.get('/barbearia/tema')
@gestor_required
def get_tema():
    b    = _get_barbearia()
    cust = BarbeariaCustomizacao.query.filter_by(barbearia_id=g.barbearia_id).first()
    return jsonify({
        'cor_primaria':  cust.cor_primaria  if cust else '#BA7517',
        'cor_fundo':     cust.cor_secundaria if cust else '#1a1a1a',
        'cor_card':      None,
        'fonte':         cust.fonte         if cust else 'Inter',
        'nome_exibicao': b.nome_exibicao or b.nome,
    }), 200
