"""
Utilitários de timezone para o sistema BarberOS.

Regra: toda lógica de negócio (slots, agendamentos, datas) opera em Brasília (UTC-3).
Timestamps de auditoria (criado_em, atualizado_em) são gravados em UTC.
"""
from datetime import datetime, timezone, timedelta

BRASILIA = timezone(timedelta(hours=-3))
UTC      = timezone.utc


def agora_brasilia() -> datetime:
    """Datetime atual timezone-aware em Brasília (UTC-3)."""
    return datetime.now(BRASILIA)


def hoje_brasilia():
    """Date atual em Brasília — substitui date.today() em lógica de negócio."""
    return datetime.now(BRASILIA).date()


def agora_utc() -> datetime:
    """Datetime atual timezone-aware em UTC — para timestamps de auditoria."""
    return datetime.now(UTC)


def naive_brasilia() -> datetime:
    """Datetime atual em Brasília sem tzinfo — para comparar com datetimes naive do banco."""
    return datetime.now(BRASILIA).replace(tzinfo=None)
