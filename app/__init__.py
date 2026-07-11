import os
import sys
import logging
from datetime import timedelta
from flask import Flask, jsonify
from dotenv import load_dotenv

load_dotenv()

from .extensions import db, migrate, jwt, limiter  # noqa: E402 — importado após load_dotenv

# Re-exporta db/migrate/jwt para que imports legados `from app import db` continuem funcionando
__all__ = ['db', 'migrate', 'jwt', 'limiter', 'create_app']


# Trechos que denunciam uma chave-placeholder esquecida no .env (Script 19/
# Bloco 1.1). Checagem case-insensitive — cobre os placeholders já vistos
# neste projeto (SECRET_KEY='your-secret-key-here', JWT_SECRET_KEY continha
# 'SUBSTITUA-POR-...' — esse último passava no check de 32+ chars mas era
# claramente um lembrete não preenchido).
_KNOWN_BAD = (
    'your-secret-key', 'dev-secret', 'test-secret', 'substitua',
    'change-me', 'changeme', 'secret-key-here',
)


def _validar_chave_secreta(nome: str, valor: str) -> None:
    """Levanta RuntimeError se `valor` (SECRET_KEY ou JWT_SECRET_KEY) parecer
    um placeholder esquecido: curto demais, contém um trecho conhecido de
    placeholder, ou tem entropia baixa demais (ex: 'aaaaaa...aaaa')."""
    if len(valor) < 32:
        raise RuntimeError(
            f'{nome} deve ter no mínimo 32 bytes. '
            'Gere com: python -c "import secrets; print(secrets.token_hex(32))"'
        )

    valor_lower = valor.lower()
    for trecho in _KNOWN_BAD:
        if trecho in valor_lower:
            raise RuntimeError(
                f'{nome} parece um placeholder esquecido (contém "{trecho}"). '
                'Gere uma chave real com: '
                'python -c "import secrets; print(secrets.token_hex(32))"'
            )

    # Entropia mínima: nenhum caractere pode dominar mais de 50% da string
    # (pega placeholders tipo 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa').
    contagens = {}
    for c in valor:
        contagens[c] = contagens.get(c, 0) + 1
    if contagens and max(contagens.values()) / len(valor) > 0.5:
        raise RuntimeError(
            f'{nome} tem entropia baixa demais para ser uma chave real (um único '
            'caractere domina mais de 50% do valor). Gere uma chave real com: '
            'python -c "import secrets; print(secrets.token_hex(32))"'
        )


def _configurar_logging():
    """Garante que logger.error(...) dos módulos da aplicação (ex: commit_ou_falhar)
    apareça com timestamp em stdout — é o que gunicorn/Railway coletam como log
    (Procfile já usa --error-logfile -). Idempotente: não duplica handler se
    create_app() for chamado mais de uma vez (ex: testes)."""
    root = logging.getLogger()
    if root.handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
        stream=sys.stdout,
    )


def create_app(config=None):
    _configurar_logging()
    app = Flask(__name__)

    # ── Config ────────────────────────────────────────────────────────────────
    database_url = os.environ.get('DATABASE_URL', '')
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    if not database_url:
        raise RuntimeError('DATABASE_URL não está definida no ambiente.')

    jwt_key = os.environ.get('JWT_SECRET_KEY', '')
    _validar_chave_secreta('JWT_SECRET_KEY', jwt_key)

    secret_key = os.environ.get('SECRET_KEY', '') or jwt_key
    _validar_chave_secreta('SECRET_KEY', secret_key)

    app.config.update(
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY=secret_key,
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
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=(os.environ.get('FLASK_ENV') == 'production'),
    )

    if config:
        app.config.update(config)

    # ── Extensões ─────────────────────────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)

    # ── Cloudinary (Script 19/Bloco 1.1) ─────────────────────────────────────
    # Configurado UMA vez aqui no startup — antes, cloudinary.config(...) era
    # chamado de novo a cada request em 3 arquivos de rota diferentes
    # (pub/agendamento.py, super/barbearias.py, gestor/catalogo.py), o que é
    # redundante (a config é global no SDK, não por-request) e espalha a
    # leitura das env vars por vários lugares.
    import cloudinary
    cloudinary.config(
        cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
        api_key=os.environ.get('CLOUDINARY_API_KEY'),
        api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
    )

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

    @app.errorhandler(429)
    def handle_429(e):
        return jsonify({'erro': 'Muitas tentativas. Aguarde um instante e tente novamente.'}), 429

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get('/health')
    @limiter.exempt
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

    from .routes.gestor.clientes import gestor_clientes_bp
    app.register_blueprint(gestor_clientes_bp)

    from .routes.gestor.barbearia import gestor_barbearia_bp
    app.register_blueprint(gestor_barbearia_bp)

    from .routes.cliente.notificacoes import cliente_notif_bp
    app.register_blueprint(cliente_notif_bp)

    from .routes.barbeiro.notificacoes import barbeiro_notif_bp
    app.register_blueprint(barbeiro_notif_bp)

    from .routes.barbeiro.agendamentos import barbeiro_ag_bp
    app.register_blueprint(barbeiro_ag_bp)

    from .routes.barbeiro.horario import barbeiro_horario_bp
    app.register_blueprint(barbeiro_horario_bp)

    from .routes.barbeiro.clientes import barbeiro_cli_bp
    app.register_blueprint(barbeiro_cli_bp)

    from .routes.gestor.cupons import cupons_bp
    app.register_blueprint(cupons_bp)

    from .routes.cliente.cupons import cliente_cupons_bp
    app.register_blueprint(cliente_cupons_bp)

    from .routes.cliente.perfil import cliente_perfil_bp
    app.register_blueprint(cliente_perfil_bp)

    from .routes.vip import vip_bp
    app.register_blueprint(vip_bp)

    from .routes.gestor.estoque import gestor_estoque_bp
    app.register_blueprint(gestor_estoque_bp)

    from .routes.gestor.vendas import gestor_vendas_bp
    app.register_blueprint(gestor_vendas_bp)

    from .routes.barbeiro.vendas import barbeiro_vendas_bp
    app.register_blueprint(barbeiro_vendas_bp)

    from .routes.barbeiro.produtos import barbeiro_produtos_bp
    app.register_blueprint(barbeiro_produtos_bp)

    from .routes.barbeiro.caixa import barbeiro_caixa_bp
    app.register_blueprint(barbeiro_caixa_bp)

    # ── Scheduler de lembretes ────────────────────────────────────────────────
    # Iniciado após todos os blueprints para garantir que os modelos estejam prontos.
    # Em testes unitários, passar DISABLE_SCHEDULER=1 no ambiente para não iniciar.
    if not os.environ.get('DISABLE_SCHEDULER'):
        from .utils.scheduler import iniciar_scheduler
        iniciar_scheduler(app)

    return app
