from flask import Blueprint, request, g, jsonify
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import (
    Barbearia, Usuario, FeatureMetadata, FeatureBarbearia,
    BarbeariaCustomizacao, ConfiguracaoAgendamento,
)
from app.exceptions import APIError
from app.decorators.auth import super_required
from app.utils import normalizar_telefone

super_bp = Blueprint('super', __name__, url_prefix='/api/v1/super')

# ── Helpers ───────────────────────────────────────────────────────────────────

_COR_FIELDS = [
    'cor_primaria', 'cor_secundaria', 'cor_acentuacao',
    'texto_primario', 'texto_secundario', 'texto_terciario',
    'botao_primario', 'botao_secundario',
]

def _fmt_barbearia(b):
    return {
        'id':              b.id,
        'nome':            b.nome,
        'nome_exibicao':   b.nome_exibicao,
        'slug':            b.slug,
        'ativo':           b.ativo,
        'url_agendamento': b.url_agendamento,
        'chave_pix':       b.chave_pix,
        'pix_nome_titular': b.pix_nome_titular,
        'pix_cidade':      b.pix_cidade,
        'pix_banco':       b.pix_banco,
        'criado_em':       b.criado_em.isoformat() if b.criado_em else None,
    }


def _fmt_customizacao(c):
    if not c:
        return None
    return {f: getattr(c, f) for f in _COR_FIELDS + ['fonte']}


def _features_map(barbearia_id):
    """2 queries: todas as features do catálogo + flags da barbearia."""
    todas = FeatureMetadata.query.order_by(FeatureMetadata.nome).all()
    flags = {
        fb.feature_id: fb.ativo
        for fb in FeatureBarbearia.query.filter_by(barbearia_id=barbearia_id).all()
    }
    return {fm.nome: flags.get(fm.id, False) for fm in todas}


def _get_barbearia_or_404(barbearia_id):
    b = db.session.get(Barbearia, barbearia_id)
    if not b:
        raise APIError('Barbearia não encontrada.', 404)
    return b


# ── POST /api/v1/super/barbearias ─────────────────────────────────────────────

@super_bp.post('/barbearias')
@super_required
def criar_barbearia():
    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    nome          = (dados.get('nome') or '').strip()
    slug          = (dados.get('slug') or '').strip().lower()
    nome_exibicao = (dados.get('nome_exibicao') or '').strip() or None
    gestor_nome   = (dados.get('gestor_nome') or '').strip()
    gestor_email  = (dados.get('gestor_email') or '').strip().lower()
    gestor_tel    = (dados.get('gestor_telefone') or '').strip()
    gestor_senha  = dados.get('gestor_senha') or ''

    if not nome:
        raise APIError('"nome" é obrigatório.')
    if not slug:
        raise APIError('"slug" é obrigatório.')
    if not gestor_nome:
        raise APIError('"gestor_nome" é obrigatório.')
    if not gestor_email:
        raise APIError('"gestor_email" é obrigatório.')
    if not gestor_tel:
        raise APIError('"gestor_telefone" é obrigatório.')
    gestor_tel_norm, tel_erro = normalizar_telefone(gestor_tel)
    if tel_erro:
        raise APIError(f'"gestor_telefone": {tel_erro}')
    if len(gestor_senha) < 6:
        raise APIError('"gestor_senha" deve ter no mínimo 6 caracteres.')

    if Barbearia.query.filter_by(slug=slug).first():
        raise APIError(f'Slug "{slug}" já está em uso.', 409)
    if Usuario.query.filter_by(email=gestor_email).first():
        raise APIError(f'Email "{gestor_email}" já está em uso.', 409)

    # Bloco atômico — tudo ou nada
    barbearia = Barbearia(nome=nome, slug=slug, nome_exibicao=nome_exibicao, ativo=True)
    db.session.add(barbearia)
    db.session.flush()  # obtém barbearia.id sem commitar

    gestor = Usuario(
        barbearia_id=barbearia.id,
        nome=gestor_nome,
        email=gestor_email,
        telefone=gestor_tel_norm,
        senha=generate_password_hash(gestor_senha),
        perfil='gestor',
        ativo=True,
    )
    db.session.add(gestor)

    db.session.add(BarbeariaCustomizacao(barbearia_id=barbearia.id))
    db.session.add(ConfiguracaoAgendamento(barbearia_id=barbearia.id))

    for fm in FeatureMetadata.query.all():
        db.session.add(FeatureBarbearia(
            barbearia_id=barbearia.id,
            feature_id=fm.id,
            ativo=False,
        ))

    db.session.commit()

    return jsonify({
        'mensagem': 'Barbearia criada com sucesso.',
        'barbearia': _fmt_barbearia(barbearia),
        'gestor': {'id': gestor.id, 'nome': gestor.nome, 'email': gestor.email},
    }), 201


# ── GET /api/v1/super/barbearias ──────────────────────────────────────────────

@super_bp.get('/barbearias')
@super_required
def listar_barbearias():
    ativo_param = request.args.get('ativo')
    q = Barbearia.query
    if ativo_param == 'true':
        q = q.filter_by(ativo=True)
    elif ativo_param == 'false':
        q = q.filter_by(ativo=False)
    return jsonify([_fmt_barbearia(b) for b in q.order_by(Barbearia.nome).all()]), 200


# ── GET /api/v1/super/barbearias/<id> ────────────────────────────────────────

@super_bp.get('/barbearias/<int:barbearia_id>')
@super_required
def detalhar_barbearia(barbearia_id):
    b = _get_barbearia_or_404(barbearia_id)
    gestor = Usuario.query.filter_by(
        barbearia_id=barbearia_id, perfil='gestor', ativo=True
    ).first()
    customizacao = BarbeariaCustomizacao.query.filter_by(barbearia_id=barbearia_id).first()
    return jsonify({
        **_fmt_barbearia(b),
        'gestor': (
            {'id': gestor.id, 'nome': gestor.nome, 'email': gestor.email}
            if gestor else None
        ),
        'customizacao': _fmt_customizacao(customizacao),
        'features': _features_map(barbearia_id),
    }), 200


# ── PATCH /api/v1/super/barbearias/<id> ──────────────────────────────────────

@super_bp.patch('/barbearias/<int:barbearia_id>')
@super_required
def editar_barbearia(barbearia_id):
    b = _get_barbearia_or_404(barbearia_id)
    dados = request.get_json(silent=True) or {}

    if 'nome' in dados:
        nome = (dados['nome'] or '').strip()
        if not nome:
            raise APIError('"nome" não pode ser vazio.')
        b.nome = nome

    if 'nome_exibicao' in dados:
        b.nome_exibicao = (dados['nome_exibicao'] or '').strip() or None

    if 'slug' in dados:
        slug = (dados['slug'] or '').strip().lower()
        if not slug:
            raise APIError('"slug" não pode ser vazio.')
        existente = Barbearia.query.filter_by(slug=slug).first()
        if existente and existente.id != barbearia_id:
            raise APIError(f'Slug "{slug}" já está em uso.', 409)
        b.slug = slug

    for campo in ('url_agendamento', 'chave_pix', 'pix_nome_titular', 'pix_cidade', 'pix_banco'):
        if campo in dados:
            setattr(b, campo, (dados[campo] or '').strip() or None)

    db.session.commit()
    return jsonify({'mensagem': 'Barbearia atualizada.', 'barbearia': _fmt_barbearia(b)}), 200


# ── POST /api/v1/super/barbearias/<id>/desativar ──────────────────────────────

@super_bp.post('/barbearias/<int:barbearia_id>/desativar')
@super_required
def desativar_barbearia(barbearia_id):
    b = _get_barbearia_or_404(barbearia_id)
    if not b.ativo:
        raise APIError('Barbearia já está inativa.')

    b.ativo = False
    Usuario.query.filter_by(barbearia_id=barbearia_id).update({'ativo': False})
    db.session.commit()

    return jsonify({'mensagem': 'Barbearia desativada.', 'id': barbearia_id}), 200


# ── POST /api/v1/super/barbearias/<id>/ativar ────────────────────────────────

@super_bp.post('/barbearias/<int:barbearia_id>/ativar')
@super_required
def ativar_barbearia(barbearia_id):
    b = _get_barbearia_or_404(barbearia_id)
    if b.ativo:
        raise APIError('Barbearia já está ativa.')

    b.ativo = True
    # Reativa apenas o gestor — barbeiros e clientes reativam via gestor
    Usuario.query.filter_by(barbearia_id=barbearia_id, perfil='gestor').update({'ativo': True})
    db.session.commit()

    return jsonify({'mensagem': 'Barbearia reativada.', 'id': barbearia_id}), 200


# ── GET /api/v1/super/barbearias/<id>/features ───────────────────────────────

@super_bp.get('/barbearias/<int:barbearia_id>/features')
@super_required
def listar_features(barbearia_id):
    _get_barbearia_or_404(barbearia_id)
    return jsonify(_features_map(barbearia_id)), 200


# ── PUT /api/v1/super/barbearias/<id>/features/<nome> ────────────────────────

@super_bp.put('/barbearias/<int:barbearia_id>/features/<nome_feature>')
@super_required
def toggle_feature(barbearia_id, nome_feature):
    _get_barbearia_or_404(barbearia_id)

    fm = FeatureMetadata.query.filter_by(nome=nome_feature).first()
    if not fm:
        raise APIError(f'Feature "{nome_feature}" não existe no catálogo.', 404)

    fb = FeatureBarbearia.query.filter_by(
        barbearia_id=barbearia_id, feature_id=fm.id
    ).first()

    if fb:
        fb.ativo = not fb.ativo
    else:
        fb = FeatureBarbearia(barbearia_id=barbearia_id, feature_id=fm.id, ativo=True)
        db.session.add(fb)

    db.session.commit()

    estado = 'ativada' if fb.ativo else 'desativada'
    return jsonify({'feature': nome_feature, 'ativo': fb.ativo, 'mensagem': f'Feature {estado}.'}), 200


# ── GET /api/v1/super/barbearias/<id>/customizacao ───────────────────────────

@super_bp.get('/barbearias/<int:barbearia_id>/customizacao')
@super_required
def ver_customizacao(barbearia_id):
    _get_barbearia_or_404(barbearia_id)
    c = BarbeariaCustomizacao.query.filter_by(barbearia_id=barbearia_id).first()
    if not c:
        raise APIError('Customização não encontrada.', 404)
    return jsonify(_fmt_customizacao(c)), 200


# ── PUT /api/v1/super/barbearias/<id>/customizacao ───────────────────────────

@super_bp.put('/barbearias/<int:barbearia_id>/customizacao')
@super_required
def editar_customizacao(barbearia_id):
    _get_barbearia_or_404(barbearia_id)

    c = BarbeariaCustomizacao.query.filter_by(barbearia_id=barbearia_id).first()
    if not c:
        raise APIError('Customização não encontrada.', 404)

    dados = request.get_json(silent=True) or {}

    for campo in _COR_FIELDS:
        if campo in dados:
            valor = (dados[campo] or '').strip()
            if valor and not valor.startswith('#'):
                raise APIError(f'"{campo}" deve ser um código hex (#RRGGBB).')
            setattr(c, campo, valor or getattr(c, campo))

    if 'fonte' in dados:
        c.fonte = (dados['fonte'] or '').strip() or c.fonte

    db.session.commit()
    return jsonify({'mensagem': 'Customização atualizada.', 'customizacao': _fmt_customizacao(c)}), 200


# ── Trigger manual do scheduler (apenas super, apenas em dev) ─────────────────

@super_bp.post('/scheduler/executar-lembretes')
@super_required
def executar_lembretes_agora():
    """
    Dispara o job de lembretes imediatamente (sem esperar o intervalo de 1 min).
    Útil para testar: criar um agendamento na janela de notificação e chamar este endpoint.
    NÃO disponibilizar em produção sem autenticação adicional.
    """
    from app.utils.scheduler import _executar_lembretes
    import traceback
    try:
        _executar_lembretes()
        return jsonify({'mensagem': 'Job executado. Verifique as notificações geradas.'}), 200
    except Exception as exc:
        return jsonify({'erro': str(exc), 'traceback': traceback.format_exc()}), 500
