"""Seeds idempotentes para dados de plataforma (não dados de barbearia).
Executar via CLI: flask seed-metadata / flask seed-admin
"""
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.utils.db import commit_ou_falhar

# Features disponíveis na plataforma — ordem é só para legibilidade
FEATURES = [
    ('planos',               'Planos de assinatura mensal para clientes'),
    ('relatorios_avancados', 'Relatórios customizáveis e exportação Excel/PDF'),
    ('vip_brindes',          'Programa VIP com níveis e brindes por fidelidade'),
    ('agendamento_login',    'Exige login do cliente para agendar online'),
    ('historico_cliente',    'Histórico completo de atendimentos por cliente'),
    ('cupons',               'Cupons de desconto para clientes'),
    ('fila_espera',          'Lista de espera para horários lotados'),
    ('comissao',             'Cálculo de comissão por barbeiro (avulso e plano)'),
    ('notificacoes',         'Notificações por SMS/WhatsApp/e-mail'),
    ('pix_integrado',        'Pagamento PIX com comprovante e aprovação manual'),
]


def seed_feature_metadata():
    """Insere ou atualiza o catálogo de features. Seguro para rodar múltiplas vezes."""
    from app.models import FeatureMetadata
    for nome, descricao in FEATURES:
        existente = FeatureMetadata.query.filter_by(nome=nome).first()
        if not existente:
            db.session.add(FeatureMetadata(nome=nome, descricao=descricao))
        elif existente.descricao != descricao:
            existente.descricao = descricao
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
