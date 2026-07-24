"""
Links temporários pra comprovante PIX.

As URLs do Cloudinary (`ag_{id}.png`, `plano_sol_{id}.png`) nunca são
enviadas pro navegador — em vez disso, geramos um token opaco e assinado
que resolve pro comprovante real só dentro da janela de validade, via
GET /comprovante/<token> (rota pública, mas o token já carrega a prova de
que quem pediu o link tinha acesso autenticado ao registro na hora da geração).
"""
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app

_SALT = 'comprovante-temp-link'
LINK_TTL_SEGUNDOS = 600  # 10 minutos


def _serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt=_SALT)


def gerar_link_comprovante(tipo, ref_id, barbearia_id):
    """tipo: 'agendamento', 'plano', 'compra' ou 'duvida_msg'. Retorna o path
    relativo (/comprovante/<token>)."""
    token = _serializer().dumps({'tipo': tipo, 'ref_id': ref_id, 'barbearia_id': barbearia_id})
    return f'/comprovante/{token}'


def decodificar_token_comprovante(token):
    """Retorna o payload do token ou levanta ValueError se expirado/inválido."""
    try:
        return _serializer().loads(token, max_age=LINK_TTL_SEGUNDOS)
    except (BadSignature, SignatureExpired):
        raise ValueError('Link expirado ou inválido.')
