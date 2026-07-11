from datetime import date
from flask import Blueprint, g, jsonify, request, send_file
from app.exceptions import APIError
from app.decorators.auth import gestor_required
from app.utils.features import feature_required
from app.labels import L
from app.utils.relatorio import (
    COLUNAS, COLUNAS_OBRIGATORIAS, validar_colunas,
    gerar_dados, gerar_excel, gerar_pdf,
)
from app.utils.tz import hoje_brasilia, naive_brasilia

gestor_relatorios_bp = Blueprint('gestor_relatorios', __name__, url_prefix='/api/v1/gestor')


def _parse_params():
    """Extrai e valida os query params comuns a todos os endpoints de relatório."""
    colunas_raw = request.args.get('colunas', '')
    if colunas_raw:
        colunas_solicitadas = [c.strip() for c in colunas_raw.split(',') if c.strip()]
    else:
        colunas_solicitadas = list(COLUNAS.keys())

    try:
        colunas = validar_colunas(colunas_solicitadas)
    except ValueError as exc:
        raise APIError(str(exc), 422)

    de_str  = request.args.get('de',  hoje_brasilia().replace(day=1).isoformat())
    ate_str = request.args.get('ate', hoje_brasilia().isoformat())
    try:
        de  = date.fromisoformat(de_str)
        ate = date.fromisoformat(ate_str)
    except ValueError:
        raise APIError('Parâmetros "de" e "ate" devem estar no formato YYYY-MM-DD.', 422)

    if de > ate:
        raise APIError('"de" não pode ser posterior a "ate".', 422)

    return colunas, de, ate


def _barbearia_nome() -> str:
    from app.models import Barbearia
    b = Barbearia.query.get(g.barbearia_id)
    return b.nome if b else 'Barbearia'


# ── JSON ──────────────────────────────────────────────────────────────────────

@gestor_relatorios_bp.get('/relatorios/agendamentos')
@gestor_required
def relatorio_agendamentos_json():
    """
    Retorna relatório de agendamentos em JSON.

    Query params:
      colunas  — lista separada por vírgula; padrão: todas as colunas.
                 Colunas obrigatórias não podem ser omitidas.
      de       — data inicial YYYY-MM-DD; padrão: primeiro dia do mês atual.
      ate      — data final   YYYY-MM-DD; padrão: hoje.
    """
    colunas, de, ate = _parse_params()
    dados = gerar_dados(g.barbearia_id, de, ate, colunas)

    receita_total = sum(float(l.get('valor_total', 0)) for l in dados) if 'valor_total' in colunas else None
    periodo = f'{de.strftime("%d/%m/%Y")} a {ate.strftime("%d/%m/%Y")}'

    return jsonify({
        'barbearia':    _barbearia_nome(),
        'periodo':      periodo,
        'gerado_em':    naive_brasilia().strftime('%d/%m/%Y %H:%M'),
        'colunas_ativas': colunas,
        'colunas_disponiveis': {
            k: {'label': v['label'], 'obrigatorio': v['obrigatorio']}
            for k, v in COLUNAS.items()
        },
        'total_registros': len(dados),
        'receita_total': round(receita_total, 2) if receita_total is not None else None,
        'dados': dados,
        'rotulos': {
            'agendamento':  L('agendamento'),
            'cliente':      L('cliente'),
            'servico':      L('servico'),
            'servicos':     L('servicos'),
            'profissional': L('profissional'),
            'receita':      L('receita'),
            'plano':        L('plano'),
        },
    }), 200


# ── Excel ─────────────────────────────────────────────────────────────────────

@gestor_relatorios_bp.get('/relatorios/agendamentos/excel')
@gestor_required
@feature_required('relatorios_avancados')
def relatorio_agendamentos_excel():
    """Exporta relatório de agendamentos em Excel (.xlsx)."""
    colunas, de, ate = _parse_params()
    dados = gerar_dados(g.barbearia_id, de, ate, colunas)
    nome_barbearia = _barbearia_nome()
    periodo = f'{de.strftime("%d/%m/%Y")} a {ate.strftime("%d/%m/%Y")}'

    buf = gerar_excel(dados, colunas, nome_barbearia, periodo)
    nome_arquivo = (
        f'relatorio_{nome_barbearia.lower().replace(" ", "_")}'
        f'_{de.isoformat()}_{ate.isoformat()}.xlsx'
    )
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=nome_arquivo,
    )


# ── PDF ───────────────────────────────────────────────────────────────────────

@gestor_relatorios_bp.get('/relatorios/agendamentos/pdf')
@gestor_required
@feature_required('relatorios_avancados')
def relatorio_agendamentos_pdf():
    """Exporta relatório de agendamentos em PDF. Cabeçalho com nome da barbearia e período."""
    colunas, de, ate = _parse_params()
    dados = gerar_dados(g.barbearia_id, de, ate, colunas)
    nome_barbearia = _barbearia_nome()
    periodo = f'{de.strftime("%d/%m/%Y")} a {ate.strftime("%d/%m/%Y")}'

    buf = gerar_pdf(dados, colunas, nome_barbearia, periodo)
    nome_arquivo = (
        f'relatorio_{nome_barbearia.lower().replace(" ", "_")}'
        f'_{de.isoformat()}_{ate.isoformat()}.pdf'
    )
    return send_file(
        buf,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=nome_arquivo,
    )


# ── Coluna schema ─────────────────────────────────────────────────────────────

@gestor_relatorios_bp.get('/relatorios/colunas')
@gestor_required
def listar_colunas():
    """Lista todas as colunas disponíveis com flag de obrigatoriedade."""
    return jsonify({
        'colunas': {
            k: {'label': v['label'], 'obrigatorio': v['obrigatorio']}
            for k, v in COLUNAS.items()
        },
        'obrigatorias': sorted(COLUNAS_OBRIGATORIAS),
    }), 200
