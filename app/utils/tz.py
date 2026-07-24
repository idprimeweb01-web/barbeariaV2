"""
Utilitários de timezone para o sistema BarberOS.

Regra: toda lógica de negócio (slots, agendamentos, datas) opera em Brasília (UTC-3).
Timestamps de auditoria (criado_em, atualizado_em) são gravados em UTC.
"""
from datetime import datetime, date, time as time_t, timezone, timedelta

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


def limites_utc_do_dia_brasilia(de: date, ate: date) -> tuple[datetime, datetime]:
    """Converte um intervalo de datas LOCAIS de Brasília (ex: 'de'/'ate' de
    um filtro de tela) em limites de datetime UTC-naive, pra filtrar
    colunas gravadas em UTC (criado_em de AuditoriaLog/ClienteDuvida/Venda
    etc.) pelo dia civil que o usuário vê, não o dia civil UTC.

    Sem isso, `db.func.date(coluna_utc) >= de` compara a data UTC direto
    contra uma data de Brasília — entre ~21h e meia-noite (Brasília), a
    coluna já está gravada com a data UTC do dia SEGUINTE, e o registro
    some do filtro até o dia virar em Brasília também (achado em teste
    manual na listagem de dúvidas do gestor)."""
    inicio = datetime.combine(de, time_t.min) + timedelta(hours=3)
    fim    = datetime.combine(ate, time_t.max) + timedelta(hours=3)
    return inicio, fim


def utc_naive_para_brasilia(dt: datetime) -> datetime:
    """Converte um datetime naive gravado como UTC (ex: Notificacao.criado_em)
    para naive em Brasília, só pra EXIBIÇÃO — sem isso, uma tela que mostra
    esse timestamp pro usuário final aparece 3h à frente do horário local
    (achado em teste manual no sino de notificação do barbeiro)."""
    return dt - timedelta(hours=3)
