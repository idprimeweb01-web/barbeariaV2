PLANO_LIMITE_ILIMITADO = 99999  # sentinela: PlanoServico.limite_uso_mensal é NOT NULL


def limite_para_fora(valor):
    """Converte o sentinela de 'ilimitado' para None ao expor um limite na API."""
    return None if valor is None or valor >= PLANO_LIMITE_ILIMITADO else valor


def limite_para_dentro(valor):
    """Converte None/0/ausente vindo do front para o sentinela de ilimitado."""
    if valor is None:
        return PLANO_LIMITE_ILIMITADO
    try:
        valor = int(valor)
    except (TypeError, ValueError):
        return PLANO_LIMITE_ILIMITADO
    return valor if valor > 0 else PLANO_LIMITE_ILIMITADO
