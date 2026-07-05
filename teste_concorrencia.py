"""
Teste manual de concorrência — Bloco 2.2 (Script 07).

Roda com o servidor de pé (ex: `python wsgi.py` em outro terminal) e valida:
  1. 10 threads criando o MESMO agendamento (mesmo barbeiro/horário) via
     POST /api/v1/pub/<slug>/agendar — exatamente 1 deve dar 201, o resto 409.
  2. 5 threads aprovando a MESMA solicitação de plano PIX — exatamente 1 deve
     dar 200, o resto 409.

Cria seus próprios dados de teste (barbearia/gestor/barbeiro/cliente/plano
descartáveis) via contexto da aplicação, e apaga tudo ao final.

Uso:
    python teste_concorrencia.py [base_url]
    (base_url default: http://127.0.0.1:5000)
"""
import sys
import threading
from datetime import time as time_cls, timedelta

import requests
from werkzeug.security import generate_password_hash

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5000'
N_THREADS_BOOKING = 10
N_THREADS_APROVACAO = 5


def setup():
    from app import create_app
    from app.extensions import db
    from app.models import (
        Barbearia, Usuario, Barbeiro, Cliente, Servico, ConfiguracaoAgenda,
        BarbeiroServico, Plano, PlanoServico, ClientePlano, ClientePlanoSolicitacao,
    )
    from app.utils.tz import naive_brasilia

    app = create_app()
    ctx = app.app_context()
    ctx.push()

    b = Barbearia(nome='QA Concorrencia', slug='qa-concorrencia', ativo=True)
    db.session.add(b); db.session.flush()

    ug = Usuario(barbearia_id=b.id, nome='QA Gestor', telefone='11999991000',
                 email='qa.gestor.concorrencia@teste.com', senha=generate_password_hash('senha123'),
                 perfil='gestor', ativo=True)
    ub = Usuario(barbearia_id=b.id, nome='QA Barbeiro', telefone='11999991001',
                 perfil='barbeiro', ativo=True, senha=generate_password_hash('x'))
    cliu = Usuario(barbearia_id=b.id, nome='QA Cliente', telefone='11999991002',
                 perfil='cliente', ativo=True, senha=generate_password_hash('x'))
    db.session.add_all([ug, ub, cliu]); db.session.flush()

    barb = Barbeiro(barbearia_id=b.id, usuario_id=ub.id, ativo=True)
    db.session.add(barb); db.session.flush()

    cli = Cliente(barbearia_id=b.id, usuario_id=cliu.id, nome='QA Cliente',
                  telefone='11999991002', ativo=True)
    db.session.add(cli); db.session.flush()

    serv = Servico(barbearia_id=b.id, nome='Corte Concorrencia', preco=30,
                    duracao_minutos=30, ativo=True)
    db.session.add(serv); db.session.flush()
    db.session.add(BarbeiroServico(barbeiro_id=barb.id, servico_id=serv.id))

    db.session.add(ConfiguracaoAgenda(
        barbearia_id=b.id, barbeiro_id=barb.id,
        horario_abertura=time_cls(8, 0), horario_fechamento=time_cls(20, 0),
        intervalo_minutos=30, loja_aberta=True,
    ))

    plano = Plano(barbearia_id=b.id, nome='Plano Concorrencia', preco_mensal=50, ativo=True)
    db.session.add(plano); db.session.flush()
    db.session.add(PlanoServico(plano_id=plano.id, servico_id=serv.id,
                                 limite_uso_mensal=99999, dias_expiracao=30, ativo=True))
    sol = ClientePlanoSolicitacao(barbearia_id=b.id, cliente_id=cli.id, plano_id=plano.id,
                                   valor=50, metodo_pagamento='local', status='pendente')
    db.session.add(sol)

    db.session.commit()

    slot = (naive_brasilia() + timedelta(days=5)).replace(hour=14, minute=0, second=0, microsecond=0)

    dados = {
        'slug': b.slug,
        'barbearia_id': b.id,
        'barbeiro_id': barb.id,
        'servico_id': serv.id,
        'gestor_email': 'qa.gestor.concorrencia@teste.com',
        'sol_id': sol.id,
        'slot_iso': slot.isoformat(),
    }
    ctx.pop()
    return dados


def cleanup(dados):
    from app import create_app
    from app.extensions import db
    from app.models import (
        Barbearia, Usuario, Barbeiro, Cliente, Servico, ConfiguracaoAgenda,
        BarbeiroServico, Plano, PlanoServico, ClientePlano, ClientePlanoSolicitacao,
        Agendamento, AgendamentoServico, TokenRevogado,
    )

    app = create_app()
    with app.app_context():
        bid = dados['barbearia_id']
        ag_ids = [a.id for a in Agendamento.query.filter_by(barbearia_id=bid).all()]
        AgendamentoServico.query.filter(AgendamentoServico.agendamento_id.in_(ag_ids)).delete(synchronize_session=False)
        Agendamento.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        ClientePlano.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        ClientePlanoSolicitacao.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        plano_ids = [p.id for p in Plano.query.filter_by(barbearia_id=bid).all()]
        PlanoServico.query.filter(PlanoServico.plano_id.in_(plano_ids)).delete(synchronize_session=False)
        Plano.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        barb_ids = [x.id for x in Barbeiro.query.filter_by(barbearia_id=bid).all()]
        BarbeiroServico.query.filter(BarbeiroServico.barbeiro_id.in_(barb_ids)).delete(synchronize_session=False)
        ConfiguracaoAgenda.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Servico.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Cliente.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Barbeiro.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        uids = [u.id for u in Usuario.query.filter_by(barbearia_id=bid).all()]
        TokenRevogado.query.filter(TokenRevogado.usuario_id.in_(uids)).delete(synchronize_session=False)
        Usuario.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Barbearia.query.filter_by(id=bid).delete(synchronize_session=False)
        db.session.commit()


def teste_double_booking(dados):
    resultados = []
    lock = threading.Lock()

    def tentar():
        payload = {
            'barbeiro_id': dados['barbeiro_id'],
            'servicos': [{'servico_id': dados['servico_id']}],
            'data_hora': dados['slot_iso'],
            'metodo_pagamento': 'local',
            'telefone': '11999991002',
            'nome': 'QA Cliente',
        }
        try:
            r = requests.post(f'{BASE_URL}/api/v1/pub/{dados["slug"]}/agendar', json=payload, timeout=15)
            status = r.status_code
        except Exception as e:
            status = f'ERRO: {e}'
        with lock:
            resultados.append(status)

    threads = [threading.Thread(target=tentar) for _ in range(N_THREADS_BOOKING)]
    for t in threads: t.start()
    for t in threads: t.join()

    n_201 = resultados.count(201)
    n_409 = resultados.count(409)
    outros = [r for r in resultados if r not in (201, 409)]
    print(f'  Resultados: {resultados}')
    print(f'  201 (sucesso): {n_201}  |  409 (conflito): {n_409}  |  outros: {outros}')
    ok = (n_201 == 1 and n_409 == N_THREADS_BOOKING - 1)
    print(f'  {"PASSOU" if ok else "FALHOU"}: esperado exatamente 1x 201 e {N_THREADS_BOOKING-1}x 409.')
    return ok


def teste_dupla_aprovacao_plano(dados):
    # Login do gestor
    s = requests.Session()
    r = s.post(f'{BASE_URL}/entrar', json={
        'email': dados['gestor_email'], 'senha': 'senha123',
    }, timeout=15)
    if r.status_code != 200:
        print(f'  ERRO no login do gestor: {r.status_code} {r.text}')
        return False

    resultados = []
    lock = threading.Lock()

    def tentar():
        try:
            r2 = s.put(
                f'{BASE_URL}/api/v1/gestor/planos/solicitacoes/{dados["sol_id"]}/aprovar',
                json={}, timeout=15,
            )
            status = r2.status_code
        except Exception as e:
            status = f'ERRO: {e}'
        with lock:
            resultados.append(status)

    threads = [threading.Thread(target=tentar) for _ in range(N_THREADS_APROVACAO)]
    for t in threads: t.start()
    for t in threads: t.join()

    n_200 = resultados.count(200)
    n_409 = resultados.count(409)
    outros = [r for r in resultados if r not in (200, 409)]
    print(f'  Resultados: {resultados}')
    print(f'  200 (sucesso): {n_200}  |  409 (conflito): {n_409}  |  outros: {outros}')
    ok = (n_200 == 1 and n_409 == N_THREADS_APROVACAO - 1)
    print(f'  {"PASSOU" if ok else "FALHOU"}: esperado exatamente 1x 200 e {N_THREADS_APROVACAO-1}x 409.')
    return ok


def main():
    print(f'Testando concorrência contra {BASE_URL}')
    print('Preparando dados de teste...')
    dados = setup()
    try:
        print(f'\n[1] {N_THREADS_BOOKING} threads agendando o MESMO slot ({dados["slot_iso"]})...')
        ok1 = teste_double_booking(dados)

        print(f'\n[2] {N_THREADS_APROVACAO} threads aprovando a MESMA solicitação (#{dados["sol_id"]})...')
        ok2 = teste_dupla_aprovacao_plano(dados)

        print('\n=== RESUMO ===')
        print(f'Double-booking:      {"PASSOU" if ok1 else "FALHOU"}')
        print(f'Dupla aprovação:     {"PASSOU" if ok2 else "FALHOU"}')
        sys.exit(0 if (ok1 and ok2) else 1)
    finally:
        print('\nLimpando dados de teste...')
        cleanup(dados)


if __name__ == '__main__':
    main()
