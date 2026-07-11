from flask import Blueprint, request, g, jsonify
from app import db
from app.models import VipNivel, ClienteVip, ClienteVipHistorico, Cliente
from app.utils import registrar_auditoria
from app.decorators.auth import gestor_required
from app.utils.features import feature_required
from app.utils.db import commit_ou_falhar

vip_bp = Blueprint('vip', __name__, url_prefix='/api/v1/gestor/vip')

TIPOS_BRINDE_VALIDOS = {'fisico', 'desconto'}


def _erro(msg, code=400):
    return jsonify({'erro': msg}), code


def _validar_brindes(valor):
    """Valida a lista estruturada [{"name": "...", "description": "..."}].
    None -> lista vazia (campo opcional). Levanta ValueError com mensagem
    pronta pra devolver ao cliente se o formato estiver errado."""
    if valor is None:
        return []
    if not isinstance(valor, list):
        raise ValueError('"brindes" deve ser uma lista de objetos {name, description}.')

    limpos = []
    for item in valor:
        if not isinstance(item, dict):
            raise ValueError('Cada item de "brindes" deve ser um objeto {name, description}.')
        nome = (item.get('name') or '').strip()
        descricao = (item.get('description') or '').strip()
        if not nome:
            raise ValueError('Cada brinde precisa de "name".')
        limpos.append({'name': nome, 'description': descricao})
    return limpos


def _fmt_nivel(v):
    return {
        'id':                v.id,
        'nivel':             v.nivel,
        'brinde_descricao':  v.brinde_descricao,
        'brindes':           v.brindes or [],
        'tipo_brinde':       v.tipo_brinde,
        'valor_desconto':    float(v.valor_desconto) if v.valor_desconto is not None else None,
        'modo_brinde_ativo': v.modo_brinde_ativo,
        'ativo':             v.ativo,
        'criado_em':         v.criado_em.isoformat() if v.criado_em else None,
    }


# ── GET /api/v1/gestor/vip/niveis ─────────────────────────────────────────────────

@vip_bp.get('/niveis')
@gestor_required
def listar_niveis():
    barbearia_id = g.barbearia_id
    rows = VipNivel.query.filter_by(barbearia_id=barbearia_id).order_by(VipNivel.nivel).all()
    return jsonify([_fmt_nivel(v) for v in rows])


# ── POST /api/v1/gestor/vip/niveis ────────────────────────────────────────────────

@vip_bp.post('/niveis')
@gestor_required
@feature_required('vip_brindes')
def criar_nivel():
    barbearia_id = g.barbearia_id
    dados = request.get_json(silent=True)
    if not dados:
        return _erro('Corpo da requisição inválido ou ausente.')

    nivel       = dados.get('nivel')
    descricao   = (dados.get('brinde_descricao') or '').strip()
    tipo_brinde = (dados.get('tipo_brinde') or '').strip().lower()
    valor       = dados.get('valor_desconto')

    if not isinstance(nivel, int) or nivel < 1:
        return _erro('"nivel" deve ser um número inteiro positivo.')
    if not descricao:
        return _erro('"brinde_descricao" é obrigatório.')
    if tipo_brinde not in TIPOS_BRINDE_VALIDOS:
        return _erro(f'"tipo_brinde" deve ser: {", ".join(sorted(TIPOS_BRINDE_VALIDOS))}.')
    if tipo_brinde == 'desconto':
        try:
            valor = float(valor)
            if valor < 0:
                raise ValueError
        except (TypeError, ValueError):
            return _erro('"valor_desconto" deve ser um número positivo quando tipo_brinde é "desconto".')
    else:
        valor = None

    try:
        brindes = _validar_brindes(dados.get('brindes'))
    except ValueError as e:
        return _erro(str(e))

    if VipNivel.query.filter_by(barbearia_id=barbearia_id, nivel=nivel).first():
        return _erro('Já existe um nível VIP com este número.', 409)

    vip_nivel = VipNivel(
        barbearia_id=barbearia_id,
        nivel=nivel,
        brinde_descricao=descricao,
        brindes=brindes,
        tipo_brinde=tipo_brinde,
        valor_desconto=valor,
        ativo=bool(dados.get('ativo', True)),
        modo_brinde_ativo=bool(dados.get('modo_brinde_ativo', True)),
    )
    db.session.add(vip_nivel)
    commit_ou_falhar('vip.criar_nivel')
    registrar_auditoria(g.user_id, barbearia_id, 'create', 'vip_nivel', vip_nivel.id,
                         f'Criou nível VIP {nivel}.')
    return jsonify({'mensagem': 'Nível VIP criado.', 'nivel': _fmt_nivel(vip_nivel)}), 201


# ── PUT /api/v1/gestor/vip/niveis/<id> ────────────────────────────────────────────

@vip_bp.put('/niveis/<int:nivel_id>')
@gestor_required
@feature_required('vip_brindes')
def editar_nivel(nivel_id):
    barbearia_id = g.barbearia_id
    vip_nivel = VipNivel.query.filter_by(id=nivel_id, barbearia_id=barbearia_id).first()
    if not vip_nivel:
        return _erro('Nível VIP não encontrado.', 404)

    dados = request.get_json(silent=True) or {}

    if 'nivel' in dados:
        nivel = dados['nivel']
        if not isinstance(nivel, int) or nivel < 1:
            return _erro('"nivel" deve ser um número inteiro positivo.')
        dup = VipNivel.query.filter_by(barbearia_id=barbearia_id, nivel=nivel).first()
        if dup and dup.id != vip_nivel.id:
            return _erro('Já existe um nível VIP com este número.', 409)
        vip_nivel.nivel = nivel
    if 'brinde_descricao' in dados:
        descricao = (dados['brinde_descricao'] or '').strip()
        if not descricao:
            return _erro('"brinde_descricao" não pode ser vazio.')
        vip_nivel.brinde_descricao = descricao
    if 'brindes' in dados:
        try:
            vip_nivel.brindes = _validar_brindes(dados['brindes'])
        except ValueError as e:
            return _erro(str(e))
    if 'tipo_brinde' in dados:
        tipo_brinde = (dados['tipo_brinde'] or '').strip().lower()
        if tipo_brinde not in TIPOS_BRINDE_VALIDOS:
            return _erro(f'"tipo_brinde" deve ser: {", ".join(sorted(TIPOS_BRINDE_VALIDOS))}.')
        vip_nivel.tipo_brinde = tipo_brinde
        if tipo_brinde != 'desconto':
            vip_nivel.valor_desconto = None
    if 'valor_desconto' in dados and vip_nivel.tipo_brinde == 'desconto':
        try:
            valor = float(dados['valor_desconto'])
            if valor < 0:
                raise ValueError
        except (TypeError, ValueError):
            return _erro('"valor_desconto" deve ser um número positivo.')
        vip_nivel.valor_desconto = valor
    if 'ativo' in dados:
        vip_nivel.ativo = bool(dados['ativo'])
    if 'modo_brinde_ativo' in dados:
        vip_nivel.modo_brinde_ativo = bool(dados['modo_brinde_ativo'])

    commit_ou_falhar('vip.editar_nivel')
    registrar_auditoria(g.user_id, barbearia_id, 'edit', 'vip_nivel', vip_nivel.id,
                         f'Editou nível VIP {vip_nivel.nivel}.')
    return jsonify({'mensagem': 'Nível VIP atualizado.', 'nivel': _fmt_nivel(vip_nivel)})


# ── PUT /api/v1/gestor/vip/niveis/<id>/modo-brinde ────────────────────────────────

@vip_bp.put('/niveis/<int:nivel_id>/modo-brinde')
@gestor_required
@feature_required('vip_brindes')
def toggle_modo_brinde(nivel_id):
    barbearia_id = g.barbearia_id
    vip_nivel = VipNivel.query.filter_by(id=nivel_id, barbearia_id=barbearia_id).first()
    if not vip_nivel:
        return _erro('Nível VIP não encontrado.', 404)

    vip_nivel.modo_brinde_ativo = not vip_nivel.modo_brinde_ativo
    commit_ou_falhar('vip.toggle_modo_brinde')
    return jsonify({
        'mensagem': f"Modo brinde {'ativado' if vip_nivel.modo_brinde_ativo else 'desativado'}.",
        'nivel': _fmt_nivel(vip_nivel),
    })


# ── DELETE /api/v1/gestor/vip/niveis/<id> ─────────────────────────────────────────

@vip_bp.delete('/niveis/<int:nivel_id>')
@gestor_required
@feature_required('vip_brindes')
def deletar_nivel(nivel_id):
    barbearia_id = g.barbearia_id
    vip_nivel = VipNivel.query.filter_by(id=nivel_id, barbearia_id=barbearia_id).first()
    if not vip_nivel:
        return _erro('Nível VIP não encontrado.', 404)

    if ClienteVip.query.filter_by(barbearia_id=barbearia_id, nivel_vip_atual=vip_nivel.nivel).first():
        return _erro('Este nível VIP está vinculado a clientes. Inative-o em vez de deletar.', 409)

    nivel_num = vip_nivel.nivel
    db.session.delete(vip_nivel)
    commit_ou_falhar('vip.deletar_nivel')
    registrar_auditoria(g.user_id, barbearia_id, 'delete', 'vip_nivel', nivel_id,
                         f'Deletou nível VIP {nivel_num}.')
    return jsonify({'mensagem': 'Nível VIP deletado.', 'id': nivel_id})


# ── GET /api/v1/gestor/vip/clientes ───────────────────────────────────────────
# v1.2: lista clientes com nível VIP > 0. Sem @feature_required — leitura,
# mesmo padrão de listar_niveis (só as escritas são gateadas neste arquivo).

@vip_bp.get('/clientes')
@gestor_required
def listar_clientes_vip():
    barbearia_id = g.barbearia_id

    q = ClienteVip.query.filter_by(barbearia_id=barbearia_id).filter(ClienteVip.nivel_vip_atual > 0)

    nivel_param = request.args.get('nivel')
    if nivel_param is not None:
        try:
            q = q.filter(ClienteVip.nivel_vip_atual == int(nivel_param))
        except ValueError:
            return _erro('"nivel" deve ser um inteiro.', 422)

    try:
        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 50))))
    except ValueError:
        return _erro('"page" e "per_page" devem ser inteiros.', 422)

    paginado = q.order_by(ClienteVip.nivel_vip_atual.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    cliente_ids = [cv.cliente_id for cv in paginado.items]
    clientes_map = (
        {c.id: c for c in Cliente.query.filter(Cliente.id.in_(cliente_ids)).all()}
        if cliente_ids else {}
    )

    return jsonify({
        'dados': [
            {
                'cliente_id':             cv.cliente_id,
                'cliente_nome':           clientes_map.get(cv.cliente_id).nome if clientes_map.get(cv.cliente_id) else None,
                'nivel_vip_atual':        cv.nivel_vip_atual,
                'meses_consecutivos':     cv.meses_consecutivos,
                'data_proxima_renovacao': cv.data_proxima_renovacao.isoformat() if cv.data_proxima_renovacao else None,
                'atualizado_em':          cv.atualizado_em.isoformat() if cv.atualizado_em else None,
            }
            for cv in paginado.items
        ],
        'page':     paginado.page,
        'per_page': paginado.per_page,
        'total':    paginado.total,
        'pages':    paginado.pages,
    }), 200


# ── GET /api/v1/gestor/vip/clientes/<id>/historico ────────────────────────────

@vip_bp.get('/clientes/<int:cliente_id>/historico')
@gestor_required
def historico_cliente_vip(cliente_id):
    barbearia_id = g.barbearia_id

    cliente = Cliente.query.filter_by(id=cliente_id, barbearia_id=barbearia_id).first()
    if not cliente:
        return _erro('Cliente não encontrado.', 404)

    try:
        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 50))))
    except ValueError:
        return _erro('"page" e "per_page" devem ser inteiros.', 422)

    paginado = (
        ClienteVipHistorico.query
        .filter_by(cliente_id=cliente_id, barbearia_id=barbearia_id)
        .order_by(ClienteVipHistorico.criado_em.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return jsonify({
        'dados': [
            {
                'id':             h.id,
                'evento_tipo':    h.evento_tipo,
                'nivel_anterior': h.nivel_anterior,
                'nivel_novo':     h.nivel_novo,
                'descricao':      h.descricao,
                'criado_em':      h.criado_em.isoformat() if h.criado_em else None,
            }
            for h in paginado.items
        ],
        'page':     paginado.page,
        'per_page': paginado.per_page,
        'total':    paginado.total,
        'pages':    paginado.pages,
    }), 200
