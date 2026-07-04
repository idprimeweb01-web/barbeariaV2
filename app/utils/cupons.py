from app.extensions import db
from app.models import Cupom
from app.exceptions import APIError
from app.utils.features import feature_ativa
from app.utils.tz import hoje_brasilia


def validar_cupom(barbearia_id: int, codigo: str, subtotal: float) -> tuple[Cupom, float]:
    """
    Valida um código de cupom para a barbearia e retorna (cupom, valor_desconto).
    Levanta APIError (422) com mensagem específica em qualquer condição inválida.
    """
    if not feature_ativa(barbearia_id, 'cupons'):
        raise APIError('Cupons não estão disponíveis para esta barbearia.', 403)

    codigo_norm = (codigo or '').strip().upper()
    if not codigo_norm:
        raise APIError('Informe um código de cupom.', 422)

    cupom = Cupom.query.filter_by(barbearia_id=barbearia_id, codigo=codigo_norm).first()
    if not cupom:
        raise APIError('Cupom não encontrado.', 422)
    if not cupom.ativo:
        raise APIError('Este cupom não está mais ativo.', 422)
    if cupom.data_expiracao < hoje_brasilia():
        raise APIError('Este cupom expirou.', 422)
    if cupom.quantidade_maxima_usos is not None and cupom.quantidade_usos >= cupom.quantidade_maxima_usos:
        raise APIError('Este cupom atingiu o limite de utilizações.', 422)

    desconto = calcular_desconto(cupom, subtotal)
    return cupom, desconto


def calcular_desconto(cupom: Cupom, subtotal: float) -> float:
    if cupom.tipo_desconto == 'percentual':
        valor = subtotal * float(cupom.valor_desconto) / 100
    else:
        valor = float(cupom.valor_desconto)
    return round(min(valor, subtotal), 2)


def incrementar_uso_cupom(cupom_id: int):
    cupom = db.session.get(Cupom, cupom_id)
    if cupom:
        cupom.quantidade_usos += 1


def decrementar_uso_cupom(cupom_id: int):
    cupom = db.session.get(Cupom, cupom_id)
    if cupom and cupom.quantidade_usos > 0:
        cupom.quantidade_usos -= 1
