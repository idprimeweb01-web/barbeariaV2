"""
VIP leveling (v1.2) — progressão de nível VIP por meses consecutivos de plano
ativo, com janela de tolerância pós-cancelamento.

Reaproveita VipNivel/ClienteVip existentes (app/routes/vip.py já tem o CRUD
de níveis) — só adiciona a progressão automática, que nunca existia (Script
15 deixou incrementar_nivel_vip/resetar_nivel_vip prontas em app/utils/vip.py
mas nenhum endpoint as chamava).

data_proxima_renovacao (coluna já existente em ClienteVip) faz o papel de
"até quando o nível VIP continua valendo" tanto pra renovação normal quanto
pra janela de tolerância pós-cancelamento — não há coluna separada pra isso.
"""
import datetime as dt

from app.extensions import db
from app.models import ClienteVip, ClienteVipHistorico, Cliente, VipNivel
from app.utils.tz import hoje_brasilia
from app.utils.notificacoes import criar_notificacao

DIAS_TOLERANCIA_VENCIMENTO = 45


def calcular_vip_level(cliente_id: int, barbearia_id: int) -> int:
    """Nível VIP atual = meses consecutivos, limitado ao maior nível
    realmente configurado pela barbearia (gestor cria do zero — não há
    número fixo de níveis)."""
    cv = ClienteVip.query.filter_by(cliente_id=cliente_id, barbearia_id=barbearia_id).first()
    if not cv:
        return 0

    maior_nivel = db.session.query(db.func.max(VipNivel.nivel)).filter_by(
        barbearia_id=barbearia_id, ativo=True
    ).scalar()
    if not maior_nivel:
        return 0

    return min(cv.meses_consecutivos, maior_nivel)


def _usuario_id_do_cliente(cliente_id: int) -> int | None:
    cli = db.session.get(Cliente, cliente_id)
    return cli.usuario_id if cli else None


def _nome_nivel(barbearia_id: int, nivel: int) -> str:
    if nivel <= 0:
        return 'nenhum'
    vn = VipNivel.query.filter_by(barbearia_id=barbearia_id, nivel=nivel, ativo=True).first()
    return vn.brinde_descricao if vn else f'nível {nivel}'


def _registrar_e_notificar(cliente_id, barbearia_id, evento_tipo, titulo, texto,
                            nivel_anterior=None, nivel_novo=None, descricao=None):
    usuario_id = _usuario_id_do_cliente(cliente_id)
    if usuario_id:
        criar_notificacao(
            barbearia_id=barbearia_id, usuario_id=usuario_id,
            tipo=evento_tipo.lower(), titulo=titulo, corpo=texto, canal='in_app',
        )
    db.session.add(ClienteVipHistorico(
        barbearia_id=barbearia_id, cliente_id=cliente_id, evento_tipo=evento_tipo,
        nivel_anterior=nivel_anterior, nivel_novo=nivel_novo,
        descricao=descricao or texto,
    ))


def notificar_upgrade_vip(cliente_id: int, barbearia_id: int, nivel_anterior: int, nivel_novo: int) -> None:
    nome = _nome_nivel(barbearia_id, nivel_novo)
    _registrar_e_notificar(
        cliente_id, barbearia_id, 'UPGRADE',
        titulo=f'Você subiu de nível VIP!',
        texto=f'Parabéns! Você agora tem o brinde "{nome}". Aproveite seus novos benefícios.',
        nivel_anterior=nivel_anterior, nivel_novo=nivel_novo,
    )


def notificar_downgrade_vip(cliente_id: int, barbearia_id: int, nivel_anterior: int, nivel_novo: int) -> None:
    nome = _nome_nivel(barbearia_id, nivel_novo)
    _registrar_e_notificar(
        cliente_id, barbearia_id, 'DOWNGRADE',
        titulo='Seu nível VIP mudou',
        texto=f'Seu nível VIP agora corresponde ao brinde "{nome}". Continue aproveitando seus benefícios!',
        nivel_anterior=nivel_anterior, nivel_novo=nivel_novo,
    )


def notificar_aviso_vencimento(cliente_id: int, barbearia_id: int, dias_restantes: int) -> None:
    _registrar_e_notificar(
        cliente_id, barbearia_id, 'AVISO_VENCIMENTO',
        titulo='Seu VIP está vencendo',
        texto=(
            f'Seu plano venceu, mas você ainda tem {dias_restantes} dia(s) '
            'pra renovar sem perder seus benefícios VIP. Renove agora!'
        ),
        descricao=f'Aviso enviado faltando {dias_restantes} dia(s).',
    )


def processar_evento_plano(cliente_id: int, barbearia_id: int, evento_tipo: str) -> None:
    """Processa eventos de plano (aprovacao, cancelamento, vencimento) e
    atualiza o status VIP. As mudanças em ClienteVip/ClienteVipHistorico não
    são comitadas aqui — quem chama decide o momento (mesmo padrão de
    app/utils/vip.py:incrementar_nivel_vip). ATENÇÃO: criar_notificacao()
    faz seu próprio commit interno (padrão já existente no projeto) — se
    nivel_novo != nivel_anterior, a notificação já sai comitada antes do
    commit_ou_falhar do chamador; não depender de tudo cair na mesma
    transação."""
    cv = ClienteVip.query.filter_by(cliente_id=cliente_id, barbearia_id=barbearia_id).first()
    nivel_anterior = calcular_vip_level(cliente_id, barbearia_id)

    if evento_tipo == 'aprovacao':
        if not cv:
            cv = ClienteVip(cliente_id=cliente_id, barbearia_id=barbearia_id)
            db.session.add(cv)
            db.session.flush()
        cv.meses_consecutivos = (cv.meses_consecutivos or 0) + 1
        cv.data_proxima_renovacao = None

    elif evento_tipo == 'cancelamento':
        if cv:
            cv.data_proxima_renovacao = hoje_brasilia() + dt.timedelta(days=DIAS_TOLERANCIA_VENCIMENTO)

    elif evento_tipo == 'vencimento':
        if cv and cv.data_proxima_renovacao and hoje_brasilia() > cv.data_proxima_renovacao:
            # Janela de tolerância expirada sem renovar — reseta progressão
            cv.meses_consecutivos = 0
            cv.data_proxima_renovacao = None

    nivel_novo = calcular_vip_level(cliente_id, barbearia_id)

    if nivel_novo > nivel_anterior:
        notificar_upgrade_vip(cliente_id, barbearia_id, nivel_anterior, nivel_novo)
    elif nivel_novo < nivel_anterior:
        notificar_downgrade_vip(cliente_id, barbearia_id, nivel_anterior, nivel_novo)

    if evento_tipo == 'vencimento' and cv and cv.data_proxima_renovacao:
        dias_restantes = (cv.data_proxima_renovacao - hoje_brasilia()).days
        if dias_restantes in (15, 7, 3, 1):
            notificar_aviso_vencimento(cliente_id, barbearia_id, dias_restantes)
