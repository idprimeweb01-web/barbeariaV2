from collections import defaultdict
from datetime import datetime, timedelta, time as Time
from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import func
from app import db
from app.models import (
    Usuario, Barbeiro, Barbearia, Cliente, Servico, BarbeiroServico,
    ConfiguracaoAgenda, Agendamento, AgendamentoServico,
    HorarioBloqueado, Produto, ReservaProduto,
    Atendimento, SolicitacaoLiberacao,
    Plano, PlanoServico, PlanoBarbeiro, ClientePlano, ClientePlanoUso,
)
from app.utils import normalizar_telefone, get_barbearia_atual, limite_para_fora
from app.routes.auth import barbeiro_required
from app.routes.features import cliente_required

agenda = Blueprint('agenda', __name__)


def _erro(msg, code=400):
    return jsonify({'erro': msg}), code


def _barbeiro_do_usuario(usuario_id, barbearia_id):
    return Barbeiro.query.filter_by(
        usuario_id=usuario_id, ativo=True, barbearia_id=barbearia_id
    ).first()


def _slots_livres(config, data_dt, agendamentos, bloqueios):
    abertura  = datetime.combine(data_dt, config.horario_abertura)
    fechamento = datetime.combine(data_dt, config.horario_fechamento)
    passo     = timedelta(minutes=config.intervalo_minutos)
    slots = []
    atual = abertura
    while atual + passo <= fechamento:
        fim_slot = atual + passo
        ocupado = any(
            ag.data_hora < fim_slot
            and ag.data_hora + timedelta(minutes=ag.duracao_minutos) > atual
            for ag in agendamentos
        ) or any(
            bl.data_hora_inicio < fim_slot and bl.data_hora_fim > atual
            for bl in bloqueios
        )
        if not ocupado:
            slots.append(atual.strftime('%H:%M'))
        atual += passo
    return slots


def _agendamentos_do_dia(barbeiro_id, data_dt, barbearia_id):
    inicio = datetime.combine(data_dt, Time(0, 0))
    fim    = inicio + timedelta(days=1)
    return Agendamento.query.filter(
        Agendamento.barbearia_id == barbearia_id,
        Agendamento.barbeiro_id  == barbeiro_id,
        Agendamento.status       == 'agendado',
        Agendamento.data_hora    >= inicio,
        Agendamento.data_hora    < fim,
    ).all()


def _bloqueios_do_dia(barbeiro_id, data_dt, barbearia_id):
    inicio = datetime.combine(data_dt, Time(0, 0))
    fim    = inicio + timedelta(days=1)
    return HorarioBloqueado.query.filter(
        HorarioBloqueado.barbearia_id    == barbearia_id,
        HorarioBloqueado.barbeiro_id     == barbeiro_id,
        HorarioBloqueado.data_hora_inicio < fim,
        HorarioBloqueado.data_hora_fim   > inicio,
    ).all()


# ── ROTAS DO BARBEIRO ──────────────────────────────────────────────────────────

@agenda.get('/agenda/meus-agendamentos')
@barbeiro_required
def meus_agendamentos():
    uid          = int(get_jwt_identity())
    barbearia_id = get_barbearia_atual()
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)
    if not barbeiro:
        return _erro('Perfil de barbeiro não encontrado.', 404)

    data_str = request.args.get('data', '').strip()
    if not data_str:
        return _erro('Parâmetro "data" é obrigatório (formato: YYYY-MM-DD).')
    try:
        data_dt = datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        return _erro('Formato de data inválido. Use YYYY-MM-DD.')

    inicio = datetime.combine(data_dt, Time(0, 0))
    fim    = inicio + timedelta(days=1)

    registros = (
        db.session.query(Agendamento, Cliente, Servico)
        .join(Cliente, Agendamento.cliente_id == Cliente.id)
        .join(Servico, Agendamento.servico_id == Servico.id)
        .filter(
            Agendamento.barbearia_id == barbearia_id,
            Agendamento.barbeiro_id  == barbeiro.id,
            Agendamento.data_hora    >= inicio,
            Agendamento.data_hora    < fim,
        )
        .order_by(Agendamento.data_hora)
        .all()
    )

    # Batch load atendimentos for these agendamentos
    ag_ids = [ag.id for ag, _, _ in registros]
    at_map = {
        at.agendamento_id: at.id
        for at in Atendimento.query.filter(Atendimento.agendamento_id.in_(ag_ids)).all()
    } if ag_ids else {}

    # Batch-load serviços e produtos de todos os agendamentos do dia
    ag_ids = [ag.id for ag, _, _ in registros]
    svs_map: dict = defaultdict(list)
    for ag_sv in (AgendamentoServico.query
                  .filter(AgendamentoServico.agendamento_id.in_(ag_ids)).all()
                  if ag_ids else []):
        sv_obj = db.session.get(Servico, ag_sv.servico_id)
        svs_map[ag_sv.agendamento_id].append({
            'nome':           sv_obj.nome if sv_obj else '—',
            'quantidade':     ag_sv.quantidade,
            'preco_unitario': float(ag_sv.preco_unitario),
            'subtotal':       round(float(ag_sv.preco_unitario) * ag_sv.quantidade, 2),
        })
    pds_map: dict = defaultdict(list)
    for rp in (ReservaProduto.query
               .filter(ReservaProduto.agendamento_id.in_(ag_ids),
                       ReservaProduto.status != 'cancelado').all()
               if ag_ids else []):
        pd_obj = db.session.get(Produto, rp.produto_id)
        preco  = float(pd_obj.preco) if pd_obj else 0.0
        pds_map[rp.agendamento_id].append({
            'nome':           pd_obj.nome if pd_obj else '—',
            'quantidade':     rp.quantidade,
            'preco_unitario': preco,
            'subtotal':       round(preco * rp.quantidade, 2),
        })

    agendamentos_fmt = []
    for ag, cl, sv in registros:
        svs = svs_map.get(ag.id) or [
            {'nome': sv.nome, 'quantidade': 1,
             'preco_unitario': float(sv.preco), 'subtotal': float(sv.preco)}
        ]
        pds = pds_map.get(ag.id, [])
        total = round(sum(x['subtotal'] for x in svs) + sum(x['subtotal'] for x in pds), 2)
        agendamentos_fmt.append({
            'id':              ag.id,
            'cliente':         cl.nome,
            'cliente_foto':    cl.foto,
            'telefone':        cl.telefone,
            'servico':         sv.nome,
            'servico_preco':   float(sv.preco),
            'servicos':        svs,
            'produtos':        pds,
            'total':           total,
            'data_hora':       ag.data_hora.isoformat(),
            'duracao_minutos': ag.duracao_minutos,
            'status':          ag.status,
            'observacao':      ag.observacao,
            'atendimento_id':  at_map.get(ag.id),
            'em_atendimento':  ag.id in at_map,
        })

    # Bloqueios do dia para este barbeiro
    bloqueios_dia = HorarioBloqueado.query.filter(
        HorarioBloqueado.barbearia_id    == barbearia_id,
        HorarioBloqueado.barbeiro_id     == barbeiro.id,
        HorarioBloqueado.data_hora_inicio <  inicio + timedelta(days=1),
        HorarioBloqueado.data_hora_fim   >  inicio,
    ).all()

    # Solicitações pendentes deste barbeiro neste dia
    solic_pendentes = SolicitacaoLiberacao.query.filter_by(
        barbearia_id=barbearia_id,
        barbeiro_id=barbeiro.id,
        data=data_dt,
        status='pendente',
    ).all()

    # Monta mapa (hora_inicio, hora_fim) → solicitação
    solic_map = {
        (s.hora_inicio, s.hora_fim): {'id': s.id, 'status': s.status}
        for s in solic_pendentes
    }

    bloqueios_fmt = []
    for bl in bloqueios_dia:
        dia_inteiro = (
            bl.data_hora_inicio.hour == 0 and bl.data_hora_inicio.minute == 0
            and bl.data_hora_fim.hour == 23 and bl.data_hora_fim.minute >= 59
        )
        h_ini = bl.data_hora_inicio.time()
        h_fim = bl.data_hora_fim.time()
        solic = solic_map.get((None, None) if dia_inteiro else (h_ini, h_fim))
        bloqueios_fmt.append({
            'id':          bl.id,
            'hora_inicio': bl.data_hora_inicio.strftime('%H:%M'),
            'hora_fim':    bl.data_hora_fim.strftime('%H:%M'),
            'motivo':      bl.motivo,
            'dia_inteiro': dia_inteiro,
            'solicitacao': solic,
        })

    return jsonify({
        'agendamentos': agendamentos_fmt,
        'bloqueios':    bloqueios_fmt,
    })


@agenda.post('/agenda/agendamento-manual')
@barbeiro_required
def agendamento_manual():
    uid          = int(get_jwt_identity())
    barbearia_id = get_barbearia_atual()
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)
    if not barbeiro:
        return _erro('Perfil de barbeiro não encontrado.', 404)

    dados = request.get_json(silent=True)
    if not dados:
        return _erro('Corpo da requisição inválido ou ausente.')

    nome          = (dados.get('nome') or '').strip()
    telefone_raw  = (dados.get('telefone') or '').strip()
    servico_id    = dados.get('servico_id')
    data_hora_str = (dados.get('data_hora') or '').strip()

    if not nome:
        return _erro('O campo "nome" é obrigatório.')
    if not telefone_raw:
        return _erro('O campo "telefone" é obrigatório.')
    telefone, tel_erro = normalizar_telefone(telefone_raw)
    if tel_erro:
        return _erro(tel_erro)
    if not servico_id:
        return _erro('O campo "servico_id" é obrigatório.')
    if not data_hora_str:
        return _erro('O campo "data_hora" é obrigatório (formato: YYYY-MM-DDTHH:MM).')
    try:
        data_hora = datetime.strptime(data_hora_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        return _erro('Formato de "data_hora" inválido. Use YYYY-MM-DDTHH:MM.')

    vinculo = BarbeiroServico.query.filter_by(
        barbeiro_id=barbeiro.id, servico_id=servico_id
    ).first()
    if not vinculo:
        return _erro('Este serviço não é oferecido pelo seu perfil.')

    servico = Servico.query.filter_by(id=servico_id, barbearia_id=barbearia_id, ativo=True).first()
    if not servico:
        return _erro('Serviço não encontrado.', 404)

    config = ConfiguracaoAgenda.query.filter_by(
        barbeiro_id=barbeiro.id, barbearia_id=barbearia_id
    ).first()
    if not config:
        return _erro('Configure sua agenda antes de usar o agendamento manual.')

    data_dt = data_hora.date()
    slots   = _slots_livres(
        config, data_dt,
        _agendamentos_do_dia(barbeiro.id, data_dt, barbearia_id),
        _bloqueios_do_dia(barbeiro.id, data_dt, barbearia_id),
    )
    if data_hora.strftime('%H:%M') not in slots:
        return _erro(f'O horário {data_hora.strftime("%H:%M")} não está disponível.')

    cliente = Cliente.query.filter_by(telefone=telefone, barbearia_id=barbearia_id).first()
    if not cliente:
        cliente = Cliente(nome=nome, telefone=telefone, barbearia_id=barbearia_id)
        db.session.add(cliente)
    else:
        cliente.nome  = nome
        cliente.ativo = True
    db.session.flush()

    agendamento = Agendamento(
        barbearia_id=barbearia_id,
        cliente_id=cliente.id,
        barbeiro_id=barbeiro.id,
        servico_id=servico_id,
        data_hora=data_hora,
        duracao_minutos=servico.duracao_minutos,
        status='agendado',
    )
    db.session.add(agendamento)
    db.session.commit()

    return jsonify({
        'mensagem': 'Agendamento manual criado com sucesso.',
        'agendamento': {
            'id':              agendamento.id,
            'cliente':         cliente.nome,
            'telefone':        cliente.telefone,
            'servico':         servico.nome,
            'data_hora':       data_hora.isoformat(),
            'duracao_minutos': agendamento.duracao_minutos,
            'status':          agendamento.status,
        },
    }), 201


@agenda.put('/agendamentos/<int:agendamento_id>')
@barbeiro_required
def editar_agendamento(agendamento_id):
    uid          = int(get_jwt_identity())
    barbearia_id = get_barbearia_atual()
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)
    if not barbeiro:
        return _erro('Perfil de barbeiro não encontrado.', 404)

    ag = Agendamento.query.filter_by(id=agendamento_id, barbearia_id=barbearia_id).first()
    if not ag:
        return _erro('Agendamento não encontrado.', 404)
    if ag.barbeiro_id != barbeiro.id:
        return _erro('Você não tem permissão para editar este agendamento.', 403)
    if ag.status != 'agendado':
        return _erro(f'Não é possível editar um agendamento com status "{ag.status}".')

    dados = request.get_json(silent=True) or {}

    if 'servico_id' in dados:
        novo_sid = dados['servico_id']
        if not BarbeiroServico.query.filter_by(barbeiro_id=barbeiro.id, servico_id=novo_sid).first():
            return _erro('Este serviço não é oferecido pelo seu perfil.')
        novo_servico = Servico.query.filter_by(id=novo_sid, barbearia_id=barbearia_id, ativo=True).first()
        if not novo_servico:
            return _erro('Serviço não encontrado.', 404)
        ag.servico_id       = novo_sid
        ag.duracao_minutos  = novo_servico.duracao_minutos

    if 'data_hora' in dados:
        try:
            nova_dh = datetime.strptime(dados['data_hora'], '%Y-%m-%dT%H:%M')
        except ValueError:
            return _erro('Formato de "data_hora" inválido. Use YYYY-MM-DDTHH:MM.')
        config = ConfiguracaoAgenda.query.filter_by(barbeiro_id=barbeiro.id, barbearia_id=barbearia_id).first()
        if config:
            data_dt = nova_dh.date()
            ags_dia = Agendamento.query.filter(
                Agendamento.barbearia_id == barbearia_id,
                Agendamento.barbeiro_id  == barbeiro.id,
                Agendamento.status       == 'agendado',
                Agendamento.data_hora    >= datetime.combine(data_dt, Time(0, 0)),
                Agendamento.data_hora    < datetime.combine(data_dt, Time(0, 0)) + timedelta(days=1),
                Agendamento.id           != ag.id,
            ).all()
            slots = _slots_livres(config, data_dt, ags_dia,
                                  _bloqueios_do_dia(barbeiro.id, data_dt, barbearia_id))
            if nova_dh.strftime('%H:%M') not in slots:
                return _erro(f'O horário {nova_dh.strftime("%H:%M")} não está disponível.')
        ag.data_hora = nova_dh

    if 'observacao' in dados:
        ag.observacao = dados['observacao']

    db.session.commit()
    return jsonify({
        'mensagem': 'Agendamento atualizado com sucesso.',
        'agendamento': {
            'id':              ag.id,
            'data_hora':       ag.data_hora.isoformat(),
            'servico_id':      ag.servico_id,
            'duracao_minutos': ag.duracao_minutos,
            'observacao':      ag.observacao,
            'status':          ag.status,
        },
    })


@agenda.delete('/agendamentos/<int:agendamento_id>')
@barbeiro_required
def cancelar_agendamento(agendamento_id):
    uid          = int(get_jwt_identity())
    barbearia_id = get_barbearia_atual()
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)
    if not barbeiro:
        return _erro('Perfil de barbeiro não encontrado.', 404)

    ag = Agendamento.query.filter_by(id=agendamento_id, barbearia_id=barbearia_id).first()
    if not ag:
        return _erro('Agendamento não encontrado.', 404)
    if ag.barbeiro_id != barbeiro.id:
        return _erro('Você não tem permissão para cancelar este agendamento.', 403)
    if ag.status == 'cancelado':
        return _erro('Este agendamento já está cancelado.')

    ag.status = 'cancelado'
    reservas = ReservaProduto.query.filter_by(agendamento_id=ag.id, status='reservado').all()
    for r in reservas:
        r.status = 'cancelado'
        prod = db.session.get(Produto, r.produto_id)
        if prod:
            prod.quantidade_reservada = max(0, (prod.quantidade_reservada or 0) - r.quantidade)
    db.session.commit()
    return jsonify({'mensagem': 'Agendamento cancelado com sucesso.', 'id': agendamento_id})


@agenda.put('/configuracao-agenda')
@barbeiro_required
def configurar_agenda():
    uid          = int(get_jwt_identity())
    barbearia_id = get_barbearia_atual()
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)
    if not barbeiro:
        return _erro('Perfil de barbeiro não encontrado.', 404)

    dados = request.get_json(silent=True)
    if not dados:
        return _erro('Corpo da requisição inválido ou ausente.')

    config = ConfiguracaoAgenda.query.filter_by(
        barbeiro_id=barbeiro.id, barbearia_id=barbearia_id
    ).first()
    if not config:
        for campo in ('horario_abertura', 'horario_fechamento', 'intervalo_minutos'):
            if campo not in dados:
                return _erro(f'Campo "{campo}" é obrigatório na primeira configuração.')
        config = ConfiguracaoAgenda(barbeiro_id=barbeiro.id, barbearia_id=barbearia_id)
        db.session.add(config)

    if 'horario_abertura' in dados:
        try:
            config.horario_abertura = datetime.strptime(dados['horario_abertura'], '%H:%M').time()
        except ValueError:
            return _erro('Formato de "horario_abertura" inválido. Use HH:MM.')
    if 'horario_fechamento' in dados:
        try:
            config.horario_fechamento = datetime.strptime(dados['horario_fechamento'], '%H:%M').time()
        except ValueError:
            return _erro('Formato de "horario_fechamento" inválido. Use HH:MM.')
    if 'intervalo_minutos' in dados:
        iv = dados['intervalo_minutos']
        if not isinstance(iv, int) or iv < 10:
            return _erro('"intervalo_minutos" deve ser inteiro e no mínimo 10.')
        config.intervalo_minutos = iv
    if 'loja_aberta' in dados:
        if not isinstance(dados['loja_aberta'], bool):
            return _erro('"loja_aberta" deve ser true ou false.')
        config.loja_aberta = dados['loja_aberta']

    if config.horario_abertura >= config.horario_fechamento:
        return _erro('"horario_abertura" deve ser anterior a "horario_fechamento".')

    config.atualizado_em = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'mensagem': 'Agenda configurada com sucesso.',
        'configuracao': {
            'barbeiro_id':        config.barbeiro_id,
            'horario_abertura':   config.horario_abertura.strftime('%H:%M'),
            'horario_fechamento': config.horario_fechamento.strftime('%H:%M'),
            'intervalo_minutos':  config.intervalo_minutos,
            'loja_aberta':        config.loja_aberta,
        },
    })


@agenda.post('/horarios-bloqueados')
@barbeiro_required
def bloquear_horario():
    uid          = int(get_jwt_identity())
    barbearia_id = get_barbearia_atual()
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)
    if not barbeiro:
        return _erro('Perfil de barbeiro não encontrado.', 404)

    dados = request.get_json(silent=True)
    if not dados:
        return _erro('Corpo da requisição inválido ou ausente.')

    inicio_str = (dados.get('data_hora_inicio') or '').strip()
    fim_str    = (dados.get('data_hora_fim') or '').strip()
    motivo     = (dados.get('motivo') or '').strip() or None

    if not inicio_str:
        return _erro('O campo "data_hora_inicio" é obrigatório.')
    if not fim_str:
        return _erro('O campo "data_hora_fim" é obrigatório.')
    try:
        inicio = datetime.strptime(inicio_str, '%Y-%m-%dT%H:%M')
        fim    = datetime.strptime(fim_str,    '%Y-%m-%dT%H:%M')
    except ValueError:
        return _erro('Formato inválido. Use YYYY-MM-DDTHH:MM.')
    if fim <= inicio:
        return _erro('"data_hora_fim" deve ser posterior a "data_hora_inicio".')

    bloqueio = HorarioBloqueado(
        barbearia_id=barbearia_id,
        barbeiro_id=barbeiro.id,
        data_hora_inicio=inicio,
        data_hora_fim=fim,
        motivo=motivo,
    )
    db.session.add(bloqueio)
    db.session.commit()

    return jsonify({
        'mensagem': 'Horário bloqueado com sucesso.',
        'bloqueio': {
            'id':               bloqueio.id,
            'data_hora_inicio': inicio.isoformat(),
            'data_hora_fim':    fim.isoformat(),
            'motivo':           bloqueio.motivo,
        },
    }), 201


@agenda.delete('/horarios-bloqueados/<int:bloqueio_id>')
@barbeiro_required
def desbloquear_horario(bloqueio_id):
    uid          = int(get_jwt_identity())
    barbearia_id = get_barbearia_atual()
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)
    if not barbeiro:
        return _erro('Perfil de barbeiro não encontrado.', 404)

    bloqueio = HorarioBloqueado.query.filter_by(id=bloqueio_id, barbearia_id=barbearia_id).first()
    if not bloqueio:
        return _erro('Bloqueio não encontrado.', 404)
    if bloqueio.barbeiro_id != barbeiro.id:
        return _erro('Você não tem permissão para remover este bloqueio.', 403)

    db.session.delete(bloqueio)
    db.session.commit()
    return jsonify({'mensagem': 'Horário desbloqueado com sucesso.', 'id': bloqueio_id})


# ── GET /agenda/url-agendamento ───────────────────────────────────────────────

@agenda.get('/agenda/url-agendamento')
@barbeiro_required
def url_agendamento_barbearia():
    barbearia_id = get_barbearia_atual()
    b = db.session.get(Barbearia, barbearia_id)
    if not b:
        return _erro('Barbearia não encontrada.', 404)
    return jsonify({
        'url':  b.url_agendamento or f'/b/{b.slug}/',
        'slug': b.slug,
        'nome': b.nome,
    })


# ── GET /agenda/minha-config ──────────────────────────────────────────────────

@agenda.get('/agenda/minha-config')
@barbeiro_required
def minha_config():
    uid          = int(get_jwt_identity())
    barbearia_id = get_barbearia_atual()
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)
    if not barbeiro:
        return _erro('Perfil de barbeiro não encontrado.', 404)
    config = ConfiguracaoAgenda.query.filter_by(
        barbeiro_id=barbeiro.id, barbearia_id=barbearia_id
    ).first()
    if not config:
        return _erro('Agenda não configurada. Peça ao gestor para configurar.', 404)
    return jsonify({
        'horario_abertura':   config.horario_abertura.strftime('%H:%M'),
        'horario_fechamento': config.horario_fechamento.strftime('%H:%M'),
        'intervalo_minutos':  config.intervalo_minutos,
        'loja_aberta':        config.loja_aberta,
    })


# ── GET /agenda/meus-servicos ──────────────────────────────────────────────────

@agenda.get('/agenda/meus-servicos')
@barbeiro_required
def meus_servicos():
    uid          = int(get_jwt_identity())
    barbearia_id = get_barbearia_atual()
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)
    if not barbeiro:
        return _erro('Perfil de barbeiro não encontrado.', 404)
    registros = (
        db.session.query(Servico)
        .join(BarbeiroServico, BarbeiroServico.servico_id == Servico.id)
        .filter(
            BarbeiroServico.barbeiro_id == barbeiro.id,
            Servico.barbearia_id        == barbearia_id,
            Servico.ativo               == True,
        )
        .order_by(Servico.nome)
        .all()
    )
    return jsonify([
        {
            'id':              s.id,
            'nome':            s.nome,
            'duracao_minutos': s.duracao_minutos,
            'preco':           float(s.preco),
        }
        for s in registros
    ])


# ── GET /agenda/meu-dashboard ─────────────────────────────────────────────────

@agenda.get('/agenda/meu-dashboard')
@barbeiro_required
def meu_dashboard():
    uid          = int(get_jwt_identity())
    barbearia_id = get_barbearia_atual()
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)
    if not barbeiro:
        return _erro('Perfil de barbeiro não encontrado.', 404)

    hoje_d  = datetime.now().date()
    ontem_d = hoje_d - timedelta(days=1)

    def _fat_dia(dia):
        ini = datetime.combine(dia, Time(0, 0))
        fim = ini + timedelta(days=1)
        r = db.session.query(func.sum(Atendimento.total)).filter(
            Atendimento.barbeiro_id     == barbeiro.id,
            Atendimento.status_operacao == 'efetuado',
            Atendimento.criado_em       >= ini,
            Atendimento.criado_em       <  fim,
        ).scalar()
        return float(r or 0)

    def _ags_dia(dia, statuses=None):
        ini = datetime.combine(dia, Time(0, 0))
        fim = ini + timedelta(days=1)
        q = Agendamento.query.filter(
            Agendamento.barbearia_id == barbearia_id,
            Agendamento.barbeiro_id  == barbeiro.id,
            Agendamento.data_hora    >= ini,
            Agendamento.data_hora    <  fim,
        )
        if statuses:
            q = q.filter(Agendamento.status.in_(statuses))
        return q.all()

    fat_hoje  = _fat_dia(hoje_d)
    fat_ontem = _fat_dia(ontem_d)
    ags_hoje  = _ags_dia(hoje_d, ['agendado', 'concluido'])
    ags_ontem = _ags_dia(ontem_d, ['agendado', 'concluido'])

    config = ConfiguracaoAgenda.query.filter_by(
        barbeiro_id=barbeiro.id, barbearia_id=barbearia_id
    ).first()
    total_slots = 0
    if config:
        ab, fe = (datetime.combine(hoje_d, config.horario_abertura),
                  datetime.combine(hoje_d, config.horario_fechamento))
        iv, cur = timedelta(minutes=config.intervalo_minutos), ab
        while cur + iv <= fe:
            total_slots += 1
            cur += iv

    taxa_ocupacao = round(len(ags_hoje) / total_slots * 100) if total_slots else 0

    agora   = datetime.now()
    proximo = None
    for ag in sorted(_ags_dia(hoje_d, ['agendado']), key=lambda x: x.data_hora):
        if ag.data_hora > agora:
            cli = db.session.get(Cliente, ag.cliente_id)
            sv  = db.session.get(Servico, ag.servico_id)
            proximo = {
                'nome':     cli.nome if cli else '?',
                'servico':  sv.nome  if sv  else '?',
                'hora':     ag.data_hora.strftime('%H:%M'),
                'data_hora': ag.data_hora.isoformat(),
            }
            break

    receita_7dias = []
    for i in range(6, -1, -1):
        dia = hoje_d - timedelta(days=i)
        receita_7dias.append({'data': dia.isoformat(), 'receita': _fat_dia(dia)})

    return jsonify({
        'atendimentos_hoje':  len(ags_hoje),
        'atendimentos_ontem': len(ags_ontem),
        'faturamento_hoje':   fat_hoje,
        'faturamento_ontem':  fat_ontem,
        'taxa_ocupacao':      taxa_ocupacao,
        'total_slots':        total_slots,
        'slots_ocupados':     len(ags_hoje),
        'proximo_cliente':    proximo,
        'receita_7dias':      receita_7dias,
    })


# ── GET /agenda/meu-perfil ────────────────────────────────────────────────────

@agenda.get('/agenda/meu-perfil')
@barbeiro_required
def meu_perfil():
    uid          = int(get_jwt_identity())
    barbearia_id = get_barbearia_atual()
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)
    if not barbeiro:
        return _erro('Perfil de barbeiro não encontrado.', 404)
    u = db.session.get(Usuario, uid)
    return jsonify({
        'barbeiro_id':         barbeiro.id,
        'nome':                u.nome,
        'email':               u.email,
        'telefone':            u.telefone,
        'comissao_percentual': float(barbeiro.comissao_percentual),
        'foto':                barbeiro.foto,
        'bio':                 barbeiro.bio,
    })


# ── PUT /agenda/meu-perfil ────────────────────────────────────────────────────

@agenda.put('/agenda/meu-perfil')
@barbeiro_required
def atualizar_meu_perfil():
    uid          = int(get_jwt_identity())
    barbearia_id = get_barbearia_atual()
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)
    if not barbeiro:
        return _erro('Perfil de barbeiro não encontrado.', 404)
    u    = db.session.get(Usuario, uid)
    dados = request.get_json(silent=True) or {}
    if 'nome' in dados:
        n = (dados['nome'] or '').strip()
        if not n: return _erro('"nome" não pode ser vazio.')
        u.nome = n
    if 'email' in dados:
        e = (dados['email'] or '').strip().lower()
        if e and '@' not in e: return _erro('E-mail inválido.')
        dup = Usuario.query.filter_by(email=e).first()
        if dup and dup.id != uid: return _erro('E-mail já cadastrado.', 409)
        u.email = e or None
    if 'telefone' in dados:
        t = (dados['telefone'] or '').strip()
        if t: u.telefone = t
    if 'bio' in dados:
        barbeiro.bio = (dados['bio'] or '').strip() or None
    db.session.commit()
    return jsonify({
        'mensagem': 'Perfil atualizado.',
        'usuario':  {'nome': u.nome, 'email': u.email, 'telefone': u.telefone},
    })


# ── RESERVAS DE PRODUTOS ───────────────────────────────────────────────────────

@agenda.get('/agendamentos/<int:agendamento_id>/reservas')
@barbeiro_required
def listar_reservas(agendamento_id):
    barbearia_id = get_barbearia_atual()
    ag = Agendamento.query.filter_by(id=agendamento_id, barbearia_id=barbearia_id).first()
    if not ag:
        return _erro('Agendamento não encontrado.', 404)

    reservas = ReservaProduto.query.filter_by(agendamento_id=agendamento_id).all()
    resultado = []
    for r in reservas:
        produto = db.session.get(Produto, r.produto_id)
        resultado.append({
            'id':         r.id,
            'produto_id': r.produto_id,
            'nome':       produto.nome if produto else None,
            'quantidade': r.quantidade,
            'status':     r.status,
        })
    return jsonify(resultado)


@agenda.post('/agenda/solicitar-liberacao')
@barbeiro_required
def solicitar_liberacao():
    uid          = int(get_jwt_identity())
    barbearia_id = get_barbearia_atual()
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)
    if not barbeiro:
        return _erro('Perfil de barbeiro não encontrado.', 404)

    dados = request.get_json(silent=True)

    print(f"\n[SOLICITAR-LIBERACAO] raw body recebido: {dados}")

    if not dados:
        return _erro('Corpo inválido ou ausente.')

    data_str    = (dados.get('data')        or '').strip()
    hora_inicio = (dados.get('hora_inicio') or '').strip() or None
    hora_fim    = (dados.get('hora_fim')    or '').strip() or None
    motivo      = (dados.get('motivo')      or '').strip() or None

    print(f"  data_str    = {repr(data_str)}")
    print(f"  hora_inicio = {repr(hora_inicio)}")
    print(f"  hora_fim    = {repr(hora_fim)}")
    print(f"  motivo      = {repr(motivo)}")

    if not data_str:
        return _erro('"data" é obrigatório.')
    try:
        data_dt = datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        return _erro('Formato de data inválido.')

    h_ini = h_fim = None
    if hora_inicio and hora_fim:
        try:
            h_ini = datetime.strptime(hora_inicio, '%H:%M').time()
            h_fim = datetime.strptime(hora_fim,    '%H:%M').time()
        except ValueError:
            print(f"  ERRO: formato de hora inválido")
            return _erro('Formato de hora inválido. Use HH:MM.')

    print(f"  h_ini (time) = {h_ini}")
    print(f"  h_fim (time) = {h_fim}")
    print(f"  barbeiro_id  = {barbeiro.id}  barbearia_id = {barbearia_id}")

    # Verifica solicitação já existente (evita duplicatas)
    existente = SolicitacaoLiberacao.query.filter_by(
        barbearia_id=barbearia_id,
        barbeiro_id=barbeiro.id,
        data=data_dt,
        hora_inicio=h_ini,
        hora_fim=h_fim,
        status='pendente',
    ).first()
    if existente:
        print(f"  DUPLICATA: sol_id={existente.id} já existe")
        return _erro('Já existe uma solicitação pendente para este horário.', 409)

    sol = SolicitacaoLiberacao(
        barbearia_id=barbearia_id,
        barbeiro_id=barbeiro.id,
        data=data_dt,
        hora_inicio=h_ini,
        hora_fim=h_fim,
        motivo=motivo,
    )
    db.session.add(sol)
    db.session.commit()

    print(f"  SALVO: sol_id={sol.id}  data={sol.data}  hora_inicio={sol.hora_inicio}  hora_fim={sol.hora_fim}\n")

    return jsonify({'mensagem': 'Solicitação enviada ao gestor.', 'id': sol.id}), 201


@agenda.get('/agenda/notificacoes-liberacao')
@barbeiro_required
def notificacoes_liberacao():
    uid          = int(get_jwt_identity())
    barbearia_id = get_barbearia_atual()
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)
    if not barbeiro:
        return _erro('Perfil de barbeiro não encontrado.', 404)

    pendentes = SolicitacaoLiberacao.query.filter(
        SolicitacaoLiberacao.barbearia_id == barbearia_id,
        SolicitacaoLiberacao.barbeiro_id  == barbeiro.id,
        SolicitacaoLiberacao.status.in_(['aprovado', 'rejeitado']),
        SolicitacaoLiberacao.notificado   == False,
    ).all()

    result = []
    for sol in pendentes:
        result.append({
            'id':          sol.id,
            'data':        sol.data.isoformat(),
            'hora_inicio': sol.hora_inicio.strftime('%H:%M') if sol.hora_inicio else None,
            'hora_fim':    sol.hora_fim.strftime('%H:%M')    if sol.hora_fim    else None,
            'status':      sol.status,
            'motivo':      sol.motivo,
        })
        sol.notificado = True

    db.session.commit()
    return jsonify(result)


@agenda.delete('/reservas/<int:reserva_id>')
@barbeiro_required
def cancelar_reserva(reserva_id):
    barbearia_id = get_barbearia_atual()
    reserva = db.session.get(ReservaProduto, reserva_id)
    if not reserva:
        return _erro('Reserva não encontrada.', 404)

    # Verifica que o agendamento é desta barbearia
    ag = Agendamento.query.filter_by(id=reserva.agendamento_id, barbearia_id=barbearia_id).first()
    if not ag:
        return _erro('Reserva não encontrada.', 404)

    if reserva.status == 'confirmado':
        return _erro('Não é possível cancelar uma reserva já confirmada.')
    if reserva.status == 'cancelado':
        return _erro('Esta reserva já está cancelada.')

    reserva.status = 'cancelado'
    db.session.commit()
    return jsonify({'mensagem': 'Reserva cancelada com sucesso.', 'id': reserva_id})


# ── GET /agenda/meus-planos (barbeiro) ──────────────────────────────────────────

@agenda.get('/agenda/meus-planos')
@barbeiro_required
def meus_planos_barbeiro():
    uid          = int(get_jwt_identity())
    barbearia_id = get_barbearia_atual()
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)
    if not barbeiro:
        return _erro('Perfil de barbeiro não encontrado.', 404)

    vinculos = PlanoBarbeiro.query.filter_by(barbeiro_id=barbeiro.id, barbearia_id=barbearia_id).all()
    resultado = []
    for v in vinculos:
        plano = db.session.get(Plano, v.plano_id)
        if not plano or not plano.ativo:
            continue
        vinculos_sv = PlanoServico.query.filter_by(plano_id=plano.id, ativo=True).all()
        servicos = [s.nome for s in Servico.query.filter(
            Servico.id.in_([vs.servico_id for vs in vinculos_sv])).all()] if vinculos_sv else []
        resultado.append({
            'id': plano.id,
            'nome': plano.nome,
            'preco_mensal': float(plano.preco_mensal),
            'clientes': ClientePlano.query.filter_by(plano_id=plano.id, ativo=True).count(),
            'servicos': servicos,
        })
    return jsonify(resultado)


# ── GET /agenda/agendamentos-hoje (barbeiro) ────────────────────────────────────

@agenda.get('/agenda/agendamentos-hoje')
@barbeiro_required
def agendamentos_hoje_barbeiro():
    uid          = int(get_jwt_identity())
    barbearia_id = get_barbearia_atual()
    barbeiro     = _barbeiro_do_usuario(uid, barbearia_id)
    if not barbeiro:
        return _erro('Perfil de barbeiro não encontrado.', 404)

    hoje    = datetime.utcnow().date()
    ini_dia = datetime.combine(hoje, Time(0, 0))
    fim_dia = ini_dia + timedelta(days=1)

    rows = (
        db.session.query(Agendamento, Cliente, Servico)
        .join(Cliente, Agendamento.cliente_id == Cliente.id)
        .join(Servico, Agendamento.servico_id == Servico.id)
        .filter(
            Agendamento.barbeiro_id == barbeiro.id,
            Agendamento.barbearia_id == barbearia_id,
            Agendamento.status == 'agendado',
            Agendamento.data_hora >= ini_dia,
            Agendamento.data_hora < fim_dia,
        )
        .order_by(Agendamento.data_hora)
        .all()
    )

    resultado = []
    for ag, cl, sv in rows:
        cliente_plano = ClientePlano.query.filter_by(cliente_id=cl.id, ativo=True).first()
        plano_nome = None
        if cliente_plano and ClientePlanoUso.query.filter_by(
            cliente_plano_id=cliente_plano.id, servico_id=sv.id, data_uso=ag.data_hora.date(),
        ).first():
            plano = db.session.get(Plano, cliente_plano.plano_id)
            plano_nome = plano.nome if plano else None
        resultado.append({
            'id': ag.id,
            'hora': ag.data_hora.strftime('%H:%M'),
            'cliente_nome': cl.nome,
            'servico': sv.nome,
            'plano_nome': plano_nome,
            'status': ag.status,
        })
    return jsonify(resultado)


# ── ROTAS DO CLIENTE (app autenticado) ──────────────────────────────────────────

def _cliente_atual():
    usuario = db.session.get(Usuario, int(get_jwt_identity()))
    return usuario.cliente if usuario else None


def _plano_ativo_do_cliente(cliente):
    return ClientePlano.query.filter_by(cliente_id=cliente.id, ativo=True).first()


@agenda.get('/cliente/proximos-agendamentos')
@cliente_required
def proximos_agendamentos_cliente():
    cliente = _cliente_atual()
    if not cliente:
        return _erro('Cadastro de cliente não encontrado para este usuário.', 404)

    rows = (
        db.session.query(Agendamento, Barbeiro, Usuario, Servico)
        .join(Barbeiro, Agendamento.barbeiro_id == Barbeiro.id)
        .join(Usuario,  Barbeiro.usuario_id == Usuario.id)
        .join(Servico,  Agendamento.servico_id == Servico.id)
        .filter(
            Agendamento.cliente_id == cliente.id,
            Agendamento.status == 'agendado',
            Agendamento.data_hora >= datetime.utcnow(),
        )
        .order_by(Agendamento.data_hora)
        .limit(5)
        .all()
    )
    return jsonify([
        {
            'id': ag.id,
            'data_hora': ag.data_hora.isoformat(),
            'barbeiro_nome': u.nome,
            'servico_nome': sv.nome,
            'status': ag.status,
        }
        for ag, b, u, sv in rows
    ])


@agenda.get('/cliente/agendar/opcoes')
@cliente_required
def opcoes_agendar_cliente():
    cliente = _cliente_atual()
    if not cliente:
        return _erro('Cadastro de cliente não encontrado para este usuário.', 404)
    barbearia_id = cliente.barbearia_id

    cliente_plano = _plano_ativo_do_cliente(cliente)
    servicos_plano = []
    barbeiros_ids_plano = None

    if cliente_plano:
        vinculos = PlanoServico.query.filter_by(plano_id=cliente_plano.plano_id, ativo=True).all()
        janela_30d = datetime.utcnow().date() - timedelta(days=30)
        for v in vinculos:
            sv = db.session.get(Servico, v.servico_id)
            if not sv or not sv.ativo:
                continue
            ja_usou = ClientePlanoUso.query.filter(
                ClientePlanoUso.cliente_plano_id == cliente_plano.id,
                ClientePlanoUso.servico_id == v.servico_id,
                ClientePlanoUso.usado == True,
                ClientePlanoUso.data_uso >= janela_30d,
            ).count()
            if ja_usou < v.limite_uso_mensal:
                limite_fmt = limite_para_fora(v.limite_uso_mensal)
                servicos_plano.append({
                    'id': sv.id, 'nome': sv.nome,
                    'limite_mensal': limite_fmt, 'ja_usou': ja_usou,
                    'disponivel': (v.limite_uso_mensal - ja_usou) if limite_fmt is not None else None,
                })
        vinculos_barbeiro = PlanoBarbeiro.query.filter_by(plano_id=cliente_plano.plano_id).all()
        if vinculos_barbeiro:
            barbeiros_ids_plano = [v.barbeiro_id for v in vinculos_barbeiro]

    servicos_avulso = [
        {'id': s.id, 'nome': s.nome, 'preco': float(s.preco), 'duracao_minutos': s.duracao_minutos}
        for s in Servico.query.filter_by(barbearia_id=barbearia_id, ativo=True).order_by(Servico.nome).all()
    ]

    barbeiros_q = Barbeiro.query.filter_by(barbearia_id=barbearia_id, ativo=True)
    if barbeiros_ids_plano:
        barbeiros_q = barbeiros_q.filter(Barbeiro.id.in_(barbeiros_ids_plano))
    barbeiros = []
    for b in barbeiros_q.all():
        u = db.session.get(Usuario, b.usuario_id)
        if u and u.ativo:
            barbeiros.append({'id': b.id, 'nome': u.nome, 'foto': b.foto})

    return jsonify({
        'tem_plano': cliente_plano is not None,
        'plano_id': cliente_plano.plano_id if cliente_plano else None,
        'servicos_plano': servicos_plano,
        'servicos_avulso': servicos_avulso,
        'barbeiros': barbeiros,
    })


@agenda.get('/cliente/agendar/horarios')
@cliente_required
def horarios_cliente():
    cliente = _cliente_atual()
    if not cliente:
        return _erro('Cadastro de cliente não encontrado para este usuário.', 404)

    barbeiro_id = request.args.get('barbeiro_id', type=int)
    data_str = request.args.get('data', '').strip()
    if not barbeiro_id:
        return _erro('"barbeiro_id" é obrigatório.')
    if not data_str:
        return _erro('"data" é obrigatório (YYYY-MM-DD).')
    try:
        data_dt = datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        return _erro('Formato de data inválido. Use YYYY-MM-DD.')

    barbeiro = Barbeiro.query.filter_by(id=barbeiro_id, barbearia_id=cliente.barbearia_id, ativo=True).first()
    if not barbeiro:
        return _erro('Barbeiro não encontrado.', 404)
    config = ConfiguracaoAgenda.query.filter_by(barbeiro_id=barbeiro_id, barbearia_id=cliente.barbearia_id).first()
    if not config:
        return _erro('O barbeiro ainda não configurou sua agenda.')

    agendamentos = _agendamentos_do_dia(barbeiro_id, data_dt, cliente.barbearia_id)
    bloqueios = _bloqueios_do_dia(barbeiro_id, data_dt, cliente.barbearia_id)
    slots = _slots_livres(config, data_dt, agendamentos, bloqueios)
    return jsonify({'slots': slots, 'data': data_str})


@agenda.post('/cliente/agendar')
@cliente_required
def criar_agendamento_cliente():
    cliente = _cliente_atual()
    if not cliente:
        return _erro('Cadastro de cliente não encontrado para este usuário.', 404)
    barbearia_id = cliente.barbearia_id

    dados = request.get_json(silent=True)
    if not dados:
        return _erro('Corpo da requisição inválido ou ausente.')

    servico_id    = dados.get('servico_id')
    barbeiro_id   = dados.get('barbeiro_id')
    data_str      = (dados.get('data') or '').strip()
    hora_str      = (dados.get('hora') or '').strip()
    usar_plano    = bool(dados.get('usar_plano', False))

    if not servico_id:  return _erro('"servico_id" é obrigatório.')
    if not barbeiro_id: return _erro('"barbeiro_id" é obrigatório.')
    if not data_str or not hora_str: return _erro('"data" e "hora" são obrigatórios.')
    try:
        data_hora = datetime.strptime(f'{data_str} {hora_str}', '%Y-%m-%d %H:%M')
    except ValueError:
        return _erro('Formato de data/hora inválido.')

    servico = Servico.query.filter_by(id=servico_id, barbearia_id=barbearia_id, ativo=True).first()
    if not servico:
        return _erro('Serviço não encontrado.', 404)
    barbeiro = Barbeiro.query.filter_by(id=barbeiro_id, barbearia_id=barbearia_id, ativo=True).first()
    if not barbeiro:
        return _erro('Barbeiro não encontrado.', 404)
    if not BarbeiroServico.query.filter_by(barbeiro_id=barbeiro_id, servico_id=servico_id).first():
        return _erro('Este barbeiro não atende este serviço.')

    cliente_plano = _plano_ativo_do_cliente(cliente)
    vinculo_plano = None
    if usar_plano:
        if not cliente_plano:
            return _erro('Você não possui um plano ativo.')
        vinculo_plano = PlanoServico.query.filter_by(
            plano_id=cliente_plano.plano_id, servico_id=servico_id, ativo=True,
        ).first()
        if not vinculo_plano:
            return _erro('Este serviço não está incluído no seu plano.')
        janela_30d = datetime.utcnow().date() - timedelta(days=30)
        ja_usou = ClientePlanoUso.query.filter(
            ClientePlanoUso.cliente_plano_id == cliente_plano.id,
            ClientePlanoUso.servico_id == servico_id,
            ClientePlanoUso.usado == True,
            ClientePlanoUso.data_uso >= janela_30d,
        ).count()
        if ja_usou >= vinculo_plano.limite_uso_mensal:
            return _erro('Você já utilizou a cota deste serviço no seu plano este mês.', 409)

        vinculos_barbeiro = PlanoBarbeiro.query.filter_by(plano_id=cliente_plano.plano_id).all()
        if vinculos_barbeiro and barbeiro_id not in [v.barbeiro_id for v in vinculos_barbeiro]:
            return _erro('Este barbeiro não atende clientes deste plano.')

    config = ConfiguracaoAgenda.query.filter_by(barbeiro_id=barbeiro_id, barbearia_id=barbearia_id).first()
    if not config:
        return _erro('O barbeiro ainda não configurou sua agenda.')
    data_dt = data_hora.date()
    slots = _slots_livres(
        config, data_dt,
        _agendamentos_do_dia(barbeiro_id, data_dt, barbearia_id),
        _bloqueios_do_dia(barbeiro_id, data_dt, barbearia_id),
    )
    if hora_str not in slots:
        return _erro(f'O horário {hora_str} não está disponível.')

    agendamento = Agendamento(
        barbearia_id=barbearia_id,
        cliente_id=cliente.id,
        barbeiro_id=barbeiro_id,
        servico_id=servico_id,
        data_hora=data_hora,
        duracao_minutos=servico.duracao_minutos,
        status='agendado',
    )
    db.session.add(agendamento)
    db.session.flush()
    db.session.add(AgendamentoServico(
        agendamento_id=agendamento.id, servico_id=servico_id,
        quantidade=1, preco_unitario=servico.preco,
    ))

    if vinculo_plano:
        hoje = datetime.utcnow().date()
        db.session.add(ClientePlanoUso(
            cliente_plano_id=cliente_plano.id, servico_id=servico_id,
            data_uso=hoje, semana_do_mes=min(((hoje.day - 1) // 7) + 1, 5), usado=True,
        ))

    db.session.commit()

    return jsonify({
        'mensagem': f'Agendamento confirmado! Barbeiro: {db.session.get(Usuario, barbeiro.usuario_id).nome}',
        'agendamento_id': agendamento.id,
        'status': agendamento.status,
        'incluido_no_plano': vinculo_plano is not None,
    }), 201
