"""
Rotas públicas da barbearia, acessadas via /b/<slug>/...
Não exigem autenticação — usadas pelo cliente final para agendar.
"""
from datetime import datetime, timedelta, time as Time
from flask import Blueprint, request, jsonify
from app import db
from app.models import (
    Barbearia, Usuario, Barbeiro, Cliente, Servico, BarbeiroServico,
    ConfiguracaoAgenda, Agendamento, AgendamentoServico,
    HorarioBloqueado, Produto, ReservaProduto, BarbeariaCustomizacao,
)
from app.utils import normalizar_telefone

publica = Blueprint('publica', __name__, url_prefix='/b')


def _erro(msg, code=400):
    return jsonify({'erro': msg}), code


def _get_barbearia(slug):
    b = Barbearia.query.filter_by(slug=slug, ativo=True).first()
    if not b:
        return None, (_erro('Barbearia não encontrada.', 404))
    return b, None


def _todos_os_slots(config, data_dt, agendamentos, bloqueios):
    """Retorna (livres, ocupados) onde ocupados = [{hora, nome}]."""
    abertura   = datetime.combine(data_dt, config.horario_abertura)
    fechamento = datetime.combine(data_dt, config.horario_fechamento)
    passo      = timedelta(minutes=config.intervalo_minutos)
    livres, ocupados = [], []
    atual = abertura
    while atual + passo <= fechamento:
        fim_slot = atual + passo
        bloqueado = any(
            bl.data_hora_inicio < fim_slot and bl.data_hora_fim > atual
            for bl in bloqueios
        )
        if not bloqueado:
            ag_ocup = next((
                ag for ag in agendamentos
                if ag.data_hora < fim_slot
                and ag.data_hora + timedelta(minutes=ag.duracao_minutos) > atual
            ), None)
            hora_str = atual.strftime('%H:%M')
            if ag_ocup:
                cli = db.session.get(Cliente, ag_ocup.cliente_id)
                nome_curto = (cli.nome or '?').split()[0] if cli else '?'
                ocupados.append({'hora': hora_str, 'nome': nome_curto})
            else:
                livres.append(hora_str)
        atual += passo
    return livres, ocupados


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


# ── GET /b/<slug>/barbeiros ────────────────────────────────────────────────────

@publica.get('/<slug>/barbeiros')
def listar_barbeiros(slug):
    barbearia, err = _get_barbearia(slug)
    if err:
        return err

    registros = (
        db.session.query(Barbeiro, Usuario)
        .join(Usuario, Barbeiro.usuario_id == Usuario.id)
        .filter(
            Barbeiro.barbearia_id == barbearia.id,
            Barbeiro.ativo == True,
            Usuario.ativo  == True,
        )
        .all()
    )
    return jsonify([
        {'id': b.id, 'nome': u.nome, 'foto': b.foto, 'bio': b.bio}
        for b, u in registros
    ])


# ── GET /b/<slug>/barbeiros/<id>/servicos ──────────────────────────────────────

@publica.get('/<slug>/barbeiros/<int:barbeiro_id>/servicos')
def servicos_do_barbeiro(slug, barbeiro_id):
    barbearia, err = _get_barbearia(slug)
    if err:
        return err

    barbeiro = Barbeiro.query.filter_by(
        id=barbeiro_id, barbearia_id=barbearia.id, ativo=True
    ).first()
    if not barbeiro:
        return _erro('Barbeiro não encontrado.', 404)

    registros = (
        db.session.query(Servico)
        .join(BarbeiroServico, BarbeiroServico.servico_id == Servico.id)
        .filter(
            BarbeiroServico.barbeiro_id == barbeiro_id,
            Servico.barbearia_id == barbearia.id,
            Servico.ativo        == True,
        )
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
        for s in registros
    ])


# ── GET /b/<slug>/agenda/horarios-disponiveis ──────────────────────────────────

@publica.get('/<slug>/agenda/horarios-disponiveis')
def horarios_disponiveis(slug):
    barbearia, err = _get_barbearia(slug)
    if err:
        return err

    barbeiro_id = request.args.get('barbeiro_id', type=int)
    data_str    = request.args.get('data', '').strip()

    if not barbeiro_id:
        return _erro('Parâmetro "barbeiro_id" é obrigatório.')
    if not data_str:
        return _erro('Parâmetro "data" é obrigatório (formato: YYYY-MM-DD).')
    try:
        data_dt = datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        return _erro('Formato de data inválido. Use YYYY-MM-DD.')

    barbeiro = Barbeiro.query.filter_by(
        id=barbeiro_id, barbearia_id=barbearia.id, ativo=True
    ).first()
    if not barbeiro:
        return _erro('Barbeiro não encontrado.', 404)

    config = ConfiguracaoAgenda.query.filter_by(
        barbeiro_id=barbeiro_id, barbearia_id=barbearia.id
    ).first()
    if not config:
        return _erro('O barbeiro ainda não configurou sua agenda.')

    livres, ocupados = _todos_os_slots(
        config, data_dt,
        _agendamentos_do_dia(barbeiro_id, data_dt, barbearia.id),
        _bloqueios_do_dia(barbeiro_id, data_dt, barbearia.id),
    )
    return jsonify({
        'data':        data_str,
        'barbeiro_id': barbeiro_id,
        'horarios':    livres,
        'ocupados':    ocupados,
    })


# ── GET /b/<slug>/produtos ─────────────────────────────────────────────────────

@publica.get('/<slug>/produtos')
def listar_produtos_publico(slug):
    b, err = _get_barbearia(slug)
    if err:
        return err
    produtos = (
        Produto.query
        .filter_by(barbearia_id=b.id, ativo=True)
        .filter(Produto.quantidade_estoque > 0)
        .order_by(Produto.nome)
        .all()
    )
    return jsonify([
        {
            'id':        p.id,
            'nome':      p.nome,
            'categoria': p.categoria,
            'preco':     float(p.preco),
            'foto':      p.foto,
            'disponivel': p.quantidade_disponivel,
        }
        for p in produtos
    ])


# ── POST /b/<slug>/agendamentos ────────────────────────────────────────────────

@publica.post('/<slug>/agendamentos')
def criar_agendamento(slug):
    barbearia, err = _get_barbearia(slug)
    if err:
        return err

    dados = request.get_json(silent=True)
    if not dados:
        return _erro('Corpo da requisição inválido ou ausente.')

    nome             = (dados.get('nome')     or '').strip()
    telefone_raw     = (dados.get('telefone') or '').strip()
    email_raw        = (dados.get('email')    or '').strip().lower()
    barbeiro_id      = dados.get('barbeiro_id')
    data_hora_str    = (dados.get('data_hora') or '').strip()
    metodo_pagamento = (dados.get('metodo_pagamento') or '').strip().lower() or None

    if not nome:          return _erro('O campo "nome" é obrigatório.')
    if not telefone_raw:  return _erro('O campo "telefone" é obrigatório.')
    telefone, tel_erro = normalizar_telefone(telefone_raw)
    if tel_erro:          return _erro(tel_erro)
    if not barbeiro_id:   return _erro('O campo "barbeiro_id" é obrigatório.')
    if not data_hora_str: return _erro('O campo "data_hora" é obrigatório (YYYY-MM-DDTHH:MM).')
    if metodo_pagamento and metodo_pagamento not in ('pix', 'local'):
        return _erro('"metodo_pagamento" deve ser "pix" ou "local".')
    try:
        data_hora = datetime.strptime(data_hora_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        return _erro('Formato de "data_hora" inválido. Use YYYY-MM-DDTHH:MM.')

    barbeiro = Barbeiro.query.filter_by(
        id=barbeiro_id, barbearia_id=barbearia.id, ativo=True
    ).first()
    if not barbeiro:
        return _erro('Barbeiro não encontrado.', 404)

    config = ConfiguracaoAgenda.query.filter_by(
        barbeiro_id=barbeiro_id, barbearia_id=barbearia.id
    ).first()
    if not config:
        return _erro('O barbeiro ainda não configurou sua agenda.')

    # ── Serviços: novo formato [{id, quantidade}] ou compat servico_id ──────────
    svs_input = dados.get('servicos') or []
    if not svs_input and dados.get('servico_id'):
        svs_input = [{'id': dados['servico_id'], 'quantidade': 1}]
    if not svs_input:
        return _erro('"servicos" é obrigatório — passe [{id, quantidade}].')

    svs_validados = []   # [(Servico, quantidade)]
    duracao_total = 0
    for item in svs_input:
        sv_id = item.get('id')
        qty   = item.get('quantidade', 1)
        try:
            qty = int(qty)
        except (TypeError, ValueError):
            return _erro('Quantidade de serviço inválida.')
        if not sv_id or qty < 1:
            return _erro('Item de serviço inválido.')
        if not BarbeiroServico.query.filter_by(barbeiro_id=barbeiro_id, servico_id=sv_id).first():
            return _erro(f'Serviço {sv_id} não é oferecido por este barbeiro.')
        sv = Servico.query.filter_by(id=sv_id, barbearia_id=barbearia.id, ativo=True).first()
        if not sv:
            return _erro(f'Serviço {sv_id} não encontrado.', 404)
        svs_validados.append((sv, qty))
        duracao_total += sv.duracao_minutos * qty

    # ── Produtos: novo formato [{id, quantidade}] ou compat produtos_reservados ──
    pds_input = dados.get('produtos') or []
    if not pds_input:
        for pid in (dados.get('produtos_reservados') or []):
            pds_input.append({'id': pid, 'quantidade': 1})

    pds_validados = []   # [(Produto, quantidade)]
    for item in pds_input:
        pd_id = item.get('id')
        qty   = item.get('quantidade', 1)
        try:
            qty = int(qty)
        except (TypeError, ValueError):
            return _erro('Quantidade de produto inválida.')
        if not pd_id or qty < 1:
            return _erro('Item de produto inválido.')
        pd = Produto.query.filter_by(id=pd_id, barbearia_id=barbearia.id, ativo=True).first()
        if not pd:
            return _erro(f'Produto {pd_id} não encontrado.', 404)
        if pd.quantidade_disponivel < qty:
            return _erro(f'Produto "{pd.nome}" sem estoque disponível (disponível: {pd.quantidade_disponivel}).')
        pds_validados.append((pd, qty))

    # ── Verificar disponibilidade ──────────────────────────────────────────────
    data_dt = data_hora.date()
    livres, _ = _todos_os_slots(
        config, data_dt,
        _agendamentos_do_dia(barbeiro_id, data_dt, barbearia.id),
        _bloqueios_do_dia(barbeiro_id, data_dt, barbearia.id),
    )
    if data_hora.strftime('%H:%M') not in livres:
        return _erro(f'O horário {data_hora.strftime("%H:%M")} não está disponível.')

    # ── Criar / recuperar cliente ──────────────────────────────────────────────
    cliente = Cliente.query.filter_by(telefone=telefone, barbearia_id=barbearia.id).first()
    if not cliente:
        cliente = Cliente(nome=nome, telefone=telefone, barbearia_id=barbearia.id,
                          email=email_raw or None)
        db.session.add(cliente)
    else:
        cliente.nome  = nome
        cliente.ativo = True
        if email_raw and not cliente.email:
            cliente.email = email_raw
    db.session.flush()

    # ── Criar agendamento (servico_id = primeiro, para compat) ─────────────────
    sv_principal, _ = svs_validados[0]
    agendamento = Agendamento(
        barbearia_id=barbearia.id,
        cliente_id=cliente.id,
        barbeiro_id=barbeiro_id,
        servico_id=sv_principal.id,
        data_hora=data_hora,
        duracao_minutos=duracao_total,
        status='agendado',
        metodo_pagamento=metodo_pagamento,
    )
    db.session.add(agendamento)
    db.session.flush()

    # ── Registrar todos os serviços ────────────────────────────────────────────
    for sv, qty in svs_validados:
        db.session.add(AgendamentoServico(
            agendamento_id=agendamento.id,
            servico_id=sv.id,
            quantidade=qty,
            preco_unitario=sv.preco,
        ))

    # ── Reservar produtos ──────────────────────────────────────────────────────
    reservas_criadas = []
    for pd, qty in pds_validados:
        db.session.add(ReservaProduto(
            agendamento_id=agendamento.id,
            produto_id=pd.id,
            quantidade=qty,
            status='reservado',
        ))
        pd.quantidade_reservada = (pd.quantidade_reservada or 0) + qty
        reservas_criadas.append({'produto_id': pd.id, 'nome': pd.nome, 'quantidade': qty})

    db.session.commit()

    total = round(
        sum(float(sv.preco) * qty for sv, qty in svs_validados) +
        sum(float(pd.preco) * qty for pd, qty in pds_validados),
        2,
    )

    pix_copia_cola = None
    if metodo_pagamento == 'pix' and barbearia.chave_pix:
        from app.utils import gerar_pix_copia_cola
        try:
            pix_copia_cola = gerar_pix_copia_cola(
                chave=barbearia.chave_pix,
                nome_titular=barbearia.pix_nome_titular or barbearia.nome_exibicao or barbearia.nome,
                cidade=barbearia.pix_cidade or 'BRASIL',
                valor=total,
                txid=f'AG{agendamento.id}',
            )
        except ValueError:
            pix_copia_cola = None

    return jsonify({
        'mensagem': 'Agendamento criado com sucesso.',
        'agendamento': {
            'id':              agendamento.id,
            'cliente':         cliente.nome,
            'telefone':        cliente.telefone,
            'barbeiro_id':     barbeiro_id,
            'servicos':        [{'nome': sv.nome, 'quantidade': qty, 'preco': float(sv.preco)} for sv, qty in svs_validados],
            'produtos':        reservas_criadas,
            'data_hora':       data_hora.isoformat(),
            'duracao_minutos': duracao_total,
            'status':          agendamento.status,
            'total':           total,
            'metodo_pagamento': metodo_pagamento,
            'chave_pix':       barbearia.chave_pix if metodo_pagamento == 'pix' else None,
            'pix_copia_cola':  pix_copia_cola,
        },
    }), 201


# ── GET /b/<slug>/barbearia-info ───────────────────────────────────────────────

@publica.get('/<slug>/barbearia-info')
def barbearia_info(slug):
    b, err = _get_barbearia(slug)
    if err:
        return err
    cust = BarbeariaCustomizacao.query.filter_by(barbearia_id=b.id).first()
    return jsonify({
        'id':                b.id,
        'nome':              b.nome,
        'slug':              b.slug,
        'cor_primaria':      (cust.cor_primaria if cust else None)   or b.cor_primaria or '#BA7517',
        'cor_fundo':         (cust.cor_secundaria if cust else None) or b.cor_fundo    or '#1a1a1a',
        'cor_card':          b.cor_card or '#2a2a2a',
        'cor_acentuacao':    (cust.cor_acentuacao if cust else None) or '#FFD700',
        'texto_primario':    (cust.texto_primario if cust else None) or '#FFFFFF',
        'texto_secundario':  (cust.texto_secundario if cust else None) or '#CCCCCC',
        'texto_terciario':   (cust.texto_terciario if cust else None) or '#888888',
        'botao_primario':    (cust.botao_primario if cust else None) or (cust.cor_primaria if cust else None) or b.cor_primaria or '#BA7517',
        'botao_secundario':  (cust.botao_secundario if cust else None) or '#555555',
        'logo_url':          b.logo_url,
        'fonte':             (cust.fonte if cust else None) or b.fonte or 'Inter',
        'chave_pix':         b.chave_pix,
    })


# ── GET /b/<slug>/servicos ─────────────────────────────────────────────────────

@publica.get('/<slug>/servicos')
def listar_servicos_publico(slug):
    b, err = _get_barbearia(slug)
    if err:
        return err
    servicos = Servico.query.filter_by(barbearia_id=b.id, ativo=True).order_by(Servico.nome).all()
    return jsonify([
        {
            'id':              s.id,
            'nome':            s.nome,
            'descricao':       s.descricao,
            'preco':           float(s.preco),
            'duracao_minutos': s.duracao_minutos,
        }
        for s in servicos
    ])


# ── GET /b/<slug>/agendamento/<id> ─────────────────────────────────────────────

@publica.get('/<slug>/agendamento/<int:ag_id>')
def agendamento_publico(slug, ag_id):
    b, err = _get_barbearia(slug)
    if err:
        return err
    ag = Agendamento.query.filter_by(id=ag_id, barbearia_id=b.id).first()
    if not ag:
        return _erro('Agendamento não encontrado.', 404)

    cli    = db.session.get(Cliente,  ag.cliente_id)
    barb   = db.session.get(Barbeiro, ag.barbeiro_id)
    barb_u = db.session.get(Usuario,  barb.usuario_id) if barb else None

    # Todos os serviços via AgendamentoServico
    ag_svs = AgendamentoServico.query.filter_by(agendamento_id=ag.id).all()
    svs_fmt = []
    total_svs = 0.0
    for ag_sv in ag_svs:
        sv = db.session.get(Servico, ag_sv.servico_id)
        subtotal = float(ag_sv.preco_unitario) * ag_sv.quantidade
        svs_fmt.append({
            'nome':          sv.nome if sv else '—',
            'quantidade':    ag_sv.quantidade,
            'preco_unitario': float(ag_sv.preco_unitario),
            'subtotal':      round(subtotal, 2),
        })
        total_svs += subtotal

    # Fallback para agendamentos sem AgendamentoServico (formato antigo)
    if not svs_fmt and ag.servico_id:
        sv = db.session.get(Servico, ag.servico_id)
        if sv:
            svs_fmt = [{'nome': sv.nome, 'quantidade': 1,
                        'preco_unitario': float(sv.preco), 'subtotal': float(sv.preco)}]
            total_svs = float(sv.preco)

    # Todos os produtos via ReservaProduto
    reservas = ReservaProduto.query.filter(
        ReservaProduto.agendamento_id == ag.id,
        ReservaProduto.status != 'cancelado',
    ).all()
    pds_fmt = []
    total_pds = 0.0
    for rp in reservas:
        pd = db.session.get(Produto, rp.produto_id)
        preco = float(pd.preco) if pd else 0.0
        subtotal = preco * rp.quantidade
        pds_fmt.append({
            'nome':          pd.nome if pd else '—',
            'quantidade':    rp.quantidade,
            'preco_unitario': preco,
            'subtotal':      round(subtotal, 2),
        })
        total_pds += subtotal

    total = round(total_svs + total_pds, 2)
    sv_principal = svs_fmt[0] if svs_fmt else {'nome': '—', 'preco': 0}

    pix_copia_cola = None
    if ag.metodo_pagamento == 'pix' and b.chave_pix:
        from app.utils import gerar_pix_copia_cola
        try:
            pix_copia_cola = gerar_pix_copia_cola(
                chave=b.chave_pix,
                nome_titular=b.pix_nome_titular or b.nome_exibicao or b.nome,
                cidade=b.pix_cidade or 'BRASIL',
                valor=total,
                txid=f'AG{ag.id}',
            )
        except ValueError:
            pix_copia_cola = None

    return jsonify({
        'id':              ag.id,
        'data_hora':       ag.data_hora.isoformat(),
        'duracao_minutos': ag.duracao_minutos,
        'status':          ag.status,
        'metodo_pagamento': ag.metodo_pagamento,
        'chave_pix':       b.chave_pix if ag.metodo_pagamento == 'pix' else None,
        'pix_copia_cola':  pix_copia_cola,
        'barbeiro': {
            'nome': barb_u.nome if barb_u else '—',
            'foto': barb.foto   if barb   else None,
        },
        'servicos': svs_fmt,
        'produtos': pds_fmt,
        'total':    total,
        # compat com versão anterior
        'servico':  sv_principal,
        'cliente':  {'nome': cli.nome if cli else '—'},
        'barbearia': {'nome': b.nome},
    })
