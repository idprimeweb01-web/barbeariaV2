"""
Teste de integração — v1.2 (PDV/Caixa, VIP leveling, reset de senha).

Cria seu próprio tenant QA descartável, exercita os endpoints via test_client
(HTTP real, não chamada direta de função) cobrindo caminho feliz, bordas e
erros, e apaga tudo ao final — mesmo padrão de medir_queries.py/teste_concorrencia.py.

Uso:
    python teste_v1_2_pdv_vip_reset.py
"""
import os
import sys
from datetime import time as time_cls, date, timedelta

os.environ.setdefault('DISABLE_SCHEDULER', '1')

from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import (
    Barbearia, Usuario, Barbeiro, Cliente, Servico, Produto,
    Plano, PlanoServico, ClientePlanoSolicitacao, ClientePlano,
    FeatureMetadata, FeatureBarbearia, ClienteVip, ClienteVipHistorico,
    VipNivel, BarbeiroCaixa, ItemCaixa, SolicitacaoSenha, Notificacao,
)

FALHAS = []


def check(nome, cond, detalhe=''):
    status = 'OK ' if cond else 'FAIL'
    print(f'[{status}] {nome}' + (f' — {detalhe}' if detalhe and not cond else ''))
    if not cond:
        FALHAS.append(nome)


def setup(app):
    with app.app_context():
        b = Barbearia(nome='QA v1.2', slug='qa-v1-2', ativo=True)
        db.session.add(b)
        db.session.flush()

        gestor = Usuario(barbearia_id=b.id, nome='QA Gestor', telefone='11999992000',
                          email='qa.gestor.v12@teste.com', senha=generate_password_hash('senha123'),
                          perfil='gestor', ativo=True)
        usr_barb1 = Usuario(barbearia_id=b.id, nome='QA Barbeiro 1', telefone='11999992001',
                             perfil='barbeiro', ativo=True, senha=generate_password_hash('senha123'))
        usr_barb2 = Usuario(barbearia_id=b.id, nome='QA Barbeiro 2', telefone='11999992002',
                             perfil='barbeiro', ativo=True, senha=generate_password_hash('senha123'))
        usr_cli = Usuario(barbearia_id=b.id, nome='QA Cliente', telefone='11999992003',
                           email='qa.cliente.v12@teste.com',
                           perfil='cliente', ativo=True, senha=generate_password_hash('senha123'))
        usr_cli2 = Usuario(barbearia_id=b.id, nome='QA Cliente 2', telefone='11999992004',
                            email='qa.cliente2.v12@teste.com',
                            perfil='cliente', ativo=True, senha=generate_password_hash('senha123'))
        db.session.add_all([gestor, usr_barb1, usr_barb2, usr_cli, usr_cli2])
        db.session.flush()

        barb1 = Barbeiro(barbearia_id=b.id, usuario_id=usr_barb1.id, ativo=True)
        barb2 = Barbeiro(barbearia_id=b.id, usuario_id=usr_barb2.id, ativo=True)
        db.session.add_all([barb1, barb2])
        db.session.flush()

        cli = Cliente(barbearia_id=b.id, usuario_id=usr_cli.id, nome='QA Cliente',
                       telefone='11999992003', ativo=True)
        cli2 = Cliente(barbearia_id=b.id, usuario_id=usr_cli2.id, nome='QA Cliente 2',
                        telefone='11999992004', ativo=True)
        db.session.add_all([cli, cli2])
        db.session.flush()

        produto = Produto(barbearia_id=b.id, nome='Pomada QA', preco=20, custo_unitario=10,
                           quantidade_estoque=5, ativo=True)
        db.session.add(produto)

        servico = Servico(barbearia_id=b.id, nome='Corte QA', preco=30, duracao_minutos=30, ativo=True)
        db.session.add(servico)
        db.session.flush()

        plano = Plano(barbearia_id=b.id, nome='Plano QA', preco_mensal=50, ativo=True)
        db.session.add(plano)
        db.session.flush()
        db.session.add(PlanoServico(plano_id=plano.id, servico_id=servico.id,
                                     limite_uso_mensal=99999, dias_expiracao=30, ativo=True))

        plano_limitado = Plano(barbearia_id=b.id, nome='Plano QA Limitado', preco_mensal=80,
                                ativo=True, max_assinaturas=1)
        db.session.add(plano_limitado)
        db.session.flush()
        db.session.add(PlanoServico(plano_id=plano_limitado.id, servico_id=servico.id,
                                     limite_uso_mensal=99999, dias_expiracao=30, ativo=True))

        # Habilita as features que os fluxos exigem — bypassando criar_barbearia(),
        # que faria isso via ativo_por_padrao/SegmentoFeaturePadrao.
        for nome_feature in ('produtos_venda', 'vip_brindes'):
            fm = FeatureMetadata.query.filter_by(nome=nome_feature).first()
            if fm:
                db.session.add(FeatureBarbearia(barbearia_id=b.id, feature_id=fm.id, ativo=True))

        db.session.commit()
        return {
            'barbearia_id': b.id, 'slug': b.slug,
            'gestor_email': gestor.email, 'gestor_id': gestor.id,
            'barb1_id': barb1.id, 'barb2_id': barb2.id,
            'cliente_id': cli.id, 'cliente_usuario_id': usr_cli.id,
            'cliente2_id': cli2.id, 'cliente2_email': usr_cli2.email,
            'produto_id': produto.id, 'plano_id': plano.id,
            'plano_limitado_id': plano_limitado.id,
        }


def cleanup(app, bid):
    with app.app_context():
        from app.models import MovimentacaoEstoque
        MovimentacaoEstoque.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        ItemCaixa.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        BarbeiroCaixa.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        ClienteVipHistorico.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        ClienteVip.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        VipNivel.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Notificacao.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        ClientePlano.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        ClientePlanoSolicitacao.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        PlanoServico.query.filter(PlanoServico.plano_id.in_(
            db.session.query(Plano.id).filter_by(barbearia_id=bid)
        )).delete(synchronize_session=False)
        Plano.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Servico.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Produto.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        FeatureBarbearia.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        uids = [u.id for u in Usuario.query.filter_by(barbearia_id=bid).all()]
        from app.models import TokenRevogado, AuditoriaLog
        TokenRevogado.query.filter(TokenRevogado.usuario_id.in_(uids)).delete(synchronize_session=False)
        AuditoriaLog.query.filter(AuditoriaLog.usuario_id.in_(uids)).delete(synchronize_session=False)
        SolicitacaoSenha.query.filter(SolicitacaoSenha.usuario_id.in_(uids)).delete(synchronize_session=False)
        Barbeiro.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Cliente.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Usuario.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        # notificações pro super_admin (hierarquia de reset de senha) não têm
        # barbearia_id deste tenant — limpa por tipo pra não sujar o banco real
        Notificacao.query.filter_by(tipo='reset_senha').filter(
            Notificacao.corpo.like('%QA%')
        ).delete(synchronize_session=False)
        Barbearia.query.filter_by(id=bid).delete(synchronize_session=False)
        db.session.commit()


def testar_pdv_caixa(client, ctx):
    print('\n--- PDV/Caixa ---')
    r = client.post('/entrar', json={'email': ctx['barb1_email'], 'senha': 'senha123'})
    check('login barbeiro 1', r.status_code == 200, str(r.get_json()))

    r = client.get('/api/v1/barbeiro/caixa')
    check('GET caixa antes de abrir -> null', r.status_code == 200 and r.get_json() is None)

    r = client.post('/api/v1/barbeiro/caixa')
    check('POST abrir caixa -> 201', r.status_code == 201, str(r.get_json()))
    caixa_id = r.get_json()['id']

    r2 = client.post('/api/v1/barbeiro/caixa')
    check('POST abrir caixa de novo -> 200 (idempotente)', r2.status_code == 200 and r2.get_json()['id'] == caixa_id)

    r = client.post(f'/api/v1/barbeiro/caixa/{caixa_id}/itens', json={
        'produto_id': ctx['produto_id'], 'quantidade': 2, 'desconto_percentual': 10,
        'forma_pagamento': 'pix',
    })
    check('POST item valido -> 201', r.status_code == 201, str(r.get_json()))
    body = r.get_json()
    check('total do item calculado certo (2*20 - 10% = 36.0)', abs(body['total'] - 36.0) < 0.01, str(body['total']))
    item_id = body['itens'][0]['id']

    r = client.post(f'/api/v1/barbeiro/caixa/{caixa_id}/itens', json={
        'produto_id': ctx['produto_id'], 'quantidade': 999, 'forma_pagamento': 'pix',
    })
    check('POST item com estoque insuficiente -> 422', r.status_code == 422, str(r.get_json()))

    r = client.post(f'/api/v1/barbeiro/caixa/{caixa_id}/itens', json={
        'produto_id': ctx['produto_id'], 'quantidade': 1, 'forma_pagamento': 'boleto',
    })
    check('POST item com forma_pagamento invalida -> 422', r.status_code == 422, str(r.get_json()))

    r = client.delete(f'/api/v1/barbeiro/caixa/itens/{item_id}')
    check('DELETE item -> 200', r.status_code == 200, str(r.get_json()))

    with client.application.app_context():
        produto = db.session.get(Produto, ctx['produto_id'])
        check('estoque voltou ao original apos remover item', produto.quantidade_estoque == 5, str(produto.quantidade_estoque))

    r = client.patch(f'/api/v1/barbeiro/caixa/{caixa_id}/fechar')
    check('PATCH fechar caixa -> 200', r.status_code == 200, str(r.get_json()))

    r = client.post(f'/api/v1/barbeiro/caixa/{caixa_id}/itens', json={
        'produto_id': ctx['produto_id'], 'quantidade': 1, 'forma_pagamento': 'pix',
    })
    check('POST item em caixa fechada -> 422', r.status_code == 422, str(r.get_json()))

    r = client.post('/sair')

    r = client.post('/entrar', json={'email': ctx['barb2_email'], 'senha': 'senha123'})
    check('login barbeiro 2', r.status_code == 200)
    r = client.get(f'/api/v1/barbeiro/caixa?data={date.today().isoformat()}')
    # barbeiro 2 não tem caixa própria hoje -> None, não a do barbeiro 1
    check('GET caixa do barbeiro 2 nao ve a do barbeiro 1', r.status_code == 200 and r.get_json() is None)
    r = client.patch(f'/api/v1/barbeiro/caixa/{caixa_id}/fechar')
    check('barbeiro 2 tentando fechar caixa do barbeiro 1 -> 404 (nao 403, nao revela)', r.status_code == 404, str(r.get_json()))
    client.post('/sair')


def testar_vip(client, ctx):
    print('\n--- VIP (niveis + leveling) ---')
    r = client.post('/entrar', json={'email': ctx['gestor_email'], 'senha': 'senha123'})
    check('login gestor', r.status_code == 200, str(r.get_json()))

    r = client.get('/api/v1/gestor/vip/niveis')
    check('GET niveis vazio no inicio', r.status_code == 200 and r.get_json() == [])

    r = client.post('/api/v1/gestor/vip/niveis', json={
        'nivel': 1, 'brinde_descricao': 'Corte gratis', 'tipo_brinde': 'fisico',
        'brindes': [{'name': 'Corte gratis', 'description': 'Um corte por mes'},
                    {'name': 'Bebida', 'description': 'Cafe ou agua'}],
    })
    check('POST nivel 1 com brindes estruturados -> 201', r.status_code == 201, str(r.get_json()))
    nivel1_id = r.get_json()['nivel']['id']
    check('brindes voltam na resposta com 2 itens', len(r.get_json()['nivel']['brindes']) == 2, str(r.get_json()))

    r = client.post('/api/v1/gestor/vip/niveis', json={
        'nivel': 99, 'brinde_descricao': 'invalido', 'tipo_brinde': 'fisico',
        'brindes': [{'description': 'sem nome'}],
    })
    check('POST nivel com brinde sem "name" -> 400', r.status_code == 400, str(r.get_json()))
    r = client.get('/api/v1/gestor/vip/niveis')
    check('nivel 99 invalido nao foi criado', all(n['nivel'] != 99 for n in r.get_json()))

    r = client.put(f'/api/v1/gestor/vip/niveis/{nivel1_id}', json={
        'brindes': [{'name': 'Corte + barba gratis', 'description': 'Atualizado'}],
    })
    check('PUT editar brindes -> 200', r.status_code == 200, str(r.get_json()))
    check('brindes atualizados tem 1 item', len(r.get_json()['nivel']['brindes']) == 1, str(r.get_json()))

    r = client.post('/api/v1/gestor/vip/niveis', json={
        'nivel': 2, 'brinde_descricao': '10% desconto', 'tipo_brinde': 'desconto', 'valor_desconto': 10,
    })
    check('POST nivel 2 -> 201', r.status_code == 201, str(r.get_json()))

    with client.application.app_context():
        sol1 = ClientePlanoSolicitacao(barbearia_id=ctx['barbearia_id'], cliente_id=ctx['cliente_id'],
                                        plano_id=ctx['plano_id'], valor=50, metodo_pagamento='local', status='pendente')
        db.session.add(sol1)
        db.session.commit()
        sol1_id = sol1.id

    r = client.put(f'/api/v1/gestor/planos/solicitacoes/{sol1_id}/aprovar')
    check('PUT aprovar solicitacao 1 -> 200', r.status_code == 200, str(r.get_json()))

    with client.application.app_context():
        cv = ClienteVip.query.filter_by(cliente_id=ctx['cliente_id'], barbearia_id=ctx['barbearia_id']).first()
        check('nivel VIP sobe pra 1 apos 1a aprovacao', cv is not None and cv.nivel_vip_atual == 1,
              str(cv.nivel_vip_atual if cv else None))

    with client.application.app_context():
        sol2 = ClientePlanoSolicitacao(barbearia_id=ctx['barbearia_id'], cliente_id=ctx['cliente_id'],
                                        plano_id=ctx['plano_id'], valor=50, metodo_pagamento='local', status='pendente')
        db.session.add(sol2)
        db.session.commit()
        sol2_id = sol2.id

    r = client.put(f'/api/v1/gestor/planos/solicitacoes/{sol2_id}/aprovar')
    check('PUT aprovar solicitacao 2 -> 200', r.status_code == 200, str(r.get_json()))

    with client.application.app_context():
        cv = ClienteVip.query.filter_by(cliente_id=ctx['cliente_id'], barbearia_id=ctx['barbearia_id']).first()
        check('nivel VIP sobe pra 2 apos 2a aprovacao (mes consecutivo)', cv.nivel_vip_atual == 2, str(cv.nivel_vip_atual))

    r = client.get('/api/v1/gestor/vip/clientes')
    check('GET clientes VIP lista o cliente', r.status_code == 200 and r.get_json()['total'] == 1, str(r.get_json()))

    r = client.get(f'/api/v1/gestor/vip/clientes/{ctx["cliente_id"]}/historico')
    hist = r.get_json()
    check('GET historico tem 2 eventos UPGRADE', r.status_code == 200 and hist['total'] == 2, str(hist))

    client.post('/sair')

    # cliente cancela a assinatura mais recente
    r = client.post(f'/b/{ctx["slug"]}/entrar', json={'email': 'qa.cliente.v12@teste.com', 'senha': 'senha123'})
    check('login cliente', r.status_code == 200, str(r.get_json()))

    with client.application.app_context():
        cp = ClientePlano.query.filter_by(cliente_id=ctx['cliente_id'], ativo=True).first()
        cp_id = cp.id if cp else None
    check('existe ClientePlano ativo pra cancelar', cp_id is not None)

    r = client.post(f'/api/v1/cliente/planos/{cp_id}/cancelar')
    check('POST cancelar assinatura -> 200', r.status_code == 200, str(r.get_json()))

    with client.application.app_context():
        cv = ClienteVip.query.filter_by(cliente_id=ctx['cliente_id'], barbearia_id=ctx['barbearia_id']).first()
        check('janela de tolerancia aberta apos cancelamento', cv.data_proxima_renovacao is not None)
        check('nivel VIP preservado durante a janela', cv.nivel_vip_atual == 2, str(cv.nivel_vip_atual))

    client.post('/sair')

    # simula a janela ja ter fechado (fura a data pro passado) e roda a varredura direto
    with client.application.app_context():
        from app.utils.scheduler import _varrer_vencimento_vip
        cv = ClienteVip.query.filter_by(cliente_id=ctx['cliente_id'], barbearia_id=ctx['barbearia_id']).first()
        cv.data_proxima_renovacao = date.today() - timedelta(days=1)
        db.session.commit()
        _varrer_vencimento_vip()
        db.session.refresh(cv)
        check('varredura de vencimento reseta nivel pra 0 apos janela fechada', cv.nivel_vip_atual == 0, str(cv.nivel_vip_atual))
        check('data_proxima_renovacao limpa apos reset', cv.data_proxima_renovacao is None)
        n_downgrade = ClienteVipHistorico.query.filter_by(
            cliente_id=ctx['cliente_id'], barbearia_id=ctx['barbearia_id'], evento_tipo='DOWNGRADE'
        ).count()
        check('historico registrou o DOWNGRADE', n_downgrade == 1, str(n_downgrade))


def testar_limite_plano(client, ctx):
    print('\n--- Limite de clientes por plano (max_assinaturas) ---')

    r = client.post(f'/b/{ctx["slug"]}/entrar', json={'email': 'qa.cliente.v12@teste.com', 'senha': 'senha123'})
    check('login cliente 1', r.status_code == 200)
    r = client.post(f'/api/v1/pub/{ctx["slug"]}/planos/{ctx["plano_limitado_id"]}/solicitar', json={'metodo_pagamento': 'local'})
    check('cliente 1 solicita plano limitado (vaga livre) -> 201', r.status_code == 201, str(r.get_json()))
    sol1_id = r.get_json()['solicitacao_id']
    client.post('/sair')

    r = client.post(f'/b/{ctx["slug"]}/entrar', json={'email': ctx['cliente2_email'], 'senha': 'senha123'})
    check('login cliente 2', r.status_code == 200)
    r = client.post(f'/api/v1/pub/{ctx["slug"]}/planos/{ctx["plano_limitado_id"]}/solicitar', json={'metodo_pagamento': 'local'})
    check('cliente 2 solicita plano limitado (ainda 0 ativos) -> 201', r.status_code == 201, str(r.get_json()))
    sol2_id = r.get_json()['solicitacao_id']
    client.post('/sair')

    r = client.post('/entrar', json={'email': ctx['gestor_email'], 'senha': 'senha123'})
    check('login gestor', r.status_code == 200)

    r = client.put(f'/api/v1/gestor/planos/solicitacoes/{sol1_id}/aprovar')
    check('aprovar solicitacao do cliente 1 (1o, dentro do limite) -> 200', r.status_code == 200, str(r.get_json()))

    r = client.put(f'/api/v1/gestor/planos/solicitacoes/{sol2_id}/aprovar')
    check('aprovar solicitacao do cliente 2 (plano ja cheio) -> 403', r.status_code == 403, str(r.get_json()))

    with client.application.app_context():
        ativos = ClientePlano.query.filter_by(plano_id=ctx['plano_limitado_id'], ativo=True).count()
        check('exatamente 1 ClientePlano ativo pro plano limitado (nao furou o limite)', ativos == 1, str(ativos))

    r = client.put(f'/api/v1/gestor/planos/solicitacoes/{sol2_id}/rejeitar', json={'motivo': 'plano cheio'})
    check('rejeitar solicitacao pendente do cliente 2 -> 200', r.status_code == 200, str(r.get_json()))
    client.post('/sair')

    r = client.post(f'/b/{ctx["slug"]}/entrar', json={'email': ctx['cliente2_email'], 'senha': 'senha123'})
    check('login cliente 2 de novo', r.status_code == 200)
    r = client.post(f'/api/v1/pub/{ctx["slug"]}/planos/{ctx["plano_limitado_id"]}/solicitar', json={'metodo_pagamento': 'local'})
    check('cliente 2 tenta solicitar de novo, plano ja cheio -> 403 (checagem preventiva)',
          r.status_code == 403, str(r.get_json()))
    client.post('/sair')


def testar_reset_senha(client, ctx):
    print('\n--- Reset de senha ---')
    r = client.post('/api/v1/auth/solicitar-reset-senha', json={'email': ctx['gestor_email']})
    msg_existente = r.get_json()['mensagem']
    check('solicitar com email existente -> 200', r.status_code == 200)

    r2 = client.post('/api/v1/auth/solicitar-reset-senha', json={'email': 'nao.existe.v12@teste.com'})
    check('solicitar com email inexistente -> 200 (nao revela)', r2.status_code == 200)
    check('mensagem identica pra email existente e inexistente (anti-enumeracao)',
          r2.get_json()['mensagem'] == msg_existente)

    with client.application.app_context():
        sol = SolicitacaoSenha.query.filter_by(
            usuario_id=ctx['gestor_id']
        ).order_by(SolicitacaoSenha.criado_em.desc()).first()
        token, codigo_certo = sol.token, sol.codigo_novo

    for i in range(3):
        r = client.post('/api/v1/auth/confirmar-reset-senha', json={'token': token, 'codigo': '00000000'})
        if i < 2:
            check(f'codigo errado tentativa {i+1} -> 401', r.status_code == 401, str(r.get_json()))
        else:
            check('3a tentativa errada -> ja bate o limite (401 nesta, 429 na proxima)', r.status_code in (401, 429))

    r = client.post('/api/v1/auth/confirmar-reset-senha', json={'token': token, 'codigo': codigo_certo})
    check('codigo certo apos 3 erros -> 429 (limite atingido, mesmo com codigo certo)', r.status_code == 429, str(r.get_json()))

    # nova solicitacao (a antiga travou) -> confirma com codigo certo de primeira
    client.post('/api/v1/auth/solicitar-reset-senha', json={'email': ctx['gestor_email']})
    with client.application.app_context():
        sol2 = SolicitacaoSenha.query.filter_by(
            usuario_id=ctx['gestor_id']
        ).order_by(SolicitacaoSenha.criado_em.desc()).first()
        token2, codigo2 = sol2.token, sol2.codigo_novo

    r = client.post('/api/v1/auth/confirmar-reset-senha', json={'token': token2, 'codigo': codigo2})
    check('codigo certo em solicitacao nova -> 200 com tokens', r.status_code == 200 and 'access_token' in r.get_json(),
          str(r.get_json()))

    r = client.post('/api/v1/auth/confirmar-reset-senha', json={'token': token2, 'codigo': codigo2})
    # 429 é aceitável aqui: o teste já fez varias chamadas seguidas a este
    # endpoint (RL_RESET_SENHA='5 per minute') — o rate limit pode disparar
    # antes da checagem de "já confirmado". Ambos são rejeição correta.
    check('reuso do codigo ja confirmado -> 422 ou 429 (rate limit)', r.status_code in (422, 429), str(r.get_json()))

    r = client.post('/api/v1/auth/login', json={'email': ctx['gestor_email'], 'senha': 'senha123'})
    check('login com senha ANTIGA falha apos reset -> 401', r.status_code == 401, str(r.get_json()))

    r = client.post('/api/v1/auth/login', json={'email': ctx['gestor_email'], 'senha': codigo2})
    check('login com senha NOVA (=codigo) funciona -> 200', r.status_code == 200, str(r.get_json()))

    with client.application.app_context():
        n = Notificacao.query.filter(
            Notificacao.tipo == 'reset_senha', Notificacao.corpo.like('%QA Gestor%')
        ).count()
        check('notificacao in-app de reset foi criada pra hierarquia', n >= 1, str(n))


def main():
    app = create_app()
    dados = setup(app)
    with app.app_context():
        barb1 = db.session.get(Barbeiro, dados['barb1_id'])
        barb2 = db.session.get(Barbeiro, dados['barb2_id'])
        barb1_usr = db.session.get(Usuario, barb1.usuario_id)
        barb2_usr = db.session.get(Usuario, barb2.usuario_id)
        barb1_usr.email = 'qa.barbeiro1.v12@teste.com'
        barb2_usr.email = 'qa.barbeiro2.v12@teste.com'
        db.session.commit()
        dados['barb1_email'] = barb1_usr.email
        dados['barb2_email'] = barb2_usr.email

    client = app.test_client()
    try:
        testar_pdv_caixa(client, dados)
        testar_vip(client, dados)
        testar_limite_plano(client, dados)
        testar_reset_senha(client, dados)
    finally:
        cleanup(app, dados['barbearia_id'])

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
