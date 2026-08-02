"""
Teste de regressão — Bloco 1 da FASE 2 (corrida aprovar × rejeitar em compras).

Prova que POST /api/v1/gestor/compras/<id>/rejeitar não sobrescreve um pedido
que outra transação já está no meio de aprovar: se outra transação já
segura o lock da linha (FOR UPDATE) e ainda não comitou, rejeitar_compra tem
que ESPERAR, e ao acordar ver o status já mudado e responder 409 — nunca
sobrescrever.

Determinismo: em vez de disparar duas requisições HTTP "ao mesmo tempo" e
torcer pra elas se sobreporem (testado e descartado — com um atraso de 2ms
entre threads, a corrida não se reproduziu nem 1x em 8 tentativas mesmo SEM
a correção, porque o trabalho de rede+DB de uma request rápida pode terminar
antes da outra sequer começar; teste que não falha sem o fix não prova nada),
este teste SEGURA o lock da linha manualmente via uma conexão SQL crua
(simulando uma transação "aprovar" em andamento, sem comitar), só então
dispara a chamada HTTP real de POST .../rejeitar, e só depois libera o lock
(commit) — garantindo a sobreposição de verdade a cada execução, sem depender
de timing.

Usa servidor real (werkzeug.serving.make_server) — necessário pra chamada
HTTP real bloquear de fato no lock do Postgres enquanto a conexão crua
segura a linha (lição já registrada no projeto, Script 17 da refatoração
v1.1: test_client() sozinho não gera contenção de lock genuína).

Uso:
    python teste_compras_concorrencia.py
"""
import os
import sys
import threading
import time

# Precisa ser setado ANTES do `from app import create_app` (dentro de
# iniciar_servidor): com FLASK_ENV=production (valor real do .env local),
# os cookies bos_at/bos_rt saem com Secure=True (Script de segurança
# e1eec07), e requests/http.cookiejar não reenvia cookie Secure numa conexão
# http:// pura — todo request pós-login voltaria 401. O servidor real deste
# teste roda em HTTP puro (localhost), então usamos um FLASK_ENV de teste.
os.environ['FLASK_ENV'] = 'testing'

import requests
from sqlalchemy import text
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server

PORT = 5098
BASE_URL = f'http://127.0.0.1:{PORT}'
N_RODADAS = 6  # trials independentes


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
        Barbearia, Usuario, Cliente, Produto, SolicitacaoCompraProduto, SolicitacaoCompraItem,
        FeatureMetadata, FeatureBarbearia,
    )

    with app.app_context():
        b = Barbearia(nome='QA Compras Concorrencia', slug='qa-compras-concorrencia', ativo=True)
        db.session.add(b); db.session.flush()

        meta = FeatureMetadata.query.filter_by(nome='produtos_venda').first()
        if meta:
            db.session.add(FeatureBarbearia(barbearia_id=b.id, feature_id=meta.id, ativo=True))

        ug = Usuario(barbearia_id=b.id, nome='QA Gestor', telefone='11999992000',
                     email='qa.gestor.compras@teste.com', senha=generate_password_hash('senha123'),
                     perfil='gestor', ativo=True)
        cliu = Usuario(barbearia_id=b.id, nome='QA Cliente', telefone='11999992002',
                        perfil='cliente', ativo=True, senha=generate_password_hash('x'))
        db.session.add_all([ug, cliu]); db.session.flush()

        cli = Cliente(barbearia_id=b.id, usuario_id=cliu.id, nome='QA Cliente',
                       telefone='11999992002', ativo=True)
        db.session.add(cli); db.session.flush()

        produto = Produto(barbearia_id=b.id, nome='Produto Concorrencia', preco=50,
                           custo_unitario=20, quantidade_estoque=1000, ativo=True)
        db.session.add(produto); db.session.flush()

        sol_ids = []
        for _ in range(N_RODADAS):
            sol = SolicitacaoCompraProduto(
                barbearia_id=b.id, cliente_id=cli.id,
                valor_original=50, valor_desconto=0, valor_total=50,
                metodo_pagamento='pix', status='pendente',
            )
            db.session.add(sol); db.session.flush()
            db.session.add(SolicitacaoCompraItem(
                solicitacao_id=sol.id, produto_id=produto.id, quantidade=1, preco_unitario=50,
            ))
            sol_ids.append(sol.id)
        db.session.commit()

        return {
            'barbearia_id': b.id,
            'slug': b.slug,
            'gestor_email': 'qa.gestor.compras@teste.com',
            'produto_id': produto.id,
            'sol_ids': sol_ids,
        }


def cleanup(app, dados):
    from app.extensions import db
    from app.models import (
        Barbearia, Usuario, Cliente, Produto, SolicitacaoCompraProduto, SolicitacaoCompraItem,
        Venda, VendaItem, MovimentacaoEstoque, Notificacao, AuditoriaLog, FeatureBarbearia,
    )

    with app.app_context():
        bid = dados['barbearia_id']
        FeatureBarbearia.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        AuditoriaLog.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Notificacao.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        SolicitacaoCompraItem.query.filter(
            SolicitacaoCompraItem.solicitacao_id.in_(dados['sol_ids'])
        ).delete(synchronize_session=False)
        SolicitacaoCompraProduto.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        venda_ids = [v.id for v in Venda.query.filter_by(barbearia_id=bid).all()]
        VendaItem.query.filter(VendaItem.venda_id.in_(venda_ids)).delete(synchronize_session=False)
        MovimentacaoEstoque.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Venda.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Produto.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Cliente.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Usuario.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Barbearia.query.filter_by(id=bid).delete(synchronize_session=False)
        db.session.commit()


def _login():
    s = requests.Session()
    r = s.post(f'{BASE_URL}/entrar', json={
        'email': 'qa.gestor.compras@teste.com', 'senha': 'senha123',
    }, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f'Login falhou: {r.status_code} {r.text}')
    return s


def testar_rejeitar_contra_lock_segurado(app, session, sol_id):
    """
    Segura o lock da linha (simulando uma transação 'aprovar' em andamento,
    sem comitar) numa conexão SQL separada, dispara o POST real de rejeitar
    NUM THREAD (vai bloquear até o lock ser liberado), confirma que a
    chamada realmente ficou bloqueada (não voltou instantaneamente), libera
    o lock simulando que 'aprovar' venceu, e checa o resultado.
    """
    from app.extensions import db

    with app.app_context():
        engine = db.engine
    conn = engine.connect()
    trans = conn.begin()
    conn.execute(text(
        'SELECT id FROM solicitacao_compra_produto WHERE id = :id FOR UPDATE'
    ), {'id': sol_id})
    # Lock adquirido e transação ainda aberta — estado equivalente ao de
    # aprovar_compra logo após seu próprio `.with_for_update().first()`,
    # antes do commit.

    resultado = {}

    def chamar_rejeitar():
        try:
            resp = session.post(
                f'{BASE_URL}/api/v1/gestor/compras/{sol_id}/rejeitar', json={}, timeout=15,
            )
            resultado['status'] = resp.status_code
        except Exception as e:
            resultado['status'] = f'ERRO: {e}'
        resultado['terminou_em'] = time.monotonic()

    t = threading.Thread(target=chamar_rejeitar)
    t0 = time.monotonic()
    t.start()

    # Dá tempo da request HTTP realmente chegar no servidor e tentar
    # adquirir o lock (bloqueando) antes de liberarmos — não é uma corrida
    # de "quem primeiro", é só garantir que ela teve chance de se anexar à
    # fila de espera do lock antes de soltarmos.
    time.sleep(0.3)
    ainda_bloqueada = t.is_alive()

    # Simula 'aprovar' vencendo: muda o status e comita, liberando o lock.
    conn.execute(text(
        "UPDATE solicitacao_compra_produto SET status = 'aprovada', respondido_em = now() "
        "WHERE id = :id"
    ), {'id': sol_id})
    trans.commit()
    conn.close()

    t.join(timeout=15)
    duracao = resultado.get('terminou_em', time.monotonic()) - t0

    return {
        'sol_id': sol_id,
        'ficou_bloqueada_antes_do_release': ainda_bloqueada,
        'status_http': resultado.get('status'),
        'duracao_s': round(duracao, 3),
    }


def verificar_consistencia_banco(app, resultados):
    from app.extensions import db
    from app.models import SolicitacaoCompraProduto

    ok = True
    with app.app_context():
        for r in resultados:
            sol = db.session.get(SolicitacaoCompraProduto, r['sol_id'])
            if sol.status != 'aprovada':
                print(f'  [sol {sol.id}] INCONSISTENTE: status="{sol.status}" '
                      f'(esperado "aprovada" — rejeitar não pode ter sobrescrito)')
                ok = False
            if sol.motivo_rejeicao is not None:
                print(f'  [sol {sol.id}] INCONSISTENTE: motivo_rejeicao="{sol.motivo_rejeicao}" '
                      f'(deveria ser None — rejeitar não pode ter gravado nada)')
                ok = False
    print(f'  Consistência de banco (nenhum pedido aprovado foi sobrescrito por rejeitar): {"OK" if ok else "FALHOU"}')
    return ok


def main():
    print('Subindo servidor real em background...')
    server, app = iniciar_servidor()
    time.sleep(1)  # tempo pro socket abrir

    print('Preparando dados de teste...')
    dados = setup(app)
    try:
        session = _login()

        print(f'\n[1] {N_RODADAS} trials: lock segurado (simula aprovar em andamento) '
              f'+ POST real de rejeitar concorrente...')
        resultados = []
        for sol_id in dados['sol_ids']:
            r = testar_rejeitar_contra_lock_segurado(app, session, sol_id)
            marca = 'OK' if (r['ficou_bloqueada_antes_do_release'] and r['status_http'] == 409) else 'FALHOU'
            print(f'  [sol {sol_id}] bloqueou_antes_do_release={r["ficou_bloqueada_antes_do_release"]} '
                  f'status_http={r["status_http"]} duracao={r["duracao_s"]}s  -> {marca}')
            resultados.append(r)

        n_bloqueou = sum(1 for r in resultados if r['ficou_bloqueada_antes_do_release'])
        n_409 = sum(1 for r in resultados if r['status_http'] == 409)
        ok1 = (n_bloqueou == N_RODADAS and n_409 == N_RODADAS)
        print(f'\n  Bloquearam de verdade esperando o lock: {n_bloqueou}/{N_RODADAS}')
        print(f'  Responderam 409 (não sobrescreveram):    {n_409}/{N_RODADAS}')

        print('\n[2] Verificando consistência do banco...')
        ok2 = verificar_consistencia_banco(app, resultados)

        print('\n=== RESUMO ===')
        print(f'rejeitar respeita lock concorrente e não sobrescreve: {"PASSOU" if ok1 else "FALHOU"}')
        print(f'Consistência de banco:                                {"PASSOU" if ok2 else "FALHOU"}')
        sys.exit(0 if (ok1 and ok2) else 1)
    finally:
        print('\nLimpando dados de teste...')
        cleanup(app, dados)
        server.shutdown()


if __name__ == '__main__':
    main()
