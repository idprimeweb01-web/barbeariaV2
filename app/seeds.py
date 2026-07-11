"""Seeds idempotentes para dados de plataforma (não dados de barbearia).
Executar via CLI: flask seed-metadata / flask seed-admin
"""
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.utils.db import commit_ou_falhar

# Features disponíveis na plataforma — ordem é só para legibilidade.
# 3º elemento (ativo_por_padrao): quando True e a feature é NOVA (inserida
# agora pela 1ª vez), todas as barbearias JÁ EXISTENTES ganham
# FeatureBarbearia(ativo=True) automaticamente — ver seed_feature_metadata().
FEATURES = [
    ('planos',               'Planos de assinatura mensal para clientes', False),
    ('relatorios_avancados', 'Relatórios customizáveis e exportação Excel/PDF', False),
    ('vip_brindes',          'Programa VIP com níveis e brindes por fidelidade', False),
    ('agendamento_login',    'Exige login do cliente para agendar online', False),
    ('historico_cliente',    'Histórico completo de atendimentos por cliente', False),
    ('cupons',               'Cupons de desconto para clientes', False),
    ('fila_espera',          'Lista de espera para horários lotados', False),
    ('comissao',             'Cálculo de comissão por barbeiro (avulso e plano)', False),
    ('notificacoes',         'Notificações por SMS/WhatsApp/e-mail', False),
    ('pix_integrado',        'Pagamento PIX com comprovante e aprovação manual', False),
    ('produtos_venda',       'Venda avulsa de produtos com controle de estoque', True),
]


def seed_feature_metadata():
    """Insere ou atualiza o catálogo de features. Seguro para rodar múltiplas vezes.
    Features NOVAS com ativo_por_padrao=True ativam automaticamente para
    todas as barbearias já existentes (só na criação — nunca reativa algo
    que o gestor tenha desligado manualmente depois)."""
    from app.models import FeatureMetadata, FeatureBarbearia, Barbearia
    novas_ativas_por_padrao = []
    for nome, descricao, ativo_por_padrao in FEATURES:
        existente = FeatureMetadata.query.filter_by(nome=nome).first()
        if not existente:
            meta = FeatureMetadata(nome=nome, descricao=descricao, ativo_por_padrao=ativo_por_padrao)
            db.session.add(meta)
            db.session.flush()
            if ativo_por_padrao:
                novas_ativas_por_padrao.append(meta)
        elif existente.descricao != descricao:
            existente.descricao = descricao

    if novas_ativas_por_padrao:
        barbearia_ids = [b.id for b in Barbearia.query.all()]
        for meta in novas_ativas_por_padrao:
            for bid in barbearia_ids:
                db.session.add(FeatureBarbearia(barbearia_id=bid, feature_id=meta.id, ativo=True))
            print(f'[seed] Feature "{meta.nome}" ativada por padrão para {len(barbearia_ids)} barbearia(s) existente(s).')

    commit_ou_falhar('seeds.seed_feature_metadata')
    print(f'[seed] FeatureMetadata: {len(FEATURES)} features sincronizadas.')


_SEGMENTOS = [
    ('barbearia', 'Barbearia', {
        'rotulo_tenant': 'Barbearia', 'rotulo_tenant_plural': 'Barbearias',
        'rotulo_profissional': 'Barbeiro', 'rotulo_profissional_plural': 'Barbeiros',
        'rotulo_servico': 'Serviço', 'rotulo_servico_plural': 'Serviços',
        'rotulo_agendamento': 'Agendamento', 'rotulo_agendamento_plural': 'Agendamentos',
        'rotulo_cliente': 'Cliente', 'rotulo_cliente_plural': 'Clientes',
        'rotulo_produto': 'Produto', 'rotulo_produto_plural': 'Produtos',
        'rotulo_plano': 'Plano', 'rotulo_plano_plural': 'Planos',
        'rotulo_pagamento': 'Pagamento', 'rotulo_faturamento': 'Faturamento',
        'rotulo_relatorio': 'Relatório',
    }),
    ('salao', 'Salão de Beleza', {
        'rotulo_tenant': 'Salão', 'rotulo_tenant_plural': 'Salões',
        'rotulo_profissional': 'Cabeleireira', 'rotulo_profissional_plural': 'Cabeleireiras',
        'rotulo_servico': 'Tratamento', 'rotulo_servico_plural': 'Tratamentos',
        'rotulo_agendamento': 'Sessão', 'rotulo_agendamento_plural': 'Sessões',
        'rotulo_cliente': 'Cliente', 'rotulo_cliente_plural': 'Clientes',
        'rotulo_produto': 'Produto', 'rotulo_produto_plural': 'Produtos',
        'rotulo_plano': 'Pacote', 'rotulo_plano_plural': 'Pacotes',
        'rotulo_pagamento': 'Pagamento', 'rotulo_faturamento': 'Faturamento',
        'rotulo_relatorio': 'Relatório',
    }),
    ('manicure', 'Nail Art / Manicure', {
        'rotulo_tenant': 'Ateliê', 'rotulo_tenant_plural': 'Ateliês',
        'rotulo_profissional': 'Manicure', 'rotulo_profissional_plural': 'Manicures',
        'rotulo_servico': 'Design', 'rotulo_servico_plural': 'Designs',
        'rotulo_agendamento': 'Sessão', 'rotulo_agendamento_plural': 'Sessões',
        'rotulo_cliente': 'Cliente', 'rotulo_cliente_plural': 'Clientes',
        'rotulo_produto': 'Material', 'rotulo_produto_plural': 'Materiais',
        'rotulo_plano': 'Pacote', 'rotulo_plano_plural': 'Pacotes',
        'rotulo_pagamento': 'Pagamento', 'rotulo_faturamento': 'Faturamento',
        'rotulo_relatorio': 'Relatório',
    }),
    ('clinica', 'Clínica', {
        'rotulo_tenant': 'Clínica', 'rotulo_tenant_plural': 'Clínicas',
        'rotulo_profissional': 'Médico', 'rotulo_profissional_plural': 'Médicos',
        'rotulo_servico': 'Procedimento', 'rotulo_servico_plural': 'Procedimentos',
        'rotulo_agendamento': 'Consulta', 'rotulo_agendamento_plural': 'Consultas',
        'rotulo_cliente': 'Paciente', 'rotulo_cliente_plural': 'Pacientes',
        'rotulo_produto': 'Medicamento', 'rotulo_produto_plural': 'Medicamentos',
        'rotulo_plano': 'Programa', 'rotulo_plano_plural': 'Programas',
        'rotulo_pagamento': 'Pagamento', 'rotulo_faturamento': 'Faturamento',
        'rotulo_relatorio': 'Relatório',
    }),
]


def seed_segmentos():
    """Insere ou atualiza os segmentos de mercado e seus rótulos. Idempotente."""
    from app.models import Segmento, SegmentoRotulo
    from app.labels import L

    for chave, nome, cols in _SEGMENTOS:
        seg = Segmento.query.filter_by(chave=chave).first()
        if not seg:
            seg = Segmento(nome=nome, chave=chave)
            db.session.add(seg)
            db.session.flush()
            print(f'[seed] Segmento "{chave}" criado.')
        else:
            seg.nome = nome

        row = SegmentoRotulo.query.filter_by(segmento_id=seg.id).first()
        if not row:
            row = SegmentoRotulo(segmento_id=seg.id)
            db.session.add(row)
        for col, val in cols.items():
            setattr(row, col, val)

    commit_ou_falhar('seeds.seed_segmentos')
    L.invalidar()
    print(f'[seed] {len(_SEGMENTOS)} segmentos sincronizados.')


# Combinação padrão de features por segmento — dados de PRODUTO, ainda não
# validados com o dono (placeholder ilustrativo, ver MODELAGEM_FEATURES_POR_SEGMENTO.md
# C.2 item 7). Ajustar antes de considerar definitivo.
_SEGMENTO_FEATURES_PADRAO = {
    'barbearia': {'produtos_venda': True, 'comissao': True, 'notificacoes': True},
    'salao':     {'produtos_venda': True, 'planos': True, 'vip_brindes': True},
    'manicure':  {'produtos_venda': True},
    'clinica':   {'historico_cliente': True, 'notificacoes': True},
}


def seed_segmento_feature_padrao():
    """Popula os padrões de feature por segmento. Idempotente."""
    from app.models import Segmento, FeatureMetadata, SegmentoFeaturePadrao
    for chave, features in _SEGMENTO_FEATURES_PADRAO.items():
        seg = Segmento.query.filter_by(chave=chave).first()
        if not seg:
            continue
        for nome_feature, ativo in features.items():
            fm = FeatureMetadata.query.filter_by(nome=nome_feature).first()
            if not fm:
                continue
            row = SegmentoFeaturePadrao.query.filter_by(
                segmento_id=seg.id, feature_id=fm.id
            ).first()
            if not row:
                row = SegmentoFeaturePadrao(segmento_id=seg.id, feature_id=fm.id)
                db.session.add(row)
            row.ativo_por_padrao = ativo

    commit_ou_falhar('seeds.seed_segmento_feature_padrao')
    print('[seed] SegmentoFeaturePadrao sincronizado.')


def seed_super_admin():
    """Cria barbearia 'admin' e usuário super_admin inicial se ainda não existirem."""
    from app.models import Barbearia, Usuario
    barbearia = Barbearia.query.filter_by(slug='admin').first()
    if not barbearia:
        barbearia = Barbearia(nome='Administração', slug='admin', ativo=True)
        db.session.add(barbearia)
        db.session.flush()
        print('[seed] Barbearia "admin" criada.')
    else:
        print('[seed] Barbearia "admin" já existe.')

    admin = Usuario.query.filter_by(perfil='super_admin').first()
    if not admin:
        admin = Usuario(
            barbearia_id=None,
            nome='Super Admin',
            telefone='00000000000',
            email='adm@barbearia.com',
            senha=generate_password_hash('123456'),
            perfil='super_admin',
            ativo=True,
        )
        db.session.add(admin)
        commit_ou_falhar('seeds.seed_super_admin')
        print('[seed] super_admin criado: adm@barbearia.com / 123456')
        print('[AVISO] Altere a senha do super_admin em produção imediatamente.')
    else:
        print('[seed] super_admin já existe.')
