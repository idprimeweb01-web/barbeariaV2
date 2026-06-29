from datetime import timedelta
from functools import wraps
from flask import (
    Blueprint, request, session, redirect, url_for,
    render_template, jsonify, make_response, abort,
)
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    verify_jwt_in_request, get_jwt_identity,
)
from werkzeug.security import check_password_hash
from app.extensions import db
from app.models import Usuario, Barbearia

views_bp = Blueprint('views', __name__)

_PERFIL_REDIRECT = {
    'super_admin': '/super/',
    'gestor':      '/gestor/',
    'barbeiro':    '/barbeiro/',
}

_COOKIE_OPTS = dict(httponly=True, samesite='Lax', path='/')


def session_required(*perfis):
    """Guard para rotas de tela (não-API). Redireciona para /entrar se não autenticado."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('views.entrar'))
            if perfis and session.get('perfil') not in perfis:
                return redirect(url_for('views.entrar'))
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ── GET /entrar ───────────────────────────────────────────────────────────────

@views_bp.get('/entrar')
def entrar():
    if 'user_id' in session:
        perfil = session.get('perfil', '')
        return redirect(_PERFIL_REDIRECT.get(perfil, '/entrar'))
    return render_template('staff/login.html')


# ── POST /entrar ──────────────────────────────────────────────────────────────

@views_bp.post('/entrar')
def entrar_post():
    dados = request.get_json(silent=True) or {}
    email  = (dados.get('email') or '').strip().lower()
    senha  = dados.get('senha') or ''
    lembrar = bool(dados.get('lembrar'))

    if not email or not senha:
        return jsonify({'erro': 'E-mail e senha são obrigatórios.'}), 400

    usuario = Usuario.query.filter_by(email=email).first()

    if not usuario or not usuario.senha or not check_password_hash(usuario.senha, senha):
        return jsonify({'erro': 'Credenciais inválidas.'}), 401

    if not usuario.ativo:
        return jsonify({'erro': 'Conta desativada. Entre em contato com o suporte.'}), 403

    if usuario.perfil == 'cliente':
        return jsonify({
            'erro': (
                'Esta entrada é para a equipe. '
                'Clientes acessam pelo link do estabelecimento.'
            )
        }), 403

    if usuario.perfil not in _PERFIL_REDIRECT:
        return jsonify({'erro': 'Perfil não reconhecido.'}), 403

    access_token  = create_access_token(identity=str(usuario.id))
    refresh_token = create_refresh_token(identity=str(usuario.id))

    resp = make_response(
        jsonify({'ok': True, 'redirect': _PERFIL_REDIRECT[usuario.perfil]}),
        200,
    )

    # Access token: 15 min (alinhado com JWT_ACCESS_TOKEN_EXPIRES)
    resp.set_cookie('bos_at', access_token, max_age=15 * 60, **_COOKIE_OPTS)
    # Refresh token: 30 dias se "lembrar", cookie de sessão caso contrário
    rt_max_age = 30 * 24 * 3600 if lembrar else None
    resp.set_cookie('bos_rt', refresh_token, max_age=rt_max_age, **_COOKIE_OPTS)

    session.permanent = lembrar
    session['user_id']      = usuario.id
    session['nome']         = usuario.nome
    session['perfil']       = usuario.perfil
    session['barbearia_id'] = usuario.barbearia_id

    return resp


# ── POST /entrar/renovar ──────────────────────────────────────────────────────

@views_bp.post('/entrar/renovar')
def renovar():
    """
    Renova o access token (bos_at) usando o refresh token (bos_rt).
    Chamado automaticamente por bos.js quando recebe 401.
    """
    try:
        verify_jwt_in_request(refresh=True, locations=['cookies'])
        uid     = get_jwt_identity()
        usuario = db.session.get(Usuario, int(uid))
        if not usuario or not usuario.ativo:
            return jsonify({'erro': 'Sessão inválida.'}), 401

        new_at = create_access_token(identity=str(uid))
        resp   = make_response(jsonify({'ok': True}), 200)
        resp.set_cookie('bos_at', new_at, max_age=15 * 60, **_COOKIE_OPTS)

        session['user_id']      = usuario.id
        session['nome']         = usuario.nome
        session['perfil']       = usuario.perfil
        session['barbearia_id'] = usuario.barbearia_id

        return resp
    except Exception:
        return jsonify({'erro': 'Sessão expirada. Faça login novamente.'}), 401


# ── POST /sair ────────────────────────────────────────────────────────────────

@views_bp.post('/sair')
def sair():
    session.clear()
    resp = make_response(jsonify({'ok': True}), 200)
    resp.delete_cookie('bos_at', path='/')
    resp.delete_cookie('bos_rt', path='/')
    return resp


# ── Contexto compartilhado para área do gestor ───────────────────────────────

def _gestor_ctx():
    bid = session.get('barbearia_id')
    b   = db.session.get(Barbearia, bid) if bid else None
    return {
        'g_nome':   session.get('nome', 'Usuário'),
        'g_perfil': session.get('perfil', ''),
        'bk_slug':  b.slug if b else '',
        'bk_nome':  (b.nome_exibicao or b.nome) if b else 'BarberOS',
    }


# ── Área do Gestor ────────────────────────────────────────────────────────────

@views_bp.get('/gestor')
@views_bp.get('/gestor/')
@session_required('gestor', 'super_admin')
def area_gestor():
    return redirect('/gestor/dashboard')


@views_bp.get('/gestor/dashboard')
@session_required('gestor', 'super_admin')
def gestor_dashboard():
    return render_template('gestor/dashboard.html', **_gestor_ctx())


@views_bp.get('/gestor/barbeiros')
@session_required('gestor', 'super_admin')
def gestor_barbeiros():
    return render_template('gestor/barbeiros.html', **_gestor_ctx())


@views_bp.get('/gestor/servicos')
@session_required('gestor', 'super_admin')
def gestor_servicos():
    return render_template('gestor/servicos.html', **_gestor_ctx())


@views_bp.get('/gestor/produtos')
@session_required('gestor', 'super_admin')
def gestor_produtos():
    return render_template('gestor/produtos.html', **_gestor_ctx())


@views_bp.get('/gestor/agenda')
@session_required('gestor', 'super_admin')
def gestor_agenda():
    return render_template('gestor/agenda.html', **_gestor_ctx())


@views_bp.get('/gestor/clientes')
@session_required('gestor', 'super_admin')
def gestor_clientes():
    return render_template('gestor/clientes.html', **_gestor_ctx())


@views_bp.get('/gestor/relatorios')
@session_required('gestor', 'super_admin')
def gestor_relatorios():
    return render_template('gestor/relatorios.html', **_gestor_ctx())


@views_bp.get('/gestor/planos')
@session_required('gestor', 'super_admin')
def gestor_planos():
    return render_template('gestor/planos.html', **_gestor_ctx())


@views_bp.get('/gestor/vip')
@session_required('gestor', 'super_admin')
def gestor_vip():
    return render_template('gestor/vip.html', **_gestor_ctx())


@views_bp.get('/gestor/pix-approval')
@session_required('gestor', 'super_admin')
def gestor_pix_approval():
    return render_template('gestor/pix_approval.html', **_gestor_ctx())


@views_bp.get('/gestor/esqueci-senha')
@session_required('gestor', 'super_admin')
def gestor_esqueci_senha():
    return render_template('gestor/esqueci_senha.html', **_gestor_ctx())


@views_bp.get('/gestor/configuracoes/pix')
@session_required('gestor', 'super_admin')
def gestor_config_pix():
    return render_template('gestor/config_pix.html', **_gestor_ctx())


def _barbeiro_ctx():
    bid = session.get('barbearia_id')
    b   = db.session.get(Barbearia, bid) if bid else None
    return {
        'b_nome':  session.get('nome', 'Barbeiro'),
        'bk_slug': b.slug if b else '',
        'bk_nome': (b.nome_exibicao or b.nome) if b else 'BarberOS',
    }


@views_bp.get('/barbeiro')
@views_bp.get('/barbeiro/')
@session_required('barbeiro', 'super_admin')
def area_barbeiro():
    return redirect('/barbeiro/dashboard')


@views_bp.get('/barbeiro/dashboard')
@session_required('barbeiro', 'super_admin')
def barbeiro_dashboard():
    return render_template('barbeiro/dashboard.html', **_barbeiro_ctx())


@views_bp.get('/barbeiro/agendamentos')
@session_required('barbeiro', 'super_admin')
def barbeiro_agendamentos():
    return render_template('barbeiro/agendamentos.html', **_barbeiro_ctx())


@views_bp.get('/barbeiro/horario')
@session_required('barbeiro', 'super_admin')
def barbeiro_horario():
    return render_template('barbeiro/horario.html', **_barbeiro_ctx())


@views_bp.get('/barbeiro/clientes')
@session_required('barbeiro', 'super_admin')
def barbeiro_clientes():
    return render_template('barbeiro/clientes.html', **_barbeiro_ctx())


# ── Área Super Admin ──────────────────────────────────────────────────────────

def _super_ctx():
    return {'sa_nome': session.get('nome', 'Super Admin')}


@views_bp.get('/super')
@views_bp.get('/super/')
@session_required('super_admin')
def area_super():
    return redirect('/super/dashboard')


@views_bp.get('/super/dashboard')
@session_required('super_admin')
def super_dashboard():
    return render_template('super/dashboard.html', **_super_ctx())


@views_bp.get('/super/barbearias')
@session_required('super_admin')
def super_barbearias():
    return render_template('super/barbearias.html', **_super_ctx())


@views_bp.get('/super/gestores')
@session_required('super_admin')
def super_gestores():
    return render_template('super/em_construcao.html', secao='Gestores', **_super_ctx())


@views_bp.get('/super/relatorios')
@session_required('super_admin')
def super_relatorios():
    return render_template('super/em_construcao.html', secao='Relatórios', **_super_ctx())


@views_bp.get('/super/features')
@session_required('super_admin')
def super_features():
    return render_template('super/em_construcao.html', secao='Features', **_super_ctx())


@views_bp.get('/super/auditoria')
@session_required('super_admin')
def super_auditoria():
    return render_template('super/em_construcao.html', secao='Auditoria', **_super_ctx())


@views_bp.get('/super/customizacao')
@session_required('super_admin')
def super_customizacao():
    return render_template('super/customizacao.html', **_super_ctx())


# ── Área pública de agendamento ───────────────────────────────────────────────

@views_bp.get('/b/<slug>')
@views_bp.get('/b/<slug>/')
def pub_booking(slug):
    from app.models import Barbearia, BarbeariaCustomizacao, ConfiguracaoAgendamento
    b = Barbearia.query.filter_by(slug=slug, ativo=True).first()
    if not b:
        abort(404)
    custom  = BarbeariaCustomizacao.query.filter_by(barbearia_id=b.id).first()
    config  = ConfiguracaoAgendamento.query.filter_by(barbearia_id=b.id).first()
    cor     = (custom.cor_primaria if custom else None) or '#f39c12'
    ant_max = (config.antecedencia_maxima_dias if config else None) or 60
    bk_nome = b.nome_exibicao or b.nome
    return render_template(
        'pub/booking.html',
        slug=slug,
        bk_nome=bk_nome,
        cor_primaria=cor,
        antecedencia_maxima_dias=ant_max,
    )
