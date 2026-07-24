"""Perfil do gestor: editar os dados da própria barbearia (sem depender do
super_admin) e a própria conta (nome/e-mail/senha). Chave PIX/webhook/aparência
já têm suas próprias telas — este arquivo não duplica esses campos."""
from datetime import time as time_t
from flask import Blueprint, request, g, jsonify
import cloudinary
import cloudinary.uploader
from werkzeug.security import check_password_hash, generate_password_hash
from app.extensions import db
from app.models import Barbearia, Usuario, BarbeariaCustomizacao
from app.exceptions import APIError
from app.decorators.auth import gestor_required
from app.utils.db import commit_ou_falhar
from app.utils.auditoria import registrar_auditoria
from app.utils.imagem import validar_upload_imagem

gestor_perfil_bp = Blueprint('gestor_perfil', __name__, url_prefix='/api/v1/gestor/perfil')

_CAMPOS_ENDERECO = ('rua', 'numero', 'complemento', 'bairro', 'cidade', 'estado', 'cep')


def _parse_hora(valor):
    if not valor:
        return None
    try:
        h, m = valor.split(':')
        return time_t(int(h), int(m))
    except (ValueError, AttributeError):
        raise APIError('Horário inválido. Use o formato HH:MM.', 422)


@gestor_perfil_bp.get('')
@gestor_required
def get_perfil():
    b = db.session.get(Barbearia, g.barbearia_id)
    u = db.session.get(Usuario, g.user_id)
    custom = BarbeariaCustomizacao.query.filter_by(barbearia_id=g.barbearia_id).first()

    return jsonify({
        'barbearia': {
            'nome_exibicao':      b.nome_exibicao or b.nome,
            'telefone_contato':   b.telefone_contato,
            'email_contato':      b.email_contato,
            'instagram':          b.instagram,
            **{c: getattr(b, c) for c in _CAMPOS_ENDERECO},
            'horario_abertura':   b.horario_abertura.strftime('%H:%M') if b.horario_abertura else None,
            'horario_fechamento': b.horario_fechamento.strftime('%H:%M') if b.horario_fechamento else None,
            'logo_url':           custom.logo_url if custom else None,
        },
        'conta': {
            'nome':  u.nome,
            'email': u.email,
        },
    }), 200


@gestor_perfil_bp.patch('/barbearia')
@gestor_required
def editar_barbearia():
    b = db.session.get(Barbearia, g.barbearia_id)
    dados = request.get_json(silent=True) or {}

    if 'nome_exibicao' in dados:
        nome = (dados['nome_exibicao'] or '').strip()
        if not nome:
            raise APIError('"nome_exibicao" não pode ser vazio.', 422)
        b.nome_exibicao = nome

    if 'telefone_contato' in dados:
        b.telefone_contato = (dados['telefone_contato'] or '').strip() or None

    if 'email_contato' in dados:
        b.email_contato = (dados['email_contato'] or '').strip() or None

    if 'instagram' in dados:
        b.instagram = (dados['instagram'] or '').strip() or None

    for campo in _CAMPOS_ENDERECO:
        if campo in dados:
            setattr(b, campo, (dados[campo] or '').strip() or None)

    if 'horario_abertura' in dados:
        b.horario_abertura = _parse_hora(dados['horario_abertura'])
    if 'horario_fechamento' in dados:
        b.horario_fechamento = _parse_hora(dados['horario_fechamento'])

    commit_ou_falhar('gestor.perfil.editar_barbearia')
    return jsonify({'mensagem': 'Dados da barbearia atualizados.'}), 200


@gestor_perfil_bp.patch('/conta')
@gestor_required
def editar_conta():
    u = db.session.get(Usuario, g.user_id)
    dados = request.get_json(silent=True) or {}

    if 'nome' in dados:
        nome = (dados['nome'] or '').strip()
        if not nome:
            raise APIError('"nome" não pode ser vazio.', 422)
        u.nome = nome

    if 'email' in dados:
        email = (dados['email'] or '').strip().lower()
        if not email:
            raise APIError('"email" não pode ser vazio.', 422)
        existente = Usuario.query.filter(Usuario.email == email, Usuario.id != u.id).first()
        if existente:
            raise APIError('Já existe uma conta com este e-mail.', 409)
        u.email = email

    commit_ou_falhar('gestor.perfil.editar_conta')
    return jsonify({'mensagem': 'Conta atualizada.'}), 200


@gestor_perfil_bp.post('/senha')
@gestor_required
def trocar_senha():
    u = db.session.get(Usuario, g.user_id)
    dados = request.get_json(silent=True) or {}

    senha_atual = dados.get('senha_atual') or ''
    senha_nova  = dados.get('senha_nova') or ''

    if not u.senha or not check_password_hash(u.senha, senha_atual):
        raise APIError('Senha atual incorreta.', 401)
    if len(senha_nova) < 8:
        raise APIError('A nova senha deve ter no mínimo 8 caracteres.', 422)

    u.senha = generate_password_hash(senha_nova)
    commit_ou_falhar('gestor.perfil.trocar_senha')
    registrar_auditoria(u.id, g.barbearia_id, 'edit', 'usuario', u.id, f'{u.nome} trocou a própria senha.')
    return jsonify({'mensagem': 'Senha alterada com sucesso.'}), 200


@gestor_perfil_bp.post('/logo')
@gestor_required
def upload_logo():
    if 'arquivo' not in request.files:
        raise APIError('Campo "arquivo" é obrigatório.', 400)
    arq = request.files['arquivo']
    validar_upload_imagem(arq)

    try:
        resultado = cloudinary.uploader.upload(
            arq.stream,
            folder='barberos/customizacao',
            public_id=f'barbearia_{g.barbearia_id}_logo',
            overwrite=True,
            unique_filename=False,
            invalidate=True,
            resource_type='image',
        )
    except Exception as exc:
        raise APIError(f'Cloudinary: {exc}', 502)

    url = resultado.get('secure_url')
    if not url:
        raise APIError('Cloudinary não retornou a URL da imagem.', 502)

    custom = BarbeariaCustomizacao.query.filter_by(barbearia_id=g.barbearia_id).first()
    if not custom:
        custom = BarbeariaCustomizacao(barbearia_id=g.barbearia_id)
        db.session.add(custom)
    custom.logo_url = url

    commit_ou_falhar('gestor.perfil.upload_logo')
    return jsonify({'mensagem': 'Logo atualizada.', 'logo_url': url}), 200
