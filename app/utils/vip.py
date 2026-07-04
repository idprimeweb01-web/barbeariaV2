from datetime import timedelta
from app.utils.tz import hoje_brasilia


def _get_or_create_cliente_vip(cliente_id, barbearia_id):
    from app.extensions import db
    from app.models import ClienteVip
    cv = ClienteVip.query.filter_by(cliente_id=cliente_id, barbearia_id=barbearia_id).first()
    if not cv:
        cv = ClienteVip(cliente_id=cliente_id, barbearia_id=barbearia_id, nivel_vip_atual=0)
        db.session.add(cv)
        db.session.flush()
    return cv


def incrementar_nivel_vip(cliente_id, barbearia_id):
    """Chamado a cada mês de plano aprovado/renovado: +1 nível, renova prazo 30 dias."""
    from app.extensions import db
    cv = _get_or_create_cliente_vip(cliente_id, barbearia_id)
    cv.nivel_vip_atual = (cv.nivel_vip_atual or 0) + 1
    cv.data_proxima_renovacao = hoje_brasilia() + timedelta(days=30)
    db.session.commit()
    return cv.nivel_vip_atual


def resetar_nivel_vip(cliente_id, barbearia_id):
    """Chamado quando cliente cancela plano: volta para nível 0."""
    from app.extensions import db
    cv = _get_or_create_cliente_vip(cliente_id, barbearia_id)
    cv.nivel_vip_atual = 0
    cv.data_proxima_renovacao = None
    db.session.commit()
    return cv.nivel_vip_atual
