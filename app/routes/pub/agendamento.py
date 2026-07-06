"""
Rotas públicas de agendamento (sem autenticação obrigatória).
- quick-booking por telefone (cria/reutiliza Cliente)
- slots disponíveis por recurso (A1: barbeiro como recurso agendável)
- lista de barbeiros e serviços para exibição pública
"""
import os
import cloudinary
import cloudinary.uploader
from datetime import datetime, date, time as time_t
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy.exc import IntegrityError
from app.utils.tz import hoje_brasilia, naive_brasilia
from app.extensions import db, limiter
from app.models import (
    Barbearia, Barbeiro, Usuario, Cliente, Servico, BarbeiroServico,
    Agendamento, AgendamentoServico, AgendamentoSolicitacaoPix,
    ConfiguracaoAgendamento, ConfiguracaoAgenda, HorarioBloqueado,
    ClientePlano, PlanoServico, ClientePlanoUso, Plano,
)
from app.utils.planos import PLANO_LIMITE_ILIMITADO
from app.exceptions import APIError
from app.utils import normalizar_telefone, gerar_slots, verificar_conflito, gerar_pix_copia_cola
from app.utils.agenda import fim_agendamento
from app.utils.notificacoes import notificar_cliente
from app.utils.features import feature_ativa
from app.utils.cupons import validar_cupom, incrementar_uso_cupom
from app.utils.auditoria import registrar_auditoria
from app.labels import L
from app.utils.db import commit_ou_falhar

pub_bp = Blueprint('pub', __name__, url_prefix='/api/v1/pub')


# ── Helpers internos ──────────────────────────────────────────────────────────

def _get_barbearia_ou_404(slug: str) -> Barbearia:
    b = Barbearia.query.filter_by(slug=slug, ativo=True).first()
    if not b:
        raise APIError(f'{L("tenant")} não encontrada ou inativa.', 404)
    return b


def _get_config(barbearia_id: int) -> ConfiguracaoAgendamento:
    """Retorna ConfiguracaoAgendamento com fallback de defaults (A3)."""
    c = ConfiguracaoAgendamento.query.filter_by(barbearia_id=barbearia_id).first()
    if not c:
        c = ConfiguracaoAgendamento(
            barbearia_id=barbearia_id,
            cancelamento_horas_minimas=3,
            permite_multi_servico=True,
            quick_booking_sem_login=True,
            intervalo_slot_minutos=15,
            antecedencia_maxima_dias=60,
        )
    return c


def _fmt_agendamento(ag, servicos_info, barbeiro_nomes=None):
    """
    barbeiro_nomes: dict {barbeiro_id: nome} pré-carregado em lote (Bloco 5.1)
    para uso em listagens. Quando None (chamada de item único: criar/detalhar),
    cai na query pontual, aceitável fora de um loop.
    """
    fim = fim_agendamento(ag.data_hora, ag.duracao_minutos)
    if barbeiro_nomes is not None:
        nome = barbeiro_nomes.get(ag.barbeiro_id)
    else:
        br = db.session.get(Barbeiro, ag.barbeiro_id) if ag.barbeiro_id else None
        br_usr = db.session.get(Usuario, br.usuario_id) if br else None
        nome = br_usr.nome if br_usr else None
    return {
        'id':               ag.id,
        'status':           ag.status,
        'valor_total':      float(ag.valor_total),
        'valor_desconto':   float(ag.valor_desconto or 0),
        'subtotal':         float(ag.valor_total) + float(ag.valor_desconto or 0),
        'cupom_id':         ag.cupom_id,
        'duracao_total':    ag.duracao_minutos,
        'inicio':           ag.data_hora.isoformat(),
        'fim':              fim.isoformat(),
        'metodo_pagamento': ag.metodo_pagamento,
        'observacao':       ag.observacao,
        'barbeiro_id':      ag.barbeiro_id,
        'barbeiro_nome':    nome,
        'servicos':         servicos_info,
    }


def _resolver_plano(
    cliente_id: int,
    barbearia_id: int,
    servico_id: int,
    barbeiro_id: int,
    data_hora: datetime | None = None,
):
    """
    Verifica se o cliente tem ClientePlano ativo que cobre este serviço,
    respeitando compatibilidade de barbeiro e limite de uso mensal.

    Plano aberto  (Plano.barbeiro_id = NULL) → vale para qualquer barbeiro.
    Plano vinculado (Plano.barbeiro_id != NULL) → vale somente para esse barbeiro.

    O limite mensal é contado no mês/ano do AGENDAMENTO, não do dia atual.

    Retorna (cliente_plano_id, True) se coberto e dentro do limite.
    Retorna (None, False) caso contrário → serviço cobrado como avulso.
    """
    ref = data_hora.date() if data_hora else hoje_brasilia()

    assinaturas = (
        ClientePlano.query
        .filter_by(barbearia_id=barbearia_id, cliente_id=cliente_id, ativo=True)
        .all()
    )
    for cp in assinaturas:
        # EC02: plano com data_fim vencida nunca deveria continuar valendo.
        if cp.data_fim is not None and cp.data_fim < ref:
            continue

        plano = db.session.get(Plano, cp.plano_id)
        if not plano or not plano.ativo:
            continue

        # Compatibilidade de barbeiro
        if plano.barbeiro_id is not None and plano.barbeiro_id != barbeiro_id:
            continue  # plano vinculado a outro barbeiro

        # EC13: plano vinculado a um barbeiro que foi desativado não deveria
        # continuar valendo, mesmo que o agendamento seja com esse mesmo id.
        if plano.barbeiro_id is not None:
            barb = db.session.get(Barbeiro, plano.barbeiro_id)
            if not barb or not barb.ativo:
                continue

        ps = PlanoServico.query.filter_by(
            plano_id=plano.id, servico_id=servico_id, ativo=True
        ).first()
        if not ps:
            continue  # serviço não incluso neste plano

        # Verifica limite mensal: conta no mês do agendamento
        if ps.limite_uso_mensal != PLANO_LIMITE_ILIMITADO:
            uso_mes = (
                ClientePlanoUso.query
                .filter(
                    ClientePlanoUso.cliente_plano_id == cp.id,
                    ClientePlanoUso.servico_id == servico_id,
                    db.extract('year',  ClientePlanoUso.data_uso) == ref.year,
                    db.extract('month', ClientePlanoUso.data_uso) == ref.month,
                )
                .count()
            )
            if uso_mes >= ps.limite_uso_mensal:
                continue  # limite atingido → tenta próximo plano ou avulso

        return cp.id, True

    return None, False


def _criar_agendamento_core(
    barbearia_id: int,
    barbeiro_id: int,
    cliente_id: int,
    data_hora: datetime,
    itens: list,       # list of {servico_id, is_plano_solicitado}
    metodo: str,
    observacao: str | None,
    cupom_codigo: str | None = None,
):
    """
    Núcleo atômico de criação de agendamento.
    Aplicado por quick-booking (pub) e por booking autenticado (cliente).
    """
    config = _get_config(barbearia_id)

    # Verifica antecedência máxima (usa data de Brasília, não UTC do servidor)
    dias_ahead = (data_hora.date() - hoje_brasilia()).days
    if dias_ahead < 0:
        raise APIError('Não é possível agendar no passado.')
    if dias_ahead > config.antecedencia_maxima_dias:
        raise APIError(
            f'Agendamento disponível com no máximo {config.antecedencia_maxima_dias} dias de antecedência.'
        )

    # Valida multi-serviço
    if len(itens) > 1 and not config.permite_multi_servico:
        raise APIError(f'Esta {L("tenant")} não permite agendamento de múltiplos {L("servicos").lower()} ao mesmo tempo.')

    # Valida cada serviço
    servicos_obj = []
    for item in itens:
        s = Servico.query.filter_by(id=item['servico_id'], barbearia_id=barbearia_id, ativo=True).first()
        if not s:
            raise APIError(f'{L("servico")} id={item["servico_id"]} não encontrado ou inativo.', 404)

        oferece = BarbeiroServico.query.filter_by(
            barbeiro_id=barbeiro_id, servico_id=s.id
        ).first()
        if not oferece:
            raise APIError(
                f'{L("profissional")} não oferece o {L("servico").lower()} "{s.nome}".', 422
            )
        servicos_obj.append((s, item.get('is_plano', False)))

    duracao_total = sum(s.duracao_minutos for s, _ in servicos_obj)

    # Verifica conflito de horário (A1: resource_id = barbeiro_id)
    conflito = verificar_conflito(barbeiro_id, data_hora, duracao_total)
    if conflito:
        fim_conf = fim_agendamento(conflito.data_hora, conflito.duracao_minutos)
        raise APIError(
            f'Horário ocupado. O {L("profissional").lower()} tem agendamento das '
            f'{conflito.data_hora.strftime("%H:%M")} às {fim_conf.strftime("%H:%M")}.',
            409,
        )

    # Bloqueia o passado por instante exato (não só por data) — cobre o caso
    # de horário já passado HOJE, que o check de antecedência acima (por
    # dia) não pega.
    if data_hora <= naive_brasilia():
        raise APIError('Este horário já passou. Escolha um horário futuro.', 422)

    # Revalida contra a agenda real (ConfiguracaoAgenda, HorarioBloqueado,
    # PausaBarbeiro) — verificar_conflito só olha OUTROS agendamentos, então
    # sozinho não pega o gestor reduzindo o horário/bloqueando o dia/pausa
    # enquanto o cliente tinha a página de booking aberta. Chamado UMA vez
    # só, fora de qualquer loop de serviço (gerar_slots pode ser custoso).
    slots_validos = gerar_slots(barbeiro_id, data_hora.date(), duracao_total)
    if data_hora.strftime('%H:%M') not in slots_validos:
        raise APIError(
            f'Este horário não está mais disponível para este {L("profissional").lower()}. '
            'Atualize a página e escolha outro.',
            422,
        )

    # Calcula preços: sempre tenta resolver plano automaticamente para cada serviço
    # _resolver_plano só enxerga o uso já GRAVADO no banco — os usos do próprio
    # booking (ex: 2x o mesmo serviço no mesmo pedido) ainda não existem lá.
    # Sem este controle, dois itens iguais no mesmo booking passariam pelo
    # plano mesmo com limite_uso_mensal=1, e colidiriam na uq_plano_uso_dia
    # (Bloco 2.1) ao tentar gravar 2 ClientePlanoUso idênticos. Regra: dentro
    # do MESMO booking, só a 1ª ocorrência de (plano, serviço) consome o
    # plano — repetições no mesmo pedido são cobradas como avulso.
    plano_usado_no_booking = set()
    itens_finais = []
    for s, _ in servicos_obj:
        cliente_plano_id, is_plano = _resolver_plano(
            cliente_id, barbearia_id, s.id, barbeiro_id, data_hora
        )
        if is_plano and (cliente_plano_id, s.id) in plano_usado_no_booking:
            cliente_plano_id, is_plano = None, False
        elif is_plano:
            plano_usado_no_booking.add((cliente_plano_id, s.id))

        preco = 0.0 if is_plano else float(s.preco)
        itens_finais.append({
            'servico': s,
            'preco': preco,
            'is_plano': is_plano,
            'cliente_plano_id': cliente_plano_id,
        })

    subtotal = sum(i['preco'] for i in itens_finais)

    # Cupom de desconto (opcional)
    cupom = None
    valor_desconto = 0.0
    if cupom_codigo:
        cupom, valor_desconto = validar_cupom(barbearia_id, cupom_codigo, subtotal)

    valor_total = round(subtotal - valor_desconto, 2)

    # Status inicial
    status = 'aguardando_comprovante' if valor_total > 0 and metodo == 'pix' else 'agendado'

    ag = Agendamento(
        barbearia_id=barbearia_id,
        cliente_id=cliente_id,
        barbeiro_id=barbeiro_id,
        data_hora=data_hora,
        duracao_minutos=duracao_total,
        status=status,
        valor_total=valor_total,
        valor_desconto=valor_desconto,
        cupom_id=cupom.id if cupom else None,
        metodo_pagamento=metodo,
        observacao=observacao,
    )
    db.session.add(ag)
    try:
        db.session.flush()
    except IntegrityError:
        # Rede de segurança final: uq_ag_barbeiro_slot (Bloco 2.1) pegou uma
        # corrida que o lock em verificar_conflito não pôde evitar (primeiro
        # agendamento do barbeiro no dia — nada para travar com FOR UPDATE).
        db.session.rollback()
        raise APIError('Este horário acabou de ser reservado. Escolha outro.', 409)

    # Cupom só conta uso quando o agendamento nasce confirmado (sem PIX pendente)
    if cupom and status == 'agendado':
        try:
            incrementar_uso_cupom(cupom.id, barbearia_id)
        except APIError:
            db.session.rollback()
            raise

    servicos_info = []
    for item in itens_finais:
        s = item['servico']
        as_ = AgendamentoServico(
            agendamento_id=ag.id,
            servico_id=s.id,
            quantidade=1,
            preco_unitario=item['preco'],
            is_plano=item['is_plano'],
            cliente_plano_id=item['cliente_plano_id'],
        )
        db.session.add(as_)

        # Registra uso do plano (para controle de limite mensal)
        if item['is_plano'] and item['cliente_plano_id']:
            dia = ag.data_hora.date()
            db.session.add(ClientePlanoUso(
                cliente_plano_id=item['cliente_plano_id'],
                servico_id=s.id,
                data_uso=dia,
                semana_do_mes=((dia.day - 1) // 7) + 1,
                usado=True,
            ))

        servicos_info.append({
            'servico_id':  s.id,
            'nome':        s.nome,
            'duracao':     s.duracao_minutos,
            'preco':       item['preco'],
            'is_plano':    item['is_plano'],
        })

    # Gera PIX se necessário
    pix_info = None
    if status == 'aguardando_comprovante':
        pix_solicitacao = AgendamentoSolicitacaoPix(
            barbearia_id=barbearia_id,
            agendamento_id=ag.id,
            status='pendente',
        )
        db.session.add(pix_solicitacao)

        barbearia = db.session.get(Barbearia, barbearia_id)
        if barbearia and barbearia.chave_pix and barbearia.pix_nome_titular:
            codigo_pix = gerar_pix_copia_cola(
                chave=barbearia.chave_pix,
                nome_titular=barbearia.pix_nome_titular,
                cidade=barbearia.pix_cidade or 'SAO PAULO',
                valor=valor_total,
                txid=f'AG{ag.id:06d}',
            )
        else:
            codigo_pix = None

        pix_info = {'status': 'pendente', 'codigo_pix': codigo_pix}

    try:
        db.session.commit()
    except IntegrityError:
        # Corrida entre bookings PARALELOS (requisições diferentes) usando o
        # mesmo (plano, serviço, dia) — uq_plano_uso_dia (Bloco 2.1) pegou.
        db.session.rollback()
        raise APIError(
            'Limite de uso do plano para este serviço foi atingido. '
            'Tente novamente ou escolha outro serviço.',
            409,
        )
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error('commit falhou em pub.agendamento._criar_agendamento_core: %s', exc, exc_info=True)
        raise APIError('Erro ao criar agendamento. Tente novamente.', 500)

    # Notificação de confirmação de agendamento (stub — sem envio real)
    if feature_ativa(barbearia_id, 'notificacoes'):
        servicos_nomes = ', '.join(s.nome for s, _ in servicos_obj)
        notificar_cliente(
            barbearia_id=barbearia_id,
            cliente_id=cliente_id,
            descricao=(
                f'Agendamento #{ag.id} confirmado para '
                f'{ag.data_hora.strftime("%d/%m/%Y %H:%M")} — {servicos_nomes}'
            ),
        )

    return ag, servicos_info, pix_info


# ── GET /pub/<slug>/servicos ──────────────────────────────────────────────────

@pub_bp.get('/<slug>/servicos')
def listar_servicos_publico(slug):
    b = _get_barbearia_ou_404(slug)
    servicos = (
        db.session.query(Servico)
        .join(BarbeiroServico, BarbeiroServico.servico_id == Servico.id)
        .join(Barbeiro, Barbeiro.id == BarbeiroServico.barbeiro_id)
        .filter(
            Barbeiro.barbearia_id == b.id,
            Barbeiro.ativo == True,
            Servico.ativo == True,
        )
        .order_by(Servico.nome)
        .distinct()
        .all()
    )
    return jsonify([
        {
            'id':              s.id,
            'nome':            s.nome,
            'descricao':       s.descricao,
            'duracao_minutos': s.duracao_minutos,
            'preco':           float(s.preco),
        }
        for s in servicos
    ]), 200


# ── GET /pub/<slug>/barbeiros ─────────────────────────────────────────────────

@pub_bp.get('/<slug>/barbeiros')
def listar_barbeiros_publico(slug):
    b = _get_barbearia_ou_404(slug)
    q = (
        Barbeiro.query
        .filter_by(barbearia_id=b.id, ativo=True)
        .join(Usuario)
        .order_by(Usuario.nome)
    )

    # Optional filter: only barbers who offer ALL requested services
    servico_ids_str = request.args.get('servico_ids', '')
    if servico_ids_str:
        try:
            servico_ids = [int(x) for x in servico_ids_str.split(',') if x.strip()]
            for sid in servico_ids:
                q = q.filter(
                    Barbeiro.id.in_(
                        db.session.query(BarbeiroServico.barbeiro_id)
                        .filter_by(servico_id=sid)
                    )
                )
        except ValueError:
            pass

    barbeiros = q.all()
    return jsonify([
        {
            'id':   br.id,
            'nome': br.usuario.nome,
            'bio':  br.bio,
            'foto': br.foto,
        }
        for br in barbeiros
    ]), 200


# ── GET /pub/<slug>/barbeiros/<id>/servicos ───────────────────────────────────

@pub_bp.get('/<slug>/barbeiros/<int:barbeiro_id>/servicos')
def listar_servicos_barbeiro_publico(slug, barbeiro_id):
    b = _get_barbearia_ou_404(slug)
    br = Barbeiro.query.filter_by(id=barbeiro_id, barbearia_id=b.id, ativo=True).first()
    if not br:
        raise APIError(f'{L("profissional")} não encontrado.', 404)

    servicos = (
        db.session.query(Servico)
        .join(BarbeiroServico, BarbeiroServico.servico_id == Servico.id)
        .filter(BarbeiroServico.barbeiro_id == barbeiro_id, Servico.ativo == True)
        .order_by(Servico.nome)
        .all()
    )
    return jsonify([
        {
            'id':              s.id,
            'nome':            s.nome,
            'descricao':       s.descricao,
            'duracao_minutos': s.duracao_minutos,
            'preco':           float(s.preco),
        }
        for s in servicos
    ]), 200


# ── GET /pub/<slug>/barbeiros/<id>/slots ──────────────────────────────────────

@pub_bp.get('/<slug>/barbeiros/<int:barbeiro_id>/slots')
@limiter.limit(os.environ.get('RL_SLOTS', '60 per minute'))
def slots_disponiveis(slug, barbeiro_id):
    b = _get_barbearia_ou_404(slug)
    br = Barbeiro.query.filter_by(id=barbeiro_id, barbearia_id=b.id, ativo=True).first()
    if not br:
        raise APIError(f'{L("profissional")} não encontrado.', 404)

    data_str = request.args.get('data')
    duracao  = request.args.get('duracao', type=int)

    if not data_str:
        raise APIError('Parâmetro "data" (YYYY-MM-DD) é obrigatório.')
    if not duracao or duracao <= 0:
        raise APIError('Parâmetro "duracao" (minutos) é obrigatório e deve ser positivo.')

    try:
        data = date.fromisoformat(data_str)
    except ValueError:
        raise APIError('Formato de data inválido. Use YYYY-MM-DD.')

    config = _get_config(b.id)
    dias_ahead = (data - hoje_brasilia()).days
    if dias_ahead < 0:
        raise APIError('Não é possível consultar datas passadas.')
    if dias_ahead > config.antecedencia_maxima_dias:
        raise APIError(f'Data além do limite de {config.antecedencia_maxima_dias} dias.')

    # BUG#2: antes, um barbeiro sem ConfiguracaoAgenda (ou com o dia inteiro
    # bloqueado) simplesmente retornava uma grade vazia, sem explicar por quê
    # — o cliente achava que o app estava quebrado. 200 (não 503) para não
    # quebrar consumidores externos futuros (integração WhatsApp/n8n).
    cfg_agenda = ConfiguracaoAgenda.query.filter_by(barbeiro_id=barbeiro_id).first()
    if not cfg_agenda:
        return jsonify({
            'data': data_str, 'barbeiro_id': barbeiro_id, 'duracao': duracao,
            'slots': [], 'indisponivel': True,
            'motivo': f'Este {L("profissional").lower()} ainda não configurou seus horários.',
        }), 200
    if not cfg_agenda.loja_aberta:
        return jsonify({
            'data': data_str, 'barbeiro_id': barbeiro_id, 'duracao': duracao,
            'slots': [], 'indisponivel': True,
            'motivo': f'Este {L("profissional").lower()} não está atendendo no momento.',
        }), 200

    dia_inicio = datetime.combine(data, time_t(0, 0))
    dia_fim    = datetime.combine(data, time_t(23, 59, 59))
    bloqueio_dia_inteiro = HorarioBloqueado.query.filter(
        HorarioBloqueado.barbeiro_id == barbeiro_id,
        HorarioBloqueado.data_hora_inicio <= dia_inicio,
        HorarioBloqueado.data_hora_fim >= dia_fim,
    ).first()
    if bloqueio_dia_inteiro:
        return jsonify({
            'data': data_str, 'barbeiro_id': barbeiro_id, 'duracao': duracao,
            'slots': [], 'indisponivel': True,
            'motivo': bloqueio_dia_inteiro.motivo or 'Sem atendimento neste dia.',
        }), 200

    # A1: gerar_slots recebe resource_id (barbeiro_id hoje, recurso genérico no futuro)
    slots = gerar_slots(barbeiro_id, data, duracao)
    return jsonify({
        'data': data_str, 'barbeiro_id': barbeiro_id, 'duracao': duracao,
        'slots': slots, 'indisponivel': False, 'motivo': None,
    }), 200


# ── POST /pub/<slug>/agendar ──────────────────────────────────────────────────

@pub_bp.post('/<slug>/agendar')
@limiter.limit(os.environ.get('RL_AGENDAR', '10 per minute'))
def quick_booking(slug):
    barbearia = _get_barbearia_ou_404(slug)
    config = _get_config(barbearia.id)

    dados = request.get_json(silent=True)
    if not dados:
        raise APIError('Corpo da requisição inválido ou ausente.')

    # Identificação do cliente por telefone
    telefone_raw = (dados.get('telefone') or '').strip()
    if not telefone_raw:
        raise APIError('"telefone" é obrigatório para quick-booking.')

    tel_norm, tel_erro = normalizar_telefone(telefone_raw)
    if tel_erro:
        raise APIError(f'Telefone: {tel_erro}')

    # Encontra ou cria o Cliente por telefone (vínculo por telefone — sem duplicar)
    cliente = Cliente.query.filter_by(
        barbearia_id=barbearia.id, telefone=tel_norm
    ).first()

    if not cliente:
        nome = (dados.get('nome') or '').strip()
        if not nome:
            raise APIError('"nome" é obrigatório para novos clientes.')
        cliente = Cliente(
            barbearia_id=barbearia.id,
            nome=nome,
            telefone=tel_norm,
            email=(dados.get('email') or '').strip() or None,
            ativo=True,
        )
        db.session.add(cliente)
        db.session.flush()
        cliente_criado = True
    else:
        cliente_criado = False

    # Dados do agendamento
    barbeiro_id = dados.get('barbeiro_id')
    data_hora_str = dados.get('data_hora')
    itens = dados.get('servicos') or []
    metodo = (dados.get('metodo_pagamento') or 'local').strip().lower()
    observacao = (dados.get('observacao') or '').strip() or None

    if not isinstance(barbeiro_id, int):
        raise APIError('"barbeiro_id" é obrigatório e deve ser um inteiro.')
    if not itens:
        raise APIError(f'Pelo menos um {L("servico").lower()} é obrigatório.')
    if not data_hora_str:
        raise APIError('"data_hora" é obrigatório (formato ISO 8601).')

    try:
        data_hora = datetime.fromisoformat(data_hora_str)
    except ValueError:
        raise APIError('"data_hora" inválido. Use formato ISO 8601 (YYYY-MM-DDTHH:MM:SS).')

    br = Barbeiro.query.filter_by(id=barbeiro_id, barbearia_id=barbearia.id, ativo=True).first()
    if not br:
        raise APIError(f'{L("profissional")} não encontrado.', 404)

    ag, servicos_info, pix_info = _criar_agendamento_core(
        barbearia_id=barbearia.id,
        barbeiro_id=barbeiro_id,
        cliente_id=cliente.id,
        data_hora=data_hora,
        itens=itens,
        metodo=metodo,
        observacao=observacao,
    )

    return jsonify({
        **_fmt_agendamento(ag, servicos_info),
        'cliente': {
            'id':      cliente.id,
            'nome':    cliente.nome,
            'telefone': cliente.telefone,
            'criado':  cliente_criado,
        },
        'pix': pix_info,
    }), 201


# ── POST /api/v1/pub/<slug>/agendamentos/<id>/comprovante ─────────────────────
# Público — identificação por slug + agendamento_id apenas.
# Aceita multipart com campo "arquivo" (JPEG/PNG, max 5 MB).

_TIPOS_COMPROVANTE = {'image/jpeg', 'image/jpg', 'image/png'}
_MAX_BYTES_COMP    = 5 * 1024 * 1024


def _validar_magic_bytes(arq):
    """Valida os bytes reais do arquivo (JPEG/PNG) — mimetype do client é forjável.
    Assume que o stream já está no início; deixa o stream de volta no início ao final."""
    arq.stream.seek(0)
    header = arq.stream.read(8)
    arq.stream.seek(0)
    e_jpeg = header[:3] == b'\xff\xd8\xff'
    e_png  = header[:8] == b'\x89PNG\r\n\x1a\n'
    if not (e_jpeg or e_png):
        raise APIError('Arquivo não é JPEG ou PNG válido.', 400)


def _cfg_cloudinary_pub():
    cloudinary.config(
        cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
        api_key=os.environ.get('CLOUDINARY_API_KEY'),
        api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
    )


@pub_bp.post('/<slug>/agendamentos/<int:agendamento_id>/comprovante')
@limiter.limit(os.environ.get('RL_COMPROVANTE', '3 per minute'))
def upload_comprovante(slug, agendamento_id):
    barbearia = _get_barbearia_ou_404(slug)

    ag = Agendamento.query.filter_by(
        id=agendamento_id, barbearia_id=barbearia.id
    ).first()
    if not ag:
        raise APIError('Agendamento não encontrado.', 404)

    if ag.metodo_pagamento != 'pix':
        raise APIError('Este agendamento não é via PIX.', 400)

    # EC10: antes, comprovante era aceito em qualquer status (inclusive
    # agendamento já aprovado, cancelado ou concluído).
    _STATUS_ACEITA_COMPROVANTE = {'aguardando_comprovante', 'aguardando_aprovacao'}
    if ag.status not in _STATUS_ACEITA_COMPROVANTE:
        raise APIError('Não é possível enviar comprovante para este agendamento.', 422)

    if 'arquivo' not in request.files:
        raise APIError('Campo "arquivo" é obrigatório.', 400)

    arq = request.files['arquivo']
    if not arq.filename:
        raise APIError('Nenhum arquivo enviado.', 400)
    if arq.mimetype not in _TIPOS_COMPROVANTE:
        raise APIError('Tipo não permitido. Use JPEG ou PNG.', 400)
    arq.seek(0, 2)
    if arq.tell() > _MAX_BYTES_COMP:
        raise APIError('Arquivo muito grande. Máximo 5 MB.', 400)
    arq.seek(0)
    _validar_magic_bytes(arq)

    from datetime import datetime as _dt
    now  = _dt.utcnow()
    ano  = now.strftime('%Y')
    mes  = now.strftime('%m')
    folder    = f'barbearia/{barbearia.id}/comprovantes/{ano}/{mes}'
    public_id = f'ag_{agendamento_id}'

    _cfg_cloudinary_pub()
    try:
        resultado = cloudinary.uploader.upload(
            arq.stream,
            folder=folder,
            public_id=public_id,
            overwrite=True,
            unique_filename=False,
            invalidate=True,
            resource_type='image',
        )
    except Exception as exc:
        current_app.logger.error(f'Cloudinary: falha ao enviar comprovante (ag {agendamento_id}): {exc}', exc_info=True)
        raise APIError('Erro ao enviar comprovante. Tente novamente.', 502)

    url = resultado.get('secure_url')
    if not url:
        raise APIError('Cloudinary não retornou URL.', 502)

    # Deriva do `ag` já validado (tenant do slug) em vez do path param cru — defesa em profundidade.
    pix = AgendamentoSolicitacaoPix.query.filter_by(agendamento_id=ag.id, barbearia_id=barbearia.id).first()
    # EC15: se já havia um comprovante (reenvio), registra em auditoria.
    reenvio = bool(pix and pix.comprovante_url)
    if pix:
        pix.comprovante_url = url

    if ag.status == 'aguardando_comprovante':
        ag.status = 'aguardando_aprovacao'

    commit_ou_falhar('pub.agendamento.upload_comprovante')

    if reenvio:
        # Registrada após o commit principal — falha de log não reverte o upload.
        registrar_auditoria(
            usuario_id=None,
            barbearia_id=barbearia.id,
            tipo_acao='edicao',
            entidade='agendamento_solicitacao_pix',
            entidade_id=pix.id,
            descricao='Comprovante reenviado pelo cliente.',
        )

    return jsonify({'mensagem': 'Comprovante enviado com sucesso.', 'url': url, 'status': ag.status}), 200
