import re
from datetime import datetime, timedelta, time as Time, date
from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from werkzeug.security import generate_password_hash
from sqlalchemy import func
from app import db
from app.models import Barbearia, Usuario, Barbeiro, Pagamento, Atendimento
from app.routes.auth import super_admin_required
from app.utils import registrar_auditoria

super_admin = Blueprint('super_admin', __name__, url_prefix='/super')

_SLUG_RE  = re.compile(r'^[a-z0-9-]+$')
_COR_RE   = re.compile(r'^#[0-9a-fA-F]{6}$')


def _erro(msg, code=400):
    return jsonify({'erro': msg}), code


def _fmt_barbearia(b, total_barbeiros=0, gestor=None):
    return {
        'id':               b.id,
        'nome':             b.nome,
        'slug':             b.slug,
        'ativo':            b.ativo,
        'criado_em':        b.criado_em.isoformat() if b.criado_em else None,
        'url_agendamento':  b.url_agendamento or f'/b/{b.slug}/',
        'tema': {
            'nome_exibicao': b.nome_exibicao or b.nome,
            'cor_primaria':  b.cor_primaria,
            'cor_fundo':     b.cor_fundo,
            'cor_card':      b.cor_card,
            'logo_url':      b.logo_url,
            'fonte':         b.fonte,
        },
        'total_barbeiros': total_barbeiros,
        'gestor': gestor,
    }


def _hash_senha(senha: str) -> str:
    return generate_password_hash(senha)


# ── GET /super/barbearias ──────────────────────────────────────────────────────

@super_admin.get('/barbearias/lista')
@super_admin_required
def listar_barbearias():
    barbearias = Barbearia.query.order_by(Barbearia.id).all()
    resultado = []
    for b in barbearias:
        total_barbeiros = Barbeiro.query.filter_by(barbearia_id=b.id, ativo=True).count()
        gestor_u = Usuario.query.filter_by(barbearia_id=b.id, perfil='gestor', ativo=True).first()
        gestor_info = None
        if gestor_u:
            gestor_info = {'id': gestor_u.id, 'nome': gestor_u.nome, 'email': gestor_u.email}
        resultado.append(_fmt_barbearia(b, total_barbeiros, gestor_info))
    return jsonify(resultado)


# ── POST /super/barbearias ─────────────────────────────────────────────────────

@super_admin.post('/barbearias')
@super_admin_required
def criar_barbearia():
    dados = request.get_json(silent=True)
    if not dados:
        return _erro('Corpo da requisição inválido ou ausente.')

    nome = (dados.get('nome') or '').strip()
    slug = (dados.get('slug') or '').strip().lower()

    if not nome:
        return _erro('O campo "nome" é obrigatório.')
    if not slug:
        return _erro('O campo "slug" é obrigatório.')
    if not _SLUG_RE.match(slug):
        return _erro('O slug deve conter apenas letras minúsculas, números e hífens.')
    if len(slug) > 50:
        return _erro('O slug deve ter no máximo 50 caracteres.')
    if Barbearia.query.filter_by(slug=slug).first():
        return _erro('Este slug já está em uso.', 409)

    tema_dados = dados.get('tema') or {}
    barbearia = Barbearia(
        nome=nome, slug=slug,
        nome_exibicao=(tema_dados.get('nome_exibicao') or '').strip() or None,
        cor_primaria=(tema_dados.get('cor_primaria') or '#BA7517'),
        cor_fundo=(tema_dados.get('cor_fundo') or '#1a1a1a'),
        cor_card=(tema_dados.get('cor_card') or '#2a2a2a'),
        fonte=(tema_dados.get('fonte') or 'Inter'),
        logo_url=(tema_dados.get('logo_url') or '').strip() or None,
    )
    db.session.add(barbearia)
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia.id, 'create', 'barbearia', barbearia.id,
                         f'Criou barbearia "{nome}".')

    return jsonify({
        'mensagem':  'Barbearia criada com sucesso.',
        'barbearia': _fmt_barbearia(barbearia),
    }), 201


# ── PUT /super/barbearias/<id> ─────────────────────────────────────────────────

@super_admin.put('/barbearias/<int:barbearia_id>')
@super_admin_required
def editar_barbearia(barbearia_id):
    barbearia = db.session.get(Barbearia, barbearia_id)
    if not barbearia:
        return _erro('Barbearia não encontrada.', 404)

    dados = request.get_json(silent=True) or {}

    if 'nome' in dados:
        nome = (dados['nome'] or '').strip()
        if not nome:
            return _erro('"nome" não pode ser vazio.')
        barbearia.nome = nome

    if 'slug' in dados:
        slug = (dados['slug'] or '').strip().lower()
        if not slug:
            return _erro('"slug" não pode ser vazio.')
        if not _SLUG_RE.match(slug):
            return _erro('O slug deve conter apenas letras minúsculas, números e hífens.')
        existente = Barbearia.query.filter_by(slug=slug).first()
        if existente and existente.id != barbearia_id:
            return _erro('Este slug já está em uso.', 409)
        barbearia.slug = slug

    if 'ativo' in dados:
        if not isinstance(dados['ativo'], bool):
            return _erro('"ativo" deve ser true ou false.')
        barbearia.ativo = dados['ativo']

    # Campos de tema (opcionais)
    tema = dados.get('tema') or {}
    for campo_cor in ('cor_primaria', 'cor_fundo', 'cor_card'):
        if campo_cor in tema:
            val = (tema[campo_cor] or '').strip()
            if val and not _COR_RE.match(val):
                return _erro(f'"{campo_cor}" deve ser um hex válido (ex: #BA7517).')
            setattr(barbearia, campo_cor, val or getattr(barbearia, campo_cor))

    if 'logo_url' in tema:
        barbearia.logo_url = (tema['logo_url'] or '').strip() or None
    if 'fonte' in tema:
        barbearia.fonte = (tema['fonte'] or '').strip() or 'Inter'
    if 'nome_exibicao' in tema:
        barbearia.nome_exibicao = (tema['nome_exibicao'] or '').strip() or None

    if 'url_agendamento' in dados:
        url = (dados['url_agendamento'] or '').strip()
        barbearia.url_agendamento = url or None

    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'edit', 'barbearia', barbearia_id,
                         f'Editou barbearia "{barbearia.nome}".')
    return jsonify({'mensagem': 'Barbearia atualizada com sucesso.', 'barbearia': _fmt_barbearia(barbearia)})


# ── PUT /super/barbearias/<id>/tema ───────────────────────────────────────────

@super_admin.put('/barbearias/<int:barbearia_id>/tema')
@super_admin_required
def atualizar_tema(barbearia_id):
    barbearia = db.session.get(Barbearia, barbearia_id)
    if not barbearia:
        return _erro('Barbearia não encontrada.', 404)

    dados = request.get_json(silent=True) or {}

    for campo_cor in ('cor_primaria', 'cor_fundo', 'cor_card'):
        if campo_cor in dados:
            val = (dados[campo_cor] or '').strip()
            if val and not _COR_RE.match(val):
                return _erro(f'"{campo_cor}" deve ser um hex válido (ex: #BA7517).')
            if val:
                setattr(barbearia, campo_cor, val)

    if 'logo_url' in dados:
        barbearia.logo_url = (dados['logo_url'] or '').strip() or None
    if 'fonte' in dados:
        barbearia.fonte = (dados['fonte'] or '').strip() or 'Inter'

    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'edit', 'barbearia', barbearia_id,
                         f'Atualizou tema de "{barbearia.nome}".')
    return jsonify({
        'mensagem': 'Tema atualizado com sucesso.',
        'tema': {
            'cor_primaria': barbearia.cor_primaria,
            'cor_fundo':    barbearia.cor_fundo,
            'cor_card':     barbearia.cor_card,
            'logo_url':     barbearia.logo_url,
            'fonte':        barbearia.fonte,
        },
    })


# ── GET /super/usuarios ────────────────────────────────────────────────────────

@super_admin.get('/usuarios')
@super_admin_required
def listar_usuarios():
    usuarios = (
        db.session.query(Usuario, Barbearia)
        .outerjoin(Barbearia, Usuario.barbearia_id == Barbearia.id)
        .order_by(Barbearia.nome, Usuario.nome)
        .all()
    )
    return jsonify([
        {
            'id':           u.id,
            'nome':         u.nome,
            'email':        u.email,
            'telefone':     u.telefone,
            'perfil':       u.perfil,
            'ativo':        u.ativo,
            'barbearia_id': u.barbearia_id,
            'barbearia':    b.nome if b else None,
        }
        for u, b in usuarios
    ])


# ── POST /super/gestor ─────────────────────────────────────────────────────────

@super_admin.post('/gestor')
@super_admin_required
def criar_gestor():
    dados = request.get_json(silent=True)
    if not dados:
        return _erro('Corpo da requisição inválido ou ausente.')

    nome         = (dados.get('nome') or '').strip()
    email        = (dados.get('email') or '').strip().lower()
    telefone     = (dados.get('telefone') or '').strip()
    senha        = (dados.get('senha') or '').strip()
    barbearia_id = dados.get('barbearia_id')

    if not nome:
        return _erro('O campo "nome" é obrigatório.')
    if not email or '@' not in email:
        return _erro('O campo "email" é obrigatório e deve ser válido.')
    if not telefone:
        return _erro('O campo "telefone" é obrigatório.')
    if not senha or len(senha) < 6:
        return _erro('A senha deve ter no mínimo 6 caracteres.')
    if not barbearia_id:
        return _erro('O campo "barbearia_id" é obrigatório.')

    barbearia = db.session.get(Barbearia, barbearia_id)
    if not barbearia:
        return _erro('Barbearia não encontrada.', 404)
    if Usuario.query.filter_by(email=email).first():
        return _erro('E-mail já cadastrado.', 409)

    usuario = Usuario(
        barbearia_id=barbearia_id,
        nome=nome,
        telefone=telefone,
        email=email,
        senha=_hash_senha(senha),
        perfil='gestor',
    )
    db.session.add(usuario)
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'create', 'usuario', usuario.id,
                         f'Criou gestor "{nome}" para "{barbearia.nome}".')

    return jsonify({
        'mensagem': 'Gestor criado com sucesso.',
        'usuario': {
            'id':           usuario.id,
            'nome':         usuario.nome,
            'email':        usuario.email,
            'telefone':     usuario.telefone,
            'perfil':       usuario.perfil,
            'barbearia_id': usuario.barbearia_id,
            'barbearia':    barbearia.nome,
        },
    }), 201


# ── GET /super/gestores ────────────────────────────────────────────────────────

@super_admin.get('/gestores/lista')
@super_admin_required
def listar_gestores():
    rows = (
        db.session.query(Usuario, Barbearia)
        .outerjoin(Barbearia, Usuario.barbearia_id == Barbearia.id)
        .filter(Usuario.perfil == 'gestor')
        .order_by(Usuario.nome).all()
    )
    return jsonify([
        {
            'id': u.id, 'nome': u.nome, 'email': u.email, 'telefone': u.telefone,
            'ativo': u.ativo, 'barbearia_id': u.barbearia_id,
            'barbearia': b.nome if b else None,
        }
        for u, b in rows
    ])


# ── PUT /super/gestor/<id> ─────────────────────────────────────────────────────

@super_admin.put('/gestor/<int:gestor_id>')
@super_admin_required
def editar_gestor(gestor_id):
    u = db.session.get(Usuario, gestor_id)
    if not u or u.perfil != 'gestor':
        return _erro('Gestor não encontrado.', 404)
    dados = request.get_json(silent=True) or {}
    if 'nome' in dados:
        n = (dados['nome'] or '').strip()
        if not n: return _erro('"nome" não pode ser vazio.')
        u.nome = n
    if 'email' in dados:
        e = (dados['email'] or '').strip().lower()
        dup = Usuario.query.filter_by(email=e).first()
        if dup and dup.id != u.id: return _erro('E-mail já cadastrado.', 409)
        u.email = e or None
    if 'telefone' in dados:
        u.telefone = (dados['telefone'] or '').strip() or u.telefone
    if 'barbearia_id' in dados:
        if dados['barbearia_id'] and not db.session.get(Barbearia, dados['barbearia_id']):
            return _erro('Barbearia não encontrada.', 404)
        u.barbearia_id = dados['barbearia_id']
    if 'ativo' in dados:
        u.ativo = bool(dados['ativo'])
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), u.barbearia_id, 'edit', 'usuario', u.id,
                         f'Editou gestor "{u.nome}".')
    return jsonify({'mensagem': 'Gestor atualizado.', 'gestor': {'id': u.id, 'nome': u.nome}})


# ── PUT /super/gestor/<id>/resetar-senha ──────────────────────────────────────

@super_admin.put('/gestor/<int:gestor_id>/resetar-senha')
@super_admin_required
def resetar_senha_gestor(gestor_id):
    u = db.session.get(Usuario, gestor_id)
    if not u or u.perfil != 'gestor':
        return _erro('Gestor não encontrado.', 404)
    dados = request.get_json(silent=True) or {}
    nova = (dados.get('nova_senha') or '').strip()
    if not nova or len(nova) < 6:
        return _erro('Senha mínima de 6 caracteres.')
    u.senha = _hash_senha(nova)
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), u.barbearia_id, 'edit', 'usuario', u.id,
                         f'Redefiniu senha do gestor "{u.nome}".')
    return jsonify({'mensagem': 'Senha redefinida.', 'gestor': {'id': u.id, 'nome': u.nome}})


# ── GET /super/dashboard/metricas ─────────────────────────────────────────────

@super_admin.get('/dashboard/metricas')
@super_admin_required
def dashboard_metricas():
    total_barbearias = Barbearia.query.count()
    total_usuarios   = Usuario.query.count()
    total_faturamento = db.session.query(func.sum(Pagamento.valor)).filter_by(status='aprovado').scalar() or 0

    hoje = date.today()
    receita_7dias = []
    for i in range(6, -1, -1):
        dia = hoje - timedelta(days=i)
        ini = datetime.combine(dia, Time(0, 0))
        fim = ini + timedelta(days=1)
        r = db.session.query(func.sum(Pagamento.valor)).filter(
            Pagamento.status   == 'aprovado',
            Pagamento.criado_em >= ini,
            Pagamento.criado_em <  fim,
        ).scalar() or 0
        receita_7dias.append({'data': dia.isoformat(), 'receita': float(r)})

    ultimas = Barbearia.query.order_by(Barbearia.id.desc()).limit(5).all()

    return jsonify({
        'total_barbearias':  total_barbearias,
        'total_usuarios':    total_usuarios,
        'total_faturamento': float(total_faturamento),
        'receita_7dias':     receita_7dias,
        'ultimas_barbearias': [
            {'id': b.id, 'nome': b.nome, 'slug': b.slug, 'ativo': b.ativo,
             'criado_em': b.criado_em.isoformat() if b.criado_em else None}
            for b in ultimas
        ],
    })
