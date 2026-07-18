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
    """Datetime atual em UTC, SEM tzinfo (naive) — para timestamps de
    auditoria e comparação com colunas TIMESTAMP WITHOUT TIME ZONE.

    Precisa ser naive pelo mesmo motivo do naive_brasilia(): se o valor
    entregue ao driver for tz-aware, o Postgres reconverte usando o
    TimeZone da SESSÃO (não necessariamente UTC) antes de gravar/comparar,
    corrompendo o valor silenciosamente."""
    return datetime.now(UTC).replace(tzinfo=None)


def naive_brasilia() -> datetime:
    """Datetime atual em Brasília sem tzinfo — para comparar com datetimes naive do banco."""
    return datetime.now(BRASILIA).replace(tzinfo=None)


def utc_naive_para_brasilia(dt: datetime) -> datetime:
    """Converte um datetime naive gravado como UTC (ex: Notificacao.criado_em)
    para naive em Brasília, só pra EXIBIÇÃO — sem isso, uma tela que mostra
    esse timestamp pro usuário final aparece 3h à frente do horário local
    (achado em teste manual no sino de notificação do barbeiro)."""
    return dt - timedelta(hours=3)
