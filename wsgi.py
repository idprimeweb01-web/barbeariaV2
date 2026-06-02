import os
import traceback

print(f"DATABASE_URL = {repr(os.getenv('DATABASE_URL'))}", flush=True)
print(f"FLASK_APP = {repr(os.getenv('FLASK_APP'))}", flush=True)

try:
    from app import create_app
    app = create_app()
    print("SUCCESS: app created OK", flush=True)
except Exception as e:
    print(f"FATAL ERROR during app creation: {e}", flush=True)
    traceback.print_exc()
    raise


@app.route('/test')
def test():
    return {'status': 'ok'}, 200


@app.route('/init-admin')
def init_admin():
    from app import db
    from app.models import Barbearia, Usuario
    from werkzeug.security import generate_password_hash
    try:
        barbearia = Barbearia.query.filter_by(slug='admin').first()
        if not barbearia:
            barbearia = Barbearia(nome='Admin', slug='admin')
            db.session.add(barbearia)
            db.session.flush()

        usuario = Usuario.query.filter_by(email='adm@barbearia.com').first()
        if not usuario:
            usuario = Usuario(
                barbearia_id=barbearia.id,
                nome='Admin',
                telefone='00000000000',
                email='adm@barbearia.com',
                senha=generate_password_hash('123456'),
                perfil='super_admin',
                ativo=True,
            )
            db.session.add(usuario)
            msg = 'Usuário criado com sucesso.'
        else:
            usuario.senha = generate_password_hash('123456')
            usuario.ativo = True
            usuario.perfil = 'super_admin'
            msg = 'Senha resetada com sucesso.'

        db.session.commit()
        return {'status': 'ok', 'msg': msg, 'email': 'adm@barbearia.com', 'senha': '123456'}, 200
    except Exception as e:
        return {'status': 'erro', 'msg': str(e)}, 500


@app.cli.command('seed-admin')
def seed_admin():
    """Cria ou reseta o usuário super_admin inicial."""
    from app import db
    from app.models import Barbearia, Usuario
    from werkzeug.security import generate_password_hash

    barbearia = Barbearia.query.filter_by(slug='admin').first()
    if not barbearia:
        barbearia = Barbearia(nome='Admin', slug='admin')
        db.session.add(barbearia)
        db.session.flush()
        print(f"Barbearia criada: id={barbearia.id}")
    else:
        print(f"Barbearia já existe: id={barbearia.id}")

    usuario = Usuario.query.filter_by(email='adm@barbearia.com').first()
    if not usuario:
        usuario = Usuario(
            barbearia_id=barbearia.id,
            nome='Admin',
            telefone='00000000000',
            email='adm@barbearia.com',
            senha=generate_password_hash('123456'),
            perfil='super_admin',
            ativo=True,
        )
        db.session.add(usuario)
        print("Usuário criado.")
    else:
        usuario.senha = generate_password_hash('123456')
        usuario.ativo = True
        usuario.perfil = 'super_admin'
        print("Usuário já existia - senha resetada.")

    db.session.commit()
    print("OK: adm@barbearia.com / 123456")


if __name__ == "__main__":
    app.run()
