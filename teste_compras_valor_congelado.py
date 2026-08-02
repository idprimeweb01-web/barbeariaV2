"""
Teste de regressão — Bloco 2 da FASE 2 (C1: honrar valor congelado na
aprovação de compra, em vez de recalcular preço/cupom atuais).

Cobre os 3 cenários do achado C1 de PLANO_DE_ACAO.md:
  1. Preço do produto muda entre o pedido e a aprovação — a Venda tem que
     ficar com o valor que o cliente pagou via PIX, não o preço novo.
  2. Cupom é desativado entre o pedido e a aprovação — aprovação tem que
     concluir mesmo assim, honrando o desconto congelado (não pode travar
     um pedido já pago).
  3. Cupom atinge o limite global de usos entre o pedido e a aprovação —
     aprovação conclui honrando o desconto, CupomUso fica marcado
     honrado_fora_limite=True, e o contador global do cupom NÃO é
     incrementado por essa venda específica.

Usa test_client() (in-process, sem concorrência envolvida — diferente do
Bloco 1, aqui não há disputa de lock pra testar). Cria seus próprios dados
descartáveis e apaga tudo ao final.

Uso:
    python teste_compras_valor_congelado.py
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
        b = Barbearia(nome='QA Valor Congelado', slug='qa-valor-congelado', ativo=True)
        db.session.add(b); db.session.flush()

        for nome_feature in ('produtos_venda', 'cupons'):
            meta = FeatureMetadata.query.filter_by(nome=nome_feature).first()
            if meta:
                db.session.add(FeatureBarbearia(barbearia_id=b.id, feature_id=meta.id, ativo=True))

        ug = Usuario(barbearia_id=b.id, nome='QA Gestor', telefone='11999993000',
                     email='qa.gestor.congelado@teste.com', senha=generate_password_hash('senha123'),
                     perfil='gestor', ativo=True)
        cliu = Usuario(barbearia_id=b.id, nome='QA Cliente', telefone='11999993002',
                        perfil='cliente', ativo=True, senha=generate_password_hash('x'))
        db.session.add_all([ug, cliu]); db.session.flush()

        cli = Cliente(barbearia_id=b.id, usuario_id=cliu.id, nome='QA Cliente',
                       telefone='11999993002', ativo=True)
        db.session.add(cli); db.session.flush()

        # Um produto por cenário, pra não misturar efeitos colaterais entre eles.
        produtos = {}
        for chave in ('preco_mudou', 'cupom_desativado', 'cupom_esgotado'):
            p = Produto(barbearia_id=b.id, nome=f'Produto {chave}', preco=100,
                        custo_unitario=40, quantidade_estoque=100, ativo=True)
            db.session.add(p); db.session.flush()
            produtos[chave] = p.id

        cupom_desativado = Cupom(
            barbearia_id=b.id, nome='Cupom Desativa', codigo='DESATIVA10',
            tipo_desconto='percentual', valor_desconto=50,
            data_expiracao=hoje_brasilia() + timedelta(days=30),
            aplica_todos_produtos=True, ativo=True,
        )
        cupom_esgotado = Cupom(
            barbearia_id=b.id, nome='Cupom Esgota', codigo='ESGOTA10',
            tipo_desconto='percentual', valor_desconto=50,
            data_expiracao=hoje_brasilia() + timedelta(days=30),
            aplica_todos_produtos=True, ativo=True,
            quantidade_maxima_usos=1, quantidade_usos=0,
        )
        db.session.add_all([cupom_desativado, cupom_esgotado])
        db.session.commit()

        return {
            'barbearia_id': b.id,
            'gestor_email': 'qa.gestor.congelado@teste.com',
            'cliente_id': cli.id,
            'produtos': produtos,
            'cupom_desativado_id': cupom_desativado.id,
            'cupom_esgotado_id': cupom_esgotado.id,
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


def _criar_solicitacao_pendente(app, dados, produto_id, cupom_codigo=None, desconto_pct=0):
    """Cria a SolicitacaoCompraProduto direto via ORM, já com valores
    congelados como o endpoint real (cliente/produtos.py::criar_compra)
    faria — preco_unitario do produto NO MOMENTO do pedido."""
    from app.extensions import db
    from app.models import Produto, SolicitacaoCompraProduto, SolicitacaoCompraItem

    with app.app_context():
        produto = db.session.get(Produto, produto_id)
        preco_no_pedido = float(produto.preco)
        valor_original = preco_no_pedido * 1  # quantidade=1
        valor_desconto = round(valor_original * desconto_pct / 100, 2)
        valor_total = round(valor_original - valor_desconto, 2)

        sol = SolicitacaoCompraProduto(
            barbearia_id=dados['barbearia_id'], cliente_id=dados['cliente_id'],
            valor_original=valor_original, valor_desconto=valor_desconto, valor_total=valor_total,
            cupom_codigo=cupom_codigo, metodo_pagamento='pix', status='pendente',
        )
        db.session.add(sol); db.session.flush()
        db.session.add(SolicitacaoCompraItem(
            solicitacao_id=sol.id, produto_id=produto_id, quantidade=1, preco_unitario=preco_no_pedido,
        ))
        db.session.commit()
        return sol.id, valor_total, preco_no_pedido


def cenario_1_preco_mudou(app, client, dados):
    print('\n[Cenário 1] Preço do produto muda entre pedido e aprovação')
    from app.extensions import db
    from app.models import Produto, SolicitacaoCompraProduto, Venda

    produto_id = dados['produtos']['preco_mudou']
    sol_id, valor_congelado, preco_no_pedido = _criar_solicitacao_pendente(app, dados, produto_id)
    print(f'  Pedido criado: preço no pedido=R${preco_no_pedido:.2f}, valor_total congelado=R${valor_congelado:.2f}')

    with app.app_context():
        produto = db.session.get(Produto, produto_id)
        produto.preco = 250  # gestor muda o preço antes de aprovar
        db.session.commit()
        print('  Preço do produto alterado pelo gestor para R$250,00 (antes de aprovar).')

    resp = client.post(f'/api/v1/gestor/compras/{sol_id}/aprovar', json={})
    ok_http = resp.status_code == 200
    print(f'  POST aprovar -> {resp.status_code}')

    with app.app_context():
        sol = db.session.get(SolicitacaoCompraProduto, sol_id)
        venda = db.session.get(Venda, sol.venda_id) if sol.venda_id else None
        valor_venda = float(venda.valor_total) if venda else None

    ok_valor = venda is not None and abs(valor_venda - valor_congelado) < 0.01
    print(f'  venda.valor_total={valor_venda}  (esperado={valor_congelado})')
    ok = ok_http and ok_valor
    print(f'  {"PASSOU" if ok else "FALHOU"}')
    return ok


def cenario_2_cupom_desativado(app, client, dados):
    print('\n[Cenário 2] Cupom é desativado entre pedido e aprovação')
    from app.extensions import db
    from app.models import Cupom, SolicitacaoCompraProduto, Venda

    produto_id = dados['produtos']['cupom_desativado']
    sol_id, valor_congelado, _ = _criar_solicitacao_pendente(
        app, dados, produto_id, cupom_codigo='DESATIVA10', desconto_pct=50,
    )
    print(f'  Pedido criado com cupom DESATIVA10 (50%), valor_total congelado=R${valor_congelado:.2f}')

    with app.app_context():
        cupom = db.session.get(Cupom, dados['cupom_desativado_id'])
        cupom.ativo = False
        db.session.commit()
        print('  Cupom DESATIVA10 desativado pelo gestor (antes de aprovar).')

    resp = client.post(f'/api/v1/gestor/compras/{sol_id}/aprovar', json={})
    ok_http = resp.status_code == 200
    print(f'  POST aprovar -> {resp.status_code} (esperado 200 — não pode travar pedido já pago)')

    with app.app_context():
        sol = db.session.get(SolicitacaoCompraProduto, sol_id)
        venda = db.session.get(Venda, sol.venda_id) if sol.venda_id else None
        valor_venda = float(venda.valor_total) if venda else None

    ok_valor = venda is not None and abs(valor_venda - valor_congelado) < 0.01
    print(f'  venda.valor_total={valor_venda}  (esperado={valor_congelado})')
    ok = ok_http and ok_valor
    print(f'  {"PASSOU" if ok else "FALHOU"}')
    return ok


def cenario_3_cupom_esgotado(app, client, dados):
    print('\n[Cenário 3] Cupom atinge o limite global entre pedido e aprovação')
    from app.extensions import db
    from app.models import Cupom, CupomUso, SolicitacaoCompraProduto, Venda

    produto_id = dados['produtos']['cupom_esgotado']
    sol_id, valor_congelado, _ = _criar_solicitacao_pendente(
        app, dados, produto_id, cupom_codigo='ESGOTA10', desconto_pct=50,
    )
    print(f'  Pedido criado com cupom ESGOTA10 (50%, limite=1 uso), valor_total congelado=R${valor_congelado:.2f}')

    with app.app_context():
        # Simula outra venda consumindo o único uso disponível antes desta aprovação.
        from app.utils.cupons import incrementar_uso_cupom
        incrementar_uso_cupom(dados['cupom_esgotado_id'], dados['barbearia_id'])
        db.session.commit()
        cupom_antes = db.session.get(Cupom, dados['cupom_esgotado_id'])
        contador_antes = cupom_antes.quantidade_usos
        print(f'  Limite do cupom esgotado por outra venda (quantidade_usos={contador_antes}).')

    resp = client.post(f'/api/v1/gestor/compras/{sol_id}/aprovar', json={})
    ok_http = resp.status_code == 200
    print(f'  POST aprovar -> {resp.status_code} (esperado 200 — não pode travar pedido já pago)')

    with app.app_context():
        sol = db.session.get(SolicitacaoCompraProduto, sol_id)
        venda = db.session.get(Venda, sol.venda_id) if sol.venda_id else None
        valor_venda = float(venda.valor_total) if venda else None
        cupom_depois = db.session.get(Cupom, dados['cupom_esgotado_id'])
        uso = CupomUso.query.filter_by(venda_id=(venda.id if venda else -1)).first()

    ok_valor = venda is not None and abs(valor_venda - valor_congelado) < 0.01
    ok_contador_nao_incrementou = (cupom_depois.quantidade_usos == contador_antes)
    ok_marcado = uso is not None and uso.honrado_fora_limite is True
    print(f'  venda.valor_total={valor_venda}  (esperado={valor_congelado})')
    print(f'  cupom.quantidade_usos antes={contador_antes} depois={cupom_depois.quantidade_usos} '
          f'(esperado inalterado — não pode incrementar além do limite)')
    print(f'  CupomUso.honrado_fora_limite={uso.honrado_fora_limite if uso else None} (esperado True)')
    ok = ok_http and ok_valor and ok_contador_nao_incrementou and ok_marcado
    print(f'  {"PASSOU" if ok else "FALHOU"}')
    return ok


def main():
    from app import create_app
    app = create_app()

    print('Preparando dados de teste...')
    dados = setup(app)
    try:
        client = app.test_client()
        r = client.post('/entrar', json={'email': dados['gestor_email'], 'senha': 'senha123'})
        if r.status_code != 200:
            print(f'ERRO no login: {r.status_code} {r.get_data(as_text=True)}')
            sys.exit(1)

        r1 = cenario_1_preco_mudou(app, client, dados)
        r2 = cenario_2_cupom_desativado(app, client, dados)
        r3 = cenario_3_cupom_esgotado(app, client, dados)

        print('\n=== RESUMO ===')
        print(f'[1] Preço mudou, venda honra valor congelado:        {"PASSOU" if r1 else "FALHOU"}')
        print(f'[2] Cupom desativado, aprovação conclui honrando:    {"PASSOU" if r2 else "FALHOU"}')
        print(f'[3] Cupom esgotado, honra sem incrementar contador:  {"PASSOU" if r3 else "FALHOU"}')
        sys.exit(0 if (r1 and r2 and r3) else 1)
    finally:
        print('\nLimpando dados de teste...')
        cleanup(app, dados)


if __name__ == '__main__':
    main()
