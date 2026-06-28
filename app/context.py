from flask import g
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity


def load_user_context():
    g.user_id = None
    g.perfil = None
    g.barbearia_id = None
    try:
        verify_jwt_in_request(optional=True)
        uid = get_jwt_identity()
        if uid is not None:
            from app.extensions import db
            from app.models import Usuario
            usuario = db.session.get(Usuario, int(uid))
            if usuario and usuario.ativo:
                g.user_id = usuario.id
                g.perfil = usuario.perfil
                g.barbearia_id = usuario.barbearia_id
    except Exception:
        pass
