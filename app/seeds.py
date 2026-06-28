"""Seeds idempotentes para dados de plataforma (não dados de barbearia).
Executar via CLI: flask seed-metadata / flask seed-admin
"""
from werkzeug.security import generate_password_hash
from app.extensions import db

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
    db.session.commit()
    print(f'[seed] FeatureMetadata: {len(FEATURES)} features sincronizadas.')


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
        db.session.commit()
        print('[seed] super_admin criado: adm@barbearia.com / 123456')
        print('[AVISO] Altere a senha do super_admin em produção imediatamente.')
    else:
        print('[seed] super_admin já existe.')
