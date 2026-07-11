from datetime import timedelta
from functools import wraps
from flask import (
    Blueprint, request, session, redirect, url_for,
    render_template, jsonify, make_response, abort, current_app, flash,
)
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    verify_jwt_in_request, get_jwt_identity, get_jwt, decode_token,
)
import os
from werkzeug.security import check_password_hash, generate_password_hash
from app.extensions import db, limiter
from app.models import Usuario, Barbearia, Cliente, TokenRevogado
from app.utils.db import commit_ou_falhar

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
            if session.get('perfil') != 'super_admin':
                bid = session.get('barbearia_id')
                b = db.session.get(Barbearia, bid) if bid else None
                if not b or not b.ativo:
                    session.clear()
                    flash('Este estabelecimento está desativado.')
                    return redirect(url_for('views.entrar'))
            return f(*args, **kwargs)
        return wrapper
    return decorator


def cliente_session_required(f):
    """
    Guard para telas do cliente. O login do cliente é escopado por barbearia
    (nasce do link público /b/<slug>/), então o redirecionamento de uma sessão
    expirada volta para o login daquela barbearia, não para /entrar (staff).
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session or session.get('perfil') != 'cliente':
            slug = session.get('barbearia_slug', '')
            return redirect(f'/b/{slug}/entrar' if slug else '/')
        return f(*args, **kwargs)
    return wrapper


# ── GET /entrar ───────────────────────────────────────────────────────────────

@views_bp.get('/entrar')
def entrar():
    if 'user_id' in session:
        perfil = session.get('perfil', '')
        return redirect(_PERFIL_REDIRECT.get(perfil, '/entrar'))
    return render_template('staff/login.html')


# ── POST /entrar ──────────────────────────────────────────────────────────────

@views_bp.post('/entrar')
@limiter.limit(os.environ.get('RL_LOGIN', '5 per minute'))
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

def _revogar_jti(token_str, tipo):
    """Decodifica um JWT (access ou refresh) e registra seu jti como revogado.
    Nunca levanta — logout não pode falhar por causa de um cookie problemático."""
    if not token_str:
        return
    try:
        claims = decode_token(token_str)
        jti = claims.get('jti')
        if not jti:
            return
        uid = claims.get('sub')
        db.session.add(TokenRevogado(
            jti=jti,
            usuario_id=int(uid) if uid is not None else None,
            tipo=tipo,
            motivo='logout',
        ))
    except Exception as e:
        current_app.logger.warning(f'Logout: não foi possível revogar token {tipo}: {e}')


@views_bp.post('/sair')
def sair():
    _revogar_jti(request.cookies.get('bos_at'), 'access')
    _revogar_jti(request.cookies.get('bos_rt'), 'refresh')
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Logout: falha ao gravar revogação de token: {e}', exc_info=True)

    session.clear()
    resp = make_response(jsonify({'ok': True}), 200)
    resp.delete_cookie('bos_at', path='/')
    resp.delete_cookie('bos_rt', path='/')
    return resp


# ── Contexto compartilhado para área do gestor ───────────────────────────────

def _gestor_ctx():
    from app.models import BarbeariaCustomizacao
    bid    = session.get('barbearia_id')
    b      = db.session.get(Barbearia, bid) if bid else None
    custom = BarbeariaCustomizacao.query.filter_by(barbearia_id=bid).first() if bid else None
    return {
        'g_nome':          session.get('nome', 'Usuário'),
        'g_perfil':        session.get('perfil', ''),
        'bk_slug':         b.slug if b else '',
        'bk_nome':         (b.nome_exibicao or b.nome) if b else 'BarberOS',
        'logo_url':        custom.logo_url if custom else None,
        'imagem_capa_url': custom.imagem_capa_url if custom else None,
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


@views_bp.get('/gestor/vendas')
@session_required('gestor', 'super_admin')
def gestor_vendas():
    return render_template('gestor/vendas.html', **_gestor_ctx())


@views_bp.get('/gestor/agenda')
@session_required('gestor', 'super_admin')
def gestor_agenda():
    return render_template('gestor/agenda.html', **_gestor_ctx())


@views_bp.get('/gestor/transferencias')
@session_required('gestor', 'super_admin')
def gestor_transferencias():
    return render_template('gestor/transferencias.html', **_gestor_ctx())


@views_bp.get('/gestor/clientes')
@session_required('gestor', 'super_admin')
def gestor_clientes():
    return render_template('gestor/clientes.html', **_gestor_ctx())


@views_bp.get('/gestor/cupons')
@session_required('gestor', 'super_admin')
def gestor_cupons():
    return render_template('gestor/cupons.html', **_gestor_ctx())


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
    from app.models import BarbeariaCustomizacao
    uid    = session.get('user_id')
    bid    = session.get('barbearia_id')
    u      = db.session.get(Usuario, uid) if uid else None
    b      = db.session.get(Barbearia, bid) if bid else None
    custom = BarbeariaCustomizacao.query.filter_by(barbearia_id=bid).first() if bid else None
    return {
        'b_nome':          session.get('nome', 'Barbeiro'),
        'b_email':         u.email if u else '',
        'bk_slug':         b.slug if b else '',
        'bk_nome':         (b.nome_exibicao or b.nome) if b else 'BarberOS',
        'logo_url':        custom.logo_url if custom else None,
        'imagem_capa_url': custom.imagem_capa_url if custom else None,
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


@views_bp.get('/barbeiro/disponiveis')
@session_required('barbeiro', 'super_admin')
def barbeiro_disponiveis():
    return render_template('barbeiro/disponiveis.html', **_barbeiro_ctx())


@views_bp.get('/barbeiro/agenda')
@session_required('barbeiro', 'super_admin')
def barbeiro_agenda():
    return render_template('barbeiro/agenda.html', **_barbeiro_ctx())


@views_bp.get('/barbeiro/perfil')
@session_required('barbeiro', 'super_admin')
def barbeiro_perfil():
    return render_template('barbeiro/perfil.html', **_barbeiro_ctx())


@views_bp.get('/barbeiro/produtos')
@session_required('barbeiro', 'super_admin')
def barbeiro_produtos():
    return render_template('barbeiro/produtos.html', **_barbeiro_ctx())


@views_bp.get('/barbeiro/caixa/<int:agendamento_id>')
@session_required('barbeiro', 'super_admin')
def barbeiro_caixa(agendamento_id):
    return render_template('barbeiro/caixa.html', agendamento_id=agendamento_id, **_barbeiro_ctx())


@views_bp.get('/barbeiro/configuracoes')
@session_required('barbeiro', 'super_admin')
def barbeiro_configuracoes():
    return render_template('barbeiro/configuracoes.html', **_barbeiro_ctx())


@views_bp.get('/barbeiro/redefinicoes')
@session_required('barbeiro', 'super_admin')
def barbeiro_redefinicoes():
    return render_template('barbeiro/redefinicoes.html', **_barbeiro_ctx())


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
    return render_template('super/gestores.html', **_super_ctx())


@views_bp.get('/super/relatorios')
@session_required('super_admin')
def super_relatorios():
    return render_template('super/relatorios.html', **_super_ctx())


@views_bp.get('/super/features')
@session_required('super_admin')
def super_features():
    return render_template('super/features.html', **_super_ctx())


@views_bp.get('/super/auditoria')
@session_required('super_admin')
def super_auditoria():
    return render_template('super/auditoria.html', **_super_ctx())


@views_bp.get('/super/segmentos')
@session_required('super_admin')
def super_segmentos():
    return render_template('super/segmentos.html', **_super_ctx())


@views_bp.get('/super/segmentos/<int:seg_id>/rotulos')
@session_required('super_admin')
def super_segmento_rotulos(seg_id):
    return render_template('super/segmento_rotulos.html', seg_id=seg_id, **_super_ctx())


@views_bp.get('/super/segmentos/<int:seg_id>/features')
@session_required('super_admin')
def super_segmento_features(seg_id):
    return render_template('super/segmento_features.html', seg_id=seg_id, **_super_ctx())


@views_bp.get('/super/customizacao')
@session_required('super_admin')
def super_customizacao():
    return render_template('super/customizacao.html', **_super_ctx())


# ── Área do Cliente ───────────────────────────────────────────────────────────
# Login/cadastro do cliente nasce do link público da barbearia (/b/<slug>/),
# nunca da rota de staff (/entrar). A conta criada vincula-se apenas à
# BARBEARIA — nunca a um barbeiro específico.

def _cliente_ctx():
    from app.models import BarbeariaCustomizacao
    uid    = session.get('user_id')
    bid    = session.get('barbearia_id')
    u      = db.session.get(Usuario, uid) if uid else None
    b      = db.session.get(Barbearia, bid) if bid else None
    custom = BarbeariaCustomizacao.query.filter_by(barbearia_id=bid).first() if bid else None
    return {
        'c_nome':   session.get('nome', 'Cliente'),
        'c_email':  u.email if u else '',
        'bk_slug':  b.slug if b else '',
        'bk_nome':  (b.nome_exibicao or b.nome) if b else 'BarberOS',
        'logo_url': custom.logo_url if custom else None,
    }


@views_bp.get('/b/<slug>/entrar')
def cliente_entrar(slug):
    barbearia = Barbearia.query.filter_by(slug=slug, ativo=True).first()
    if not barbearia:
        abort(404)
    if session.get('user_id') and session.get('perfil') == 'cliente':
        return redirect('/cliente/dashboard')
    from app.models import BarbeariaCustomizacao
    custom = BarbeariaCustomizacao.query.filter_by(barbearia_id=barbearia.id).first()
    return render_template(
        'cliente/entrar.html',
        slug=slug,
        bk_nome=barbearia.nome_exibicao or barbearia.nome,
        logo_url=custom.logo_url if custom else None,
    )


@views_bp.post('/b/<slug>/entrar')
@limiter.limit(os.environ.get('RL_LOGIN', '5 per minute'))
def cliente_entrar_post(slug):
    barbearia = Barbearia.query.filter_by(slug=slug, ativo=True).first()
    if not barbearia:
        return jsonify({'erro': 'Estabelecimento não encontrado.'}), 404

    dados   = request.get_json(silent=True) or {}
    email   = (dados.get('email') or '').strip().lower()
    senha   = dados.get('senha') or ''
    lembrar = bool(dados.get('lembrar'))

    if not email or not senha:
        return jsonify({'erro': 'E-mail e senha são obrigatórios.'}), 400

    usuario = Usuario.query.filter_by(
        barbearia_id=barbearia.id, email=email, perfil='cliente'
    ).first()

    if not usuario or not usuario.senha or not check_password_hash(usuario.senha, senha):
        return jsonify({'erro': 'Credenciais inválidas.'}), 401

    if not usuario.ativo:
        return jsonify({'erro': 'Conta desativada. Entre em contato com o estabelecimento.'}), 403

    access_token  = create_access_token(identity=str(usuario.id))
    refresh_token = create_refresh_token(identity=str(usuario.id))

    resp = make_response(jsonify({'ok': True, 'redirect': '/cliente/dashboard'}), 200)
    resp.set_cookie('bos_at', access_token, max_age=15 * 60, **_COOKIE_OPTS)
    rt_max_age = 30 * 24 * 3600 if lembrar else None
    resp.set_cookie('bos_rt', refresh_token, max_age=rt_max_age, **_COOKIE_OPTS)

    session.permanent = lembrar
    session['user_id']       = usuario.id
    session['nome']          = usuario.nome
    session['perfil']        = usuario.perfil
    session['barbearia_id']  = usuario.barbearia_id
    session['barbearia_slug'] = barbearia.slug

    return resp


@views_bp.get('/b/<slug>/cadastro')
def cliente_cadastro_view(slug):
    barbearia = Barbearia.query.filter_by(slug=slug, ativo=True).first()
    if not barbearia:
        abort(404)
    if session.get('user_id') and session.get('perfil') == 'cliente':
        return redirect('/cliente/dashboard')
    from app.models import BarbeariaCustomizacao
    custom = BarbeariaCustomizacao.query.filter_by(barbearia_id=barbearia.id).first()
    return render_template(
        'cliente/cadastro.html',
        slug=slug,
        bk_nome=barbearia.nome_exibicao or barbearia.nome,
        logo_url=custom.logo_url if custom else None,
    )


@views_bp.post('/b/<slug>/cadastro')
@limiter.limit(os.environ.get('RL_CADASTRO', '5 per minute'))
def cliente_cadastro_post(slug):
    from app.utils import normalizar_telefone

    barbearia = Barbearia.query.filter_by(slug=slug, ativo=True).first()
    if not barbearia:
        return jsonify({'erro': 'Estabelecimento não encontrado.'}), 404

    dados    = request.get_json(silent=True) or {}
    nome     = (dados.get('nome') or '').strip()
    email    = (dados.get('email') or '').strip().lower()
    telefone = (dados.get('telefone') or '').strip()
    senha    = dados.get('senha') or ''

    if not nome:
        return jsonify({'erro': 'Informe seu nome.'}), 400
    if not telefone:
        return jsonify({'erro': 'Informe seu telefone.'}), 400
    if len(senha) < 6:
        return jsonify({'erro': 'A senha deve ter no mínimo 6 caracteres.'}), 400

    tel_norm, tel_erro = normalizar_telefone(telefone)
    if tel_erro:
        return jsonify({'erro': f'Telefone: {tel_erro}'}), 400

    if email and Usuario.query.filter_by(
        barbearia_id=barbearia.id, email=email, perfil='cliente'
    ).first():
        return jsonify({'erro': 'Já existe uma conta com este e-mail.'}), 409

    cliente = Cliente.query.filter_by(barbearia_id=barbearia.id, telefone=tel_norm).first()
    if cliente and cliente.usuario_id:
        return jsonify({'erro': 'Este telefone já possui uma conta. Faça login.'}), 409

    usuario = Usuario(
        barbearia_id=barbearia.id,
        nome=nome,
        telefone=tel_norm,
        email=email or None,
        senha=generate_password_hash(senha),
        perfil='cliente',
        ativo=True,
    )
    db.session.add(usuario)
    db.session.flush()

    if cliente:
        cliente.usuario_id = usuario.id
        if not cliente.email and email:
            cliente.email = email
    else:
        cliente = Cliente(
            barbearia_id=barbearia.id,
            usuario_id=usuario.id,
            nome=nome,
            telefone=tel_norm,
            email=email or None,
            ativo=True,
        )
        db.session.add(cliente)

    commit_ou_falhar('views.auth.cliente_cadastro_post')

    access_token  = create_access_token(identity=str(usuario.id))
    refresh_token = create_refresh_token(identity=str(usuario.id))

    resp = make_response(jsonify({'ok': True, 'redirect': '/cliente/dashboard'}), 201)
    resp.set_cookie('bos_at', access_token, max_age=15 * 60, **_COOKIE_OPTS)
    resp.set_cookie('bos_rt', refresh_token, max_age=30 * 24 * 3600, **_COOKIE_OPTS)

    session.permanent = True
    session['user_id']        = usuario.id
    session['nome']           = usuario.nome
    session['perfil']         = usuario.perfil
    session['barbearia_id']   = usuario.barbearia_id
    session['barbearia_slug'] = barbearia.slug

    return resp


def _cliente_spa():
    return render_template('cliente/app.html', **_cliente_ctx())


@views_bp.get('/cliente/dashboard')
@cliente_session_required
def cliente_dashboard():
    return _cliente_spa()


@views_bp.get('/cliente/planos')
@cliente_session_required
def cliente_planos():
    return _cliente_spa()


@views_bp.get('/cliente/agendar')
@cliente_session_required
def cliente_agendar():
    return _cliente_spa()


@views_bp.get('/cliente/beneficios')
@cliente_session_required
def cliente_beneficios():
    return _cliente_spa()


@views_bp.get('/cliente/historico')
@cliente_session_required
def cliente_historico():
    return _cliente_spa()


@views_bp.get('/cliente/perfil')
@cliente_session_required
def cliente_perfil():
    return _cliente_spa()


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
        logo_url=custom.logo_url if custom else None,
        imagem_capa_url=custom.imagem_capa_url if custom else None,
        imagem_fundo_url=custom.imagem_boas_vindas_url if custom else None,
    )
