from flask import Blueprint, g, jsonify
from app.extensions import db
from app.models import (
    Agendamento, AgendamentoServico, Servico, Barbeiro, Usuario, Cliente,
)
from app.decorators.auth import barbeiro_required
from app.utils.features import feature_ativa
from app.utils.tz import hoje_brasilia, naive_brasilia
from app.labels import L

barbeiro_dash_bp = Blueprint('barbeiro_dashboard', __name__, url_prefix='/api/v1/barbeiro')


def _get_barbeiro_ou_none(user_id, barbearia_id):
    return Barbeiro.query.filter_by(usuario_id=user_id, barbearia_id=barbearia_id, ativo=True).first()


def _calcular_comissao(itens, barbeiro):
    """Soma comissão correta por item: is_plano → comissao_plano_percentual; avulso → comissao_percentual."""
    total = 0.0
    for it in itens:
        pct = (
            float(barbeiro.comissao_plano_percentual)
            if it.is_plano
            else float(barbeiro.comissao_percentual)
        )
        total += float(it.preco_unitario) * pct / 100
    return round(total, 2)


@barbeiro_dash_bp.get('/dashboard')
@barbeiro_required
def dashboard_barbeiro():
    barbeiro = _get_barbeiro_ou_none(g.user_id, g.barbearia_id)
    if not barbeiro:
        return jsonify({'erro': f'{L("profissional")} não encontrado.'}), 404

    hoje = hoje_brasilia()
    mes_ano = (hoje.year, hoje.month)

    # Agendamentos de hoje
    ags_hoje = (
        Agendamento.query
        .filter(
            Agendamento.barbearia_id == g.barbearia_id,
            Agendamento.barbeiro_id == barbeiro.id,
            db.func.date(Agendamento.data_hora) == hoje,
            Agendamento.status.in_(['agendado', 'concluido']),
        )
        .all()
    )

    # Agendamentos do mês
    ags_mes = (
        Agendamento.query
        .filter(
            Agendamento.barbearia_id == g.barbearia_id,
            Agendamento.barbeiro_id == barbeiro.id,
            db.extract('year',  Agendamento.data_hora) == mes_ano[0],
            db.extract('month', Agendamento.data_hora) == mes_ano[1],
            Agendamento.status.in_(['agendado', 'concluido']),
        )
        .all()
    )

    # Comissão: calcula via AgendamentoServico para separar plano vs avulso
    def _comissao_ags(ags_list):
        total_comissao = 0.0
        total_receita  = 0.0
        for ag in ags_list:
            itens = AgendamentoServico.query.filter_by(agendamento_id=ag.id).all()
            total_comissao += _calcular_comissao(itens, barbeiro)
            total_receita  += float(ag.valor_total)
        return round(total_comissao, 2), round(total_receita, 2)

    comissao_hoje, receita_hoje = _comissao_ags(ags_hoje)
    comissao_mes,  receita_mes  = _comissao_ags(ags_mes)

    # Próximos 5 agendamentos futuros
    agora = naive_brasilia()
    proximos = (
        Agendamento.query
        .filter(
            Agendamento.barbearia_id == g.barbearia_id,
            Agendamento.barbeiro_id == barbeiro.id,
            Agendamento.data_hora >= agora,
            Agendamento.status == 'agendado',
        )
        .order_by(Agendamento.data_hora)
        .limit(5)
        .all()
    )

    proximos_fmt = []
    for ag in proximos:
        cli = db.session.get(Cliente, ag.cliente_id)
        itens = AgendamentoServico.query.filter_by(agendamento_id=ag.id).all()
        servicos_nomes = []
        for it in itens:
            s = db.session.get(Servico, it.servico_id)
            if s:
                servicos_nomes.append(s.nome)
        proximos_fmt.append({
            'id':              ag.id,
            'data_hora':       ag.data_hora.isoformat(),
            'duracao_minutos': ag.duracao_minutos,
            'status':          ag.status,
            'valor_total':     float(ag.valor_total),
            L('cliente').lower(): cli.nome if cli else None,
            L('servicos').lower(): servicos_nomes,
        })

    # Breakdown de comissão por tipo (plano vs avulso) — só se feature comissao ativa
    comissao_breakdown = None
    if feature_ativa(g.barbearia_id, 'comissao'):
        avulso_mes = 0.0
        plano_mes  = 0.0
        for ag in ags_mes:
            itens = AgendamentoServico.query.filter_by(agendamento_id=ag.id).all()
            for it in itens:
                if it.is_plano:
                    plano_mes  += float(it.preco_unitario) * float(barbeiro.comissao_plano_percentual) / 100
                else:
                    avulso_mes += float(it.preco_unitario) * float(barbeiro.comissao_percentual) / 100
        comissao_breakdown = {
            'avulso': round(avulso_mes, 2),
            'plano':  round(plano_mes, 2),
            'total':  round(avulso_mes + plano_mes, 2),
        }

    return jsonify({
        'hoje': {
            L('agendamento').lower() + 's':  len(ags_hoje),
            L('receita').lower():            receita_hoje,
            L('comissao').lower():           comissao_hoje,
        },
        'mes': {
            L('agendamento').lower() + 's':  len(ags_mes),
            L('receita').lower():            receita_mes,
            L('comissao').lower():           comissao_mes,
        },
        'proximos': proximos_fmt,
        'comissao_breakdown': comissao_breakdown,
        'rotulos': {
            'agendamento':  L('agendamento'),
            'cliente':      L('cliente'),
            'servicos':     L('servicos'),
            'receita':      L('receita'),
            'comissao':     L('comissao'),
            'profissional': L('profissional'),
        },
    }), 200
