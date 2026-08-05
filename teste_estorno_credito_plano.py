"""
Teste de regressão — Bloco 5 da FASE 2 (M1: cancelamento não estorna
crédito de plano, achado #7 de AUDITORIA_PRODUCAO.md).

Cenário: cliente com plano ativo (cobre o serviço, limite ilimitado) agenda
um serviço coberto pelo plano (consome 1 crédito — grava ClientePlanoUso) e
depois cancela o agendamento (ainda no futuro). O crédito tem que voltar
(ClientePlanoUso correspondente apagado).

Cobre também a exceção manual do gestor (`sem_estorno_plano: true`): mesmo
cenário, mas o gestor cancela pedindo explicitamente pra NÃO estornar — o
crédito tem que continuar consumido.

Usa test_client() (in-process, sem concorrência envolvida). Cria seus
próprios dados descartáveis e apaga tudo ao final.

Uso:
    python teste_estorno_credito_plano.py
"""
import sys
from datetime import timedelta

from werkzeug.security import generate_password_hash


def setup(app):
    from app.extensions import db
    from app.models import (
        Barbearia, Usuario, Barbeiro, Cliente, Servico, BarbeiroServico,
        Plano, PlanoServico, ClientePlano, ConfiguracaoAgenda,
    )
    from app.utils.tz import naive_brasilia, hoje_brasilia
    from datetime import time as time_cls

    with app.app_context():
        b = Barbearia(nome='QA Estorno Plano', slug='qa-estorno-plano', ativo=True)
        db.session.add(b); db.session.flush()

        ug = Usuario(barbearia_id=b.id, nome='QA Gestor', telefone='11999996000',
                     email='qa.gestor.estorno@teste.com', senha=generate_password_hash('senha123'),
                     perfil='gestor', ativo=True)
        ub = Usuario(barbearia_id=b.id, nome='QA Barbeiro', telefone='11999996001',
                     perfil='barbeiro', ativo=True, senha=generate_password_hash('x'))
        cliu = Usuario(barbearia_id=b.id, nome='QA Cliente', telefone='11999996002',
                       email='qa.cliente.estorno@teste.com', perfil='cliente', ativo=True,
                       senha=generate_password_hash('senha123'))
        db.session.add_all([ug, ub, cliu]); db.session.flush()

        barb = Barbeiro(barbearia_id=b.id, usuario_id=ub.id, ativo=True)
        db.session.add(barb); db.session.flush()

        cli = Cliente(barbearia_id=b.id, usuario_id=cliu.id, nome='QA Cliente',
                      telefone='11999996002', ativo=True)
        db.session.add(cli); db.session.flush()

        sv = Servico(barbearia_id=b.id, nome='Corte QA Plano', preco=50, duracao_minutos=30, ativo=True)
        db.session.add(sv); db.session.flush()
        db.session.add(BarbeiroServico(barbeiro_id=barb.id, servico_id=sv.id))
        db.session.add(ConfiguracaoAgenda(
            barbearia_id=b.id, barbeiro_id=barb.id,
            horario_abertura=time_cls(8, 0), horario_fechamento=time_cls(20, 0),
            intervalo_minutos=30, loja_aberta=True,
        ))

        plano = Plano(barbearia_id=b.id, nome='Plano QA', preco_mensal=99, ativo=True)  # barbeiro_id=None = aberto
        db.session.add(plano); db.session.flush()
        db.session.add(PlanoServico(plano_id=plano.id, servico_id=sv.id, limite_uso_mensal=99999, dias_expiracao=30, ativo=True))

        cp = ClientePlano(barbearia_id=b.id, cliente_id=cli.id, plano_id=plano.id,
                           data_inicio=hoje_brasilia(), data_fim=hoje_brasilia() + timedelta(days=30), ativo=True)
        db.session.add(cp)
        db.session.commit()

        return {
            'barbearia_id': b.id,
            'slug': b.slug,
            'gestor_email': 'qa.gestor.estorno@teste.com',
            'cliente_email': 'qa.cliente.estorno@teste.com',
            'cliente_plano_id': cp.id,
            'barbeiro_id': barb.id,
            'servico_id': sv.id,
        }


def cleanup(app, dados):
    from app.extensions import db
    from app.models import (
        Barbearia, Usuario, Barbeiro, Cliente, Servico, BarbeiroServico,
        Plano, PlanoServico, ClientePlano, ClientePlanoUso, ConfiguracaoAgenda,
        Agendamento, AgendamentoServico, Notificacao, AuditoriaLog,
    )

    with app.app_context():
        bid = dados['barbearia_id']
        AuditoriaLog.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Notificacao.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        ClientePlanoUso.query.filter_by(cliente_plano_id=dados['cliente_plano_id']).delete(synchronize_session=False)
        ag_ids = [a.id for a in Agendamento.query.filter_by(barbearia_id=bid).all()]
        AgendamentoServico.query.filter(AgendamentoServico.agendamento_id.in_(ag_ids)).delete(synchronize_session=False)
        Agendamento.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        ClientePlano.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        plano_ids = [p.id for p in Plano.query.filter_by(barbearia_id=bid).all()]
        PlanoServico.query.filter(PlanoServico.plano_id.in_(plano_ids)).delete(synchronize_session=False)
        Plano.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        barb_ids = [x.id for x in Barbeiro.query.filter_by(barbearia_id=bid).all()]
        BarbeiroServico.query.filter(BarbeiroServico.barbeiro_id.in_(barb_ids)).delete(synchronize_session=False)
        ConfiguracaoAgenda.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Servico.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Cliente.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Barbeiro.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Usuario.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Barbearia.query.filter_by(id=bid).delete(synchronize_session=False)
        db.session.commit()


def _uso_existe(app, dados, dia):
    from app.models import ClientePlanoUso
    with app.app_context():
        return ClientePlanoUso.query.filter_by(
            cliente_plano_id=dados['cliente_plano_id'], servico_id=dados['servico_id'], data_uso=dia,
        ).first() is not None


def _agendar(client, dados, slot_iso):
    return client.post('/api/v1/cliente/agendamentos', json={
        'barbeiro_id': dados['barbeiro_id'],
        'servicos': [{'servico_id': dados['servico_id']}],
        'data_hora': slot_iso,
        'metodo_pagamento': 'local',
    })


def cenario_1_cliente_cancela(app, dados):
    print('\n[Cenário 1] Cliente agenda com plano, cancela, crédito volta')
    from app.utils.tz import naive_brasilia

    client = app.test_client()
    r = client.post(f'/b/{dados["slug"]}/entrar', json={'email': dados['cliente_email'], 'senha': 'senha123'})
    if r.status_code != 200:
        print(f'  ERRO no login do cliente: {r.status_code} {r.get_data(as_text=True)}')
        return False

    slot = (naive_brasilia() + timedelta(days=10)).replace(hour=14, minute=0, second=0, microsecond=0)
    r1 = _agendar(client, dados, slot.isoformat())
    ok1 = r1.status_code == 201
    print(f'  POST agendamentos -> {r1.status_code} (esperado 201)  {"OK" if ok1 else "FALHOU"}')
    corpo1 = r1.get_json() if ok1 else {}
    is_plano = ok1 and corpo1.get('servicos', [{}])[0].get('is_plano')
    ag_id = corpo1.get('id') if ok1 else None
    print(f'  is_plano no agendamento criado: {is_plano} (esperado True)')

    consumido = _uso_existe(app, dados, slot.date())
    print(f'  ClientePlanoUso existe após agendar: {consumido} (esperado True)')

    r2 = client.post(f'/api/v1/cliente/agendamentos/{ag_id}/cancelar', json={})
    ok2 = r2.status_code == 200
    print(f'  POST cancelar -> {r2.status_code} (esperado 200)  {"OK" if ok2 else "FALHOU"}')

    estornado = not _uso_existe(app, dados, slot.date())
    print(f'  ClientePlanoUso removido após cancelar: {estornado} (esperado True — crédito de volta)')

    ok = ok1 and is_plano and consumido and ok2 and estornado
    print(f'  {"PASSOU" if ok else "FALHOU"}')
    return ok


def cenario_2_gestor_forca_sem_estorno(app, dados):
    print('\n[Cenário 2] Gestor cancela com sem_estorno_plano=true — crédito NÃO volta')
    from app.utils.tz import naive_brasilia

    client_cli = app.test_client()
    r = client_cli.post(f'/b/{dados["slug"]}/entrar', json={'email': dados['cliente_email'], 'senha': 'senha123'})
    if r.status_code != 200:
        print(f'  ERRO no login do cliente: {r.status_code} {r.get_data(as_text=True)}')
        return False

    slot = (naive_brasilia() + timedelta(days=11)).replace(hour=14, minute=0, second=0, microsecond=0)
    r1 = _agendar(client_cli, dados, slot.isoformat())
    ok1 = r1.status_code == 201
    ag_id = r1.get_json().get('id') if ok1 else None
    print(f'  POST agendamentos -> {r1.status_code} (esperado 201)  {"OK" if ok1 else "FALHOU"}')

    consumido = _uso_existe(app, dados, slot.date())
    print(f'  ClientePlanoUso existe após agendar: {consumido} (esperado True)')

    client_gestor = app.test_client()
    r = client_gestor.post('/entrar', json={'email': dados['gestor_email'], 'senha': 'senha123'})
    if r.status_code != 200:
        print(f'  ERRO no login do gestor: {r.status_code} {r.get_data(as_text=True)}')
        return False

    r2 = client_gestor.put(f'/api/v1/gestor/agendamentos/{ag_id}/cancelar', json={'sem_estorno_plano': True})
    ok2 = r2.status_code == 200
    print(f'  PUT cancelar (gestor, sem_estorno_plano=true) -> {r2.status_code} (esperado 200)  {"OK" if ok2 else "FALHOU"}')

    ainda_consumido = _uso_existe(app, dados, slot.date())
    print(f'  ClientePlanoUso continua existindo: {ainda_consumido} (esperado True — exceção manual não estorna)')

    ok = ok1 and consumido and ok2 and ainda_consumido
    print(f'  {"PASSOU" if ok else "FALHOU"}')
    return ok


def main():
    from app import create_app
    app = create_app()

    print('Preparando dados de teste...')
    dados = setup(app)
    try:
        r1 = cenario_1_cliente_cancela(app, dados)
        r2 = cenario_2_gestor_forca_sem_estorno(app, dados)

        print('\n=== RESUMO ===')
        print(f'[1] Cliente cancela, crédito volta:                 {"PASSOU" if r1 else "FALHOU"}')
        print(f'[2] Gestor força sem estorno, crédito não volta:    {"PASSOU" if r2 else "FALHOU"}')
        sys.exit(0 if (r1 and r2) else 1)
    finally:
        print('\nLimpando dados de teste...')
        cleanup(app, dados)


if __name__ == '__main__':
    main()
