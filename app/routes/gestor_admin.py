import calendar as _cal
from werkzeug.security import generate_password_hash
from collections import defaultdict
from datetime import datetime, timedelta, time as Time, date
from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import func
from app import db
from app.models import (
    Barbearia, Usuario, Barbeiro, BarbeiroServico, Servico,
    ConfiguracaoAgenda, HorarioBloqueado, Agendamento, AgendamentoServico,
    Atendimento, Produto, ReservaProduto, SolicitacaoSenha, Cliente, SolicitacaoLiberacao,
)
from app.utils import get_barbearia_atual, normalizar_telefone, registrar_auditoria
from app.routes.auth import gestor_required, barbeiro_required

gestor_admin = Blueprint('gestor_admin', __name__)


def _erro(msg, code=400):
    return jsonify({'erro': msg}), code


def _hash(senha):
    return generate_password_hash(senha)


def _fmt_barbeiro(b, u):
    ids = [x.servico_id for x in BarbeiroServico.query.filter_by(barbeiro_id=b.id).all()]
    return {
        'id': b.id, 'usuario_id': u.id,
        'nome': u.nome, 'email': u.email, 'telefone': u.telefone,
        'foto': b.foto, 'bio': b.bio,
        'comissao_percentual': float(b.comissao_percentual),
        'ativo': b.ativo, 'servicos_ids': ids,
    }


# ── GET /admin/barbeiros ───────────────────────────────────────────────────────

@gestor_admin.get('/admin/barbeiros')
@gestor_required
def listar_barbeiros():
    barbearia_id = get_barbearia_atual()
    rows = (
        db.session.query(Barbeiro, Usuario)
        .join(Usuario, Barbeiro.usuario_id == Usuario.id)
        .filter(Barbeiro.barbearia_id == barbearia_id)
        .order_by(Usuario.nome).all()
    )
    return jsonify([_fmt_barbeiro(b, u) for b, u in rows])


# ── POST /admin/barbeiros ──────────────────────────────────────────────────────

@gestor_admin.post('/admin/barbeiros')
@gestor_required
def criar_barbeiro():
    barbearia_id = get_barbearia_atual()
    dados = request.get_json(silent=True)
    if not dados:
        return _erro('Corpo inválido ou ausente.')

    nome         = (dados.get('nome') or '').strip()
    email        = (dados.get('email') or '').strip().lower()
    telefone     = (dados.get('telefone') or '').strip()
    senha        = (dados.get('senha') or '').strip()
    comissao     = dados.get('comissao_percentual', 0)
    bio          = (dados.get('bio') or '').strip() or None
    servicos_ids = dados.get('servicos_ids') or []

    if not nome:      return _erro('"nome" é obrigatório.')
    if not telefone:  return _erro('"telefone" é obrigatório.')
    if email and '@' not in email: return _erro('E-mail inválido.')
    if not senha or len(senha) < 6: return _erro('Senha mínimo 6 caracteres.')
    if not isinstance(comissao, (int, float)) or not (0 <= comissao <= 100):
        return _erro('"comissao_percentual" deve ser entre 0 e 100.')
    if email and Usuario.query.filter_by(email=email).first():
        return _erro('E-mail já cadastrado.', 409)

    usuario = Usuario(
        barbearia_id=barbearia_id, nome=nome, telefone=telefone,
        email=email or None, senha=_hash(senha), perfil='barbeiro',
    )
    db.session.add(usuario)
    db.session.flush()

    barbeiro = Barbeiro(
        barbearia_id=barbearia_id, usuario_id=usuario.id,
        comissao_percentual=comissao, bio=bio,
    )
    db.session.add(barbeiro)
    db.session.flush()

    for sid in servicos_ids:
        if Servico.query.filter_by(id=sid, barbearia_id=barbearia_id, ativo=True).first():
            db.session.add(BarbeiroServico(barbeiro_id=barbeiro.id, servico_id=sid))

    if not ConfiguracaoAgenda.query.filter_by(barbeiro_id=barbeiro.id).first():
        db.session.add(ConfiguracaoAgenda(
            barbearia_id=barbearia_id,
            barbeiro_id=barbeiro.id,
            horario_abertura=Time(8, 0),
            horario_fechamento=Time(18, 0),
            intervalo_minutos=30,
        ))

    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'create', 'barbeiro', barbeiro.id,
                         f'Criou barbeiro "{nome}".')
    return jsonify({'mensagem': 'Barbeiro criado.', 'barbeiro': _fmt_barbeiro(barbeiro, usuario)}), 201


# ── PUT /admin/barbeiros/<id> ──────────────────────────────────────────────────

@gestor_admin.put('/admin/barbeiros/<int:barbeiro_id>')
@gestor_required
def editar_barbeiro(barbeiro_id):
    barbearia_id = get_barbearia_atual()
    barbeiro = Barbeiro.query.filter_by(id=barbeiro_id, barbearia_id=barbearia_id).first()
    if not barbeiro: return _erro('Barbeiro não encontrado.', 404)

    usuario = db.session.get(Usuario, barbeiro.usuario_id)
    dados   = request.get_json(silent=True) or {}

    if 'nome' in dados:
        n = (dados['nome'] or '').strip()
        if not n: return _erro('"nome" não pode ser vazio.')
        usuario.nome = n
    if 'email' in dados:
        e = (dados['email'] or '').strip().lower()
        if e and '@' not in e: return _erro('E-mail inválido.')
        dup = Usuario.query.filter_by(email=e).first()
        if dup and dup.id != usuario.id: return _erro('E-mail já cadastrado.', 409)
        usuario.email = e or None
    if 'telefone' in dados:
        t = (dados['telefone'] or '').strip()
        if t: usuario.telefone = t
    if 'bio' in dados:
        barbeiro.bio = (dados['bio'] or '').strip() or None
    if 'comissao_percentual' in dados:
        c = dados['comissao_percentual']
        if not isinstance(c, (int, float)) or not (0 <= c <= 100):
            return _erro('"comissao_percentual" deve ser entre 0 e 100.')
        barbeiro.comissao_percentual = c
    if 'ativo' in dados:
        barbeiro.ativo = bool(dados['ativo'])
        usuario.ativo  = bool(dados['ativo'])
    if 'servicos_ids' in dados:
        BarbeiroServico.query.filter_by(barbeiro_id=barbeiro_id).delete()
        for sid in (dados['servicos_ids'] or []):
            if Servico.query.filter_by(id=sid, barbearia_id=barbearia_id).first():
                db.session.add(BarbeiroServico(barbeiro_id=barbeiro_id, servico_id=sid))

    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'edit', 'barbeiro', barbeiro.id,
                         f'Editou barbeiro "{usuario.nome}".')
    return jsonify({'mensagem': 'Barbeiro atualizado.', 'barbeiro': _fmt_barbeiro(barbeiro, usuario)})


# ── DELETE /admin/barbeiros/<id> ───────────────────────────────────────────────

@gestor_admin.delete('/admin/barbeiros/<int:barbeiro_id>')
@gestor_required
def desativar_barbeiro(barbeiro_id):
    barbearia_id = get_barbearia_atual()
    barbeiro = Barbeiro.query.filter_by(id=barbeiro_id, barbearia_id=barbearia_id).first()
    if not barbeiro: return _erro('Barbeiro não encontrado.', 404)
    barbeiro.ativo = False
    u = db.session.get(Usuario, barbeiro.usuario_id)
    if u: u.ativo = False
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'delete', 'barbeiro', barbeiro_id,
                         f'Desativou barbeiro "{u.nome if u else barbeiro_id}".')
    return jsonify({'mensagem': 'Barbeiro desativado.', 'id': barbeiro_id})


# ── GET /admin/agenda ──────────────────────────────────────────────────────────

@gestor_admin.get('/admin/agenda')
@gestor_required
def listar_agenda():
    barbearia_id = get_barbearia_atual()
    rows = (
        db.session.query(Barbeiro, Usuario, ConfiguracaoAgenda)
        .join(Usuario, Barbeiro.usuario_id == Usuario.id)
        .outerjoin(
            ConfiguracaoAgenda,
            (ConfiguracaoAgenda.barbeiro_id == Barbeiro.id) &
            (ConfiguracaoAgenda.barbearia_id == barbearia_id)
        )
        .filter(Barbeiro.barbearia_id == barbearia_id, Barbeiro.ativo == True)
        .order_by(Usuario.nome).all()
    )
    return jsonify([
        {
            'barbeiro_id': b.id, 'nome': u.nome, 'foto': b.foto,
            'comissao_percentual': float(b.comissao_percentual),
            'configuracao': {
                'horario_abertura':   c.horario_abertura.strftime('%H:%M') if c else None,
                'horario_fechamento': c.horario_fechamento.strftime('%H:%M') if c else None,
                'intervalo_minutos':  c.intervalo_minutos if c else 60,
                'loja_aberta':        c.loja_aberta if c else True,
            } if c else None,
        }
        for b, u, c in rows
    ])


# ── PUT /admin/agenda/<barbeiro_id> ────────────────────────────────────────────

@gestor_admin.put('/admin/agenda/<int:barbeiro_id>')
@gestor_required
def configurar_agenda(barbeiro_id):
    barbearia_id = get_barbearia_atual()
    barbeiro = Barbeiro.query.filter_by(id=barbeiro_id, barbearia_id=barbearia_id, ativo=True).first()
    if not barbeiro: return _erro('Barbeiro não encontrado.', 404)

    dados = request.get_json(silent=True)
    if not dados: return _erro('Corpo inválido ou ausente.')

    config = ConfiguracaoAgenda.query.filter_by(barbeiro_id=barbeiro_id, barbearia_id=barbearia_id).first()
    if not config:
        for f in ('horario_abertura', 'horario_fechamento', 'intervalo_minutos'):
            if f not in dados: return _erro(f'"{f}" é obrigatório na primeira configuração.')
        config = ConfiguracaoAgenda(barbeiro_id=barbeiro_id, barbearia_id=barbearia_id)
        db.session.add(config)

    if 'horario_abertura' in dados:
        try: config.horario_abertura = datetime.strptime(dados['horario_abertura'], '%H:%M').time()
        except ValueError: return _erro('"horario_abertura" inválido. Use HH:MM.')
    if 'horario_fechamento' in dados:
        try: config.horario_fechamento = datetime.strptime(dados['horario_fechamento'], '%H:%M').time()
        except ValueError: return _erro('"horario_fechamento" inválido. Use HH:MM.')
    if 'intervalo_minutos' in dados:
        iv = dados['intervalo_minutos']
        if not isinstance(iv, int) or iv < 10: return _erro('"intervalo_minutos" mínimo 10.')
        config.intervalo_minutos = iv
    if 'loja_aberta' in dados:
        config.loja_aberta = bool(dados['loja_aberta'])

    if config.horario_abertura and config.horario_fechamento:
        if config.horario_abertura >= config.horario_fechamento:
            return _erro('"horario_abertura" deve ser anterior a "horario_fechamento".')

    config.atualizado_em = datetime.utcnow()
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'edit', 'configuracao_agenda', config.id,
                         f'Configurou agenda do barbeiro #{barbeiro_id}.')
    return jsonify({
        'mensagem': 'Agenda salva.',
        'configuracao': {
            'barbeiro_id': barbeiro_id,
            'horario_abertura':   config.horario_abertura.strftime('%H:%M'),
            'horario_fechamento': config.horario_fechamento.strftime('%H:%M'),
            'intervalo_minutos':  config.intervalo_minutos,
            'loja_aberta':        config.loja_aberta,
        },
    })


# ── POST /admin/agenda/<barbeiro_id>/bloquear ──────────────────────────────────

@gestor_admin.post('/admin/agenda/<int:barbeiro_id>/bloquear')
@gestor_required
def bloquear_horario(barbeiro_id):
    barbearia_id = get_barbearia_atual()
    barbeiro = Barbeiro.query.filter_by(id=barbeiro_id, barbearia_id=barbearia_id, ativo=True).first()
    if not barbeiro: return _erro('Barbeiro não encontrado.', 404)

    dados = request.get_json(silent=True)
    if not dados: return _erro('Corpo inválido ou ausente.')

    ini_str = (dados.get('data_hora_inicio') or '').strip()
    fim_str = (dados.get('data_hora_fim')    or '').strip()
    motivo  = (dados.get('motivo') or '').strip() or None

    if not ini_str or not fim_str:
        return _erro('"data_hora_inicio" e "data_hora_fim" são obrigatórios.')
    try:
        ini = datetime.strptime(ini_str, '%Y-%m-%dT%H:%M')
        fim = datetime.strptime(fim_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        return _erro('Formato inválido. Use YYYY-MM-DDTHH:MM.')
    if fim <= ini: return _erro('"data_hora_fim" deve ser posterior a "data_hora_inicio".')

    b = HorarioBloqueado(barbearia_id=barbearia_id, barbeiro_id=barbeiro_id,
                         data_hora_inicio=ini, data_hora_fim=fim, motivo=motivo)
    db.session.add(b)
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'create', 'horario_bloqueado', b.id,
                         f'Bloqueou horário do barbeiro #{barbeiro_id}.')
    return jsonify({
        'mensagem': 'Horário bloqueado.',
        'bloqueio': {'id': b.id, 'data_hora_inicio': ini.isoformat(),
                     'data_hora_fim': fim.isoformat(), 'motivo': b.motivo},
    }), 201


# ── DELETE /admin/agendamentos/<id> ───────────────────────────────────────────

@gestor_admin.delete('/admin/agendamentos/<int:agendamento_id>')
@gestor_required
def cancelar_agendamento_gestor(agendamento_id):
    barbearia_id = get_barbearia_atual()
    ag = Agendamento.query.filter_by(id=agendamento_id, barbearia_id=barbearia_id).first()
    if not ag:
        return _erro('Agendamento não encontrado.', 404)
    if ag.status == 'cancelado':
        return _erro('Agendamento já está cancelado.')
    ag.status = 'cancelado'
    reservas = ReservaProduto.query.filter_by(agendamento_id=ag.id, status='reservado').all()
    for r in reservas:
        r.status = 'cancelado'
        prod = db.session.get(Produto, r.produto_id)
        if prod:
            prod.quantidade_reservada = max(0, (prod.quantidade_reservada or 0) - r.quantidade)
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'delete', 'agendamento', agendamento_id,
                         'Cancelou agendamento.')
    return jsonify({'mensagem': 'Agendamento cancelado.', 'id': agendamento_id})


# ── GET /admin/agenda/grade ───────────────────────────────────────────────────

@gestor_admin.get('/admin/agenda/grade')
@gestor_required
def agenda_grade():
    barbearia_id = get_barbearia_atual()
    barbeiro_id  = request.args.get('barbeiro_id', type=int)
    data_str     = request.args.get('data', '').strip()

    if not barbeiro_id:
        return _erro('"barbeiro_id" é obrigatório.')
    if not data_str:
        return _erro('"data" é obrigatório (formato: YYYY-MM-DD).')
    try:
        data_dt = datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        return _erro('Formato de data inválido. Use YYYY-MM-DD.')

    barbeiro = Barbeiro.query.filter_by(id=barbeiro_id, barbearia_id=barbearia_id, ativo=True).first()
    if not barbeiro:
        return _erro('Barbeiro não encontrado.', 404)
    usuario = db.session.get(Usuario, barbeiro.usuario_id)

    config = ConfiguracaoAgenda.query.filter_by(
        barbeiro_id=barbeiro_id, barbearia_id=barbearia_id
    ).first()
    config_data = {
        'horario_abertura':   config.horario_abertura.strftime('%H:%M'),
        'horario_fechamento': config.horario_fechamento.strftime('%H:%M'),
        'intervalo_minutos':  config.intervalo_minutos,
        'loja_aberta':        config.loja_aberta,
    } if config else None

    inicio_dia = datetime.combine(data_dt, Time(0, 0))
    fim_dia    = inicio_dia + timedelta(days=1)

    registros = (
        db.session.query(Agendamento, Cliente, Servico)
        .join(Cliente, Agendamento.cliente_id == Cliente.id)
        .join(Servico, Agendamento.servico_id  == Servico.id)
        .filter(
            Agendamento.barbearia_id == barbearia_id,
            Agendamento.barbeiro_id  == barbeiro_id,
            Agendamento.data_hora    >= inicio_dia,
            Agendamento.data_hora    <  fim_dia,
        )
        .order_by(Agendamento.data_hora)
        .all()
    )
    ag_ids = [ag.id for ag, _, _ in registros]
    at_map = {
        at.agendamento_id: at.id
        for at in Atendimento.query.filter(Atendimento.agendamento_id.in_(ag_ids)).all()
    } if ag_ids else {}

    # Serviços e produtos enriquecidos
    svs_map = defaultdict(list)
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
    pds_map = defaultdict(list)
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

    agendamentos = []
    for ag, cl, sv in registros:
        svs   = svs_map.get(ag.id) or [{'nome': sv.nome, 'quantidade': 1, 'preco_unitario': float(sv.preco), 'subtotal': float(sv.preco)}]
        pds   = pds_map.get(ag.id, [])
        total = round(sum(x['subtotal'] for x in svs) + sum(x['subtotal'] for x in pds), 2)
        agendamentos.append({
            'id':              ag.id,
            'cliente':         cl.nome,
            'telefone':        cl.telefone,
            'servico':         sv.nome,
            'servico_preco':   float(sv.preco),
            'servicos':        svs,
            'produtos':        pds,
            'total':           total,
            'data_hora':       ag.data_hora.isoformat(),
            'duracao_minutos': ag.duracao_minutos,
            'status':          ag.status,
            'atendimento_id':  at_map.get(ag.id),
            'em_atendimento':  ag.id in at_map,
        })

    servicos = [
        {'id': s.id, 'nome': s.nome, 'duracao_minutos': s.duracao_minutos, 'preco': float(s.preco)}
        for s in (
            db.session.query(Servico)
            .join(BarbeiroServico, BarbeiroServico.servico_id == Servico.id)
            .filter(
                BarbeiroServico.barbeiro_id == barbeiro_id,
                Servico.barbearia_id        == barbearia_id,
                Servico.ativo               == True,
            )
            .order_by(Servico.nome).all()
        )
    ]

    return jsonify({
        'barbeiro_id':   barbeiro_id,
        'barbeiro_nome': usuario.nome if usuario else '?',
        'config':        config_data,
        'agendamentos':  agendamentos,
        'servicos':      servicos,
    })


# ── POST /admin/agenda/agendamento-manual ──────────────────────────────────────

@gestor_admin.post('/admin/agenda/agendamento-manual')
@gestor_required
def agendamento_manual_gestor():
    barbearia_id = get_barbearia_atual()
    dados = request.get_json(silent=True)
    if not dados:
        return _erro('Corpo inválido ou ausente.')

    barbeiro_id   = dados.get('barbeiro_id')
    nome          = (dados.get('nome')      or '').strip()
    telefone_raw  = (dados.get('telefone')  or '').strip()
    servico_id    = dados.get('servico_id')
    data_hora_str = (dados.get('data_hora') or '').strip()

    if not barbeiro_id:   return _erro('"barbeiro_id" é obrigatório.')
    if not nome:          return _erro('"nome" é obrigatório.')
    if not telefone_raw:  return _erro('"telefone" é obrigatório.')
    if not servico_id:    return _erro('"servico_id" é obrigatório.')
    if not data_hora_str: return _erro('"data_hora" é obrigatório (YYYY-MM-DDTHH:MM).')

    try:
        data_hora = datetime.strptime(data_hora_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        return _erro('Formato de "data_hora" inválido. Use YYYY-MM-DDTHH:MM.')

    telefone, tel_erro = normalizar_telefone(telefone_raw)
    if tel_erro:
        return _erro(tel_erro)

    barbeiro = Barbeiro.query.filter_by(id=barbeiro_id, barbearia_id=barbearia_id, ativo=True).first()
    if not barbeiro:
        return _erro('Barbeiro não encontrado.', 404)

    if not BarbeiroServico.query.filter_by(barbeiro_id=barbeiro_id, servico_id=servico_id).first():
        return _erro('Este serviço não é oferecido pelo barbeiro selecionado.')

    servico = Servico.query.filter_by(id=servico_id, barbearia_id=barbearia_id, ativo=True).first()
    if not servico:
        return _erro('Serviço não encontrado.', 404)

    config = ConfiguracaoAgenda.query.filter_by(
        barbeiro_id=barbeiro_id, barbearia_id=barbearia_id
    ).first()
    if not config:
        return _erro('Barbeiro sem agenda configurada.')

    data_dt    = data_hora.date()
    ini_dia    = datetime.combine(data_dt, Time(0, 0))
    fim_dia    = ini_dia + timedelta(days=1)
    passo      = timedelta(minutes=config.intervalo_minutos)
    abertura   = datetime.combine(data_dt, config.horario_abertura)
    fechamento = datetime.combine(data_dt, config.horario_fechamento)

    ags_dia = Agendamento.query.filter(
        Agendamento.barbearia_id == barbearia_id,
        Agendamento.barbeiro_id  == barbeiro_id,
        Agendamento.status       == 'agendado',
        Agendamento.data_hora    >= ini_dia,
        Agendamento.data_hora    <  fim_dia,
    ).all()
    bloqueios = HorarioBloqueado.query.filter(
        HorarioBloqueado.barbearia_id    == barbearia_id,
        HorarioBloqueado.barbeiro_id     == barbeiro_id,
        HorarioBloqueado.data_hora_inicio < fim_dia,
        HorarioBloqueado.data_hora_fim   > ini_dia,
    ).all()

    cur = abertura
    slots = []
    while cur + passo <= fechamento:
        fim_slot = cur + passo
        ocupado = any(
            ag.data_hora < fim_slot
            and ag.data_hora + timedelta(minutes=ag.duracao_minutos) > cur
            for ag in ags_dia
        ) or any(bl.data_hora_inicio < fim_slot and bl.data_hora_fim > cur for bl in bloqueios)
        if not ocupado:
            slots.append(cur.strftime('%H:%M'))
        cur += passo

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

    ag = Agendamento(
        barbearia_id=barbearia_id,
        cliente_id=cliente.id,
        barbeiro_id=barbeiro_id,
        servico_id=servico_id,
        data_hora=data_hora,
        duracao_minutos=servico.duracao_minutos,
        status='agendado',
    )
    db.session.add(ag)
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'create', 'agendamento', ag.id,
                         f'Criou agendamento manual para "{cliente.nome}".')

    return jsonify({
        'mensagem': 'Agendamento criado com sucesso.',
        'agendamento': {
            'id':              ag.id,
            'cliente':         cliente.nome,
            'telefone':        cliente.telefone,
            'servico':         servico.nome,
            'data_hora':       data_hora.isoformat(),
            'duracao_minutos': ag.duracao_minutos,
            'status':          ag.status,
        },
    }), 201


# ── GET /admin/metricas ────────────────────────────────────────────────────────

@gestor_admin.get('/admin/metricas')
@gestor_required
def metricas():
    barbearia_id = get_barbearia_atual()
    hoje = date.today()
    ini_hoje = datetime.combine(hoje, Time(0, 0))
    fim_hoje = ini_hoje + timedelta(days=1)

    total_barbeiros    = Barbeiro.query.filter_by(barbearia_id=barbearia_id, ativo=True).count()
    total_servicos     = Servico.query.filter_by(barbearia_id=barbearia_id, ativo=True).count()
    total_produtos     = Produto.query.filter_by(barbearia_id=barbearia_id, ativo=True).count()
    agendamentos_hoje  = Agendamento.query.filter(
        Agendamento.barbearia_id == barbearia_id,
        Agendamento.status       == 'agendado',
        Agendamento.data_hora    >= ini_hoje,
        Agendamento.data_hora    <  fim_hoje,
    ).count()
    sol_pendentes = SolicitacaoSenha.query.filter_by(
        barbearia_id=barbearia_id, status='pendente'
    ).count()

    receita_7dias = []
    for i in range(6, -1, -1):
        dia = hoje - timedelta(days=i)
        ini = datetime.combine(dia, Time(0, 0))
        fim = ini + timedelta(days=1)
        r = db.session.query(func.sum(Atendimento.total)).filter(
            Atendimento.barbearia_id    == barbearia_id,
            Atendimento.status_operacao == 'efetuado',
            Atendimento.criado_em       >= ini,
            Atendimento.criado_em       <  fim,
        ).scalar() or 0
        receita_7dias.append({'data': dia.isoformat(), 'receita': float(r)})

    return jsonify({
        'total_barbeiros':   total_barbeiros,
        'total_servicos':    total_servicos,
        'total_produtos':    total_produtos,
        'agendamentos_hoje': agendamentos_hoje,
        'sol_pendentes':     sol_pendentes,
        'receita_7dias':     receita_7dias,
    })


# ── GET /admin/barbearia/status ──────────────────────────────────────────────

@gestor_admin.get('/admin/barbearia/status')
@gestor_required
def get_barbearia_status():
    barbearia_id = get_barbearia_atual()
    configs = ConfiguracaoAgenda.query.filter_by(barbearia_id=barbearia_id).all()
    # Aberta se pelo menos um barbeiro tem loja_aberta=True (ou sem configs → aberta)
    aberta = all(c.loja_aberta for c in configs) if configs else True
    return jsonify({'aberta': aberta})


@gestor_admin.put('/admin/barbearia/status')
@gestor_required
def set_barbearia_status():
    barbearia_id = get_barbearia_atual()
    dados  = request.get_json(silent=True) or {}
    aberta = bool(dados.get('aberta', True))
    configs = ConfiguracaoAgenda.query.filter_by(barbearia_id=barbearia_id).all()
    for c in configs:
        c.loja_aberta = aberta
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'edit', 'barbearia', barbearia_id,
                         f'Marcou barbearia como {"aberta" if aberta else "fechada"}.')
    return jsonify({'aberta': aberta, 'mensagem': f'Barbearia marcada como {"aberta" if aberta else "fechada"}.'})


# ── GET /admin/clientes ───────────────────────────────────────────────────────

@gestor_admin.get('/admin/clientes')
@gestor_required
def listar_clientes_admin():
    barbearia_id = get_barbearia_atual()
    q        = request.args.get('q', '').strip().lower()
    status   = request.args.get('status', '').lower()
    barb_id  = request.args.get('barbeiro_id', type=int)

    agora   = datetime.utcnow()
    ini_mes = datetime(agora.year, agora.month, 1)
    d7      = agora - timedelta(days=7)
    d30     = agora - timedelta(days=30)
    d60     = agora - timedelta(days=60)

    # ── Subqueries ─────────────────────────────────────────────
    vis_sq = (
        db.session.query(
            Agendamento.cliente_id,
            func.count(Agendamento.id).label('tv'),
            func.max(Agendamento.data_hora).label('uv'),
        )
        .filter(Agendamento.barbearia_id == barbearia_id, Agendamento.status == 'concluido')
        .group_by(Agendamento.cliente_id)
        .subquery()
    )
    gasto_sq = (
        db.session.query(
            Atendimento.cliente_id,
            func.sum(Atendimento.total).label('tg'),
        )
        .filter(Atendimento.barbearia_id == barbearia_id, Atendimento.status_operacao == 'efetuado')
        .group_by(Atendimento.cliente_id)
        .subquery()
    )

    # ── Busca todos os clientes ativos (uma query) ─────────────
    all_rows = (
        db.session.query(
            Cliente,
            func.coalesce(vis_sq.c.tv, 0).label('tv'),
            vis_sq.c.uv,
            func.coalesce(gasto_sq.c.tg, 0).label('tg'),
        )
        .outerjoin(vis_sq,   vis_sq.c.cliente_id   == Cliente.id)
        .outerjoin(gasto_sq, gasto_sq.c.cliente_id == Cliente.id)
        .filter(Cliente.barbearia_id == barbearia_id, Cliente.ativo == True)
        .order_by(Cliente.nome)
        .all()
    )

    def _status(uv, tg, criado_em):
        if float(tg or 0) >= 500:              return 'vip'
        if criado_em and criado_em >= d7:       return 'novo'
        if not uv or uv < d60:                  return 'em_risco'
        if uv < d30:                            return 'inativo'
        return 'ativo'

    # ── Stats globais ──────────────────────────────────────────
    total       = len(all_rows)
    novos_mes   = sum(1 for c,tv,uv,tg in all_rows if c.criado_em and c.criado_em >= ini_mes)
    inativos_n  = sum(1 for c,tv,uv,tg in all_rows if not uv or uv < d30)
    vip_n       = sum(1 for c,tv,uv,tg in all_rows if float(tg or 0) >= 500)
    total_g     = sum(float(tg or 0) for c,tv,uv,tg in all_rows)
    total_v     = sum(int(tv or 0) for c,tv,uv,tg in all_rows)
    ticket_g    = round(total_g / total_v, 2) if total_v else 0.0
    com_vis     = sum(1 for c,tv,uv,tg in all_rows if int(tv or 0) >= 1)
    retorno_n   = sum(1 for c,tv,uv,tg in all_rows if int(tv or 0) > 1)
    retencao    = round(retorno_n / com_vis * 100, 1) if com_vis else 0.0

    # ── Insights ───────────────────────────────────────────────
    em_risco  = [{'id': c.id, 'nome': c.nome, 'tel': c.telefone,
                  'dias': (agora - uv).days if uv else None}
                 for c,tv,uv,tg in all_rows if not uv or uv < d60][:6]
    follow_up = [{'id': c.id, 'nome': c.nome, 'tel': c.telefone,
                  'dias': (agora - uv).days}
                 for c,tv,uv,tg in all_rows if uv and d30 <= uv < d7][:6]
    novos_7d  = [{'id': c.id, 'nome': c.nome, 'tel': c.telefone}
                 for c,tv,uv,tg in all_rows if c.criado_em and c.criado_em >= d7][:6]
    top5      = sorted([(c,tv,uv,tg) for c,tv,uv,tg in all_rows if float(tg or 0) > 0],
                       key=lambda x: float(x[3] or 0), reverse=True)[:5]
    top5_fmt  = [{'id': c.id, 'nome': c.nome, 'gasto': float(tg), 'visitas': int(tv)}
                 for c,tv,uv,tg in top5]

    # ── Gráfico: novos clientes últimos 6 meses ────────────────
    MESES_PT = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']
    chart_novos = []
    for i in range(5, -1, -1):
        m, a = agora.month - i, agora.year
        while m <= 0:
            m += 12; a -= 1
        ini_m = datetime(a, m, 1)
        prox_m = m % 12 + 1; prox_a = a + (1 if m == 12 else 0)
        fim_m = datetime(prox_a, prox_m, 1)
        cnt = Cliente.query.filter(
            Cliente.barbearia_id == barbearia_id, Cliente.ativo == True,
            Cliente.criado_em >= ini_m, Cliente.criado_em < fim_m,
        ).count()
        chart_novos.append({'label': f'{MESES_PT[m-1]}/{str(a)[-2:]}', 'value': cnt})

    # ── Filtro em Python ───────────────────────────────────────
    rows = all_rows
    if q:
        rows = [r for r in rows if
                q in r[0].nome.lower() or
                q in (r[0].telefone or '') or
                q in (r[0].email or '').lower()]
    if status == 'inativos':
        rows = [r for r in rows if not r[2] or r[2] < d30]
    elif status == 'vip':
        rows = [r for r in rows if float(r[3] or 0) >= 500]
    elif status == 'novos':
        rows = [r for r in rows if r[0].criado_em and r[0].criado_em >= d7]
    elif status == 'em_risco':
        rows = [r for r in rows if not r[2] or r[2] < d60]

    if barb_id:
        ids_barb = {row[0] for row in
                    db.session.query(Agendamento.cliente_id)
                    .filter(Agendamento.barbearia_id == barbearia_id,
                            Agendamento.barbeiro_id == barb_id,
                            Agendamento.status == 'concluido')
                    .distinct().all()}
        rows = [r for r in rows if r[0].id in ids_barb]

    return jsonify({
        'stats': {
            'total':        total,
            'novos_mes':    novos_mes,
            'inativos_30d': inativos_n,
            'vip':          vip_n,
            'ticket_medio': ticket_g,
            'retencao_pct': retencao,
        },
        'insights': {
            'em_risco':  em_risco,
            'follow_up': follow_up,
            'novos_7d':  novos_7d,
            'top5':      top5_fmt,
        },
        'chart_novos': chart_novos,
        'clientes': [
            {
                'id':            c.id,
                'nome':          c.nome,
                'telefone':      c.telefone,
                'email':         c.email,
                'foto':          c.foto,
                'total_visitas': int(tv or 0),
                'ultima_visita': uv.isoformat() if uv else None,
                'total_gasto':   float(tg or 0),
                'ticket_medio':  round(float(tg or 0) / int(tv), 2) if int(tv or 0) > 0 else 0.0,
                'criado_em':     c.criado_em.isoformat() if c.criado_em else None,
                'status':        _status(uv, tg, c.criado_em),
            }
            for c, tv, uv, tg in rows
        ],
    })


# ── GET /admin/barbearia/tema ─────────────────────────────────────────────────

@gestor_admin.get('/admin/barbearia/tema')
@barbeiro_required
def get_barbearia_tema():
    barbearia_id = get_barbearia_atual()
    b = db.session.get(Barbearia, barbearia_id)
    if not b:
        return jsonify({'nome_exibicao': 'BarberOS', 'cor_primaria': '#BA7517', 'cor_fundo': '#1a1a1a', 'cor_card': '#2a2a2a', 'fonte': 'Inter'})
    return jsonify({
        'nome_exibicao': b.nome_exibicao or b.nome,
        'cor_primaria':  b.cor_primaria  or '#BA7517',
        'cor_fundo':     b.cor_fundo     or '#1a1a1a',
        'cor_card':      b.cor_card      or '#2a2a2a',
        'fonte':         b.fonte         or 'Inter',
    })


# ── PIX do gestor ──────────────────────────────────────────────────────────────

import re as _re

_RE_EMAIL    = _re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_RE_TELEFONE = _re.compile(r'^\+?55?\d{10,11}$')
_RE_CPF      = _re.compile(r'^\d{11}$')
_RE_CNPJ     = _re.compile(r'^\d{14}$')
_RE_ALEATORIA = _re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')


def _classificar_chave_pix(chave):
    chave = (chave or '').strip()
    digitos = re_sub_digitos(chave)
    if _RE_EMAIL.match(chave):
        return 'email'
    if _RE_ALEATORIA.match(chave):
        return 'aleatoria'
    if _RE_CNPJ.match(digitos):
        return 'cnpj'
    if _RE_CPF.match(digitos):
        return 'cpf'
    if _RE_TELEFONE.match(digitos):
        return 'telefone'
    return None


def re_sub_digitos(s):
    return _re.sub(r'\D', '', s or '')


# ── GET /admin/config-pix ──────────────────────────────────────────────────────

@gestor_admin.get('/admin/config-pix')
@gestor_required
def get_config_pix():
    barbearia_id = get_barbearia_atual()
    b = db.session.get(Barbearia, barbearia_id)
    if not b:
        return _erro('Barbearia não encontrada.', 404)
    return jsonify({
        'chave_pix':        b.chave_pix,
        'pix_nome_titular': b.pix_nome_titular,
        'pix_cidade':       b.pix_cidade,
        'pix_banco':        b.pix_banco,
    })


# ── PUT /admin/config-pix ──────────────────────────────────────────────────────

@gestor_admin.put('/admin/config-pix')
@gestor_required
def atualizar_config_pix():
    barbearia_id = get_barbearia_atual()
    b = db.session.get(Barbearia, barbearia_id)
    if not b:
        return _erro('Barbearia não encontrada.', 404)

    dados = request.get_json(silent=True) or {}
    chave_pix = (dados.get('chave_pix') or '').strip()
    nome_titular = (dados.get('nome_titular') or '').strip()
    cidade = (dados.get('cidade') or '').strip()

    if not chave_pix:
        return _erro('"chave_pix" é obrigatória.')
    if not nome_titular:
        return _erro('"nome_titular" é obrigatório.')
    if not cidade:
        return _erro('"cidade" é obrigatória.')
    if len(nome_titular) > 25:
        return _erro('"nome_titular" deve ter no máximo 25 caracteres (exigência do padrão PIX).')
    if len(cidade) > 15:
        return _erro('"cidade" deve ter no máximo 15 caracteres (exigência do padrão PIX).')
    if not _classificar_chave_pix(chave_pix):
        return _erro('Chave PIX inválida. Use e-mail, telefone, CPF, CNPJ ou chave aleatória.')

    b.chave_pix = chave_pix
    b.pix_nome_titular = nome_titular
    b.pix_cidade = cidade
    b.pix_banco = (dados.get('banco') or '').strip() or None
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'edit', 'barbearia', barbearia_id,
                         'Configurou a chave PIX da barbearia.')
    return jsonify({'mensagem': 'PIX configurado com sucesso.'})


# ── POST /admin/config-pix/testar ──────────────────────────────────────────────

@gestor_admin.post('/admin/config-pix/testar')
@gestor_required
def testar_chave_pix():
    dados = request.get_json(silent=True) or {}
    chave = (dados.get('chave_pix') or '').strip()
    if not chave:
        return _erro('"chave_pix" é obrigatória.')
    tipo = _classificar_chave_pix(chave)
    if not tipo:
        return jsonify({'valida': False, 'mensagem': 'Formato não reconhecido como e-mail, telefone, CPF, CNPJ ou chave aleatória.'})
    nomes = {'email': 'E-mail', 'telefone': 'Telefone', 'cpf': 'CPF', 'cnpj': 'CNPJ', 'aleatoria': 'Chave aleatória'}
    return jsonify({'valida': True, 'tipo': tipo, 'mensagem': f'Formato reconhecido: {nomes[tipo]}.'})


# ── GET /admin/agenda/bloqueios/mes ───────────────────────────────────────────

@gestor_admin.get('/admin/agenda/bloqueios/mes')
@gestor_required
def bloqueios_mes():
    barbearia_id = get_barbearia_atual()
    mes = request.args.get('mes', type=int)
    ano = request.args.get('ano', type=int)
    if not mes or not ano or not (1 <= mes <= 12) or ano < 2020:
        return _erro('"mes" (1-12) e "ano" são obrigatórios.')

    num_dias     = _cal.monthrange(ano, mes)[1]
    primeiro_dow = _cal.monthrange(ano, mes)[0]   # 0=Seg, 6=Dom (Python)

    ini_mes = datetime(ano, mes, 1)
    fim_mes = datetime(ano, mes, num_dias, 23, 59, 59)

    bloqueios = HorarioBloqueado.query.filter(
        HorarioBloqueado.barbearia_id    == barbearia_id,
        HorarioBloqueado.data_hora_inicio <= fim_mes,
        HorarioBloqueado.data_hora_fim   >= ini_mes,
    ).order_by(HorarioBloqueado.data_hora_inicio).all()

    por_dia = defaultdict(list)
    for bl in bloqueios:
        d_str      = bl.data_hora_inicio.date().isoformat()
        dia_inteiro = (
            bl.data_hora_inicio.hour == 0 and bl.data_hora_inicio.minute == 0
            and bl.data_hora_fim.hour == 23 and bl.data_hora_fim.minute >= 59
        )
        por_dia[d_str].append({
            'id':         bl.id,
            'barbeiro_id': bl.barbeiro_id,
            'hora_inicio': bl.data_hora_inicio.strftime('%H:%M'),
            'hora_fim':    bl.data_hora_fim.strftime('%H:%M'),
            'motivo':      bl.motivo,
            'dia_inteiro': dia_inteiro,
        })

    dias = []
    for d in range(1, num_dias + 1):
        data_str     = date(ano, mes, d).isoformat()
        todos_bl     = por_dia.get(data_str, [])
        # Deduplica por (hora_inicio, hora_fim) — evita mostrar N registros por barbeiro
        vistos, unicos = set(), []
        for b in todos_bl:
            k = (b['hora_inicio'], b['hora_fim'])
            if k not in vistos:
                vistos.add(k)
                unicos.append(b)
        dias.append({
            'dia':                   d,
            'data':                  data_str,
            'dia_semana':            date(ano, mes, d).weekday(),
            'bloqueios':             unicos,
            'tem_bloqueio':          bool(unicos),
            'dia_inteiro_bloqueado': any(b['dia_inteiro'] for b in unicos),
        })

    return jsonify({
        'mes': mes, 'ano': ano,
        'num_dias': num_dias,
        'primeiro_dia_semana': primeiro_dow,
        'dias': dias,
    })


# ── GET /admin/agenda/horarios ────────────────────────────────────────────────

@gestor_admin.get('/admin/agenda/horarios')
@gestor_required
def horarios_dia():
    barbearia_id = get_barbearia_atual()
    data_str = request.args.get('data', '').strip()
    if not data_str:
        return _erro('"data" é obrigatório (YYYY-MM-DD).')
    try:
        data_dt = datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        return _erro('Formato de data inválido. Use YYYY-MM-DD.')

    configs = ConfiguracaoAgenda.query.filter_by(barbearia_id=barbearia_id).all()
    if configs:
        abertura   = min(c.horario_abertura   for c in configs)
        fechamento = max(c.horario_fechamento  for c in configs)
        intervalo  = min(c.intervalo_minutos   for c in configs)
    else:
        abertura, fechamento, intervalo = Time(8, 0), Time(20, 0), 60

    ab_dt = datetime.combine(data_dt, abertura)
    fe_dt = datetime.combine(data_dt, fechamento)
    passo = timedelta(minutes=intervalo)

    slots = []
    cur = ab_dt
    while cur + passo <= fe_dt:
        slots.append(cur.strftime('%H:%M'))
        cur += passo

    return jsonify({'slots': slots, 'data': data_str, 'intervalo_minutos': intervalo})


# ── POST /admin/agenda/bloqueios ──────────────────────────────────────────────

@gestor_admin.post('/admin/agenda/bloqueios')
@gestor_required
def criar_bloqueio():
    barbearia_id = get_barbearia_atual()
    dados = request.get_json(silent=True)
    if not dados:
        return _erro('Corpo inválido ou ausente.')

    data_str    = (dados.get('data') or '').strip()
    hora_inicio = (dados.get('hora_inicio') or '').strip() or None
    hora_fim    = (dados.get('hora_fim')    or '').strip() or None
    dia_inteiro = bool(dados.get('dia_inteiro', False))
    tipo        = dados.get('tipo', 'pontual')    # 'pontual' | 'recorrente'
    padrao      = dados.get('padrao') or None      # 'dia_semana' | 'data_especifica'
    motivo      = (dados.get('motivo') or '').strip() or None

    if not data_str:
        return _erro('"data" é obrigatório (YYYY-MM-DD).')
    try:
        data_dt = datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        return _erro('Formato de data inválido.')

    if dia_inteiro:
        h_ini, h_fim = Time(0, 0), Time(23, 59)
    else:
        if not hora_inicio or not hora_fim:
            return _erro('"hora_inicio" e "hora_fim" são obrigatórios quando dia_inteiro=false.')
        try:
            h_ini = datetime.strptime(hora_inicio, '%H:%M').time()
            h_fim = datetime.strptime(hora_fim,    '%H:%M').time()
        except ValueError:
            return _erro('Formato de hora inválido. Use HH:MM.')
        if h_fim <= h_ini:
            return _erro('"hora_fim" deve ser posterior a "hora_inicio".')

    barbeiros = Barbeiro.query.filter_by(barbearia_id=barbearia_id, ativo=True).all()
    if not barbeiros:
        return _erro('Nenhum barbeiro ativo encontrado.')

    # Determina datas a bloquear
    if tipo == 'recorrente' and padrao in ('dia_semana', 'data_especifica'):
        datas = []
        cur   = data_dt
        fim_r = date(data_dt.year + 1, data_dt.month, data_dt.day)
        while cur <= fim_r:
            if padrao == 'dia_semana' and cur.weekday() == data_dt.weekday():
                datas.append(cur)
            elif padrao == 'data_especifica' and cur.day == data_dt.day:
                datas.append(cur)
            cur += timedelta(days=1)
    else:
        datas = [data_dt]

    criados = 0
    for d in datas:
        ini_dt = datetime.combine(d, h_ini)
        fim_dt = datetime.combine(d, h_fim)
        for b in barbeiros:
            db.session.add(HorarioBloqueado(
                barbearia_id=barbearia_id, barbeiro_id=b.id,
                data_hora_inicio=ini_dt, data_hora_fim=fim_dt, motivo=motivo,
            ))
            criados += 1

    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'create', 'horario_bloqueado', None,
                         f'{criados} bloqueio(s) de horário criado(s).')
    return jsonify({'mensagem': f'{criados} bloqueio(s) criado(s).', 'total': criados}), 201


# ── DELETE /admin/agenda/bloqueios/<id> ───────────────────────────────────────

@gestor_admin.delete('/admin/agenda/bloqueios/<int:bloqueio_id>')
@gestor_required
def remover_bloqueio(bloqueio_id):
    barbearia_id = get_barbearia_atual()
    bl = HorarioBloqueado.query.filter_by(id=bloqueio_id, barbearia_id=barbearia_id).first()
    if not bl:
        return _erro('Bloqueio não encontrado.', 404)
    # Remove todos os bloqueios de mesmo horário (de todos os barbeiros)
    ini, fim = bl.data_hora_inicio, bl.data_hora_fim
    n = HorarioBloqueado.query.filter_by(
        barbearia_id=barbearia_id,
        data_hora_inicio=ini,
        data_hora_fim=fim,
    ).delete()
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'delete', 'horario_bloqueado', bloqueio_id,
                         f'{n} bloqueio(s) de horário removido(s).')
    return jsonify({'mensagem': f'{n} bloqueio(s) removido(s).', 'total': n})


# ── GET /admin/agenda/solicitacoes-liberacao ──────────────────────────────────

@gestor_admin.get('/admin/agenda/solicitacoes-liberacao')
@gestor_required
def listar_solicitacoes_liberacao():
    barbearia_id  = get_barbearia_atual()
    status_filter = request.args.get('status', 'pendente')

    rows = (
        db.session.query(SolicitacaoLiberacao, Barbeiro, Usuario)
        .join(Barbeiro, SolicitacaoLiberacao.barbeiro_id == Barbeiro.id)
        .join(Usuario,  Barbeiro.usuario_id  == Usuario.id)
        .filter(
            SolicitacaoLiberacao.barbearia_id == barbearia_id,
            SolicitacaoLiberacao.status       == status_filter,
        )
        .order_by(SolicitacaoLiberacao.data_solicitacao.desc())
        .all()
    )

    return jsonify([
        {
            'id':              sol.id,
            'barbeiro_id':     sol.barbeiro_id,
            'barbeiro_nome':   u.nome,
            'data':            sol.data.isoformat(),
            'hora_inicio':     sol.hora_inicio.strftime('%H:%M') if sol.hora_inicio else None,
            'hora_fim':        sol.hora_fim.strftime('%H:%M')    if sol.hora_fim    else None,
            'dia_inteiro':     sol.hora_inicio is None,
            'motivo':          sol.motivo,
            'status':          sol.status,
            'data_solicitacao': sol.data_solicitacao.isoformat(),
        }
        for sol, b, u in rows
    ])


# ── PUT /admin/agenda/solicitacoes-liberacao/<id> ─────────────────────────────

@gestor_admin.put('/admin/agenda/solicitacoes-liberacao/<int:sol_id>')
@gestor_required
def responder_solicitacao_liberacao(sol_id):
    barbearia_id = get_barbearia_atual()
    sol = SolicitacaoLiberacao.query.filter_by(id=sol_id, barbearia_id=barbearia_id).first()
    if not sol:
        return _erro('Solicitação não encontrada.', 404)
    if sol.status != 'pendente':
        return _erro('Esta solicitação já foi respondida.')

    dados = request.get_json(silent=True) or {}
    novo_status = (dados.get('status') or '').strip()
    if novo_status not in ('aprovado', 'rejeitado'):
        return _erro('"status" deve ser "aprovado" ou "rejeitado".')

    sol.status       = novo_status
    sol.data_resposta = datetime.utcnow()
    sol.notificado   = False   # barbeiro ainda não viu a resposta

    if novo_status == 'aprovado':
        ini_dia = datetime.combine(sol.data, Time(0, 0))
        fim_dia = ini_dia + timedelta(days=1)

        if sol.hora_inicio and sol.hora_fim:
            ini_lib = datetime.combine(sol.data, sol.hora_inicio)
            fim_lib = datetime.combine(sol.data, sol.hora_fim)
        else:
            ini_lib, fim_lib = ini_dia, fim_dia   # dia inteiro → remove tudo

        print(f"\n[LIBERAÇÃO] sol_id={sol_id}")
        print(f"  sol.data       = {sol.data}")
        print(f"  sol.hora_inicio= {sol.hora_inicio}")
        print(f"  sol.hora_fim   = {sol.hora_fim}")
        print(f"  ini_lib        = {ini_lib}")
        print(f"  fim_lib        = {fim_lib}")

        # Bloqueios deste barbeiro que se sobrepõem ao intervalo liberado
        bls = HorarioBloqueado.query.filter(
            HorarioBloqueado.barbearia_id    == barbearia_id,
            HorarioBloqueado.barbeiro_id     == sol.barbeiro_id,
            HorarioBloqueado.data_hora_inicio <  fim_lib,
            HorarioBloqueado.data_hora_fim   >  ini_lib,
            HorarioBloqueado.data_hora_inicio >= ini_dia,
            HorarioBloqueado.data_hora_inicio <  fim_dia,
        ).all()

        print(f"  bloqueios encontrados = {len(bls)}")

        for bl in bls:
            bl_ini  = bl.data_hora_inicio
            bl_fim  = bl.data_hora_fim
            motivo  = bl.motivo

            print(f"\n  [BLOCO id={bl.id}]")
            print(f"    bl_ini = {bl_ini}  bl_fim = {bl_fim}")
            print(f"    recriar ANTES?  {bl_ini < ini_lib}  ({bl_ini} < {ini_lib})")
            print(f"    recriar DEPOIS? {bl_fim > fim_lib}  ({bl_fim} > {fim_lib})")

            db.session.delete(bl)

            if bl_ini < ini_lib:
                db.session.add(HorarioBloqueado(
                    barbearia_id=barbearia_id, barbeiro_id=sol.barbeiro_id,
                    data_hora_inicio=bl_ini, data_hora_fim=ini_lib, motivo=motivo,
                ))
                print(f"    → recriado ANTES: {bl_ini} — {ini_lib}")

            if bl_fim > fim_lib:
                db.session.add(HorarioBloqueado(
                    barbearia_id=barbearia_id, barbeiro_id=sol.barbeiro_id,
                    data_hora_inicio=fim_lib, data_hora_fim=bl_fim, motivo=motivo,
                ))
                print(f"    → recriado DEPOIS: {fim_lib} — {bl_fim}")

        print(f"[LIBERAÇÃO] commit\n")

    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'edit', 'solicitacao_liberacao', sol_id,
                         f'Solicitação de liberação {novo_status}.')
    return jsonify({'mensagem': f'Solicitação {novo_status}.', 'id': sol_id})
