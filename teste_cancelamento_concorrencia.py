"""
Teste de regressão — Bloco 6 da FASE 2 (lock nos 3 endpoints de
cancelamento de agendamento, achado MÉDIO da rodada de verificação de
2026-08-05: TOCTOU sem `.with_for_update()`, diferente do padrão que
`aprovar_compra`/`rejeitar_compra` já tinham desde o Bloco 1).

Prova, pros 3 atores (cliente/gestor/barbeiro), que dois cancelamentos
concorrentes do MESMO agendamento nunca processam os dois: o perdedor da
corrida tem que acordar, ver o status já `cancelado`, e responder com o
erro de "já cancelado" — não reprocessar o estorno de plano, não sobrepor
silenciosamente.

Determinismo: mesma técnica do Bloco 1 — segura o lock da linha via uma
conexão SQL crua (simulando outra transação de cancelamento já em
andamento, sem comitar ainda), só então dispara a chamada HTTP real, e só
libera o lock (simulando esse "outro cancelamento" vencendo: marca
cancelado e apaga o crédito de plano) depois de confirmar que a chamada
real ficou de fato bloqueada esperando.

Usa servidor real (werkzeug.serving.make_server) — necessário pra chamada
HTTP real bloquear de verdade no lock do Postgres.

Uso:
    python teste_cancelamento_concorrencia.py
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

PORT = 5095
BASE_URL = f'http://127.0.0.1:{PORT}'


def iniciar_servidor():
    from app import create_app
    app = create_app()
    server = make_server('127.0.0.1', PORT, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, app


def setup(app):
    from app.extensions import db
    from app.models import (
        Barbearia, Usuario, Barbeiro, Cliente, Servico, BarbeiroServico,
        Plano, PlanoServico, ClientePlano, ClientePlanoUso,
        Agendamento, AgendamentoServico,
    )
    from app.utils.tz import naive_brasilia, hoje_brasilia

    with app.app_context():
        b = Barbearia(nome='QA Cancelamento Concorrencia', slug='qa-cancel-concorrencia', ativo=True)
        db.session.add(b); db.session.flush()

        ug = Usuario(barbearia_id=b.id, nome='QA Gestor', telefone='11999998000',
                     email='qa.gestor.cancelconc@teste.com', senha=generate_password_hash('senha123'),
                     perfil='gestor', ativo=True)
        ub = Usuario(barbearia_id=b.id, nome='QA Barbeiro', telefone='11999998001',
                     email='qa.barbeiro.cancelconc@teste.com', perfil='barbeiro', ativo=True,
                     senha=generate_password_hash('senha123'))
        cliu = Usuario(barbearia_id=b.id, nome='QA Cliente', telefone='11999998002',
                        email='qa.cliente.cancelconc@teste.com', perfil='cliente', ativo=True,
                        senha=generate_password_hash('senha123'))
        db.session.add_all([ug, ub, cliu]); db.session.flush()

        barb = Barbeiro(barbearia_id=b.id, usuario_id=ub.id, ativo=True)
        db.session.add(barb); db.session.flush()

        cli = Cliente(barbearia_id=b.id, usuario_id=cliu.id, nome='QA Cliente',
                      telefone='11999998002', ativo=True)
        db.session.add(cli); db.session.flush()

        # 3 serviços distintos — uq_plano_uso_dia é (cliente_plano_id,
        # servico_id, data_uso); os 3 agendamentos deste teste caem no
        # mesmo dia, então precisam de servico_id diferente entre si.
        servicos = []
        for i in range(3):
            sv = Servico(barbearia_id=b.id, nome=f'Corte QA {i}', preco=50, duracao_minutos=30, ativo=True)
            db.session.add(sv); db.session.flush()
            db.session.add(BarbeiroServico(barbeiro_id=barb.id, servico_id=sv.id))
            servicos.append(sv)

        plano = Plano(barbearia_id=b.id, nome='Plano QA', preco_mensal=99, ativo=True)
        db.session.add(plano); db.session.flush()
        for sv in servicos:
            db.session.add(PlanoServico(plano_id=plano.id, servico_id=sv.id, limite_uso_mensal=99999, dias_expiracao=30, ativo=True))
        cp = ClientePlano(barbearia_id=b.id, cliente_id=cli.id, plano_id=plano.id,
                           data_inicio=hoje_brasilia(), data_fim=hoje_brasilia() + timedelta(days=30), ativo=True)
        db.session.add(cp); db.session.flush()

        slot_base = (naive_brasilia() + timedelta(days=15)).replace(minute=0, second=0, microsecond=0)

        def criar_ag_com_plano(hora, servico):
            dia_hora = slot_base.replace(hour=hora)
            ag = Agendamento(
                barbearia_id=b.id, barbeiro_id=barb.id, cliente_id=cli.id,
                data_hora=dia_hora, duracao_minutos=servico.duracao_minutos,
                valor_total=0, status='agendado', metodo_pagamento='local',
            )
            db.session.add(ag); db.session.flush()
            db.session.add(AgendamentoServico(
                agendamento_id=ag.id, servico_id=servico.id, preco_unitario=servico.preco,
                is_plano=True, cliente_plano_id=cp.id,
            ))
            dia = dia_hora.date()
            db.session.add(ClientePlanoUso(
                cliente_plano_id=cp.id, servico_id=servico.id, data_uso=dia,
                semana_do_mes=((dia.day - 1) // 7) + 1, usado=True,
            ))
            return ag

        ag_cliente = criar_ag_com_plano(9, servicos[0])
        ag_gestor  = criar_ag_com_plano(10, servicos[1])
        ag_barbeiro = criar_ag_com_plano(11, servicos[2])
        db.session.commit()

        return {
            'barbearia_id': b.id,
            'slug': b.slug,
            'gestor_email': 'qa.gestor.cancelconc@teste.com',
            'barbeiro_email': 'qa.barbeiro.cancelconc@teste.com',
            'cliente_email': 'qa.cliente.cancelconc@teste.com',
            'cliente_plano_id': cp.id,
            'ag_cliente': ag_cliente.id,
            'ag_gestor': ag_gestor.id,
            'ag_barbeiro': ag_barbeiro.id,
        }


def cleanup(app, dados):
    from app.extensions import db
    from app.models import (
        Barbearia, Usuario, Barbeiro, Cliente, Servico, BarbeiroServico,
        Plano, PlanoServico, ClientePlano, ClientePlanoUso,
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
        Servico.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Cliente.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Barbeiro.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Usuario.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Barbearia.query.filter_by(id=bid).delete(synchronize_session=False)
        db.session.commit()


def main():
    print('Subindo servidor real em background...')
    server, app = iniciar_servidor()
    time.sleep(1)

    print('Preparando dados de teste...')
    dados = setup(app)
    resultados = []
    try:
        # ── Cliente ──
        s_cli = requests.Session()
        r = s_cli.post(f'{BASE_URL}/b/{dados["slug"]}/entrar', json={
            'email': dados['cliente_email'], 'senha': 'senha123',
        })
        assert r.status_code == 200, f'login cliente falhou: {r.status_code} {r.text}'

        # ── Gestor ──
        s_gestor = requests.Session()
        r = s_gestor.post(f'{BASE_URL}/entrar', json={
            'email': dados['gestor_email'], 'senha': 'senha123',
        })
        assert r.status_code == 200, f'login gestor falhou: {r.status_code} {r.text}'

        # ── Barbeiro ──
        s_barb = requests.Session()
        r = s_barb.post(f'{BASE_URL}/entrar', json={
            'email': dados['barbeiro_email'], 'senha': 'senha123',
        })
        assert r.status_code == 200, f'login barbeiro falhou: {r.status_code} {r.text}'

        print('\n[1] Corrida por ator — lock segurado + cancelamento real concorrente:')

        # cliente: POST, espera 400 (mensagem "já está cancelado", sem status custom)
        def post_cliente():
            return s_cli.post(f'{BASE_URL}/api/v1/cliente/agendamentos/{dados["ag_cliente"]}/cancelar', json={})
        resultados.append(_rodar(app, dados, 'cliente', post_cliente, dados['ag_cliente'],
                                  _servico_da(app, dados, 'ag_cliente'), 400))

        # gestor: PUT, espera 400
        def put_gestor():
            return s_gestor.put(f'{BASE_URL}/api/v1/gestor/agendamentos/{dados["ag_gestor"]}/cancelar', json={})
        resultados.append(_rodar(app, dados, 'gestor', put_gestor, dados['ag_gestor'],
                                  _servico_da(app, dados, 'ag_gestor'), 400))

        # barbeiro: PATCH, espera 422
        def patch_barbeiro():
            return s_barb.patch(f'{BASE_URL}/api/v1/barbeiro/agendamentos/{dados["ag_barbeiro"]}/cancelar', json={})
        resultados.append(_rodar(app, dados, 'barbeiro', patch_barbeiro, dados['ag_barbeiro'],
                                  _servico_da(app, dados, 'ag_barbeiro'), 422))

        ok = all(resultados)
        print('\n=== RESUMO ===')
        print(f'Os 3 atores bloqueiam e respeitam o cancelamento concorrente: {"PASSOU" if ok else "FALHOU"}')
        sys.exit(0 if ok else 1)
    finally:
        print('\nLimpando dados de teste...')
        cleanup(app, dados)
        server.shutdown()


def _servico_da(app, dados, chave):
    from app.models import AgendamentoServico
    with app.app_context():
        item = AgendamentoServico.query.filter_by(agendamento_id=dados[chave]).first()
        return item.servico_id


def _rodar(app, dados, nome, chamada_http, ag_id, servico_id, status_esperado):
    from app.extensions import db
    with app.app_context():
        engine = db.engine
    conn = engine.connect()
    trans = conn.begin()
    conn.execute(text('SELECT id FROM agendamentos WHERE id = :id FOR UPDATE'), {'id': ag_id})

    resultado = {}

    def alvo():
        try:
            resp = chamada_http()
            resultado['status'] = resp.status_code
            try:
                resultado['corpo'] = resp.json()
            except ValueError:
                resultado['corpo'] = None
        except Exception as e:
            resultado['status'] = f'ERRO: {e}'
        resultado['terminou_em'] = time.monotonic()

    t = threading.Thread(target=alvo)
    t0 = time.monotonic()
    t.start()
    time.sleep(0.3)
    ainda_bloqueada = t.is_alive()

    conn.execute(text("UPDATE agendamentos SET status = 'cancelado' WHERE id = :id"), {'id': ag_id})
    conn.execute(text('''
        DELETE FROM cliente_plano_uso
        WHERE cliente_plano_id = :cpid AND servico_id = :sid
    '''), {'cpid': dados['cliente_plano_id'], 'sid': servico_id})
    trans.commit()
    conn.close()

    t.join(timeout=15)
    duracao = resultado.get('terminou_em', time.monotonic()) - t0

    ok_status = resultado.get('status') == status_esperado
    ok = ainda_bloqueada and ok_status
    print(f'  [{nome}] bloqueou_antes_do_release={ainda_bloqueada} '
          f'status_http={resultado.get("status")} (esperado {status_esperado}) '
          f'duracao={round(duracao,3)}s  -> {"OK" if ok else "FALHOU"}')
    if not ok:
        print(f'    corpo: {resultado.get("corpo")}')
    return ok


if __name__ == '__main__':
    main()
