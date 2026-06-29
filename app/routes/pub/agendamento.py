"""
Rotas públicas de agendamento (sem autenticação obrigatória).
- quick-booking por telefone (cria/reutiliza Cliente)
- slots disponíveis por recurso (A1: barbeiro como recurso agendável)
- lista de barbeiros e serviços para exibição pública
"""
from datetime import datetime, date
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models import (
    Barbearia, Barbeiro, Usuario, Cliente, Servico, BarbeiroServico,
    Agendamento, AgendamentoServico, AgendamentoSolicitacaoPix,
    ConfiguracaoAgendamento, ConfiguracaoAgenda,
    ClientePlano, PlanoServico, ClientePlanoUso, Plano,
)
from app.utils.planos import PLANO_LIMITE_ILIMITADO
from app.exceptions import APIError
from app.utils import normalizar_telefone, gerar_slots, verificar_conflito, gerar_pix_copia_cola
from app.utils.agenda import fim_agendamento
from app.utils.notificacoes import notificar_cliente
from app.utils.features import feature_ativa
from app.labels import L

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


def _fmt_agendamento(ag, servicos_info):
    fim = fim_agendamento(ag.data_hora, ag.duracao_minutos)
    return {
        'id':               ag.id,
        'status':           ag.status,
        'valor_total':      float(ag.valor_total),
        'duracao_total':    ag.duracao_minutos,
        'inicio':           ag.data_hora.isoformat(),
        'fim':              fim.isoformat(),
        'metodo_pagamento': ag.metodo_pagamento,
        'observacao':       ag.observacao,
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
    ref = data_hora.date() if data_hora else date.today()

    assinaturas = (
        ClientePlano.query
        .filter_by(barbearia_id=barbearia_id, cliente_id=cliente_id, ativo=True)
        .all()
    )
    for cp in assinaturas:
        plano = db.session.get(Plano, cp.plano_id)
        if not plano or not plano.ativo:
            continue

        # Compatibilidade de barbeiro
        if plano.barbeiro_id is not None and plano.barbeiro_id != barbeiro_id:
            continue  # plano vinculado a outro barbeiro

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
):
    """
    Núcleo atômico de criação de agendamento.
    Aplicado por quick-booking (pub) e por booking autenticado (cliente).
    """
    config = _get_config(barbearia_id)

    # Verifica antecedência máxima
    dias_ahead = (data_hora.date() - date.today()).days
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

    # Calcula preços: sempre tenta resolver plano automaticamente para cada serviço
    itens_finais = []
    for s, _ in servicos_obj:
        cliente_plano_id, is_plano = _resolver_plano(
            cliente_id, barbearia_id, s.id, barbeiro_id, data_hora
        )
        preco = 0.0 if is_plano else float(s.preco)
        itens_finais.append({
            'servico': s,
            'preco': preco,
            'is_plano': is_plano,
            'cliente_plano_id': cliente_plano_id,
        })

    valor_total = sum(i['preco'] for i in itens_finais)

    # Status inicial
    status = 'aguardando_pagamento' if valor_total > 0 and metodo == 'pix' else 'agendado'

    ag = Agendamento(
        barbearia_id=barbearia_id,
        cliente_id=cliente_id,
        barbeiro_id=barbeiro_id,
        data_hora=data_hora,
        duracao_minutos=duracao_total,
        status=status,
        valor_total=valor_total,
        metodo_pagamento=metodo,
        observacao=observacao,
    )
    db.session.add(ag)
    db.session.flush()

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
    if status == 'aguardando_pagamento':
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

    db.session.commit()

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
    dias_ahead = (data - date.today()).days
    if dias_ahead < 0:
        raise APIError('Não é possível consultar datas passadas.')
    if dias_ahead > config.antecedencia_maxima_dias:
        raise APIError(f'Data além do limite de {config.antecedencia_maxima_dias} dias.')

    # A1: gerar_slots recebe resource_id (barbeiro_id hoje, recurso genérico no futuro)
    slots = gerar_slots(barbeiro_id, data, duracao)
    return jsonify({'data': data_str, 'barbeiro_id': barbeiro_id, 'duracao': duracao, 'slots': slots}), 200


# ── POST /pub/<slug>/agendar ──────────────────────────────────────────────────

@pub_bp.post('/<slug>/agendar')
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
