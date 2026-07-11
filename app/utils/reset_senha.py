"""
Esqueci senha (v1.2) — sem e-mail externo: gera token + código de 8 dígitos,
notifica a hierarquia (gestor → super_admin) in-app, que encaminha
manualmente por WhatsApp/telefone. Token expira em 72h.
"""
import random
import string
import datetime as dt

from app.extensions import db
from app.models import SolicitacaoSenha, Usuario
from app.exceptions import APIError
from werkzeug.security import generate_password_hash
from app.utils.auth import revogar_todos_tokens
from app.utils.notificacoes import criar_notificacao

EXPIRA_EM_HORAS = 72
MAX_TENTATIVAS = 3


def gerar_codigo_recuperacao(email: str, perfis_permitidos: list | None = None) -> tuple:
    """Gera código de recuperação e notifica a hierarquia.
    Retorna (usuario, solicitacao, codigo) se encontrar, senão (None, None, None)."""
    usuario = Usuario.query.filter_by(email=email, ativo=True).first()

    if not usuario:
        return None, None, None

    if perfis_permitidos and usuario.perfil not in perfis_permitidos:
        return None, None, None

    codigo = ''.join(random.choices(string.digits, k=8))

    solicitacao = SolicitacaoSenha(
        usuario_id=usuario.id,
        barbearia_id=usuario.barbearia_id,
        token=_gerar_token_unico(),
        codigo_novo=codigo,
        expira_em=dt.datetime.utcnow() + dt.timedelta(hours=EXPIRA_EM_HORAS),
    )
    db.session.add(solicitacao)
    db.session.flush()

    for destino in _obter_hierarquia(usuario):
        _enviar_codigo(destino, usuario, codigo)

    return usuario, solicitacao, codigo


def validar_codigo_recuperacao(token: str, codigo: str) -> Usuario:
    """Valida código de recuperação. Retorna usuário se OK, levanta APIError se inválido."""
    solicitacao = SolicitacaoSenha.query.filter_by(token=token).first()

    if not solicitacao:
        raise APIError('Token inválido.', 404)
    if solicitacao.confirmado_em:
        raise APIError('Código já utilizado.', 422)
    if dt.datetime.utcnow() > solicitacao.expira_em:
        raise APIError('Código expirado.', 422)
    if solicitacao.tentativas >= MAX_TENTATIVAS:
        raise APIError('Muitas tentativas inválidas.', 429)

    if solicitacao.codigo_novo != codigo:
        solicitacao.tentativas += 1
        raise APIError('Código inválido.', 401)

    usuario = db.session.get(Usuario, solicitacao.usuario_id)
    if not usuario:
        raise APIError('Usuário não encontrado.', 404)

    usuario.senha = generate_password_hash(codigo)
    solicitacao.confirmado_em = dt.datetime.utcnow()
    solicitacao.status = 'resolvido'
    revogar_todos_tokens(usuario, 'reset_senha')

    return usuario


def _gerar_token_unico() -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))


def _obter_hierarquia(usuario: Usuario) -> list:
    """Quem recebe o código pra encaminhar: cliente → gestor da barbearia →
    super_admin; gestor/barbeiro → super_admin direto."""
    hierarquia = []

    if usuario.perfil == 'cliente' and usuario.barbearia_id:
        gestor = Usuario.query.filter_by(
            barbearia_id=usuario.barbearia_id, perfil='gestor', ativo=True
        ).first()
        if gestor:
            hierarquia.append(gestor)

    super_admin = Usuario.query.filter_by(perfil='super_admin', ativo=True).first()
    if super_admin:
        hierarquia.append(super_admin)

    return hierarquia


def _enviar_codigo(destino: Usuario, usuario: Usuario, codigo: str) -> None:
    """Entrega o código via notificação in-app — é o que o destino (gestor/
    super_admin) vai ver na tela pra encaminhar por WhatsApp. barbearia_id
    usa o da PRÓPRIA barbearia do destino (super_admin não tem uma fixa;
    cai no tenant do usuário que pediu o reset)."""
    criar_notificacao(
        barbearia_id=destino.barbearia_id or usuario.barbearia_id,
        usuario_id=destino.id,
        tipo='reset_senha',
        titulo=f'Código de recuperação para {usuario.nome}',
        corpo=(
            f'{usuario.nome} ({usuario.perfil}) esqueceu a senha. '
            f'Código: {codigo}. Encaminhe por WhatsApp — expira em {EXPIRA_EM_HORAS}h.'
        ),
        canal='in_app',
    )
