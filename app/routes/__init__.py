from flask import Blueprint, redirect, url_for, render_template, jsonify

main = Blueprint('main', __name__)


@main.get('/')
def index():
    return redirect(url_for('main.login'))


@main.get('/dev/reset-db')
def dev_reset_db():
    from scripts.reset_database import reset_all
    resultado = reset_all()
    return jsonify(resultado), 200


@main.get('/login')
def login():
    return render_template('auth/login.html')


@main.get('/cliente/login')
def cliente_login_page():
    return render_template('cliente/login.html')


@main.get('/cliente/cadastro')
def cliente_cadastro_page():
    return render_template('cliente/cadastro.html')


# ── Painel Barbeiro ────────────────────────────────────────────────────────────

@main.get('/barbeiro/dashboard')
def barbeiro_dashboard():
    return render_template('barbeiro/dashboard.html')

@main.get('/barbeiro/agenda')
def barbeiro_agenda():
    return render_template('barbeiro/agenda.html')

@main.get('/barbeiro/produtos')
def barbeiro_produtos():
    return render_template('barbeiro/produtos.html')

@main.get('/barbeiro/perfil')
def barbeiro_perfil():
    return render_template('barbeiro/perfil.html')

@main.get('/barbeiro/clientes')
def barbeiro_clientes():
    return render_template('barbeiro/clientes.html')


@main.get('/barbeiro/redefinicoes')
def barbeiro_redefinicoes():
    return render_template('barbeiro/redefinicoes.html')

@main.get('/barbeiro/configuracoes')
def barbeiro_configuracoes():
    return render_template('barbeiro/configuracoes.html')

@main.get('/barbeiro/caixa/<int:agendamento_id>')
def barbeiro_caixa(agendamento_id):
    return render_template('barbeiro/caixa.html', agendamento_id=agendamento_id)


# ── Painel Admin (legado) ──────────────────────────────────────────────────────

@main.get('/admin/dashboard')
def admin_dashboard():
    return render_template('admin/dashboard.html')


# ── Painel Gestor ──────────────────────────────────────────────────────────────

@main.get('/gestor/dashboard')
def gestor_dashboard():
    return render_template('gestor/dashboard.html')


@main.get('/gestor/barbeiros')
def gestor_barbeiros():
    return render_template('gestor/barbeiros.html')


@main.get('/gestor/servicos')
def gestor_servicos():
    return render_template('gestor/servicos.html')


@main.get('/gestor/produtos')
def gestor_produtos():
    return render_template('gestor/produtos.html')


@main.get('/gestor/agenda')
def gestor_agenda():
    return render_template('gestor/agenda.html')


@main.get('/gestor/clientes')
def gestor_clientes():
    return render_template('gestor/clientes.html')


@main.get('/gestor/esqueci-senha')
def gestor_esqueci_senha():
    return render_template('gestor/esqueci_senha.html')


@main.get('/gestor/relatorios')
def gestor_relatorios():
    return render_template('gestor/relatorios.html')


@main.get('/gestor/configuracoes/pix')
def gestor_config_pix():
    return render_template('gestor/config_pix.html')


@main.get('/gestor/pix-approval')
def gestor_pix_approval():
    return render_template('gestor/pix_approval.html')


@main.get('/gestor/planos')
def gestor_planos():
    return render_template('gestor/planos.html')


@main.get('/gestor/vip')
def gestor_vip():
    return render_template('gestor/vip.html')


# ── Painel Super Admin ─────────────────────────────────────────────────────────

@main.get('/super/dashboard')
def super_dashboard():
    return render_template('super/dashboard.html')


@main.get('/super/barbearias')
def super_barbearias():
    return render_template('super/barbearias.html')


@main.get('/super/gestores')
def super_gestores():
    return render_template('super/gestores.html')


@main.get('/super/features')
def super_features():
    return render_template('super/features.html')


@main.get('/super/relatorios')
def super_relatorios():
    return render_template('super/relatorios.html')


@main.get('/super/auditoria')
def super_auditoria():
    return render_template('super/auditoria.html')


@main.get('/super/customizacao')
def super_customizacao():
    return render_template('super/customizacao.html')


# ── Público (cliente final) ────────────────────────────────────────────────────

@main.get('/b/<slug>/')
def public_index(slug):
    return render_template('public/index.html', slug=slug)


@main.get('/b/<slug>/agendar')
def public_agendar(slug):
    return render_template('public/agendar.html', slug=slug)


@main.get('/b/<slug>/login')
def public_login(slug):
    return redirect(f'/cliente/login?b={slug}')


@main.get('/b/<slug>/confirmacao/<int:ag_id>')
def public_confirmacao(slug, ag_id):
    return render_template('public/confirmacao.html', slug=slug, ag_id=ag_id)


# ── Painel Cliente ──────────────────────────────────────────────────────────────

@main.get('/cliente/dashboard')
def cliente_dashboard():
    return render_template('cliente/dashboard.html')


@main.get('/cliente/meu-plano')
def cliente_meu_plano():
    return render_template('cliente/meu_plano.html')


@main.get('/cliente/vip')
def cliente_vip_status():
    return render_template('cliente/vip_status.html')


@main.get('/cliente/perfil')
def cliente_perfil_page():
    return render_template('cliente/perfil.html')


@main.get('/cliente/agendar')
def cliente_agendar_page():
    return render_template('cliente/agendar.html')


@main.get('/cliente/comprar-plano')
def cliente_comprar_plano_page():
    return render_template('cliente/comprar_plano.html')


@main.get('/cliente/checkout-plano')
def cliente_checkout_plano_page():
    return render_template('cliente/checkout_plano.html')


@main.get('/cliente/checkout-pix')
def cliente_checkout_pix_page():
    return render_template('cliente/checkout_pix.html')


@main.get('/cliente/customizacao')
def cliente_customizacao_page():
    return render_template('cliente/customizacao.html')
