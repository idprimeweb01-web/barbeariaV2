"""
Script de seed para PRODUÇÃO.
Executa UMA VEZ ao fazer o primeiro deploy.

Uso:
    flask seed-prod
    OU: python seeds_prod.py

Diferente de app/seeds.py (desenvolvimento), este script:
- Lê email/senha de variáveis de ambiente (ADMIN_EMAIL, ADMIN_SENHA)
- Se ADMIN_SENHA não for definida, gera senha aleatória e imprime UMA VEZ
- NÃO insere dados de teste
"""
import os
import secrets
import string


def gerar_senha_forte(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + '!@#$%^&*'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def seed_producao():
    from werkzeug.security import generate_password_hash
    from app.extensions import db
    from app.models import Barbearia, Usuario, FeatureMetadata

    # ── Features ────────────────────────────────────────────────────────────────
    from app.seeds import seed_feature_metadata
    seed_feature_metadata()

    # ── Barbearia admin ──────────────────────────────────────────────────────────
    barbearia = Barbearia.query.filter_by(slug='admin').first()
    if not barbearia:
        barbearia = Barbearia(nome='Administração', slug='admin', ativo=True)
        db.session.add(barbearia)
        db.session.flush()
        print('[prod-seed] Barbearia "admin" criada.')

    # ── Super Admin ──────────────────────────────────────────────────────────────
    existente = Usuario.query.filter_by(perfil='super_admin').first()
    if existente:
        print(f'[prod-seed] super_admin já existe: {existente.email}')
        print('[prod-seed] Senha NÃO foi alterada. Para resetar, delete o usuário e rode novamente.')
        return

    email = os.environ.get('ADMIN_EMAIL', 'admin@seudominio.com.br')
    senha = os.environ.get('ADMIN_SENHA') or gerar_senha_forte()
    senha_gerada = 'ADMIN_SENHA' not in os.environ

    admin = Usuario(
        barbearia_id=None,
        nome='Super Admin',
        telefone='00000000000',
        email=email,
        senha=generate_password_hash(senha),
        perfil='super_admin',
        ativo=True,
    )
    db.session.add(admin)
    db.session.commit()

    print()
    print('=' * 60)
    print('  SUPER ADMIN CRIADO — ANOTE ESSAS CREDENCIAIS AGORA')
    print('=' * 60)
    print(f'  Email: {email}')
    print(f'  Senha: {senha}')
    if senha_gerada:
        print()
        print('  ⚠️  Senha gerada aleatoriamente.')
        print('  Defina ADMIN_SENHA no Railway para controlar a senha.')
    print('=' * 60)
    print()


if __name__ == '__main__':
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from app import create_app
    app = create_app()
    with app.app_context():
        seed_producao()
