import os
from app import create_app

app = create_app()


@app.cli.command('seed-metadata')
def cmd_seed_metadata():
    """Popula o catálogo de FeatureMetadata. Idempotente — seguro rodar múltiplas vezes."""
    from app.seeds import seed_feature_metadata
    seed_feature_metadata()


@app.cli.command('seed-admin')
def cmd_seed_admin():
    """Cria barbearia 'admin' e super_admin inicial (adm@barbearia.com / 123456).
    Altere a senha em produção imediatamente após o primeiro acesso."""
    from app.seeds import seed_super_admin
    seed_super_admin()


if __name__ == '__main__':
    app.run()
