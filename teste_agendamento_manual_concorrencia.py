"""
Teste de regressão — Bloco 4 da FASE 2 (M2: double-booking no agendamento
manual do gestor cai em 500 genérico em vez de 409 amigável).

`agendamento_manual` (gestor cria agendamento pelo cliente) verifica conflito
via `verificar_conflito()`, que usa `.with_for_update()` — mas essa trava só
tem o que travar se JÁ existir algum agendamento (committed) daquele
barbeiro naquele dia. Quando é o PRIMEIRO agendamento do barbeiro no dia,
duas requisições concorrentes para o MESMO horário podem passar ambas pela
checagem em Python (nada visível pra travar), e só a constraint única
`uq_ag_barbeiro_slot` no banco pega a corrida no INSERT — a que chega depois
tomava 500 genérico antes deste bloco, porque faltava o try/except
IntegrityError que o fluxo público já tinha.

Determinismo (mesma lição do Bloco 1 — duas requisições HTTP "ao mesmo
tempo" não garantem sobreposição de verdade): este teste SEGURA um INSERT
não comitado do mesmo slot (barbeiro_id + data_hora) numa conexão SQL crua,
simulando uma outra transação que já passou pela checagem de conflito e está
prestes a comitar — o Postgres faz o INSERT real do endpoint ESPERAR até essa
transação decidir (commit = duplicata de verdade, gera IntegrityError). Só
então dispara a chamada HTTP real, garantindo a corrida a cada execução.

Uso:
    python teste_agendamento_manual_concorrencia.py
"""
import os
import sys
import threading
import time
from datetime import timedelta

os.environ['FLASK_ENV'] = 'testing'  # ver nota em teste_compras_concorrencia.py

import requests
from sqlalchemy import text
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server

PORT = 5097
BASE_URL = f'http://127.0.0.1:{PORT}'
N_RODADAS = 6


def iniciar_servidor():
    from app import create_app
    app = create_app()
    server = make_server('127.0.0.1', PORT, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, app


def setup(app):
    from app.extensions import db
    from app.models import Barbearia, Usuario, Barbeiro, Servico, BarbeiroServico, Cliente
    from app.utils.tz import naive_brasilia

    with app.app_context():
        b = Barbearia(nome='QA Agendamento Manual Concorrencia', slug='qa-ag-manual-concorrencia', ativo=True)
        db.session.add(b); db.session.flush()

        ug = Usuario(barbearia_id=b.id, nome='QA Gestor', telefone='11999995000',
                     email='qa.gestor.agmanual@teste.com', senha=generate_password_hash('senha123'),
                     perfil='gestor', ativo=True)
        ub = Usuario(barbearia_id=b.id, nome='QA Barbeiro', telefone='11999995001',
                     perfil='barbeiro', ativo=True, senha=generate_password_hash('x'))
        db.session.add_all([ug, ub]); db.session.flush()

        barb = Barbeiro(barbearia_id=b.id, usuario_id=ub.id, ativo=True)
        db.session.add(barb); db.session.flush()

        sv = Servico(barbearia_id=b.id, nome='Corte QA', preco=30, duracao_minutos=30, ativo=True)
        db.session.add(sv); db.session.flush()
        db.session.add(BarbeiroServico(barbeiro_id=barb.id, servico_id=sv.id))

        # Cliente "fantasma" — dono da linha segurada pela conexão crua,
        # simulando outra requisição concorrente já processada até o INSERT.
        cli_fantasma = Cliente(barbearia_id=b.id, nome='QA Cliente Fantasma', telefone='11999995099', ativo=True)
        db.session.add(cli_fantasma); db.session.flush()
        db.session.commit()

        slots = []
        for i in range(N_RODADAS):
            slot = (naive_brasilia() + timedelta(days=10 + i)).replace(hour=14, minute=0, second=0, microsecond=0)
            slots.append(slot)

        return {
            'barbearia_id': b.id,
            'gestor_email': 'qa.gestor.agmanual@teste.com',
            'barbeiro_id': barb.id,
            'servico_id': sv.id,
            'cliente_fantasma_id': cli_fantasma.id,
            'duracao_minutos': sv.duracao_minutos,
            'slots': slots,
        }


def cleanup(app, dados):
    from app.extensions import db
    from app.models import (
        Barbearia, Usuario, Barbeiro, Servico, BarbeiroServico, Cliente,
        Agendamento, AgendamentoServico, Notificacao, AuditoriaLog,
    )

    with app.app_context():
        bid = dados['barbearia_id']
        AuditoriaLog.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Notificacao.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        ag_ids = [a.id for a in Agendamento.query.filter_by(barbearia_id=bid).all()]
        AgendamentoServico.query.filter(AgendamentoServico.agendamento_id.in_(ag_ids)).delete(synchronize_session=False)
        Agendamento.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Cliente.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        barb_ids = [x.id for x in Barbeiro.query.filter_by(barbearia_id=bid).all()]
        BarbeiroServico.query.filter(BarbeiroServico.barbeiro_id.in_(barb_ids)).delete(synchronize_session=False)
        Servico.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Barbeiro.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Usuario.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Barbearia.query.filter_by(id=bid).delete(synchronize_session=False)
        db.session.commit()


def testar_rodada(app, session, dados, slot):
    """Segura um INSERT não comitado do mesmo slot (simulando outra requisição
    concorrente que já passou pela checagem de conflito), dispara o POST real
    de agendamento-manual NUM THREAD (vai esperar o INSERT decidir), confirma
    que ficou de fato esperando, libera o lock comitando a linha segurada
    (vira duplicata real), e checa o resultado."""
    from app.extensions import db

    with app.app_context():
        engine = db.engine
    conn = engine.connect()
    trans = conn.begin()
    conn.execute(text('''
        INSERT INTO agendamentos
            (barbearia_id, cliente_id, barbeiro_id, data_hora, duracao_minutos,
             status, valor_total, metodo_pagamento, status_pagamento)
        VALUES
            (:barbearia_id, :cliente_id, :barbeiro_id, :data_hora, :duracao_minutos,
             'agendado', 30, 'local', 'pendente')
    '''), {
        'barbearia_id': dados['barbearia_id'], 'cliente_id': dados['cliente_fantasma_id'],
        'barbeiro_id': dados['barbeiro_id'], 'data_hora': slot, 'duracao_minutos': dados['duracao_minutos'],
    })
    # INSERT sem commit ainda — linha existe pra outras transações que tentem
    # inserir o MESMO barbeiro_id+data_hora (a UNIQUE INDEX vai esperar essa
    # decidir), mas invisível a SELECTs simples de outras transações
    # (READ COMMITTED) — por isso verificar_conflito() não vê conflito.

    resultado = {}

    def chamar_endpoint():
        try:
            resp = session.post(f'{BASE_URL}/api/v1/gestor/agenda/agendamento-manual', json={
                'barbeiro_id': dados['barbeiro_id'], 'servico_id': dados['servico_id'],
                'data_hora': slot.isoformat(), 'nome': 'QA Cliente Manual', 'telefone': '11999995002',
            }, timeout=15)
            resultado['status'] = resp.status_code
            try:
                resultado['corpo'] = resp.json()
            except ValueError:
                resultado['corpo'] = None
        except Exception as e:
            resultado['status'] = f'ERRO: {e}'
        resultado['terminou_em'] = time.monotonic()

    t = threading.Thread(target=chamar_endpoint)
    t0 = time.monotonic()
    t.start()

    time.sleep(0.3)
    ainda_bloqueada = t.is_alive()

    trans.commit()  # a linha "fantasma" vira real — INSERT do endpoint (se ainda não tiver falhado) vai bater UniqueViolation
    conn.close()

    t.join(timeout=15)
    duracao = resultado.get('terminou_em', time.monotonic()) - t0

    return {
        'slot': slot.isoformat(),
        'ficou_bloqueada_antes_do_release': ainda_bloqueada,
        'status_http': resultado.get('status'),
        'corpo': resultado.get('corpo'),
        'duracao_s': round(duracao, 3),
    }


def main():
    print('Subindo servidor real em background...')
    server, app = iniciar_servidor()
    time.sleep(1)

    print('Preparando dados de teste...')
    dados = setup(app)
    try:
        session = requests.Session()
        r = session.post(f'{BASE_URL}/entrar', json={'email': dados['gestor_email'], 'senha': 'senha123'}, timeout=15)
        if r.status_code != 200:
            print(f'ERRO no login do gestor: {r.status_code} {r.text}')
            sys.exit(1)

        print(f'\n[1] {N_RODADAS} trials: INSERT segurado (simula outra requisição concorrente) '
              f'+ POST real de agendamento-manual pro MESMO slot...')
        resultados = []
        for slot in dados['slots']:
            r = testar_rodada(app, session, dados, slot)
            marca = 'OK' if (r['ficou_bloqueada_antes_do_release'] and r['status_http'] == 409) else 'FALHOU'
            print(f'  [{r["slot"]}] bloqueou_antes_do_release={r["ficou_bloqueada_antes_do_release"]} '
                  f'status_http={r["status_http"]} duracao={r["duracao_s"]}s  -> {marca}')
            if marca == 'FALHOU' and isinstance(r.get('corpo'), dict):
                print(f'    corpo da resposta: {r["corpo"]}')
            resultados.append(r)

        n_bloqueou = sum(1 for r in resultados if r['ficou_bloqueada_antes_do_release'])
        n_409 = sum(1 for r in resultados if r['status_http'] == 409)
        n_500 = sum(1 for r in resultados if r['status_http'] == 500)
        ok = (n_bloqueou == N_RODADAS and n_409 == N_RODADAS and n_500 == 0)

        print('\n=== RESUMO ===')
        print(f'Bloquearam de verdade esperando o INSERT concorrente: {n_bloqueou}/{N_RODADAS}')
        print(f'Responderam 409 (mensagem amigável):                  {n_409}/{N_RODADAS}')
        print(f'Responderam 500 (erro genérico — o bug original):     {n_500}/{N_RODADAS}')
        print(f'{"PASSOU" if ok else "FALHOU"}')
        sys.exit(0 if ok else 1)
    finally:
        print('\nLimpando dados de teste...')
        cleanup(app, dados)
        server.shutdown()


if __name__ == '__main__':
    main()
