import os
from datetime import timedelta
from flask import Flask, jsonify
from dotenv import load_dotenv

load_dotenv()

from .extensions import db, migrate, jwt  # noqa: E402 — importado após load_dotenv

# Re-exporta db/migrate/jwt para que imports legados `from app import db` continuem funcionando
__all__ = ['db', 'migrate', 'jwt', 'create_app']


def create_app(config=None):
    app = Flask(__name__)

    # ── Config ────────────────────────────────────────────────────────────────
    database_url = os.environ.get('DATABASE_URL', '')
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    if not database_url:
        raise RuntimeError('DATABASE_URL não está definida no ambiente.')

    jwt_key = os.environ.get('JWT_SECRET_KEY', '')
    if len(jwt_key) < 32:
        raise RuntimeError(
            'JWT_SECRET_KEY deve ter no mínimo 32 bytes. '
            'Gere com: python -c "import secrets; print(secrets.token_hex(32))"'
        )

    app.config.update(
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY=os.environ.get('SECRET_KEY', jwt_key),
        JWT_SECRET_KEY=jwt_key,
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(minutes=15),
        JWT_REFRESH_TOKEN_EXPIRES=timedelta(days=30),
        # JWT: aceita token via header (API clients) OU cookie (browser/telas)
        JWT_TOKEN_LOCATION=['headers', 'cookies'],
        JWT_HEADER_NAME='Authorization',
        JWT_HEADER_TYPE='Bearer',
        JWT_ACCESS_COOKIE_NAME='bos_at',
        JWT_REFRESH_COOKIE_NAME='bos_rt',
        JWT_COOKIE_SECURE=os.environ.get('FLASK_ENV') == 'production',
        JWT_COOKIE_SAMESITE='Lax',
        JWT_COOKIE_CSRF_PROTECT=False,  # SameSite=Lax cobre CSRF; CSRF token seria ruído
        # Flask session (guard de página, não-API)
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    )

    if config:
        app.config.update(config)

    # ── Extensões ─────────────────────────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    # ── Contexto por requisição ───────────────────────────────────────────────
    from .context import load_user_context
    app.before_request(load_user_context)

    # ── Handlers de erro ──────────────────────────────────────────────────────
    from .exceptions import APIError

    @app.errorhandler(APIError)
    def handle_api_error(e):
        return e.to_response()

    @app.errorhandler(404)
    def handle_404(e):
        return jsonify({'erro': 'Recurso não encontrado.'}), 404

    @app.errorhandler(405)
    def handle_405(e):
        return jsonify({'erro': 'Método não permitido.'}), 405

    @app.errorhandler(422)
    def handle_422(e):
        return jsonify({'erro': 'Dados inválidos na requisição.'}), 422

    @app.errorhandler(500)
    def handle_500(e):
        return jsonify({'erro': 'Erro interno do servidor.'}), 500

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get('/health')
    def health():
        return jsonify({'status': 'ok'})

    # ── Models (importados para registrar o metadata no SQLAlchemy / Alembic) ─────
    from . import models  # noqa: F401

    # ── L() disponível em todos os templates Jinja ────────────────────────────
    from .labels import L
    app.jinja_env.globals['L'] = L

    # ── Blueprints ────────────────────────────────────────────────────────────
    from .routes.views import views_bp
    app.register_blueprint(views_bp)

    from .routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    from .routes.super.barbearias import super_bp
    app.register_blueprint(super_bp)

    from .routes.gestor.catalogo import catalogo_bp
    app.register_blueprint(catalogo_bp)

    from .routes.gestor.profissionais import profissionais_bp
    app.register_blueprint(profissionais_bp)

    from .routes.pub.agendamento import pub_bp
    app.register_blueprint(pub_bp)

    from .routes.cliente.agendamento import cliente_bp
    app.register_blueprint(cliente_bp)

    from .routes.gestor.agendamento import gestor_agenda_bp
    app.register_blueprint(gestor_agenda_bp)

    from .routes.gestor.planos import planos_bp
    app.register_blueprint(planos_bp)

    from .routes.pub.planos import pub_planos_bp
    app.register_blueprint(pub_planos_bp)

    from .routes.cliente.planos import cliente_planos_bp
    app.register_blueprint(cliente_planos_bp)

    from .routes.cliente.dashboard import cliente_dash_bp
    app.register_blueprint(cliente_dash_bp)

    from .routes.barbeiro.dashboard import barbeiro_dash_bp
    app.register_blueprint(barbeiro_dash_bp)

    from .routes.gestor.dashboard import gestor_dash_bp
    app.register_blueprint(gestor_dash_bp)

    from .routes.gestor.features import gestor_features_bp
    app.register_blueprint(gestor_features_bp)

    from .routes.super.dashboard import super_dash_bp
    app.register_blueprint(super_dash_bp)

    from .routes.gestor.relatorios import gestor_relatorios_bp
    app.register_blueprint(gestor_relatorios_bp)

    from .routes.gestor.auditoria import gestor_auditoria_bp
    app.register_blueprint(gestor_auditoria_bp)

    from .routes.cliente.notificacoes import cliente_notif_bp
    app.register_blueprint(cliente_notif_bp)

    from .routes.barbeiro.notificacoes import barbeiro_notif_bp
    app.register_blueprint(barbeiro_notif_bp)

    # ── Scheduler de lembretes ────────────────────────────────────────────────
    # Iniciado após todos os blueprints para garantir que os modelos estejam prontos.
    # Em testes unitários, passar DISABLE_SCHEDULER=1 no ambiente para não iniciar.
    if not os.environ.get('DISABLE_SCHEDULER'):
        from .utils.scheduler import iniciar_scheduler
        iniciar_scheduler(app)

    return app
