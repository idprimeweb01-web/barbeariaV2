from flask import Blueprint, g, jsonify
from app.extensions import db
from app.models import (
    Agendamento, AgendamentoServico, Servico, Barbeiro, Usuario,
    ClientePlano, Plano, Cliente,
)
from app.decorators.auth import cliente_required
from app.utils.features import feature_ativa
from app.utils.tz import naive_brasilia
from app.labels import L
from app.constants import StatusAgendamento

cliente_dash_bp = Blueprint('cliente_dashboard', __name__, url_prefix='/api/v1/cliente')


def _get_cliente_ou_404(user_id, barbearia_id):
    usr = db.session.get(Usuario, user_id)
    if not usr:
        raise Exception('Usuário não encontrado.')
    cli = Cliente.query.filter_by(barbearia_id=barbearia_id, usuario_id=usr.id).first()
    return cli


@cliente_dash_bp.get('/dashboard')
@cliente_required
def dashboard_cliente():
    cli = _get_cliente_ou_404(g.user_id, g.barbearia_id)
    if not cli:
        return jsonify({
            'mensagem': f'Perfil de {L("cliente").lower()} ainda não criado nesta {L("tenant").lower()}.',
            'proximos_agendamentos': [],
            'historico_resumo': {'total_concluidos': 0, 'total_cancelados': 0},
            'planos_ativos': [],
            'rotulos': {L('agendamento'): 'agendamento', L('plano'): 'plano'},
        }), 200

    agora = naive_brasilia()

    # Próximos agendamentos (futuro, status=agendado)
    proximos = (
        Agendamento.query
        .filter(
            Agendamento.barbearia_id == g.barbearia_id,
            Agendamento.cliente_id == cli.id,
            Agendamento.data_hora >= agora,
            Agendamento.status == StatusAgendamento.AGENDADO,
        )
        .order_by(Agendamento.data_hora)
        .limit(5)
        .all()
    )

    proximos_fmt = []
    for ag in proximos:
        br = db.session.get(Barbeiro, ag.barbeiro_id)
        br_usr = db.session.get(Usuario, br.usuario_id) if br else None
        itens = AgendamentoServico.query.filter_by(agendamento_id=ag.id).all()
        servicos_nomes = []
        for it in itens:
            s = db.session.get(Servico, it.servico_id)
            if s:
                servicos_nomes.append(s.nome)
        proximos_fmt.append({
            'id':               ag.id,
            'data_hora':        ag.data_hora.isoformat(),
            'duracao_minutos':  ag.duracao_minutos,
            'status':           ag.status,
            'valor_total':      float(ag.valor_total),
            L('profissional').lower(): br_usr.nome if br_usr else None,
            L('servicos').lower():    servicos_nomes,
        })

    # Histórico resumido
    total_concluidos = Agendamento.query.filter_by(
        barbearia_id=g.barbearia_id, cliente_id=cli.id, status=StatusAgendamento.CONCLUIDO
    ).count()
    total_cancelados = Agendamento.query.filter_by(
        barbearia_id=g.barbearia_id, cliente_id=cli.id, status=StatusAgendamento.CANCELADO
    ).count()

    # Planos ativos (só se feature 'planos' estiver ligada)
    planos_ativos = []
    if feature_ativa(g.barbearia_id, 'planos'):
        cps = ClientePlano.query.filter_by(
            barbearia_id=g.barbearia_id, cliente_id=cli.id, ativo=True
        ).all()
        for cp in cps:
            p = db.session.get(Plano, cp.plano_id)
            planos_ativos.append({
                'cliente_plano_id': cp.id,
                'plano_nome':  p.nome if p else None,
                'data_inicio': cp.data_inicio.isoformat() if cp.data_inicio else None,
                'data_fim':    cp.data_fim.isoformat() if cp.data_fim else None,
            })

    return jsonify({
        'proximos_agendamentos':   proximos_fmt,
        'historico_resumo': {
            'total_concluidos': total_concluidos,
            'total_cancelados': total_cancelados,
        },
        f'{L("plano").lower()}s_ativos': planos_ativos,
        'rotulos': {
            'agendamento':  L('agendamento'),
            'profissional': L('profissional'),
            'servicos':     L('servicos'),
            'plano':        L('plano'),
            'cliente':      L('cliente'),
        },
    }), 200
