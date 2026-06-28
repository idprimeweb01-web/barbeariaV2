from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from app import db
from app.models import VipNivel, ClientePlano
from app.utils import get_barbearia_atual, registrar_auditoria
from app.routes.auth import gestor_required

vip = Blueprint('vip', __name__, url_prefix='/api/vip')

TIPOS_BRINDE_VALIDOS = {'fisico', 'desconto'}


def _erro(msg, code=400):
    return jsonify({'erro': msg}), code


def _fmt_nivel(v):
    return {
        'id':                v.id,
        'nivel':             v.nivel,
        'brinde_descricao':  v.brinde_descricao,
        'tipo_brinde':       v.tipo_brinde,
        'valor_desconto':    float(v.valor_desconto) if v.valor_desconto is not None else None,
        'modo_brinde_ativo': v.modo_brinde_ativo,
        'ativo':             v.ativo,
        'criado_em':         v.criado_em.isoformat() if v.criado_em else None,
    }


# ── GET /api/vip/niveis ──────────────────────────────────────────────────────────

@vip.get('/niveis')
@gestor_required
def listar_niveis():
    barbearia_id = get_barbearia_atual()
    rows = VipNivel.query.filter_by(barbearia_id=barbearia_id).order_by(VipNivel.nivel).all()
    return jsonify([_fmt_nivel(v) for v in rows])


# ── POST /api/vip/niveis ──────────────────────────────────────────────────────────

@vip.post('/niveis')
@gestor_required
def criar_nivel():
    barbearia_id = get_barbearia_atual()
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

    if VipNivel.query.filter_by(barbearia_id=barbearia_id, nivel=nivel).first():
        return _erro('Já existe um nível VIP com este número.', 409)

    vip_nivel = VipNivel(
        barbearia_id=barbearia_id,
        nivel=nivel,
        brinde_descricao=descricao,
        tipo_brinde=tipo_brinde,
        valor_desconto=valor,
        ativo=bool(dados.get('ativo', True)),
        modo_brinde_ativo=bool(dados.get('modo_brinde_ativo', True)),
    )
    db.session.add(vip_nivel)
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'create', 'vip_nivel', vip_nivel.id,
                         f'Criou nível VIP {nivel}.')
    return jsonify({'mensagem': 'Nível VIP criado.', 'nivel': _fmt_nivel(vip_nivel)}), 201


# ── PUT /api/vip/niveis/<id> ──────────────────────────────────────────────────────

@vip.put('/niveis/<int:nivel_id>')
@gestor_required
def editar_nivel(nivel_id):
    barbearia_id = get_barbearia_atual()
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

    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'edit', 'vip_nivel', vip_nivel.id,
                         f'Editou nível VIP {vip_nivel.nivel}.')
    return jsonify({'mensagem': 'Nível VIP atualizado.', 'nivel': _fmt_nivel(vip_nivel)})


# ── PUT /api/vip/niveis/<id>/modo-brinde ─────────────────────────────────────────

@vip.put('/niveis/<int:nivel_id>/modo-brinde')
@gestor_required
def toggle_modo_brinde(nivel_id):
    barbearia_id = get_barbearia_atual()
    vip_nivel = VipNivel.query.filter_by(id=nivel_id, barbearia_id=barbearia_id).first()
    if not vip_nivel:
        return _erro('Nível VIP não encontrado.', 404)

    vip_nivel.modo_brinde_ativo = not vip_nivel.modo_brinde_ativo
    db.session.commit()
    return jsonify({
        'mensagem': f"Modo brinde {'ativado' if vip_nivel.modo_brinde_ativo else 'desativado'}.",
        'nivel': _fmt_nivel(vip_nivel),
    })


# ── DELETE /api/vip/niveis/<id> ──────────────────────────────────────────────────

@vip.delete('/niveis/<int:nivel_id>')
@gestor_required
def deletar_nivel(nivel_id):
    barbearia_id = get_barbearia_atual()
    vip_nivel = VipNivel.query.filter_by(id=nivel_id, barbearia_id=barbearia_id).first()
    if not vip_nivel:
        return _erro('Nível VIP não encontrado.', 404)

    if ClientePlano.query.filter_by(nivel_vip=vip_nivel.id).first():
        return _erro('Este nível VIP está vinculado a clientes. Inative-o em vez de deletar.', 409)

    nivel_num = vip_nivel.nivel
    db.session.delete(vip_nivel)
    db.session.commit()
    registrar_auditoria(int(get_jwt_identity()), barbearia_id, 'delete', 'vip_nivel', nivel_id,
                         f'Deletou nível VIP {nivel_num}.')
    return jsonify({'mensagem': 'Nível VIP deletado.', 'id': nivel_id})
