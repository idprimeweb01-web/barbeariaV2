"""
Núcleo de Dúvidas do Cliente / Suporte (chat + triagem) — compartilhado
entre app/routes/cliente/duvidas.py, app/routes/gestor/duvidas.py (também
usado por barbeiro, mesma rota) e app/routes/super/duvidas.py (fila
cross-tenant do admin). Mesmo padrão de app/utils/vendas.py.
"""
import cloudinary
import cloudinary.uploader
from flask import current_app
from app.extensions import db
from app.exceptions import APIError
from app.utils.imagem import validar_upload_imagem
from app.utils.tz import naive_brasilia

MAX_IMAGENS_POR_MENSAGEM = 3


# ── Notificação dos responsáveis atuais pelo ticket ─────────────────────────

def notificar_responsaveis(duvida, titulo, mensagem):
    """Notifica quem é responsável pelo ticket AGORA: todos os gestores
    ativos da barbearia + o barbeiro específico se
    direcionado_para_tipo == 'barbeiro'. Usado sempre que o CLIENTE age
    (abre ticket, responde, ou reabre um concluído) — chamar só DEPOIS do
    commit_ou_falhar do caller, nunca antes (notificar() comita sozinha;
    se o commit principal falhar depois, a notificação já teria saído sem
    a mudança real ter persistido)."""
    from app.models import Usuario
    from app.utils.notificacoes import notificar

    gestores = Usuario.query.filter_by(
        barbearia_id=duvida.barbearia_id, perfil='gestor', ativo=True,
    ).all()
    for gestor in gestores:
        notificar(
            barbearia_id=duvida.barbearia_id, usuario_id=gestor.id,
            tipo='duvida_atividade', titulo=titulo, mensagem=mensagem,
            link=f'/gestor/duvidas-cliente?id={duvida.id}', canal='in_app',
        )

    if duvida.direcionado_para_tipo == 'barbeiro' and duvida.direcionado_para_usuario_id:
        notificar(
            barbearia_id=duvida.barbearia_id, usuario_id=duvida.direcionado_para_usuario_id,
            tipo='duvida_atividade', titulo=titulo, mensagem=mensagem,
            link=f'/barbeiro/duvidas-cliente?id={duvida.id}', canal='in_app',
        )


def notificar_admins(duvida, titulo, mensagem):
    """Notifica TODOS os super_admin ativos (times maiores podem ter mais
    de um) — usado quando um ticket é encaminhado ao suporte da plataforma."""
    from app.models import Usuario
    from app.utils.notificacoes import notificar

    admins = Usuario.query.filter_by(perfil='super_admin', ativo=True).all()
    for admin in admins:
        notificar(
            barbearia_id=duvida.barbearia_id, usuario_id=admin.id,
            tipo='duvida_atividade', titulo=titulo, mensagem=mensagem,
            link=f'/super/duvidas?id={duvida.id}', canal='in_app',
        )


# ── Timeline de auditoria própria do ticket ────────────────────────────────

def registrar_evento(*, duvida, tipo, valor_anterior=None, valor_novo=None, autor_usuario_id=None):
    """Grava uma linha em ClienteDuvidaEvento. NÃO commita — faz parte da
    mesma transação da mudança que a originou (diferente de AuditoriaLog,
    que é best-effort em transação própria: aqui queremos que a mudança e
    o registro dela sejam atômicos, já que a timeline é exibida como fonte
    de verdade do que aconteceu com o ticket)."""
    from app.models import ClienteDuvidaEvento
    db.session.add(ClienteDuvidaEvento(
        duvida_id=duvida.id,
        barbearia_id=duvida.barbearia_id,
        tipo=tipo,
        valor_anterior=str(valor_anterior) if valor_anterior is not None else None,
        valor_novo=str(valor_novo) if valor_novo is not None else None,
        autor_usuario_id=autor_usuario_id,
    ))


# ── Direcionamento na abertura ──────────────────────────────────────────────

def resolver_direcionamento(barbearia_id, categoria, direcionado_para_usuario_id):
    """Decide pra quem um ticket NOVO vai, na abertura pelo cliente.

    Regra (pedida explicitamente): categoria 'erro' SEMPRE vai pra fila
    geral do gestor, mesmo que o cliente tenha escolhido um funcionário —
    bug/erro é tratado como prioridade operacional do estabelecimento, não
    de uma pessoa específica. Fora isso, se o cliente escolheu um barbeiro
    ATIVO desta barbearia, direciona pra ele; senão cai na fila do gestor.

    Retorna (direcionado_para_tipo, direcionado_para_usuario_id_resolvido).
    """
    from app.constants import CategoriaDuvida, DirecionadoTipo
    from app.models import Barbeiro, Usuario

    if categoria == CategoriaDuvida.ERRO or not direcionado_para_usuario_id:
        return DirecionadoTipo.GESTOR, None

    alvo = (
        Barbeiro.query
        .join(Usuario, Usuario.id == Barbeiro.usuario_id)
        .filter(
            Barbeiro.barbearia_id == barbearia_id,
            Barbeiro.ativo == True,
            Usuario.id == direcionado_para_usuario_id,
        )
        .first()
    )
    if not alvo:
        return DirecionadoTipo.GESTOR, None
    return DirecionadoTipo.BARBEIRO, direcionado_para_usuario_id


# ── Mensagens (texto + até 3 imagens) ───────────────────────────────────────

def criar_mensagem(*, duvida, barbearia_id, autor_usuario_id, autor_tipo, texto, arquivos_imagem):
    """Cria uma ClienteDuvidaMensagem (texto e/ou até 3 imagens — nunca as
    duas coisas vazias) e atualiza duvida.ultima_mensagem_em.

    Se o ticket estava 'concluida', reabre pra 'pendente' automaticamente
    e registra o evento REABERTO (autor_usuario_id=None — ação do sistema,
    não de uma pessoa). 'cancelada' nunca reabre sozinho, só ação explícita
    de gestor/barbeiro/admin (ver rotas de situação).

    Não commita — quem chama decide o momento do commit_ou_falhar."""
    from app.constants import StatusClienteDuvida, TipoEventoDuvida
    from app.models import ClienteDuvidaMensagem, ClienteDuvidaMensagemImagem

    arquivos_imagem = [a for a in (arquivos_imagem or []) if a and a.filename]
    if len(arquivos_imagem) > MAX_IMAGENS_POR_MENSAGEM:
        raise APIError(f'Máximo de {MAX_IMAGENS_POR_MENSAGEM} imagens por mensagem.', 422)

    texto_limpo = (texto or '').strip()[:2000] or None
    if not texto_limpo and not arquivos_imagem:
        raise APIError('Envie um texto ou ao menos uma imagem.', 422)

    for arq in arquivos_imagem:
        validar_upload_imagem(arq)

    msg = ClienteDuvidaMensagem(
        duvida_id=duvida.id,
        barbearia_id=barbearia_id,
        autor_usuario_id=autor_usuario_id,
        autor_tipo=autor_tipo,
        texto=texto_limpo,
    )
    db.session.add(msg)
    db.session.flush()  # precisa do msg.id pro public_id determinístico das imagens

    folder = f'barberos/{barbearia_id}/duvidas'
    for ordem, arq in enumerate(arquivos_imagem):
        img = ClienteDuvidaMensagemImagem(
            mensagem_id=msg.id, barbearia_id=barbearia_id, ordem=ordem,
            imagem_url='',  # placeholder — precisa do img.id (abaixo) antes de ter a URL real
        )
        db.session.add(img)
        db.session.flush()  # precisa do img.id pro public_id determinístico

        public_id = f'duvida_{duvida.id}_msg_{msg.id}_img_{img.id}'
        try:
            resultado = cloudinary.uploader.upload(
                arq.stream, folder=folder, public_id=public_id,
                overwrite=True, unique_filename=False, invalidate=True, resource_type='image',
            )
        except Exception as exc:
            current_app.logger.error(
                f'Cloudinary: falha ao enviar imagem (dúvida {duvida.id} msg {msg.id} img {img.id}): {exc}',
                exc_info=True,
            )
            raise APIError('Erro ao enviar imagem. Tente novamente.', 502)

        url = resultado.get('secure_url')
        if not url:
            raise APIError('Cloudinary não retornou URL.', 502)
        img.imagem_url = url

    duvida.ultima_mensagem_em = naive_brasilia()

    if duvida.status == StatusClienteDuvida.CONCLUIDA:
        status_anterior = duvida.status
        duvida.status = StatusClienteDuvida.PENDENTE
        registrar_evento(
            duvida=duvida, tipo=TipoEventoDuvida.REABERTO,
            valor_anterior=status_anterior, valor_novo=duvida.status,
            autor_usuario_id=None,
        )

    return msg


# ── Consultas compartilhadas (gestor + admin) ───────────────────────────────

def query_precisa_resposta(barbearia_id=None):
    """ClienteDuvida com status='pendente' cuja ÚLTIMA mensagem foi do
    cliente — ninguém do estabelecimento respondeu ainda. Usado pelo
    dashboard do gestor (contagem) e pelo filtro ?precisa_resposta=1 das
    duas listagens (gestor tenant-scoped, admin cross-tenant se
    barbearia_id=None).

    Identifica "a última mensagem" pelo maior id da thread (monotônico por
    inserção) em vez de comparar timestamp — evita ambiguidade se duas
    mensagens da mesma thread caírem no mesmo timestamp."""
    from sqlalchemy import func
    from app.models import ClienteDuvida, ClienteDuvidaMensagem
    from app.constants import StatusClienteDuvida, AutorTipoDuvida

    ultimo_id = (
        db.session.query(func.max(ClienteDuvidaMensagem.id))
        .filter(ClienteDuvidaMensagem.duvida_id == ClienteDuvida.id)
        .correlate(ClienteDuvida)
        .scalar_subquery()
    )
    q = ClienteDuvida.query.filter(ClienteDuvida.status == StatusClienteDuvida.PENDENTE)
    if barbearia_id is not None:
        q = q.filter(ClienteDuvida.barbearia_id == barbearia_id)
    return (
        q.join(ClienteDuvidaMensagem, ClienteDuvidaMensagem.id == ultimo_id)
        .filter(ClienteDuvidaMensagem.autor_tipo == AutorTipoDuvida.CLIENTE)
    )


def ordenar_por_prioridade_e_recencia(query, campo_prioridade, campo_ultima_mensagem):
    """ORDER BY prioridade (urgente > alta > normal > baixa) e, dentro da
    mesma prioridade, ultima_mensagem_em mais recente primeiro — ordem
    padrão da fila do gestor e do admin."""
    from sqlalchemy import case
    from app.constants import PrioridadeDuvida

    peso = case(
        *[(campo_prioridade == valor, ordem) for valor, ordem in PrioridadeDuvida.ORDEM.items()],
        else_=99,
    )
    return query.order_by(peso, campo_ultima_mensagem.desc())
