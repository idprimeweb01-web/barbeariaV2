from datetime import datetime, timezone
from flask import g, current_app
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
from flask_jwt_extended.exceptions import JWTExtendedException
from jwt.exceptions import PyJWTError


def load_user_context():
    g.user_id = None
    g.perfil = None
    g.barbearia_id = None
    try:
        verify_jwt_in_request(optional=True)
    except (JWTExtendedException, PyJWTError):
        return  # token ausente/expirado/inválido — não autenticado, comportamento normal
    except Exception as e:
        current_app.logger.error(f'Erro inesperado no contexto JWT: {e}', exc_info=True)
        raise  # nunca tratar falha de banco/infra como "não autenticado" silencioso

    uid = get_jwt_identity()
    if uid is None:
        return

    claims = get_jwt()

    from app.extensions import db
    from app.models import Usuario, TokenRevogado

    jti = claims.get('jti')
    if jti and db.session.query(TokenRevogado.id).filter_by(jti=jti).first():
        return  # token revogado individualmente (logout)

    usuario = db.session.get(Usuario, int(uid))
    if not usuario or not usuario.ativo:
        return

    if usuario.token_valido_apos is not None:
        iat = claims.get('iat')
        if iat is not None:
            emitido_em = datetime.fromtimestamp(iat, tz=timezone.utc)
            valido_apos = usuario.token_valido_apos
            if valido_apos.tzinfo is None:
                valido_apos = valido_apos.replace(tzinfo=timezone.utc)
            if emitido_em < valido_apos:
                return  # token emitido antes da revogação em massa (logout/desativação)

    g.user_id = usuario.id
    g.perfil = usuario.perfil
    g.barbearia_id = usuario.barbearia_id
