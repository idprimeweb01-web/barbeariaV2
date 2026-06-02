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


@app.route('/init-barbearia')
def init_barbearia():
    from app import db
    from app.models import Barbearia, Usuario
    try:
        slug = 'c.c.barber'
        barbearia = Barbearia.query.filter_by(slug=slug).first()
        if not barbearia:
            barbearia = Barbearia(nome='C.C. Barber', slug=slug, ativo=True)
            db.session.add(barbearia)
            db.session.flush()
            msg_b = f'Barbearia criada: id={barbearia.id}'
        else:
            msg_b = f'Barbearia já existe: id={barbearia.id}'

        usuario = Usuario.query.filter_by(email='adm@barbearia.com').first()
        if usuario:
            usuario.barbearia_id = barbearia.id
            msg_u = 'Admin vinculado à barbearia c.c.barber'
        else:
            msg_u = 'Usuário adm@barbearia.com não encontrado'

        db.session.commit()
        return {'status': 'ok', 'barbearia': msg_b, 'usuario': msg_u, 'slug': slug}, 200
    except Exception as e:
        return {'status': 'erro', 'msg': str(e)}, 500


@app.cli.command('limpar-testes')
def limpar_testes():
    """Apaga dados de teste, mantendo barbearia c.c.barber e adm@barbearia.com."""
    from app import db
    from app.models import (
        Pagamento, AtendimentoItem, ReservaProduto, AgendamentoServico,
        Atendimento, Agendamento, HorarioBloqueado, SolicitacaoLiberacao,
        SolicitacaoSenha, BarbeiroServico, ConfiguracaoAgenda,
        Barbeiro, Servico, Produto, Cliente, Usuario, Barbearia,
    )

    # Preserva barbearia c.c.barber e usuário admin
    barbearia = Barbearia.query.filter_by(slug='c.c.barber').first()
    admin = Usuario.query.filter_by(email='adm@barbearia.com').first()

    barbearia_id = barbearia.id if barbearia else None
    admin_id = admin.id if admin else None

    tabelas = [
        Pagamento, AtendimentoItem, ReservaProduto, AgendamentoServico,
        Atendimento, Agendamento, HorarioBloqueado, SolicitacaoLiberacao,
        SolicitacaoSenha, BarbeiroServico, ConfiguracaoAgenda,
    ]
    for modelo in tabelas:
        n = db.session.query(modelo).delete(synchronize_session=False)
        if n: print(f"  {modelo.__tablename__}: {n} removido(s)")

    # Barbeiros e usuários ligados a eles (exceto admin)
    barbeiros = Barbeiro.query.all()
    for b in barbeiros:
        if b.usuario_id != admin_id:
            u = db.session.get(Usuario, b.usuario_id)
            db.session.delete(b)
            if u: db.session.delete(u)
    print(f"  barbeiros: {len(barbeiros)} removido(s)")

    # Serviços, produtos, clientes
    for modelo in [Servico, Produto, Cliente]:
        n = db.session.query(modelo).delete(synchronize_session=False)
        if n: print(f"  {modelo.__tablename__}: {n} removido(s)")

    # Usuários extras (não admin)
    n = db.session.query(Usuario).filter(Usuario.id != admin_id).delete(synchronize_session=False)
    if n: print(f"  usuarios extras: {n} removido(s)")

    # Barbearias extras (não c.c.barber)
    n = db.session.query(Barbearia).filter(Barbearia.id != barbearia_id).delete(synchronize_session=False)
    if n: print(f"  barbearias extras: {n} removido(s)")

    db.session.commit()
    print("\nOK — banco limpo. Mantidos: c.c.barber + adm@barbearia.com")


if __name__ == "__main__":
    app.run()
