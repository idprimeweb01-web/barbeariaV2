import re
from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from app import db
from app.models import BarbeariaCustomizacao, Barbearia
from app.utils import registrar_auditoria
from app.routes.auth import super_admin_required

customizacao = Blueprint('customizacao', __name__, url_prefix='/api/super')

_COR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')
CAMPOS_COR = (
    'cor_primaria', 'cor_secundaria', 'cor_acentuacao',
    'texto_primario', 'texto_secundario', 'texto_terciario',
    'botao_primario', 'botao_secundario',
)


def _erro(msg, code=400):
    return jsonify({'erro': msg}), code


def _get_or_create(barbearia_id):
    c = BarbeariaCustomizacao.query.filter_by(barbearia_id=barbearia_id).first()
    if not c:
        c = BarbeariaCustomizacao(barbearia_id=barbearia_id)
        db.session.add(c)
        db.session.commit()
    return c


def _fmt(c, nome_barbearia):
    return {
        'barbearia_id': c.barbearia_id,
        'barbearia_nome': nome_barbearia,
        'cor_primaria': c.cor_primaria,
        'cor_secundaria': c.cor_secundaria,
        'cor_acentuacao': c.cor_acentuacao,
        'texto_primario': c.texto_primario,
        'texto_secundario': c.texto_secundario,
        'texto_terciario': c.texto_terciario,
        'botao_primario': c.botao_primario,
        'botao_secundario': c.botao_secundario,
        'logo_filename': c.logo_filename,
        'fundo_padrao_filename': c.fundo_padrao_filename,
        'fonte': c.fonte,
    }


# ── GET /api/super/customizacoes ─────────────────────────────────────────────────

@customizacao.get('/customizacoes')
@super_admin_required
def listar_customizacoes():
    barbearias = Barbearia.query.order_by(Barbearia.nome).all()
    return jsonify([_fmt(_get_or_create(b.id), b.nome) for b in barbearias])


# ── PUT /api/super/customizacoes/<barbearia_id> ──────────────────────────────────

@customizacao.put('/customizacoes/<int:barbearia_id>')
@super_admin_required
def atualizar_customizacao(barbearia_id):
    barbearia = db.session.get(Barbearia, barbearia_id)
    if not barbearia:
        return _erro('Barbearia não encontrada.', 404)

    c = _get_or_create(barbearia_id)
    dados = request.get_json(silent=True) or {}

    for campo in CAMPOS_COR:
        if campo in dados:
            val = (dados[campo] or '').strip()
            if val and not _COR_RE.match(val):
                return _erro(f'"{campo}" deve ser um hex válido (ex: #BA7517).')
            if val:
                setattr(c, campo, val)
    if 'fonte' in dados:
        c.fonte = (dados['fonte'] or '').strip() or 'Inter'
    if 'logo_filename' in dados:
        c.logo_filename = (dados['logo_filename'] or '').strip() or None
    if 'fundo_padrao_filename' in dados:
        c.fundo_padrao_filename = (dados['fundo_padrao_filename'] or '').strip() or None

    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'edit', 'customizacao', c.id,
                         f'Atualizou customização visual de "{barbearia.nome}".')
    return jsonify({'mensagem': 'Customização atualizada.', 'customizacao': _fmt(c, barbearia.nome)})
