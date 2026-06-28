import json
from datetime import date
from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from app import db
from app.models import (
    Usuario, Cliente, Plano, PlanoServico, Servico, Barbearia,
    ClientePlano, ClientePlanoSolicitacao, ClienteVip, VipNivel,
)
from app.routes.auth import _hash_senha, _verificar_senha
from app.routes.features import cliente_required
from app.routes.upload import _get_arquivo, _fazer_upload
from app.utils import registrar_auditoria, resetar_nivel_vip, limite_para_fora

cliente_perfil = Blueprint('cliente_perfil', __name__, url_prefix='/api/cliente')


def _erro(msg, code=400):
    return jsonify({'erro': msg}), code


def _usuario_cliente_atual():
    usuario = db.session.get(Usuario, int(get_jwt_identity()))
    return usuario, usuario.cliente if usuario else None


def _fmt_perfil(usuario, cliente):
    membro_desde = (cliente.criado_em if cliente and cliente.criado_em else usuario.criado_em)
    return {
        'nome':           usuario.nome,
        'telefone':       usuario.telefone,
        'email':          usuario.email,
        'foto':           cliente.foto if cliente else None,
        'membro_desde':   membro_desde.isoformat() if membro_desde else None,
        'notificacoes': {
            'sms':      cliente.notif_sms      if cliente else True,
            'whatsapp': cliente.notif_whatsapp if cliente else True,
            'email':    cliente.notif_email    if cliente else True,
        } if cliente else None,
    }


# ── GET /api/cliente/profile ─────────────────────────────────────────────────────

@cliente_perfil.get('/profile')
@cliente_required
def get_profile():
    usuario, cliente = _usuario_cliente_atual()
    return jsonify(_fmt_perfil(usuario, cliente)), 200


# ── PUT /api/cliente/editar ──────────────────────────────────────────────────────

@cliente_perfil.put('/editar')
@cliente_required
def editar_perfil():
    usuario, cliente = _usuario_cliente_atual()
    dados = request.get_json(silent=True) or {}

    if 'nome' in dados:
        nome = (dados['nome'] or '').strip()
        if not nome:
            return _erro('"nome" não pode ser vazio.')
        usuario.nome = nome
        if cliente:
            cliente.nome = nome
    if 'telefone' in dados:
        telefone = (dados['telefone'] or '').strip()
        if not telefone:
            return _erro('"telefone" não pode ser vazio.')
        if cliente:
            dup = Cliente.query.filter_by(barbearia_id=cliente.barbearia_id, telefone=telefone).first()
            if dup and dup.id != cliente.id:
                return _erro('Já existe um cliente com este telefone.', 409)
        usuario.telefone = telefone
        if cliente:
            cliente.telefone = telefone
    if 'email' in dados:
        email = (dados['email'] or '').strip().lower()
        if email and '@' not in email:
            return _erro('E-mail inválido.')
        if email:
            dup = Usuario.query.filter_by(email=email).first()
            if dup and dup.id != usuario.id:
                return _erro('Este e-mail já está em uso.', 409)
        usuario.email = email or None
        if cliente:
            cliente.email = email or None

    db.session.commit()
    registrar_auditoria(usuario.id, cliente.barbearia_id if cliente else usuario.barbearia_id,
                         'edit', 'cliente', cliente.id if cliente else usuario.id, 'Alterou dados do perfil.')
    return jsonify({'mensagem': 'Dados atualizados.', 'perfil': _fmt_perfil(usuario, cliente)})


# ── PUT /api/cliente/alterar-senha ───────────────────────────────────────────────

@cliente_perfil.put('/alterar-senha')
@cliente_required
def alterar_senha():
    usuario, _ = _usuario_cliente_atual()
    dados       = request.get_json(silent=True) or {}
    senha_atual = (dados.get('senha_atual') or '').strip()
    nova_senha  = (dados.get('nova_senha')  or '').strip()
    confirmar   = (dados.get('confirmar_senha') or '').strip()

    if not senha_atual:
        return _erro('"senha_atual" é obrigatório.')
    if not nova_senha or len(nova_senha) < 6:
        return _erro('"nova_senha" deve ter no mínimo 6 caracteres.')
    if confirmar and confirmar != nova_senha:
        return _erro('A confirmação de senha não corresponde à nova senha.')
    if not _verificar_senha(senha_atual, usuario.senha):
        return _erro('Senha atual incorreta.', 401)

    usuario.senha = _hash_senha(nova_senha)
    db.session.commit()
    registrar_auditoria(usuario.id, usuario.barbearia_id, 'edit', 'usuario', usuario.id, 'Alterou a própria senha.')
    return jsonify({'mensagem': 'Senha alterada com sucesso.'})


# ── DELETE /api/cliente/deletar ──────────────────────────────────────────────────

@cliente_perfil.delete('/deletar')
@cliente_required
def deletar_conta():
    usuario, cliente = _usuario_cliente_atual()
    usuario.ativo = False
    if cliente:
        cliente.ativo = False
    db.session.commit()
    registrar_auditoria(usuario.id, usuario.barbearia_id, 'delete', 'cliente',
                         cliente.id if cliente else usuario.id, f'Cliente "{usuario.nome}" deletou a própria conta.')
    return jsonify({'mensagem': 'Conta deletada com sucesso.'})


# ── PUT /api/cliente/notificacoes ────────────────────────────────────────────────

@cliente_perfil.put('/notificacoes')
@cliente_required
def atualizar_notificacoes():
    _, cliente = _usuario_cliente_atual()
    if not cliente:
        return _erro('Cadastro de cliente não encontrado para este usuário.', 404)

    dados = request.get_json(silent=True) or {}
    if 'sms' in dados:
        cliente.notif_sms = bool(dados['sms'])
    if 'whatsapp' in dados:
        cliente.notif_whatsapp = bool(dados['whatsapp'])
    if 'email' in dados:
        cliente.notif_email = bool(dados['email'])

    db.session.commit()
    return jsonify({
        'mensagem': 'Preferências de notificação atualizadas.',
        'notificacoes': {
            'sms':      cliente.notif_sms,
            'whatsapp': cliente.notif_whatsapp,
            'email':    cliente.notif_email,
        },
    })


# ── GET /api/cliente/planos-disponiveis ──────────────────────────────────────────

@cliente_perfil.get('/planos-disponiveis')
@cliente_required
def planos_disponiveis():
    _, cliente = _usuario_cliente_atual()
    if not cliente:
        return _erro('Cadastro de cliente não encontrado para este usuário.', 404)

    rows = Plano.query.filter_by(barbearia_id=cliente.barbearia_id, ativo=True).order_by(Plano.preco_mensal).all()
    resultado = []
    for p in rows:
        vinculos = PlanoServico.query.filter_by(plano_id=p.id, ativo=True).all()
        servico_ids = [v.servico_id for v in vinculos]
        servicos = {s.id: s for s in Servico.query.filter(Servico.id.in_(servico_ids)).all()} if servico_ids else {}
        clientes_usando = ClientePlano.query.filter_by(plano_id=p.id, ativo=True).count()
        resultado.append({
            'id':           p.id,
            'nome':         p.nome,
            'descricao':    p.descricao,
            'preco_mensal': float(p.preco_mensal),
            'servicos': [
                {
                    'id': v.servico_id,
                    'nome': servicos[v.servico_id].nome if v.servico_id in servicos else '—',
                    'limite_mensal': limite_para_fora(v.limite_uso_mensal),
                }
                for v in vinculos
            ],
            'clientes_usando': clientes_usando,
        })
    return jsonify(resultado)


# ── GET /api/cliente/barbearia-pix ───────────────────────────────────────────────

@cliente_perfil.get('/barbearia-pix')
@cliente_required
def barbearia_pix():
    _, cliente = _usuario_cliente_atual()
    if not cliente:
        return _erro('Cadastro de cliente não encontrado para este usuário.', 404)
    barbearia = db.session.get(Barbearia, cliente.barbearia_id)
    if not barbearia:
        return jsonify({'chave_pix': None, 'nome_barbearia': None, 'pix_copia_cola': None})

    pix_copia_cola = None
    plano_id = request.args.get('plano_id', type=int)
    if barbearia.chave_pix and plano_id:
        plano = Plano.query.filter_by(id=plano_id, barbearia_id=barbearia.id).first()
        if plano:
            from app.utils import gerar_pix_copia_cola
            try:
                pix_copia_cola = gerar_pix_copia_cola(
                    chave=barbearia.chave_pix,
                    nome_titular=barbearia.pix_nome_titular or barbearia.nome_exibicao or barbearia.nome,
                    cidade=barbearia.pix_cidade or 'BRASIL',
                    valor=plano.preco_mensal,
                    txid=f'PLANO{plano_id}',
                )
            except ValueError:
                pix_copia_cola = None

    return jsonify({
        'chave_pix':       barbearia.chave_pix,
        'nome_barbearia':  barbearia.nome_exibicao or barbearia.nome,
        'pix_copia_cola':  pix_copia_cola,
    })


# ── GET /api/cliente/tema ────────────────────────────────────────────────────────

@cliente_perfil.get('/tema')
@cliente_required
def tema_barbearia_cliente():
    _, cliente = _usuario_cliente_atual()
    if not cliente:
        return _erro('Cadastro de cliente não encontrado para este usuário.', 404)
    b = db.session.get(Barbearia, cliente.barbearia_id)
    if not b:
        return jsonify({'nome_exibicao': 'BarberOS', 'cor_primaria': '#BA7517', 'cor_fundo': '#1a1a1a', 'cor_card': '#2a2a2a', 'fonte': 'Inter', 'logo_url': None})
    return jsonify({
        'nome_exibicao': b.nome_exibicao or b.nome,
        'cor_primaria':  b.cor_primaria  or '#BA7517',
        'cor_fundo':     b.cor_fundo     or '#1a1a1a',
        'cor_card':      b.cor_card      or '#2a2a2a',
        'fonte':         b.fonte         or 'Inter',
        'logo_url':      b.logo_url,
    })


# ── POST /api/cliente/planos/<id>/solicitar (PIX — sobe comprovante) ────────────

@cliente_perfil.post('/planos/<int:plano_id>/solicitar')
@cliente_required
def solicitar_plano(plano_id):
    try:
        print(f"[DEBUG] solicitar_plano chamado — plano_id={plano_id}")

        _, cliente = _usuario_cliente_atual()
        print(f"[DEBUG] _usuario_cliente_atual() => cliente={cliente!r} (id={getattr(cliente, 'id', None)})")
        if not cliente:
            return _erro('Cadastro de cliente não encontrado para este usuário.', 404)

        plano = Plano.query.filter_by(id=plano_id, barbearia_id=cliente.barbearia_id, ativo=True).first()
        print(f"[DEBUG] Plano buscado => {plano!r} (barbeiro_id={getattr(plano, 'barbeiro_id', 'N/A')})")
        if not plano:
            return _erro('Plano não encontrado.', 404)

        pendente = ClientePlanoSolicitacao.query.filter_by(
            cliente_id=cliente.id, plano_id=plano_id, status='pendente',
        ).first()
        print(f"[DEBUG] Solicitação pendente existente => {pendente!r}")
        if pendente:
            return _erro('Você já tem uma solicitação pendente para este plano.', 409)

        metodo_pagamento = (request.form.get('metodo_pagamento') or 'pix').strip().lower()
        print(f"[DEBUG] metodo_pagamento={metodo_pagamento!r}")
        print(f"[DEBUG] request.form={dict(request.form)!r}")
        print(f"[DEBUG] request.files={dict(request.files)!r}")
        if metodo_pagamento not in ('pix', 'local'):
            return _erro('"metodo_pagamento" deve ser "pix" ou "local".')

        comprovante_url = None
        if metodo_pagamento == 'pix':
            print("[DEBUG] Chamando _get_arquivo()...")
            arq, err = _get_arquivo()
            print(f"[DEBUG] _get_arquivo() => arq={arq!r}, err={err!r}")
            if err:
                return err
            print(f"[DEBUG] Iniciando upload Cloudinary — arquivo={getattr(arq, 'filename', arq)!r}")
            try:
                comprovante_url = _fazer_upload(arq, 'barberos/comprovantes', f'cliente_{cliente.id}_plano_{plano_id}_{int(date.today().strftime("%Y%m%d"))}')
                print(f"[DEBUG] Upload concluído => comprovante_url={comprovante_url!r}")
            except RuntimeError as exc:
                print(f"[DEBUG] RuntimeError no upload: {exc}")
                return _erro(str(exc), 502)

        print(f"[DEBUG] Criando ClientePlanoSolicitacao — cliente_id={cliente.id}, plano_id={plano_id}, barbeiro_id={plano.barbeiro_id}, barbearia_id={cliente.barbearia_id}, valor={plano.preco_mensal}, metodo={metodo_pagamento}")
        solicitacao = ClientePlanoSolicitacao(
            cliente_id=cliente.id,
            plano_id=plano_id,
            barbeiro_id=plano.barbeiro_id,
            barbearia_id=cliente.barbearia_id,
            valor=plano.preco_mensal,
            comprovante_url=comprovante_url,
            metodo_pagamento=metodo_pagamento,
            status='pendente',
        )
        db.session.add(solicitacao)
        print("[DEBUG] db.session.add OK — chamando commit()...")
        db.session.commit()
        print(f"[DEBUG] commit OK => solicitacao.id={solicitacao.id}")

        print("[DEBUG] Chamando registrar_auditoria()...")
        registrar_auditoria(
            db.session.get(Usuario, int(get_jwt_identity())).id, cliente.barbearia_id,
            'create', 'plano_solicitacao', solicitacao.id,
            f'Cliente "{cliente.nome}" solicitou o plano "{plano.nome}" ({"PIX" if metodo_pagamento == "pix" else "pagamento no local"}).',
        )
        print("[DEBUG] registrar_auditoria OK — retornando 201")

        mensagem = ('Solicitação enviada. Aguarde a aprovação da barbearia.' if metodo_pagamento == 'pix'
                    else 'Solicitação registrada. Pague na barbearia para ativar seu plano.')
        return jsonify({
            'mensagem':       mensagem,
            'solicitacao_id': solicitacao.id,
            'status':         solicitacao.status,
            'metodo_pagamento': metodo_pagamento,
        }), 201

    except Exception as e:
        print(f"\n{'='*80}")
        print(f"[DEBUG] EXCECAO EM SOLICITAR_PLANO")
        print(f"{'='*80}")
        print(f"[DEBUG] Mensagem: {str(e)}")
        print(f"[DEBUG] Tipo: {type(e).__name__}")
        print(f"{'='*80}")
        import traceback
        traceback.print_exc()
        print(f"{'='*80}\n")
        db.session.rollback()
        return _erro(f"Erro interno do servidor: {str(e)}", 500)


# ── GET /api/cliente/solicitacao/<id>/status (polling) ───────────────────────────

@cliente_perfil.get('/solicitacao/<int:solicitacao_id>/status')
@cliente_required
def status_solicitacao(solicitacao_id):
    _, cliente = _usuario_cliente_atual()
    if not cliente:
        return _erro('Cadastro de cliente não encontrado para este usuário.', 404)

    sol = ClientePlanoSolicitacao.query.filter_by(id=solicitacao_id, cliente_id=cliente.id).first()
    if not sol:
        return _erro('Solicitação não encontrada.', 404)

    return jsonify({
        'status':   sol.status,
        'plano_id': sol.plano_id,
        'motivo':   sol.motivo_rejeicao,
    })


# ── DELETE /api/cliente/meu-plano (cancelar plano ativo) ─────────────────────────

@cliente_perfil.delete('/meu-plano')
@cliente_required
def cancelar_meu_plano():
    _, cliente = _usuario_cliente_atual()
    if not cliente:
        return _erro('Cadastro de cliente não encontrado para este usuário.', 404)

    cliente_plano = ClientePlano.query.filter_by(cliente_id=cliente.id, ativo=True).first()
    if not cliente_plano:
        return _erro('Você não possui um plano ativo.', 404)

    cliente_plano.ativo = False
    cliente_plano.data_fim = date.today()
    db.session.commit()

    resetar_nivel_vip(cliente.id, cliente.barbearia_id)
    registrar_auditoria(
        db.session.get(Usuario, int(get_jwt_identity())).id, cliente.barbearia_id,
        'edit', 'cliente_plano', cliente_plano.id,
        f'Cliente "{cliente.nome}" cancelou o plano.',
    )

    return jsonify({'mensagem': 'Plano cancelado. Seu nível VIP foi reiniciado.'})


# ── POST /api/cliente/resgatar-brinde ─────────────────────────────────────────────

@cliente_perfil.post('/resgatar-brinde')
@cliente_required
def resgatar_brinde():
    _, cliente = _usuario_cliente_atual()
    if not cliente:
        return _erro('Cadastro de cliente não encontrado para este usuário.', 404)

    dados = request.get_json(silent=True) or {}
    nivel = dados.get('vip_nivel')
    if not isinstance(nivel, int) or nivel < 1:
        return _erro('"vip_nivel" é obrigatório.')

    cliente_vip = ClienteVip.query.filter_by(cliente_id=cliente.id, barbearia_id=cliente.barbearia_id).first()
    if not cliente_vip or (cliente_vip.nivel_vip_atual or 0) < nivel:
        return _erro('Você ainda não atingiu este nível VIP.', 403)

    nivel_cat = VipNivel.query.filter_by(barbearia_id=cliente.barbearia_id, nivel=nivel).first()
    if not nivel_cat or not nivel_cat.ativo:
        return _erro('Este nível VIP não está configurado.', 404)
    if not nivel_cat.modo_brinde_ativo:
        return _erro('O resgate deste brinde está temporariamente desativado.', 403)

    try:
        brindes = json.loads(cliente_vip.brindes_resgatados or '[]')
    except (TypeError, ValueError):
        brindes = []
    if any(b.get('nivel') == nivel for b in brindes if isinstance(b, dict)):
        return _erro('Você já resgatou o brinde deste nível.', 409)

    brindes.append({
        'nivel': nivel,
        'nome_brinde': nivel_cat.brinde_descricao,
        'data_resgate': date.today().isoformat(),
    })
    cliente_vip.brindes_resgatados = json.dumps(brindes)
    db.session.commit()

    registrar_auditoria(
        db.session.get(Usuario, int(get_jwt_identity())).id, cliente.barbearia_id,
        'create', 'vip_brinde', cliente_vip.id,
        f'Cliente "{cliente.nome}" resgatou o brinde do nível VIP {nivel}.',
    )

    return jsonify({'mensagem': 'Brinde resgatado com sucesso!', 'brinde': nivel_cat.brinde_descricao})
