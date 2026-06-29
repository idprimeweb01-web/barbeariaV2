"""
Zera o banco e cria o super admin.
Uso: python criar_super_admin.py
"""
import sys
from app import create_app, db
from app.models import Usuario
from werkzeug.security import generate_password_hash

EMAIL = "adm@barbearia.com"
SENHA = "123456"

app = create_app()
with app.app_context():
    # Apaga e recria todas as tabelas
    db.drop_all()
    db.create_all()
    print("Banco zerado e recriado.")

    u = Usuario(
        nome="Super Admin",
        telefone="11999999999",
        email=EMAIL,
        senha=generate_password_hash(SENHA),
        perfil="super_admin",
        barbearia_id=None,
        ativo=True,
    )
    db.session.add(u)
    db.session.commit()

    print(f"\nSuper admin criado!")
    print(f"  Email : {EMAIL}")
    print(f"  Senha : {SENHA}")
    print(f"  Perfil: super_admin")
