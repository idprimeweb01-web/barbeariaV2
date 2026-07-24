"""
Teste de integração — Dúvidas do Cliente / Suporte (v2: categorias,
prioridade/triagem, rastreabilidade do ciclo de vida).

Cobre (além de tudo que já era coberto na v1 — thread, imagens via proxy
assinado, badges, notificação, isolamento, export):
  - catálogo de 8 categorias + editável a qualquer momento (com evento na
    timeline própria do ticket, ClienteDuvidaEvento)
  - prioridade sugerida na abertura, reclassificável, influencia a
    ordenação da fila (urgente > alta > normal > baixa)
  - situação de 3 estados (pendente/concluida/cancelada); concluida reabre
    sozinha ao chegar mensagem nova; cancelada NUNCA reabre sozinho
  - timeline (ClienteDuvidaEvento) visível no detalhe do gestor/admin
  - direcionamento na abertura: cliente escolhe um funcionário específico
    (barbeiro só vê o que foi direcionado a ele) OU cai na fila do gestor;
    categoria 'erro' força a fila do gestor mesmo se um funcionário foi
    escolhido
  - admin (super_admin): fila cross-tenant automática, atribuir/
    desatribuir a si mesmo, filtros "meus tickets"/"não atribuídos"
  - encaminhar ao admin (flag + evento), sem alterar visibilidade (admin
    já vê tudo) — só destaque/filtro
  - CSAT opcional pós-conclusão, uma única vez
  - até 3 imagens por mensagem (rejeita a 4ª)
  - busca textual (assunto + conteúdo de mensagem) nas listagens do
    gestor e do admin
  - migrations aplicam/revertem (testado à parte via flask db
    upgrade/downgrade/upgrade antes deste script)

Cria seu(s) próprio(s) tenant(s) QA descartável — mesmo padrão dos demais
scripts deste projeto: test_client (HTTP real), limpa tudo ao final.

Uso:
    python teste_duvidas_cliente.py
"""
import os
import sys
import io
import base64

os.environ.setdefault('DISABLE_SCHEDULER', '1')
# Este script faz dezenas de logins/criações de ticket em sequência rápida a
# partir do mesmo IP (test_client) — bem mais chamadas por minuto do que um
# uso real permitiria. Afrouxa os limites default (5/min) só pra esta rodada
# de teste; lido via os.environ.get(...) na hora de registrar cada rota,
# então precisa estar setado ANTES do `from app import create_app` abaixo.
os.environ.setdefault('RL_LOGIN', '1000 per minute')
os.environ.setdefault('RL_CADASTRO', '1000 per minute')
os.environ.setdefault('RL_DUVIDA', '1000 per minute')

from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import (
    Barbearia, Usuario, Barbeiro, Cliente, FeatureMetadata, FeatureBarbearia,
    ClienteDuvida, ClienteDuvidaMensagem, Notificacao, AuditoriaLog, TokenRevogado,
)

FALHAS = []

# PNG válido 1x1 (magic bytes reais) — usado nos testes de upload correto.
_PNG_1PX = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk'
    '+A8AAQUBAScY42YAAAAASUVORK5CYII='
)


def check(nome, cond, detalhe=''):
    status = 'OK ' if cond else 'FAIL'
    print(f'[{status}] {nome}' + (f' — {detalhe}' if detalhe and not cond else ''))
    if not cond:
        FALHAS.append(nome)


def _criar_tenant(app, sufixo):
    with app.app_context():
        b = Barbearia(nome=f'QA Duvidas {sufixo}', slug=f'qa-duvidas-{sufixo}', ativo=True)
        db.session.add(b)
        db.session.flush()

        gestor = Usuario(
            barbearia_id=b.id, nome=f'QA Gestor Duvidas {sufixo}', telefone=f'1199999{sufixo}000',
            email=f'qa.gestor.duvidas{sufixo}@teste.com', senha=generate_password_hash('senha123'),
            perfil='gestor', ativo=True,
        )
        usr_barb1 = Usuario(
            barbearia_id=b.id, nome=f'QA Barbeiro1 Duvidas {sufixo}', telefone=f'1199999{sufixo}010',
            email=f'qa.barb1.duvidas{sufixo}@teste.com', senha=generate_password_hash('senha123'),
            perfil='barbeiro', ativo=True,
        )
        usr_barb2 = Usuario(
            barbearia_id=b.id, nome=f'QA Barbeiro2 Duvidas {sufixo}', telefone=f'1199999{sufixo}011',
            email=f'qa.barb2.duvidas{sufixo}@teste.com', senha=generate_password_hash('senha123'),
            perfil='barbeiro', ativo=True,
        )
        usr_cli = Usuario(
            barbearia_id=b.id, nome=f'QA Cliente Duvidas {sufixo}', telefone=f'1199999{sufixo}002',
            email=f'qa.cliente.duvidas{sufixo}@teste.com', senha=generate_password_hash('senha123'),
            perfil='cliente', ativo=True,
        )
        db.session.add_all([gestor, usr_barb1, usr_barb2, usr_cli])
        db.session.flush()

        barb1 = Barbeiro(barbearia_id=b.id, usuario_id=usr_barb1.id, ativo=True)
        barb2 = Barbeiro(barbearia_id=b.id, usuario_id=usr_barb2.id, ativo=True)
        db.session.add_all([barb1, barb2])
        cli = Cliente(barbearia_id=b.id, usuario_id=usr_cli.id, nome=usr_cli.nome, telefone=usr_cli.telefone, ativo=True)
        db.session.add(cli)

        # Espelha exatamente app.seeds.seed_feature_metadata(): cada feature
        # nasce no valor do seu ativo_por_padrao (duvidas_cliente = True).
        for fm in FeatureMetadata.query.all():
            db.session.add(FeatureBarbearia(barbearia_id=b.id, feature_id=fm.id, ativo=fm.ativo_por_padrao))

        db.session.commit()
        return {
            'barbearia_id': b.id, 'slug': b.slug,
            'gestor_email': gestor.email,
            'barb1_email': usr_barb1.email, 'barb1_id': barb1.id, 'barb1_usuario_id': usr_barb1.id,
            'barb2_email': usr_barb2.email, 'barb2_id': barb2.id, 'barb2_usuario_id': usr_barb2.id,
            'cliente_email': usr_cli.email, 'cliente_id': cli.id,
        }


def setup(app):
    ctx1 = _criar_tenant(app, '1')
    ctx2 = _criar_tenant(app, '2')  # tenant B, pra checar isolamento e fila cross-tenant do admin

    with app.app_context():
        super_qa = Usuario(
            barbearia_id=None, nome='QA Super Duvidas', telefone='11999995099',
            email='qa.super.duvidas@teste.com', senha=generate_password_hash('senha123'),
            perfil='super_admin', ativo=True,
        )
        db.session.add(super_qa)
        db.session.commit()
        ctx1['super_email'] = super_qa.email
        ctx1['super_id'] = super_qa.id

    ctx1['tenant2'] = ctx2
    return ctx1


def cleanup_tenant(app, bid):
    with app.app_context():
        duvida_ids = [d.id for d in ClienteDuvida.query.filter_by(barbearia_id=bid).all()]
        ClienteDuvidaMensagem.query.filter(ClienteDuvidaMensagem.duvida_id.in_(duvida_ids)).delete(synchronize_session=False)
        ClienteDuvida.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)  # cascade cuida de eventos/imagens
        Notificacao.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        AuditoriaLog.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        FeatureBarbearia.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Barbeiro.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Cliente.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        uids = [u.id for u in Usuario.query.filter_by(barbearia_id=bid).all()]
        TokenRevogado.query.filter(TokenRevogado.usuario_id.in_(uids)).delete(synchronize_session=False)
        Usuario.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Barbearia.query.filter_by(id=bid).delete(synchronize_session=False)
        db.session.commit()


def cleanup_super_qa(app, super_id):
    with app.app_context():
        TokenRevogado.query.filter_by(usuario_id=super_id).delete(synchronize_session=False)
        AuditoriaLog.query.filter_by(usuario_id=super_id).delete(synchronize_session=False)
        ClienteDuvida.query.filter_by(atribuido_a_usuario_id=super_id).update({'atribuido_a_usuario_id': None})
        db.session.commit()
        Usuario.query.filter_by(id=super_id).delete(synchronize_session=False)
        db.session.commit()


def _abrir(client, url, texto=None, assunto=None, categoria=None, prioridade=None, barbeiro_id=None, imagens_bytes=None):
    """POST multipart genérico pra abrir ticket (imagens_bytes: lista de bytes)."""
    data = {}
    if texto is not None: data['texto'] = texto
    if assunto is not None: data['assunto'] = assunto
    if categoria is not None: data['categoria'] = categoria
    if prioridade is not None: data['prioridade'] = prioridade
    if barbeiro_id is not None: data['barbeiro_id'] = str(barbeiro_id)
    if imagens_bytes:
        data['imagens'] = [(io.BytesIO(b), f'foto{i}.png') for i, b in enumerate(imagens_bytes)]
    return client.post(url, data=data, content_type='multipart/form-data')


def _responder(client, url, texto=None, imagens_bytes=None):
    data = {}
    if texto is not None: data['texto'] = texto
    if imagens_bytes:
        data['imagens'] = [(io.BytesIO(b), f'foto{i}.png') for i, b in enumerate(imagens_bytes)]
    return client.post(url, data=data, content_type='multipart/form-data')


def _login(client, email):
    r = client.post('/entrar', json={'email': email, 'senha': 'senha123'})
    return r


def _login_cliente(client, slug, email):
    return client.post(f'/b/{slug}/entrar', json={'email': email, 'senha': 'senha123'})


# ── Feature flag ──────────────────────────────────────────────────────────────

def testar_feature_flag(client, ctx):
    print('\n--- feature flag (admin) ---')
    _login(client, ctx['super_email'])

    r = client.get('/api/v1/super/features')
    body = r.get_json()
    check('GET /super/features -> 200 e catálogo inclui duvidas_cliente', r.status_code == 200 and 'duvidas_cliente' in body.get('catalogo', []), str(body)[:200])
    linha = next((x for x in body['barbearias'] if x['id'] == ctx['barbearia_id']), None)
    check('barbearia nasce com duvidas_cliente ATIVA (ativo_por_padrao=True)', linha is not None and linha['features'].get('duvidas_cliente') is True, str(linha))

    r = client.put(f'/api/v1/super/barbearias/{ctx["barbearia_id"]}/features/duvidas_cliente')
    check('toggle desliga -> 200', r.status_code == 200 and r.get_json()['ativo'] is False, str(r.get_json()))
    client.post('/sair')

    _login_cliente(client, ctx['slug'], ctx['cliente_email'])
    r = client.get('/api/v1/cliente/duvidas')
    check('feature desligada -> 403 pro cliente', r.status_code == 403, str(r.get_json()))
    client.post('/sair')

    _login(client, ctx['super_email'])
    r = client.put(f'/api/v1/super/barbearias/{ctx["barbearia_id"]}/features/duvidas_cliente')
    check('toggle religa -> 200 e ativo=True', r.status_code == 200 and r.get_json()['ativo'] is True, str(r.get_json()))
    client.post('/sair')


# ── Fluxo básico: abrir, responder, imagem, badges, notificação ───────────────

def testar_fluxo_basico(client, ctx):
    print('\n--- fluxo básico: abrir, responder, imagem via proxy, notificação ---')
    _login_cliente(client, ctx['slug'], ctx['cliente_email'])

    r = _abrir(client, '/api/v1/cliente/duvidas', assunto='Teste')
    check('abrir dúvida sem texto/imagem -> 422', r.status_code == 422, str(r.get_json()))

    r = _abrir(client, '/api/v1/cliente/duvidas', texto='Segue o print', imagens_bytes=[b'isso nao e uma imagem de verdade'])
    check('upload com magic bytes falsos -> 400', r.status_code == 400, str(r.get_json()))

    r = _abrir(client, '/api/v1/cliente/duvidas', assunto='Dúvida sobre pagamento', texto='Paguei mas não confirmou', imagens_bytes=[_PNG_1PX])
    check('abrir dúvida com texto+imagem -> 201', r.status_code == 201, str(r.get_json()))
    duvida_id = r.get_json()['duvida_id']

    with client.application.app_context():
        d = db.session.get(ClienteDuvida, duvida_id)
        check('nasce status=pendente', d.status == 'pendente', d.status)
        check('nasce categoria=duvida (default)', d.categoria == 'duvida', d.categoria)
        check('nasce prioridade=normal (default)', d.prioridade == 'normal', d.prioridade)
        check('nasce direcionado_para_tipo=gestor (sem escolha)', d.direcionado_para_tipo == 'gestor', d.direcionado_para_tipo)
        check('nasce nao_lida_gestor=True', d.nao_lida_gestor is True)

    r = client.get(f'/api/v1/cliente/duvidas/{duvida_id}')
    msg1 = r.get_json()['mensagens'][0]
    check('mensagem tem 1 imagem via proxy assinado (/comprovante/...)', len(msg1['imagens']) == 1 and msg1['imagens'][0].startswith('/comprovante/'), str(msg1['imagens']))

    r_img = client.get(msg1['imagens'][0])
    check('proxy serve a imagem -> 200 image/*', r_img.status_code == 200 and (r_img.content_type or '').startswith('image/'), f'{r_img.status_code} {r_img.content_type}')
    client.post('/sair')

    _login(client, ctx['gestor_email'])
    r = client.get('/api/v1/gestor/duvidas?precisa_resposta=1')
    check('gestor: precisa_resposta=1 encontra a dúvida', r.status_code == 200 and len(r.get_json()['dados']) == 1, str(r.get_json())[:200])

    r = client.get('/api/v1/gestor/dashboard')
    check('dashboard: duvidas_precisam_resposta == 1', r.get_json().get('duvidas_precisam_resposta') == 1, str(r.get_json().get('duvidas_precisam_resposta')))

    r = client.get(f'/api/v1/gestor/duvidas/{duvida_id}')
    check('gestor detalha -> 200 com timeline (lista, pode ser vazia)', r.status_code == 200 and 'timeline' in r.get_json(), str(r.get_json())[:200])

    r = _responder(client, f'/api/v1/gestor/duvidas/{duvida_id}/mensagens', texto='Já aprovamos, obrigado!')
    check('gestor responde -> 201', r.status_code == 201, str(r.get_json()))

    with client.application.app_context():
        aud = AuditoriaLog.query.filter_by(barbearia_id=ctx['barbearia_id'], entidade='cliente_duvida', entidade_id=duvida_id).all()
        check('AuditoriaLog registrado na resposta do gestor', any(a.tipo_acao == 'edit' for a in aud))
    client.post('/sair')

    _login_cliente(client, ctx['slug'], ctx['cliente_email'])
    r = client.get('/api/v1/cliente/notificacoes')
    check('cliente notificado in-app', r.get_json()['total'] >= 1, str(r.get_json())[:200])
    client.post('/sair')

    return duvida_id


# ── Categoria/prioridade/direcionamento ────────────────────────────────────────

def testar_categoria_prioridade_direcionamento(client, ctx):
    print('\n--- categoria/prioridade/direcionamento na abertura ---')
    _login_cliente(client, ctx['slug'], ctx['cliente_email'])

    # direcionado a um barbeiro específico
    r = _abrir(client, '/api/v1/cliente/duvidas', assunto='Preciso de ajuda', texto='oi', categoria='duvida', prioridade='alta', barbeiro_id=ctx['barb1_id'])
    check('abrir direcionado a barbeiro1 -> 201', r.status_code == 201, str(r.get_json()))
    id_barb1 = r.get_json()['duvida_id']
    with client.application.app_context():
        d = db.session.get(ClienteDuvida, id_barb1)
        check('direcionado_para_tipo=barbeiro', d.direcionado_para_tipo == 'barbeiro', d.direcionado_para_tipo)
        check('direcionado_para_usuario_id = usuario do barbeiro1', d.direcionado_para_usuario_id == ctx['barb1_usuario_id'])
        check('prioridade sugerida = alta', d.prioridade == 'alta', d.prioridade)

    # categoria 'erro' FORÇA fila do gestor mesmo escolhendo um barbeiro
    r = _abrir(client, '/api/v1/cliente/duvidas', assunto='Bug no app', texto='travou', categoria='erro', barbeiro_id=ctx['barb1_id'])
    check('abrir categoria=erro direcionado a barbeiro -> 201', r.status_code == 201, str(r.get_json()))
    id_erro = r.get_json()['duvida_id']
    with client.application.app_context():
        d = db.session.get(ClienteDuvida, id_erro)
        check('categoria erro FORÇA direcionado_para_tipo=gestor', d.direcionado_para_tipo == 'gestor', d.direcionado_para_tipo)
        check('categoria erro limpa direcionado_para_usuario_id', d.direcionado_para_usuario_id is None)

    # categoria inválida -> 422
    r = _abrir(client, '/api/v1/cliente/duvidas', texto='x', categoria='nao_existe')
    check('categoria inválida -> 422', r.status_code == 422, str(r.get_json()))
    r = _abrir(client, '/api/v1/cliente/duvidas', texto='x', prioridade='nao_existe')
    check('prioridade inválida -> 422', r.status_code == 422, str(r.get_json()))

    # lista de funcionários pro seletor "direcionar para"
    r = client.get('/api/v1/cliente/duvidas/funcionarios')
    check('GET funcionarios -> 200, inclui os 2 barbeiros ativos', r.status_code == 200 and len(r.get_json()) == 2, str(r.get_json()))
    client.post('/sair')

    # ── barbeiro1 vê só o dele; barbeiro2 não vê nada; gestor vê os 2 ──
    _login(client, ctx['barb1_email'])
    r = client.get('/api/v1/gestor/duvidas')
    ids_barb1 = {d['id'] for d in r.get_json()['dados']}
    check('barbeiro1 vê o ticket direcionado a ele', id_barb1 in ids_barb1, str(ids_barb1))
    check('barbeiro1 NÃO vê o ticket de erro (foi pra fila do gestor)', id_erro not in ids_barb1, str(ids_barb1))
    r = client.get(f'/api/v1/gestor/duvidas/{id_erro}')
    check('barbeiro1 tentando abrir ticket de outro (fila gestor) -> 404', r.status_code == 404, str(r.get_json()))
    client.post('/sair')

    _login(client, ctx['barb2_email'])
    r = client.get('/api/v1/gestor/duvidas')
    ids_barb2 = {d['id'] for d in r.get_json()['dados']}
    check('barbeiro2 NÃO vê o ticket direcionado ao barbeiro1', id_barb1 not in ids_barb2, str(ids_barb2))
    client.post('/sair')

    _login(client, ctx['gestor_email'])
    r = client.get('/api/v1/gestor/duvidas')
    ids_gestor = {d['id'] for d in r.get_json()['dados']}
    check('gestor vê AMBOS os tickets (sem restrição)', {id_barb1, id_erro}.issubset(ids_gestor), str(ids_gestor))

    # ── categoria editável a qualquer momento + timeline ──
    r = client.patch(f'/api/v1/gestor/duvidas/{id_barb1}/categoria', json={'categoria': 'financeiro'})
    check('PATCH categoria -> 200', r.status_code == 200 and r.get_json()['categoria'] == 'financeiro', str(r.get_json()))
    r = client.patch(f'/api/v1/gestor/duvidas/{id_barb1}/categoria', json={'categoria': 'nao_existe'})
    check('PATCH categoria inválida -> 422', r.status_code == 422)

    r = client.patch(f'/api/v1/gestor/duvidas/{id_barb1}/prioridade', json={'prioridade': 'urgente'})
    check('PATCH prioridade -> 200', r.status_code == 200 and r.get_json()['prioridade'] == 'urgente', str(r.get_json()))

    r = client.get(f'/api/v1/gestor/duvidas/{id_barb1}')
    timeline = r.get_json()['timeline']
    tipos = [e['tipo'] for e in timeline]
    check('timeline registrou categoria_alterada', 'categoria_alterada' in tipos, str(tipos))
    check('timeline registrou prioridade_alterada', 'prioridade_alterada' in tipos, str(tipos))
    ev_cat = next(e for e in timeline if e['tipo'] == 'categoria_alterada')
    check('evento categoria_alterada tem valor_anterior/novo corretos', ev_cat['valor_anterior'] == 'duvida' and ev_cat['valor_novo'] == 'financeiro', str(ev_cat))
    client.post('/sair')

    # ── ordenação por prioridade: urgente primeiro ──
    r = _login(client, ctx['gestor_email'])
    r = client.get('/api/v1/gestor/duvidas?per_page=50')
    dados = r.get_json()['dados']
    prioridades_ordem = {'urgente': 0, 'alta': 1, 'normal': 2, 'baixa': 3}
    pesos = [prioridades_ordem[d['prioridade']] for d in dados]
    check('listagem ordenada por prioridade (urgente > alta > normal > baixa)', pesos == sorted(pesos), str([d['prioridade'] for d in dados]))
    client.post('/sair')

    return id_barb1, id_erro


# ── Reabertura automática / cancelamento ────────────────────────────────────────

def testar_reabertura_e_cancelamento(client, ctx, duvida_id):
    print('\n--- reabertura automática (concluida) vs. cancelada (não reabre) ---')
    _login(client, ctx['gestor_email'])
    r = client.put(f'/api/v1/gestor/duvidas/{duvida_id}/concluir')
    check('gestor conclui -> 200', r.status_code == 200, str(r.get_json()))
    r = client.put(f'/api/v1/gestor/duvidas/{duvida_id}/concluir')
    check('concluir de novo -> 422 (já não está pendente)', r.status_code == 422)
    client.post('/sair')

    _login_cliente(client, ctx['slug'], ctx['cliente_email'])
    r = _responder(client, f'/api/v1/cliente/duvidas/{duvida_id}/mensagens', texto='Voltou a dar erro')
    check('cliente responde ticket concluído -> 201 e REABRE', r.status_code == 201, str(r.get_json()))
    with client.application.app_context():
        d = db.session.get(ClienteDuvida, duvida_id)
        check('status volta pra pendente automaticamente', d.status == 'pendente', d.status)
    client.post('/sair')

    _login(client, ctx['gestor_email'])
    r = client.get(f'/api/v1/gestor/duvidas/{duvida_id}')
    tipos = [e['tipo'] for e in r.get_json()['timeline']]
    check('timeline registrou reaberto', 'reaberto' in tipos, str(tipos))
    ev_reaberto = next(e for e in r.get_json()['timeline'] if e['tipo'] == 'reaberto')
    check('evento reaberto sem autor (ação do sistema)', ev_reaberto['autor'] is None, str(ev_reaberto))

    r = client.put(f'/api/v1/gestor/duvidas/{duvida_id}/cancelar')
    check('gestor cancela -> 200', r.status_code == 200, str(r.get_json()))
    r = client.put(f'/api/v1/gestor/duvidas/{duvida_id}/cancelar')
    check('cancelar de novo -> 422 (já cancelado)', r.status_code == 422)
    client.post('/sair')

    _login_cliente(client, ctx['slug'], ctx['cliente_email'])
    r = _responder(client, f'/api/v1/cliente/duvidas/{duvida_id}/mensagens', texto='Ainda quebrado')
    check('cliente NÃO consegue responder ticket cancelado -> 422 (não reabre sozinho)', r.status_code == 422, str(r.get_json()))
    client.post('/sair')


# ── Multi-imagem (até 3) ─────────────────────────────────────────────────────

def testar_multi_imagem(client, ctx):
    print('\n--- múltiplos anexos por mensagem (até 3) ---')
    _login_cliente(client, ctx['slug'], ctx['cliente_email'])
    r = _abrir(client, '/api/v1/cliente/duvidas', assunto='Prints', texto='seguem os prints', imagens_bytes=[_PNG_1PX, _PNG_1PX])
    check('abrir com 2 imagens -> 201', r.status_code == 201, str(r.get_json()))
    duvida_id = r.get_json()['duvida_id']

    r = client.get(f'/api/v1/cliente/duvidas/{duvida_id}')
    msg = r.get_json()['mensagens'][0]
    check('mensagem tem 2 imagens', len(msg['imagens']) == 2, str(msg['imagens']))
    check('as 2 imagens têm links de proxy distintos', len(set(msg['imagens'])) == 2, str(msg['imagens']))

    r = _responder(client, f'/api/v1/cliente/duvidas/{duvida_id}/mensagens', texto='mais um', imagens_bytes=[_PNG_1PX, _PNG_1PX, _PNG_1PX, _PNG_1PX])
    check('enviar 4 imagens -> 422 (máximo 3)', r.status_code == 422, str(r.get_json()))
    client.post('/sair')
    return duvida_id


# ── CSAT ──────────────────────────────────────────────────────────────────────

def testar_csat(client, ctx, duvida_id):
    print('\n--- CSAT opcional pós-conclusão ---')
    _login_cliente(client, ctx['slug'], ctx['cliente_email'])
    r = client.post(f'/api/v1/cliente/duvidas/{duvida_id}/satisfacao', json={'nota': 5})
    check('avaliar ticket ainda pendente -> 422', r.status_code == 422, str(r.get_json()))
    r = client.put(f'/api/v1/cliente/duvidas/{duvida_id}/fechar')
    check('cliente conclui o próprio ticket -> 200', r.status_code == 200, str(r.get_json()))

    r = client.post(f'/api/v1/cliente/duvidas/{duvida_id}/satisfacao', json={'nota': 6})
    check('nota fora do range -> 422', r.status_code == 422, str(r.get_json()))

    r = client.post(f'/api/v1/cliente/duvidas/{duvida_id}/satisfacao', json={'nota': 5, 'comentario': 'Ótimo atendimento'})
    check('avaliar concluído -> 200', r.status_code == 200, str(r.get_json()))

    r = client.post(f'/api/v1/cliente/duvidas/{duvida_id}/satisfacao', json={'nota': 3})
    check('avaliar de novo -> 422 (já avaliado)', r.status_code == 422, str(r.get_json()))
    client.post('/sair')

    _login(client, ctx['gestor_email'])
    r = client.get('/api/v1/gestor/duvidas')
    item = next(d for d in r.get_json()['dados'] if d['id'] == duvida_id)
    check('nota_satisfacao aparece na listagem do gestor', item['nota_satisfacao'] == 5, str(item))
    client.post('/sair')


# ── Busca textual ─────────────────────────────────────────────────────────────

def testar_busca_textual(client, ctx):
    print('\n--- busca textual (assunto + conteúdo de mensagem) ---')
    _login_cliente(client, ctx['slug'], ctx['cliente_email'])
    r = _abrir(client, '/api/v1/cliente/duvidas', assunto='Problema com token XYZQWERTY99', texto='nao consigo entrar')
    check('abrir ticket pra busca -> 201', r.status_code == 201)
    id_por_assunto = r.get_json()['duvida_id']

    r = _abrir(client, '/api/v1/cliente/duvidas', assunto='Outro assunto qualquer', texto='menciona a palavra ABACAXI42 no meio do texto')
    check('abrir 2º ticket pra busca (termo no corpo) -> 201', r.status_code == 201)
    id_por_conteudo = r.get_json()['duvida_id']
    client.post('/sair')

    _login(client, ctx['gestor_email'])
    r = client.get('/api/v1/gestor/duvidas?q=XYZQWERTY99')
    ids = {d['id'] for d in r.get_json()['dados']}
    check('gestor: busca por termo do ASSUNTO encontra', id_por_assunto in ids, str(ids))

    r = client.get('/api/v1/gestor/duvidas?q=ABACAXI42')
    ids = {d['id'] for d in r.get_json()['dados']}
    check('gestor: busca por termo do CONTEÚDO da mensagem encontra', id_por_conteudo in ids, str(ids))
    client.post('/sair')

    _login(client, ctx['super_email'])
    r = client.get('/api/v1/super/duvidas?q=XYZQWERTY99')
    ids = {d['id'] for d in r.get_json()['dados']}
    check('admin: busca por termo do ASSUNTO encontra (cross-tenant)', id_por_assunto in ids, str(ids))
    client.post('/sair')


# ── Encaminhar ao admin ──────────────────────────────────────────────────────

def testar_encaminhar_admin(client, ctx, duvida_id):
    print('\n--- encaminhar ao admin (flag + evento, não é portão de visibilidade) ---')
    _login(client, ctx['gestor_email'])
    r = client.put(f'/api/v1/gestor/duvidas/{duvida_id}/encaminhar-admin')
    check('gestor encaminha ao admin -> 200', r.status_code == 200, str(r.get_json()))
    r = client.get(f'/api/v1/gestor/duvidas/{duvida_id}')
    check('encaminhado_admin=True', r.get_json()['encaminhado_admin'] is True)
    tipos = [e['tipo'] for e in r.get_json()['timeline']]
    check('timeline registrou direcionado_admin', 'direcionado_admin' in tipos, str(tipos))
    client.post('/sair')

    _login(client, ctx['super_email'])
    r = client.get('/api/v1/super/duvidas?encaminhado=1')
    ids = {d['id'] for d in r.get_json()['dados']}
    check('admin: filtro encaminhado=1 encontra o ticket', duvida_id in ids, str(ids))
    client.post('/sair')


# ── Admin cross-tenant + atribuição ─────────────────────────────────────────────

def testar_admin_cross_tenant_e_atribuicao(client, ctx, id_tenant1):
    print('\n--- admin: fila cross-tenant + atribuir/desatribuir + "meus tickets" ---')
    tenant2 = ctx['tenant2']
    _login_cliente(client, tenant2['slug'], tenant2['cliente_email'])
    r = _abrir(client, '/api/v1/cliente/duvidas', assunto='Ticket do tenant 2', texto='oi do outro tenant')
    check('abrir ticket no tenant 2 -> 201', r.status_code == 201, str(r.get_json()))
    id_tenant2 = r.get_json()['duvida_id']
    client.post('/sair')

    _login(client, ctx['super_email'])
    r = client.get('/api/v1/super/duvidas?per_page=100')
    ids = {d['id'] for d in r.get_json()['dados']}
    check('admin vê ticket do tenant 1', id_tenant1 in ids, str(len(ids)))
    check('admin vê ticket do tenant 2 (cross-tenant)', id_tenant2 in ids, str(len(ids)))
    item2 = next(d for d in r.get_json()['dados'] if d['id'] == id_tenant2)
    check('card do admin mostra o nome da barbearia', item2['barbearia']['nome'] is not None, str(item2['barbearia']))

    r = client.get(f'/api/v1/super/duvidas/{id_tenant2}')
    check('admin detalha ticket de qualquer tenant -> 200', r.status_code == 200, str(r.get_json())[:200])

    r = client.put(f'/api/v1/super/duvidas/{id_tenant2}/atribuir')
    check('admin se atribui -> 200', r.status_code == 200, str(r.get_json()))

    r = client.get('/api/v1/super/duvidas?atribuido=me')
    ids_meus = {d['id'] for d in r.get_json()['dados']}
    check('filtro atribuido=me encontra o ticket atribuído', id_tenant2 in ids_meus, str(ids_meus))

    r = client.get('/api/v1/super/duvidas?atribuido=nenhum')
    ids_nenhum = {d['id'] for d in r.get_json()['dados']}
    check('filtro atribuido=nenhum NÃO inclui o ticket já atribuído', id_tenant2 not in ids_nenhum, str(ids_nenhum))

    r = _responder(client, f'/api/v1/super/duvidas/{id_tenant2}/mensagens', texto='Suporte da plataforma respondendo')
    check('admin responde -> 201', r.status_code == 201, str(r.get_json()))
    with client.application.app_context():
        m = ClienteDuvidaMensagem.query.filter_by(duvida_id=id_tenant2).order_by(ClienteDuvidaMensagem.id.desc()).first()
        check('mensagem do admin tem autor_tipo=admin', m.autor_tipo == 'admin', m.autor_tipo)

    r = client.put(f'/api/v1/super/duvidas/{id_tenant2}/desatribuir')
    check('admin desatribui -> 200', r.status_code == 200, str(r.get_json()))
    r = client.get('/api/v1/super/duvidas?atribuido=nenhum')
    ids_nenhum = {d['id'] for d in r.get_json()['dados']}
    check('após desatribuir, volta a aparecer em atribuido=nenhum', id_tenant2 in ids_nenhum, str(ids_nenhum))

    r = client.get('/api/v1/super/duvidas/excel')
    check('admin excel -> 200, xlsx', r.status_code == 200 and 'spreadsheetml' in (r.content_type or ''), f'{r.status_code} {r.content_type}')
    client.post('/sair')


# ── Isolamento (cliente terceiro / tenant terceiro) ─────────────────────────────

def testar_isolamento(client, ctx, duvida_id):
    print('\n--- isolamento: outro cliente / outro tenant -> 404 (nunca 403) ---')
    with client.application.app_context():
        outro_usr = Usuario(
            barbearia_id=ctx['barbearia_id'], nome='QA Outro Cliente', telefone='11999995777',
            email='qa.outro.cliente.duvidas@teste.com', senha=generate_password_hash('senha123'),
            perfil='cliente', ativo=True,
        )
        db.session.add(outro_usr)
        db.session.flush()
        outro_cli = Cliente(barbearia_id=ctx['barbearia_id'], usuario_id=outro_usr.id, nome=outro_usr.nome, telefone=outro_usr.telefone, ativo=True)
        db.session.add(outro_cli)
        db.session.commit()
        outro_email = outro_usr.email
        outro_usr_id = outro_usr.id

    _login_cliente(client, ctx['slug'], outro_email)
    r = client.get(f'/api/v1/cliente/duvidas/{duvida_id}')
    check('outro cliente (mesma barbearia) vendo dúvida alheia -> 404', r.status_code == 404, str(r.get_json()))
    client.post('/sair')

    with client.application.app_context():
        TokenRevogado.query.filter_by(usuario_id=outro_usr_id).delete(synchronize_session=False)
        Cliente.query.filter_by(usuario_id=outro_usr_id).delete(synchronize_session=False)
        Usuario.query.filter_by(id=outro_usr_id).delete(synchronize_session=False)
        db.session.commit()

    tenant2 = ctx['tenant2']
    _login(client, tenant2['gestor_email'])
    r = client.get(f'/api/v1/gestor/duvidas/{duvida_id}')
    check('gestor de outra barbearia vendo dúvida alheia -> 404', r.status_code == 404, str(r.get_json()))
    client.post('/sair')


# ── Listagem (filtros gerais) e excel do gestor ────────────────────────────────

def testar_listagem_filtros_e_excel(client, ctx):
    print('\n--- listagem (status/de/ate/categoria/prioridade) e export excel ---')
    _login(client, ctx['gestor_email'])

    r = client.get('/api/v1/gestor/duvidas?status=pendente')
    check('filtro status=pendente -> 200', r.status_code == 200, str(r.get_json())[:200])

    r = client.get('/api/v1/gestor/duvidas?categoria=financeiro,erro')
    check('filtro categoria multi-select -> 200', r.status_code == 200, str(r.get_json())[:200])
    r = client.get('/api/v1/gestor/duvidas?categoria=nao_existe')
    check('categoria inválida no filtro -> 422', r.status_code == 422)

    r = client.get('/api/v1/gestor/duvidas?prioridade=urgente,alta')
    check('filtro prioridade multi-select -> 200', r.status_code == 200, str(r.get_json())[:200])

    r = client.get('/api/v1/gestor/duvidas?de=2099-01-01&ate=2099-01-31')
    check('filtro de/ate fora do período -> 200, lista vazia', r.status_code == 200 and r.get_json()['total'] == 0, str(r.get_json())[:200])

    r = client.get('/api/v1/gestor/duvidas?de=2099-02-01&ate=2099-01-01')
    check('de > ate -> 422', r.status_code == 422, str(r.get_json()))

    r = client.get('/api/v1/gestor/duvidas?status=nao_existe')
    check('status inválido -> 422', r.status_code == 422, str(r.get_json()))

    r = client.get('/api/v1/gestor/duvidas/excel')
    check('export excel -> 200, xlsx', r.status_code == 200 and 'spreadsheetml' in (r.content_type or ''), f'{r.status_code} {r.content_type}')
    check('excel tem conteúdo (bytes > 0)', len(r.data) > 100, str(len(r.data)))

    client.post('/sair')


def main():
    app = create_app()
    ctx = setup(app)
    client = app.test_client()
    try:
        testar_feature_flag(client, ctx)
        duvida_id = testar_fluxo_basico(client, ctx)
        id_barb1, id_erro = testar_categoria_prioridade_direcionamento(client, ctx)
        testar_reabertura_e_cancelamento(client, ctx, duvida_id)
        csat_id = testar_multi_imagem(client, ctx)  # ticket novo, ainda pendente — reaproveitado pro fluxo de CSAT
        testar_csat(client, ctx, csat_id)
        testar_busca_textual(client, ctx)
        testar_encaminhar_admin(client, ctx, id_barb1)
        testar_admin_cross_tenant_e_atribuicao(client, ctx, id_barb1)
        testar_isolamento(client, ctx, duvida_id)
        testar_listagem_filtros_e_excel(client, ctx)
    finally:
        cleanup_tenant(app, ctx['barbearia_id'])
        cleanup_tenant(app, ctx['tenant2']['barbearia_id'])
        cleanup_super_qa(app, ctx['super_id'])

    print(f'\n{"="*60}')
    if FALHAS:
        print(f'{len(FALHAS)} FALHA(S):')
        for f in FALHAS:
            print(' -', f)
        sys.exit(1)
    else:
        print('TODOS OS TESTES PASSARAM')


if __name__ == '__main__':
    main()
