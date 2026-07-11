"""
Teste de integração — Frente 1 completa (features por segmento).

Cobre o que foi feito nesta rodada:
  - pix_integrado gateando aprovar_agendamento
  - relatorios_avancados gateando Excel/PDF (JSON continua livre)
  - agendamento_login sincronizando ConfiguracaoAgendamento.quick_booking_sem_login
    via toggle_feature, e enforcement real no quick-booking público
  - GET /api/v1/cliente/features
  - GET/PUT /api/v1/super/segmentos/<id>/features
  - criar_barbearia com segmento_id resolve overrides corretamente (regressão)

Cria seu próprio super_admin QA (não depende de credenciais de nenhum
usuário já existente no banco local) — mesmo padrão de isolamento de
teste_v1_2_pdv_vip_reset.py: tenant descartável, test_client (HTTP real),
limpa tudo ao final.

Uso:
    python teste_frente1_completa.py
"""
import os
import sys
import datetime as dt
from datetime import time as time_cls

os.environ.setdefault('DISABLE_SCHEDULER', '1')

from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import (
    Barbearia, Usuario, Barbeiro, Cliente, Servico, BarbeiroServico,
    ConfiguracaoAgenda, ConfiguracaoAgendamento, FeatureMetadata, FeatureBarbearia,
    Segmento, SegmentoFeaturePadrao, Agendamento, AgendamentoSolicitacaoPix,
    AgendamentoServico, AuditoriaLog, TokenRevogado,
)
from app.constants import StatusAgendamento

FALHAS = []


def check(nome, cond, detalhe=''):
    status = 'OK ' if cond else 'FAIL'
    print(f'[{status}] {nome}' + (f' — {detalhe}' if detalhe and not cond else ''))
    if not cond:
        FALHAS.append(nome)


def setup(app):
    with app.app_context():
        b = Barbearia(nome='QA Frente1', slug='qa-frente1', ativo=True)
        db.session.add(b)
        db.session.flush()

        gestor = Usuario(barbearia_id=b.id, nome='QA Gestor F1', telefone='11999993000',
                          email='qa.gestor.f1@teste.com', senha=generate_password_hash('senha123'),
                          perfil='gestor', ativo=True)
        usr_barb = Usuario(barbearia_id=b.id, nome='QA Barbeiro F1', telefone='11999993001',
                            email='qa.barbeiro.f1@teste.com',
                            perfil='barbeiro', ativo=True, senha=generate_password_hash('senha123'))
        usr_cli = Usuario(barbearia_id=b.id, nome='QA Cliente F1', telefone='11999993002',
                           email='qa.cliente.f1@teste.com',
                           perfil='cliente', ativo=True, senha=generate_password_hash('senha123'))
        # super_admin próprio do teste — não depende de credenciais alheias
        super_qa = Usuario(barbearia_id=None, nome='QA Super F1', telefone='11999993099',
                            email='qa.super.f1@teste.com', senha=generate_password_hash('senha123'),
                            perfil='super_admin', ativo=True)
        db.session.add_all([gestor, usr_barb, usr_cli, super_qa])
        db.session.flush()

        barb = Barbeiro(barbearia_id=b.id, usuario_id=usr_barb.id, ativo=True)
        db.session.add(barb)
        db.session.flush()

        cli = Cliente(barbearia_id=b.id, usuario_id=usr_cli.id, nome='QA Cliente F1',
                       telefone='11999993002', ativo=True)
        db.session.add(cli)

        servico = Servico(barbearia_id=b.id, nome='Corte QA F1', preco=30, duracao_minutos=30, ativo=True)
        db.session.add(servico)
        db.session.flush()
        db.session.add(BarbeiroServico(barbeiro_id=barb.id, servico_id=servico.id))
        db.session.add(ConfiguracaoAgenda(
            barbearia_id=b.id, barbeiro_id=barb.id,
            horario_abertura=time_cls(8, 0), horario_fechamento=time_cls(20, 0),
            intervalo_minutos=30, loja_aberta=True,
        ))
        db.session.add(ConfiguracaoAgendamento(barbearia_id=b.id, quick_booking_sem_login=True))

        # todas as features desligadas por padrão — cada teste liga a que precisa
        for fm in FeatureMetadata.query.all():
            db.session.add(FeatureBarbearia(barbearia_id=b.id, feature_id=fm.id, ativo=False))

        db.session.commit()
        return {
            'barbearia_id': b.id, 'slug': b.slug,
            'gestor_email': gestor.email, 'barb_id': barb.id,
            'cliente_id': cli.id, 'cliente_email': usr_cli.email, 'servico_id': servico.id,
            'super_email': super_qa.email, 'super_id': super_qa.id,
        }


def cleanup(app, bid):
    with app.app_context():
        ag_ids = [a.id for a in Agendamento.query.filter_by(barbearia_id=bid).all()]
        AgendamentoServico.query.filter(AgendamentoServico.agendamento_id.in_(ag_ids)).delete(synchronize_session=False)
        AgendamentoSolicitacaoPix.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Agendamento.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        ConfiguracaoAgenda.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        ConfiguracaoAgendamento.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        from app.models import BarbeariaCustomizacao
        BarbeariaCustomizacao.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        BarbeiroServico.query.filter(BarbeiroServico.barbeiro_id.in_(
            db.session.query(Barbeiro.id).filter_by(barbearia_id=bid)
        )).delete(synchronize_session=False)
        Servico.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        FeatureBarbearia.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Barbeiro.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Cliente.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        uids = [u.id for u in Usuario.query.filter_by(barbearia_id=bid).all()]
        TokenRevogado.query.filter(TokenRevogado.usuario_id.in_(uids)).delete(synchronize_session=False)
        AuditoriaLog.query.filter(AuditoriaLog.usuario_id.in_(uids)).delete(synchronize_session=False)
        Usuario.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Barbearia.query.filter_by(id=bid).delete(synchronize_session=False)
        db.session.commit()


def cleanup_super_qa(app, super_id):
    with app.app_context():
        TokenRevogado.query.filter_by(usuario_id=super_id).delete(synchronize_session=False)
        AuditoriaLog.query.filter_by(usuario_id=super_id).delete(synchronize_session=False)
        Usuario.query.filter_by(id=super_id).delete(synchronize_session=False)
        db.session.commit()


def cleanup_segmento_teste(app, seg_chave='qa_teste_seg'):
    with app.app_context():
        seg = Segmento.query.filter_by(chave=seg_chave).first()
        if seg:
            SegmentoFeaturePadrao.query.filter_by(segmento_id=seg.id).delete(synchronize_session=False)
            Segmento.query.filter_by(id=seg.id).delete(synchronize_session=False)
            db.session.commit()


def testar_pix_integrado(client, ctx):
    print('\n--- pix_integrado ---')
    with client.application.app_context():
        ag = Agendamento(
            barbearia_id=ctx['barbearia_id'], cliente_id=ctx['cliente_id'], barbeiro_id=ctx['barb_id'],
            data_hora=dt.datetime(2027, 1, 4, 10, 0), duracao_minutos=30,
            status=StatusAgendamento.AGUARDANDO_COMPROVANTE,
            valor_total=30, metodo_pagamento='pix',
        )
        db.session.add(ag)
        db.session.commit()
        ag_id = ag.id

    r = client.post('/entrar', json={'email': ctx['gestor_email'], 'senha': 'senha123'})
    check('login gestor', r.status_code == 200, str(r.get_json()))

    r = client.put(f'/api/v1/gestor/agendamentos/{ag_id}/aprovar')
    check('aprovar PIX com feature OFF -> 403', r.status_code == 403, str(r.get_json()))

    with client.application.app_context():
        fm = FeatureMetadata.query.filter_by(nome='pix_integrado').first()
        FeatureBarbearia.query.filter_by(barbearia_id=ctx['barbearia_id'], feature_id=fm.id).update({'ativo': True})
        db.session.commit()

    r = client.put(f'/api/v1/gestor/agendamentos/{ag_id}/aprovar')
    check('aprovar PIX com feature ON -> 200 (aprova de verdade)', r.status_code == 200, str(r.get_json()))
    client.post('/sair')


def testar_relatorios_avancados(client, ctx):
    print('\n--- relatorios_avancados ---')
    r = client.post('/entrar', json={'email': ctx['gestor_email'], 'senha': 'senha123'})
    check('login gestor', r.status_code == 200)

    r = client.get('/api/v1/gestor/relatorios/agendamentos')
    check('JSON sempre livre (sem feature) -> 200', r.status_code == 200, str(r.status_code))

    r = client.get('/api/v1/gestor/relatorios/agendamentos/excel')
    check('Excel sem feature -> 403', r.status_code == 403)

    r = client.get('/api/v1/gestor/relatorios/agendamentos/pdf')
    check('PDF sem feature -> 403', r.status_code == 403)

    with client.application.app_context():
        fm = FeatureMetadata.query.filter_by(nome='relatorios_avancados').first()
        FeatureBarbearia.query.filter_by(barbearia_id=ctx['barbearia_id'], feature_id=fm.id).update({'ativo': True})
        db.session.commit()

    r = client.get('/api/v1/gestor/relatorios/agendamentos/excel')
    check('Excel com feature ON -> 200', r.status_code == 200, str(r.status_code))
    r = client.get('/api/v1/gestor/relatorios/agendamentos/pdf')
    check('PDF com feature ON -> 200', r.status_code == 200, str(r.status_code))
    client.post('/sair')


def testar_agendamento_login(client, ctx):
    print('\n--- agendamento_login ---')
    # Data relativa dentro da antecedencia_maxima_dias (default 60) — data fixa
    # no passado distante ja mordeu outro teste desta sessao (licao do Script 17).
    data_teste = (dt.datetime.now() + dt.timedelta(days=5)).strftime('%Y-%m-%dT10:00:00')
    data_teste2 = (dt.datetime.now() + dt.timedelta(days=5)).strftime('%Y-%m-%dT11:00:00')

    with client.application.app_context():
        config = ConfiguracaoAgendamento.query.filter_by(barbearia_id=ctx['barbearia_id']).first()
        check('quick_booking_sem_login comeca True (feature off)', config.quick_booking_sem_login is True)

    r = client.post(f'/api/v1/pub/{ctx["slug"]}/agendar', json={
        'telefone': '11988887777', 'nome': 'Anonimo QA', 'barbeiro_id': ctx['barb_id'],
        'data_hora': data_teste, 'servicos': [{'servico_id': ctx['servico_id']}],
    })
    check('quick-booking anonimo funciona com feature off', r.status_code in (200, 201), str(r.get_json()))

    r = client.post('/entrar', json={'email': ctx['super_email'], 'senha': 'senha123'})
    check('login super_admin', r.status_code == 200, str(r.get_json()))

    r = client.put(f'/api/v1/super/barbearias/{ctx["barbearia_id"]}/features/agendamento_login')
    check('toggle agendamento_login -> 200', r.status_code == 200, str(r.get_json()))

    with client.application.app_context():
        config = ConfiguracaoAgendamento.query.filter_by(barbearia_id=ctx['barbearia_id']).first()
        check('quick_booking_sem_login virou False ao ligar a feature', config.quick_booking_sem_login is False)

    r = client.post(f'/api/v1/pub/{ctx["slug"]}/agendar', json={
        'telefone': '11988887778', 'nome': 'Anonimo QA 2', 'barbeiro_id': ctx['barb_id'],
        'data_hora': data_teste2, 'servicos': [{'servico_id': ctx['servico_id']}],
    })
    check('quick-booking anonimo bloqueado com feature ligada -> 403', r.status_code == 403, str(r.get_json()))

    r = client.put(f'/api/v1/super/barbearias/{ctx["barbearia_id"]}/features/agendamento_login')
    check('toggle de volta (desligar) -> 200', r.status_code == 200)
    with client.application.app_context():
        config = ConfiguracaoAgendamento.query.filter_by(barbearia_id=ctx['barbearia_id']).first()
        check('quick_booking_sem_login volta a True ao desligar', config.quick_booking_sem_login is True)
    client.post('/sair')


def testar_cliente_features(client, ctx):
    print('\n--- GET /api/v1/cliente/features ---')
    r = client.post(f'/b/{ctx["slug"]}/entrar', json={'email': ctx['cliente_email'], 'senha': 'senha123'})
    check('login cliente', r.status_code == 200, str(r.get_json()))

    r = client.get('/api/v1/cliente/features')
    check('GET cliente/features -> 200', r.status_code == 200, str(r.get_json()))
    lista = r.get_json()
    check('retorna as 11 features do catalogo', len(lista) == 11, str(len(lista)))
    check('cada item tem nome/descricao/ativo', all('nome' in f and 'ativo' in f for f in lista))
    client.post('/sair')


def testar_segmento_features_admin(client, ctx):
    print('\n--- admin de padrao de feature por segmento ---')
    with client.application.app_context():
        seg = Segmento.query.filter_by(chave='qa_teste_seg').first()
        if not seg:
            seg = Segmento(nome='QA Teste Segmento', chave='qa_teste_seg')
            db.session.add(seg)
            db.session.commit()
        seg_id = seg.id

    r = client.post('/entrar', json={'email': ctx['super_email'], 'senha': 'senha123'})
    check('login super_admin', r.status_code == 200)

    r = client.get(f'/api/v1/super/segmentos/{seg_id}/features')
    check('GET features do segmento -> 200, 11 itens', r.status_code == 200 and len(r.get_json()) == 11, str(r.get_json())[:200])
    check('sem override, origem = global', all(f['origem'] == 'global' for f in r.get_json()))

    r = client.put(f'/api/v1/super/segmentos/{seg_id}/features/cupons', json={'ativo_por_padrao': True})
    check('PUT liga cupons pro segmento -> 200', r.status_code == 200, str(r.get_json()))

    r = client.get(f'/api/v1/super/segmentos/{seg_id}/features')
    item_cupons = next(f for f in r.get_json() if f['feature'] == 'cupons')
    check('cupons agora tem origem=segmento e ativo_por_padrao=True',
          item_cupons['origem'] == 'segmento' and item_cupons['ativo_por_padrao'] is True, str(item_cupons))

    r = client.put(f'/api/v1/super/segmentos/{seg_id}/features/nao_existe', json={'ativo_por_padrao': True})
    check('PUT feature inexistente -> 404', r.status_code == 404, str(r.get_json()))

    r = client.put(f'/api/v1/super/segmentos/{seg_id}/features/cupons', json={})
    check('PUT sem ativo_por_padrao -> 422', r.status_code == 422, str(r.get_json()))

    client.post('/sair')
    return seg_id


def testar_criar_barbearia_com_segmento(client, ctx, seg_id):
    print('\n--- criar_barbearia com segmento resolve overrides ---')
    r = client.post('/entrar', json={'email': ctx['super_email'], 'senha': 'senha123'})
    check('login super_admin', r.status_code == 200)

    r = client.post('/api/v1/super/barbearias', json={
        'nome': 'QA Nova Segmento', 'slug': 'qa-nova-segmento',
        'gestor_nome': 'Gestor QA', 'gestor_email': 'qa.novo.gestor.f1@teste.com',
        'gestor_telefone': '11999994000', 'gestor_senha': '123456',
        'segmento_id': seg_id,
    })
    check('POST criar barbearia com segmento -> 201', r.status_code == 201, str(r.get_json()))
    body = r.get_json()
    nova_id = body['barbearia']['id']
    check('segmento_id retornado bate', body['barbearia']['segmento_id'] == seg_id, str(body['barbearia']))

    with client.application.app_context():
        fm = FeatureMetadata.query.filter_by(nome='cupons').first()
        fb = FeatureBarbearia.query.filter_by(barbearia_id=nova_id, feature_id=fm.id).first()
        check('cupons nasce ATIVO nesta barbearia (override do segmento)', fb is not None and fb.ativo is True)

    client.post('/sair')
    return nova_id


def main():
    app = create_app()
    ctx = setup(app)
    client = app.test_client()
    seg_id = None
    nova_barbearia_id = None
    try:
        testar_pix_integrado(client, ctx)
        testar_relatorios_avancados(client, ctx)
        testar_agendamento_login(client, ctx)
        testar_cliente_features(client, ctx)
        seg_id = testar_segmento_features_admin(client, ctx)
        nova_barbearia_id = testar_criar_barbearia_com_segmento(client, ctx, seg_id)
    finally:
        cleanup(app, ctx['barbearia_id'])
        cleanup_super_qa(app, ctx['super_id'])
        if nova_barbearia_id:
            cleanup(app, nova_barbearia_id)
        if seg_id:
            cleanup_segmento_teste(app)

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
