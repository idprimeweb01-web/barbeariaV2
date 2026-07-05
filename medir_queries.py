"""
Medição de queries por request — Bloco 5.1 (Script 11).

Liga um listener no evento `before_cursor_execute` do SQLAlchemy pra contar
quantas queries SQL cada request dispara, chama os endpoints afetados pelo
N+1 via test_client, e imprime a contagem ATUAL (pós-correção).

Uso:
    python medir_queries.py
"""
import sys
from datetime import time as time_cls, timedelta
from werkzeug.security import generate_password_hash
from sqlalchemy import event

from app import create_app
from app.extensions import db
from app.models import (
    Barbearia, Usuario, Barbeiro, Cliente, Servico, ConfiguracaoAgenda,
    BarbeiroServico, Agendamento, AgendamentoServico, ClienteNota,
)
from app.utils.tz import naive_brasilia


class ContadorQueries:
    def __init__(self):
        self.n = 0
        self.queries = []

    def __call__(self, conn, cursor, statement, parameters, context, executemany):
        self.n += 1
        self.queries.append(statement.strip().split('\n')[0][:100])

    def reset(self):
        self.n = 0
        self.queries = []


def setup(app):
    with app.app_context():
        b = Barbearia(nome='QA Medicao', slug='qa-medicao', ativo=True)
        db.session.add(b); db.session.flush()

        ug = Usuario(barbearia_id=b.id, nome='QA Gestor M', telefone='11999996001',
                     email='qa.gestor.medicao@teste.com', senha=generate_password_hash('senha123'),
                     perfil='gestor', ativo=True)
        ub = Usuario(barbearia_id=b.id, nome='QA Barbeiro M', telefone='11999996002',
                     email='qa.barbeiro.medicao@teste.com', senha=generate_password_hash('senha123'),
                     perfil='barbeiro', ativo=True)
        db.session.add_all([ug, ub]); db.session.flush()

        barb = Barbeiro(barbearia_id=b.id, usuario_id=ub.id, ativo=True, comissao_percentual=20)
        db.session.add(barb); db.session.flush()

        servicos = []
        for i in range(3):
            s = Servico(barbearia_id=b.id, nome=f'Servico M{i}', preco=30 + i, duracao_minutos=30, ativo=True)
            db.session.add(s); db.session.flush()
            db.session.add(BarbeiroServico(barbeiro_id=barb.id, servico_id=s.id))
            servicos.append(s)

        db.session.add(ConfiguracaoAgenda(
            barbearia_id=b.id, barbeiro_id=barb.id,
            horario_abertura=time_cls(8, 0), horario_fechamento=time_cls(20, 0),
            intervalo_minutos=15, loja_aberta=True,
        ))

        clientes = []
        for i in range(15):
            cliu = Usuario(barbearia_id=b.id, nome=f'QA Cliente M{i}', telefone=f'1199999700{i:02d}',
                            perfil='cliente', ativo=True, senha=generate_password_hash('x'))
            db.session.add(cliu); db.session.flush()
            cli = Cliente(barbearia_id=b.id, usuario_id=cliu.id, nome=f'QA Cliente M{i}', telefone=f'1199999700{i:02d}', ativo=True)
            db.session.add(cli); db.session.flush()
            clientes.append(cli)
            if i % 3 == 0:
                db.session.add(ClienteNota(barbearia_id=b.id, cliente_id=cli.id, tipo='geral', conteudo=f'Nota {i}'))

        hoje = naive_brasilia().date()
        # 15 agendamentos hoje (para a agenda do barbeiro e a listagem)
        for i, cli in enumerate(clientes):
            ag = Agendamento(
                barbearia_id=b.id, cliente_id=cli.id, barbeiro_id=barb.id,
                data_hora=naive_brasilia().replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(minutes=30 * i),
                duracao_minutos=30, status='concluido' if i < 10 else 'agendado',
                valor_total=30, metodo_pagamento='local',
            )
            db.session.add(ag); db.session.flush()
            db.session.add(AgendamentoServico(
                agendamento_id=ag.id, servico_id=servicos[i % 3].id,
                quantidade=1, preco_unitario=30, is_plano=False,
            ))

        # Mais 20 agendamentos concluídos ao longo do mês (pro dashboard)
        for i in range(20):
            cli = clientes[i % len(clientes)]
            ag = Agendamento(
                barbearia_id=b.id, cliente_id=cli.id, barbeiro_id=barb.id,
                data_hora=naive_brasilia().replace(day=1) + timedelta(days=i % 27, hours=1),
                duracao_minutos=30, status='concluido',
                valor_total=30, metodo_pagamento='local',
            )
            db.session.add(ag); db.session.flush()
            db.session.add(AgendamentoServico(
                agendamento_id=ag.id, servico_id=servicos[i % 3].id,
                quantidade=1, preco_unitario=30, is_plano=(i % 2 == 0),
            ))

        # Cliente autenticado de teste, com varios agendamentos (pra medir cliente/agendamentos)
        cliu_login = Usuario(barbearia_id=b.id, nome='QA Cliente Login M', telefone='11999996003',
                              email='qa.cliente.medicao@teste.com', senha=generate_password_hash('senha123'),
                              perfil='cliente', ativo=True)
        db.session.add(cliu_login); db.session.flush()
        cli_login = Cliente(barbearia_id=b.id, usuario_id=cliu_login.id, nome='QA Cliente Login M', telefone='11999996003', ativo=True)
        db.session.add(cli_login); db.session.flush()
        for i in range(12):
            ag = Agendamento(
                barbearia_id=b.id, cliente_id=cli_login.id, barbeiro_id=barb.id,
                data_hora=naive_brasilia() - timedelta(days=i + 1),
                duracao_minutos=30, status='concluido',
                valor_total=30, metodo_pagamento='local',
            )
            db.session.add(ag); db.session.flush()
            db.session.add(AgendamentoServico(
                agendamento_id=ag.id, servico_id=servicos[i % 3].id,
                quantidade=1, preco_unitario=30, is_plano=False,
            ))

        db.session.commit()
        return b.id, barb.id


def cleanup(app, bid):
    with app.app_context():
        from app.models import TokenRevogado
        ag_ids = [a.id for a in Agendamento.query.filter_by(barbearia_id=bid).all()]
        AgendamentoServico.query.filter(AgendamentoServico.agendamento_id.in_(ag_ids)).delete(synchronize_session=False)
        Agendamento.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        ClienteNota.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
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


def main():
    import os
    os.environ.setdefault('DISABLE_SCHEDULER', '1')
    app = create_app()
    bid, barb_id = setup(app)

    contador = ContadorQueries()
    with app.app_context():
        event.listen(db.engine, 'before_cursor_execute', contador)

    client = app.test_client()

    def medir(nome, metodo_chamada):
        contador.reset()
        resp = metodo_chamada()
        print(f'{nome}: {contador.n} queries | HTTP {resp.status_code}')
        if contador.n > 15:
            for q in contador.queries:
                print('   ', q)
        return resp

    try:
        r = client.post('/entrar', json={'email': 'qa.barbeiro.medicao@teste.com', 'senha': 'senha123'})
        assert r.status_code == 200, r.get_json()

        medir('a) GET /api/v1/barbeiro/agendamentos (dia cheio, 15 ags)',
              lambda: client.get('/api/v1/barbeiro/agendamentos'))

        medir('b+c) GET /api/v1/barbeiro/dashboard (mês com 20+ ags)',
              lambda: client.get('/api/v1/barbeiro/dashboard'))

        r3 = client.post('/b/qa-medicao/entrar', json={'email': 'qa.cliente.medicao@teste.com', 'senha': 'senha123'})
        assert r3.status_code == 200, r3.get_json()

        medir('d) GET /api/v1/cliente/agendamentos (12 ags)',
              lambda: client.get('/api/v1/cliente/agendamentos'))

        r2 = client.post('/entrar', json={'email': 'qa.gestor.medicao@teste.com', 'senha': 'senha123'})
        assert r2.status_code == 200, r2.get_json()

        medir('médio) GET /api/v1/gestor/agendamentos (dia cheio, 15 ags)',
              lambda: client.get('/api/v1/gestor/agendamentos'))

        data_hoje = naive_brasilia().date().isoformat()
        medir('médio) GET /api/v1/gestor/agenda/grade',
              lambda: client.get(f'/api/v1/gestor/agenda/grade?barbeiro_id={barb_id}&data={data_hoje}'))

    finally:
        cleanup(app, bid)


if __name__ == '__main__':
    main()
