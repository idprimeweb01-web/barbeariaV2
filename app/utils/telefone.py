import re


def normalizar_telefone(tel):
    """Remove não-dígitos e valida 8–13 dígitos (suporta DDD + número brasileiro)."""
    digitos = re.sub(r'\D', '', tel or '')
    if len(digitos) < 8:
        return None, 'Telefone deve ter no mínimo 8 dígitos.'
    if len(digitos) > 13:
        return None, 'Telefone inválido — dígitos demais.'
    return digitos, None
