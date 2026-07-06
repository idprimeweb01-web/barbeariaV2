import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()

# storage_uri padrão memory:// é por-worker (cada worker do gunicorn tem sua
# própria contagem) — em produção com múltiplos workers, setar
# RATELIMIT_STORAGE_URI para um Redis compartilhado (ex: plugin do Railway).
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[os.environ.get('RATELIMIT_DEFAULT', '300 per minute')],
    storage_uri=os.environ.get('RATELIMIT_STORAGE_URI', 'memory://'),
)
