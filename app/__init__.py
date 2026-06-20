from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
import os

load_dotenv()

db      = SQLAlchemy()
migrate = Migrate()
jwt     = JWTManager()


def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY']                = os.getenv('SECRET_KEY')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY']            = os.getenv('JWT_SECRET_KEY', os.getenv('SECRET_KEY'))

    db_url = os.getenv('DATABASE_URL', '')
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)

    if not db_url:
        print("ERROR: DATABASE_URL is not set!", flush=True)
        # Fallback para desenvolvimento (nunca vai rodar em prod, mas se rodar mostra o erro)
        db_url = 'sqlite:///fallback.db'

    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    print(f"DATABASE_URI set to: {db_url[:50]}...", flush=True)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    from app.routes import main
    from app.routes.auth       import auth
    from app.routes.agenda     import agenda
    from app.routes.catalogo   import catalogo
    from app.routes.caixa      import caixa
    from app.routes.clientes   import clientes
    from app.routes.upload     import upload
    from app.routes.relatorios import relatorios
    from app.routes.publica    import publica
    from app.routes.super_admin  import super_admin
    from app.routes.gestor_admin import gestor_admin

    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(agenda)
    app.register_blueprint(catalogo)
    app.register_blueprint(caixa)
    app.register_blueprint(clientes)
    app.register_blueprint(upload)
    app.register_blueprint(relatorios)
    app.register_blueprint(publica)
    app.register_blueprint(super_admin)
    app.register_blueprint(gestor_admin)

    from app.models import (  # noqa: F401
        Barbearia, Usuario, Barbeiro, Cliente, Servico, BarbeiroServico,
        ConfiguracaoAgenda, Agendamento, AgendamentoServico, HorarioBloqueado, Produto,
        ReservaProduto, Atendimento, AtendimentoItem, Pagamento,
        SolicitacaoSenha, SolicitacaoLiberacao,
        Plano, PlanoServico, ClientePlano, ClientePlanoUso, ClientePlanoSolicitacao,
        VipNivel, ClienteVip, FeatureBarbearia, BarbeariaCustomizacao,
    )

    return app
