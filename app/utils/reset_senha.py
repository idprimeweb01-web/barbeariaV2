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
from app.utils.notificacoes import notificar

EXPIRA_EM_HORAS = 72
MAX_TENTATIVAS = 3


def gerar_codigo_recuperacao(email: str, perfis_permitidos: list | None = None, barbearia_id: int | None = None) -> tuple:
    """Gera código de recuperação e notifica a hierarquia.
    Retorna (usuario, solicitacao, codigo) se encontrar, senão (None, None, None).

    barbearia_id: obrigatório na prática pro fluxo de cliente — e-mail de
    cliente NÃO é único entre tenants (cada barbearia tem sua própria base
    de clientes), então sem esse filtro um e-mail duplicado em duas
    barbearias resolve pro Usuario errado (achado em teste manual: o
    código foi pra hierarquia de uma barbearia enquanto o cliente testava
    em outra). Não é necessário pro fluxo staff — e-mail de
    gestor/barbeiro/super_admin é único globalmente (uq_usuario_email_staff)."""
    query = Usuario.query.filter_by(email=email, ativo=True)
    if barbearia_id is not None:
        query = query.filter_by(barbearia_id=barbearia_id)
    usuario = query.first()

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


def validar_codigo_recuperacao_por_email(email: str, codigo: str, barbearia_id: int | None = None) -> Usuario:
    """Valida código de recuperação localizando a solicitação pelo e-mail do
    usuário (o que quem esqueceu a senha realmente tem em mãos) + código
    (recebido por WhatsApp da hierarquia). Substitui o fluxo antigo por
    token — o token nunca é exposto a ninguém fora do banco, então um
    fluxo que dependesse dele era inalcançável na prática.

    barbearia_id: mesmo motivo do gerar_codigo_recuperacao — sem isso, e-mail
    de cliente duplicado entre tenants pode resolver pro Usuario errado e
    achar "nenhuma solicitação pendente" mesmo com uma pendente de verdade
    (só que presa no Usuario homônimo de outra barbearia)."""
    # Sem filtro de perfil aqui — quem já restringe é o lado da solicitação
    # (cliente via /solicitar-reset-senha, staff via /solicitar-reset-senha-staff);
    # só existe uma SolicitacaoSenha pendente se um desses dois já validou o perfil.
    query = Usuario.query.filter_by(email=email, ativo=True)
    if barbearia_id is not None:
        query = query.filter_by(barbearia_id=barbearia_id)
    usuario = query.first()
    if not usuario:
        raise APIError('Código inválido.', 401)  # mesma msg genérica — não confirma se o e-mail existe

    solicitacao = (
        SolicitacaoSenha.query
        .filter_by(usuario_id=usuario.id, status='pendente')
        .order_by(SolicitacaoSenha.criado_em.desc())
        .first()
    )
    if not solicitacao:
        raise APIError('Nenhuma solicitação de redefinição pendente para este e-mail.', 404)

    if dt.datetime.utcnow() > solicitacao.expira_em:
        raise APIError('Código expirado.', 422)
    if solicitacao.tentativas >= MAX_TENTATIVAS:
        raise APIError('Muitas tentativas inválidas.', 429)

    if solicitacao.codigo_novo != codigo:
        solicitacao.tentativas += 1
        # Commit imediato — o errorhandler global de APIError não comita, e
        # sem persistir aqui o contador de tentativas nunca avança de verdade
        # (a proteção contra força bruta ficaria só decorativa).
        db.session.commit()
        raise APIError('Código inválido.', 401)

    usuario.senha = generate_password_hash(codigo)
    solicitacao.confirmado_em = dt.datetime.utcnow()
    solicitacao.status = 'resolvido'
    revogar_todos_tokens(usuario, 'reset_senha')

    return usuario


def _gerar_token_unico() -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))


def _obter_hierarquia(usuario: Usuario) -> list:
    """Quem recebe o código pra encaminhar: cliente → gestor + barbeiros da
    barbearia (qualquer um pode repassar por WhatsApp); gestor/barbeiro →
    super_admin direto. super_admin sempre entra como fallback."""
    hierarquia = []

    if usuario.perfil == 'cliente' and usuario.barbearia_id:
        gestor = Usuario.query.filter_by(
            barbearia_id=usuario.barbearia_id, perfil='gestor', ativo=True
        ).first()
        if gestor:
            hierarquia.append(gestor)
        barbeiros = Usuario.query.filter_by(
            barbearia_id=usuario.barbearia_id, perfil='barbeiro', ativo=True
        ).all()
        hierarquia.extend(barbeiros)

    super_admin = Usuario.query.filter_by(perfil='super_admin', ativo=True).first()
    if super_admin:
        hierarquia.append(super_admin)

    return hierarquia


_TELA_SOLICITACOES_SENHA = {
    'gestor':      '/gestor/solicitacoes-senha',
    'barbeiro':    '/barbeiro/solicitacoes-senha',
    'super_admin': '/super/solicitacoes-senha',
}


def _enviar_codigo(destino: Usuario, usuario: Usuario, codigo: str) -> None:
    """Entrega o código via notificação in-app — é o que o destino (gestor/
    barbeiro/super_admin) vai ver na tela pra encaminhar por WhatsApp.
    barbearia_id usa o da PRÓPRIA barbearia do destino (super_admin não tem
    uma fixa; cai no tenant do usuário que pediu o reset)."""
    notificar(
        barbearia_id=destino.barbearia_id or usuario.barbearia_id,
        usuario_id=destino.id,
        tipo='reset_senha',
        titulo=f'Código de recuperação para {usuario.nome}',
        mensagem=(
            f'{usuario.nome} ({usuario.perfil}) esqueceu a senha. '
            f'Código: {codigo}. Encaminhe por WhatsApp — expira em {EXPIRA_EM_HORAS}h.'
        ),
        link=_TELA_SOLICITACOES_SENHA.get(destino.perfil),
        canal='in_app',
    )
