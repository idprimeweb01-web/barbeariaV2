"""
Teste de regressão — Bloco 3 da FASE 2 (A1: limite de uso de cupom por
cliente, achado #6 de AUDITORIA_PRODUCAO.md).

Cenário completo:
  1. Cliente A compra um produto com o cupom (limite_uso_por_cliente=1) →
     201, aprovado pelo gestor → cria o CupomUso que consome a "vaga" dele.
  2. Cliente A tenta comprar de novo com o MESMO cupom (mesma solicitação
     ainda nem precisa ser aprovada — o bloqueio já acontece na criação do
     pedido, em criar_compra) → tem que tomar 422.
  3. Cliente B (nunca usou o cupom) compra com o mesmo cupom → tem que
     funcionar normalmente (201) — o limite é por cliente, não global.

Usa test_client() (in-process, sem concorrência envolvida). Cria seus
próprios dados descartáveis e apaga tudo ao final.

Uso:
    python teste_cupom_limite_cliente.py
"""
import sys

from werkzeug.security import generate_password_hash


def setup(app):
    from app.extensions import db
    from app.models import (
        Barbearia, Usuario, Cliente, Produto, Cupom,
        FeatureMetadata, FeatureBarbearia,
    )
    from app.utils.tz import hoje_brasilia
    from datetime import timedelta

    with app.app_context():
        b = Barbearia(nome='QA Cupom Limite Cliente', slug='qa-cupom-limite-cliente', ativo=True)
        db.session.add(b); db.session.flush()

        for nome_feature in ('produtos_venda', 'cupons'):
            meta = FeatureMetadata.query.filter_by(nome=nome_feature).first()
            if meta:
                db.session.add(FeatureBarbearia(barbearia_id=b.id, feature_id=meta.id, ativo=True))

        ug = Usuario(barbearia_id=b.id, nome='QA Gestor', telefone='11999994000',
                     email='qa.gestor.limitecliente@teste.com', senha=generate_password_hash('senha123'),
                     perfil='gestor', ativo=True)
        cliu_a = Usuario(barbearia_id=b.id, nome='QA Cliente A', telefone='11999994001',
                          email='qa.clientea.limitecliente@teste.com', perfil='cliente', ativo=True,
                          senha=generate_password_hash('senha123'))
        cliu_b = Usuario(barbearia_id=b.id, nome='QA Cliente B', telefone='11999994002',
                          email='qa.clienteb.limitecliente@teste.com', perfil='cliente', ativo=True,
                          senha=generate_password_hash('senha123'))
        db.session.add_all([ug, cliu_a, cliu_b]); db.session.flush()

        cli_a = Cliente(barbearia_id=b.id, usuario_id=cliu_a.id, nome='QA Cliente A',
                         telefone='11999994001', ativo=True)
        cli_b = Cliente(barbearia_id=b.id, usuario_id=cliu_b.id, nome='QA Cliente B',
                         telefone='11999994002', ativo=True)
        db.session.add_all([cli_a, cli_b]); db.session.flush()

        produto = Produto(barbearia_id=b.id, nome='Produto Limite Cliente', preco=100,
                           custo_unitario=40, quantidade_estoque=100, ativo=True)
        db.session.add(produto); db.session.flush()

        cupom = Cupom(
            barbearia_id=b.id, nome='Cupom Primeira Compra', codigo='PRIMEIRA10',
            tipo_desconto='percentual', valor_desconto=10,
            data_expiracao=hoje_brasilia() + timedelta(days=30),
            aplica_todos_produtos=True, ativo=True,
            limite_uso_por_cliente=1,  # o que este bloco introduz
        )
        db.session.add(cupom)
        db.session.commit()

        return {
            'barbearia_id': b.id,
            'gestor_email': 'qa.gestor.limitecliente@teste.com',
            'cliente_a_email': 'qa.clientea.limitecliente@teste.com',
            'cliente_b_email': 'qa.clienteb.limitecliente@teste.com',
            'produto_id': produto.id,
            'cupom_id': cupom.id,
        }


def cleanup(app, dados):
    from app.extensions import db
    from app.models import (
        Barbearia, Usuario, Cliente, Produto, Cupom, CupomUso,
        SolicitacaoCompraProduto, SolicitacaoCompraItem,
        Venda, VendaItem, MovimentacaoEstoque, Notificacao, AuditoriaLog, FeatureBarbearia,
    )

    with app.app_context():
        bid = dados['barbearia_id']
        FeatureBarbearia.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        AuditoriaLog.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Notificacao.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        CupomUso.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        sol_ids = [s.id for s in SolicitacaoCompraProduto.query.filter_by(barbearia_id=bid).all()]
        SolicitacaoCompraItem.query.filter(SolicitacaoCompraItem.solicitacao_id.in_(sol_ids)).delete(synchronize_session=False)
        SolicitacaoCompraProduto.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        venda_ids = [v.id for v in Venda.query.filter_by(barbearia_id=bid).all()]
        VendaItem.query.filter(VendaItem.venda_id.in_(venda_ids)).delete(synchronize_session=False)
        MovimentacaoEstoque.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Venda.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Cupom.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Produto.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Cliente.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Usuario.query.filter_by(barbearia_id=bid).delete(synchronize_session=False)
        Barbearia.query.filter_by(id=bid).delete(synchronize_session=False)
        db.session.commit()


def _login(app, email):
    client = app.test_client()
    r = client.post(f'/b/qa-cupom-limite-cliente/entrar', json={'email': email, 'senha': 'senha123'})
    if r.status_code != 200:
        raise RuntimeError(f'Login de {email} falhou: {r.status_code} {r.get_data(as_text=True)}')
    return client


def _comprar(client, produto_id, cupom_codigo):
    return client.post('/api/v1/cliente/compras', json={
        'itens': [{'produto_id': produto_id, 'quantidade': 1}],
        'cupom_codigo': cupom_codigo,
        'metodo_pagamento': 'dinheiro',
    })


def main():
    from app import create_app
    app = create_app()

    print('Preparando dados de teste...')
    dados = setup(app)
    try:
        gestor = app.test_client()
        r = gestor.post('/entrar', json={'email': dados['gestor_email'], 'senha': 'senha123'})
        if r.status_code != 200:
            print(f'ERRO no login do gestor: {r.status_code} {r.get_data(as_text=True)}')
            sys.exit(1)

        client_a = _login(app, dados['cliente_a_email'])
        client_b = _login(app, dados['cliente_b_email'])

        print('\n[1] Cliente A compra com o cupom (1ª vez)...')
        r1 = _comprar(client_a, dados['produto_id'], 'PRIMEIRA10')
        ok1 = r1.status_code == 201
        print(f'  POST compras -> {r1.status_code} (esperado 201)  {"OK" if ok1 else "FALHOU"}')
        sol_id = r1.get_json().get('solicitacao_id') if ok1 else None

        print('\n[2] Gestor aprova o pedido (cria o CupomUso que consome a vaga da Cliente A)...')
        r2 = gestor.post(f'/api/v1/gestor/compras/{sol_id}/aprovar', json={})
        ok2 = r2.status_code == 200
        print(f'  POST aprovar -> {r2.status_code} (esperado 200)  {"OK" if ok2 else "FALHOU"}')

        print('\n[3] Cliente A tenta comprar de novo com o MESMO cupom...')
        r3 = _comprar(client_a, dados['produto_id'], 'PRIMEIRA10')
        ok3 = r3.status_code == 422
        print(f'  POST compras -> {r3.status_code} (esperado 422 — limite por cliente atingido)  {"OK" if ok3 else "FALHOU"}')
        if ok3:
            print(f'  mensagem: {r3.get_json().get("erro")}')

        print('\n[4] Cliente B (nunca usou) compra com o mesmo cupom...')
        r4 = _comprar(client_b, dados['produto_id'], 'PRIMEIRA10')
        ok4 = r4.status_code == 201
        print(f'  POST compras -> {r4.status_code} (esperado 201 — limite é por cliente, não global)  {"OK" if ok4 else "FALHOU"}')

        print('\n=== RESUMO ===')
        print(f'[1] Cliente A 1ª compra com cupom:                  {"PASSOU" if ok1 else "FALHOU"}')
        print(f'[2] Gestor aprova (consome a vaga da Cliente A):    {"PASSOU" if ok2 else "FALHOU"}')
        print(f'[3] Cliente A bloqueada na 2ª tentativa:             {"PASSOU" if ok3 else "FALHOU"}')
        print(f'[4] Cliente B consegue usar (limite é por cliente): {"PASSOU" if ok4 else "FALHOU"}')
        sys.exit(0 if (ok1 and ok2 and ok3 and ok4) else 1)
    finally:
        print('\nLimpando dados de teste...')
        cleanup(app, dados)


if __name__ == '__main__':
    main()
