from datetime import datetime, timezone
from app.extensions import db
from app.models.mixins import TenantMixin

def _utcnow():
    """Substitui datetime.utcnow() — retorna UTC timezone-aware."""
    return datetime.now(timezone.utc)


# ── Barbearia ──────────────────────────────────────────────────────────────────

class Barbearia(db.Model):
    __tablename__ = 'barbearias'

    id               = db.Column(db.Integer, primary_key=True)
    nome             = db.Column(db.String(150), nullable=False)
    nome_exibicao    = db.Column(db.String(150))
    slug             = db.Column(db.String(50), unique=True, nullable=False, index=True)
    ativo            = db.Column(db.Boolean, default=True, nullable=False)
    url_agendamento  = db.Column(db.String(255))
    chave_pix        = db.Column(db.String(255))
    pix_nome_titular = db.Column(db.String(150))
    pix_cidade       = db.Column(db.String(50))
    pix_banco        = db.Column(db.String(50))
    criado_em        = db.Column(db.DateTime, default=_utcnow)
    # ── P2: WhatsApp Business API ─────────────────────────────────────────────
    whatsapp_business_id      = db.Column(db.String(100))   # WABA ID (Meta)
    whatsapp_phone_number_id  = db.Column(db.String(100))   # Phone Number ID (Meta Cloud API)
    # ── P2: Billing da plataforma (o que o estabelecimento paga À plataforma) ─
    billing_plano             = db.Column(db.String(50))    # basic / pro / enterprise / custom
    billing_mensalidade_valor = db.Column(db.Numeric(10, 2))
    billing_vencimento_dia    = db.Column(db.Integer)       # 1-28, dia do mês
    billing_proximo_vencimento = db.Column(db.Date)
    billing_status            = db.Column(db.String(20), nullable=False, default='em_dia')
    # em_dia | atrasado | suspenso
    # ── Endereço e contato público ─────────────────────────────────────────────
    rua              = db.Column(db.String(200))
    numero           = db.Column(db.String(10))
    complemento      = db.Column(db.String(100))
    bairro           = db.Column(db.String(100))
    cidade           = db.Column(db.String(100))
    estado           = db.Column(db.String(2))
    cep              = db.Column(db.String(9))
    telefone_contato = db.Column(db.String(20))
    instagram        = db.Column(db.String(100))


# ── Usuários ───────────────────────────────────────────────────────────────────

class Usuario(db.Model):
    __tablename__ = 'usuarios'

    id              = db.Column(db.Integer, primary_key=True)
    barbearia_id    = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=True, index=True)
    nome            = db.Column(db.String(100), nullable=False)
    telefone        = db.Column(db.String(20), nullable=False)
    email           = db.Column(db.String(100))
    senha           = db.Column(db.String(255))
    perfil          = db.Column(db.String(20), nullable=False)  # super_admin, gestor, barbeiro, cliente
    ativo           = db.Column(db.Boolean, default=True, nullable=False)
    foto_perfil_url = db.Column(db.String(255))
    data_nascimento = db.Column(db.Date)
    criado_em       = db.Column(db.DateTime, default=_utcnow)
    # ── P2: 2FA ───────────────────────────────────────────────────────────────
    duplo_fator_ativo   = db.Column(db.Boolean, nullable=False, default=False)
    duplo_fator_segredo = db.Column(db.String(64))  # TOTP secret (armazenar criptografado em produção)
    # ── P2: WhatsApp ──────────────────────────────────────────────────────────
    whatsapp_verificado = db.Column(db.Boolean, nullable=False, default=False)

    barbeiro = db.relationship('Barbeiro', backref='usuario', uselist=False)
    cliente  = db.relationship('Cliente',  backref='usuario', uselist=False)


class Barbeiro(db.Model):
    __tablename__ = 'barbeiros'

    id                        = db.Column(db.Integer, primary_key=True)
    barbearia_id              = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False, index=True)
    usuario_id                = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    foto                      = db.Column(db.String(255))
    bio                       = db.Column(db.String(300))
    comissao_percentual       = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    comissao_plano_percentual = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    ativo                     = db.Column(db.Boolean, default=True, nullable=False)
    # ── P2: Comissão dinâmica ─────────────────────────────────────────────────
    comissao_tipo        = db.Column(db.String(20), nullable=False, default='percentual')
    # 'percentual' | 'fixo' — quando 'fixo', usa comissao_valor_fixo por atendimento
    comissao_valor_fixo  = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    servicos            = db.relationship('BarbeiroServico', backref='barbeiro')
    configuracao_agenda = db.relationship('ConfiguracaoAgenda', backref='barbeiro', uselist=False)


class Cliente(db.Model):
    __tablename__ = 'clientes'
    __table_args__ = (
        db.UniqueConstraint('barbearia_id', 'telefone', name='uq_cliente_barbearia_telefone'),
    )

    id              = db.Column(db.Integer, primary_key=True)
    barbearia_id    = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False, index=True)
    usuario_id      = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    nome            = db.Column(db.String(100), nullable=False)
    telefone        = db.Column(db.String(20), nullable=False)
    email           = db.Column(db.String(150))
    foto            = db.Column(db.String(255))
    observacoes     = db.Column(db.Text)
    ativo           = db.Column(db.Boolean, default=True, nullable=False)
    primeira_visita = db.Column(db.Date)
    ultimo_acesso   = db.Column(db.DateTime)
    notif_sms       = db.Column(db.Boolean, default=True, nullable=False)
    notif_whatsapp  = db.Column(db.Boolean, default=True, nullable=False)
    notif_email     = db.Column(db.Boolean, default=True, nullable=False)
    data_nascimento = db.Column(db.Date)
    criado_em       = db.Column(db.DateTime, default=_utcnow)
    # ── P2: Preferências ──────────────────────────────────────────────────────
    barbeiro_preferido_id = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=True)
    # ── P2: Carteira digital ──────────────────────────────────────────────────
    saldo_creditos        = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    # ── P2: WhatsApp opt-in ───────────────────────────────────────────────────
    whatsapp_opt_in       = db.Column(db.Boolean, nullable=False, default=False)
    # Indica que o cliente autorizou envio de mensagens via WhatsApp Business


# ── Catálogo ───────────────────────────────────────────────────────────────────

class Servico(TenantMixin, db.Model):
    __tablename__ = 'servicos'

    id              = db.Column(db.Integer, primary_key=True)
    nome            = db.Column(db.String(100), nullable=False)
    descricao       = db.Column(db.String(300))
    duracao_minutos = db.Column(db.Integer, nullable=False)
    preco           = db.Column(db.Numeric(10, 2), nullable=False)
    foto            = db.Column(db.String(255))
    ativo           = db.Column(db.Boolean, default=True, nullable=False)


class BarbeiroServico(db.Model):
    __tablename__ = 'barbeiro_servicos'
    __table_args__ = (
        db.UniqueConstraint('barbeiro_id', 'servico_id', name='uq_barbeiro_servico'),
    )

    id          = db.Column(db.Integer, primary_key=True)
    barbeiro_id = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=False, index=True)
    servico_id  = db.Column(db.Integer, db.ForeignKey('servicos.id'), nullable=False)


class Produto(TenantMixin, db.Model):
    __tablename__ = 'produtos'

    id                   = db.Column(db.Integer, primary_key=True)
    nome                 = db.Column(db.String(100), nullable=False)
    categoria            = db.Column(db.String(50))
    preco                = db.Column(db.Numeric(10, 2), nullable=False)
    quantidade_estoque   = db.Column(db.Integer, nullable=False, default=0)
    quantidade_reservada = db.Column(db.Integer, nullable=False, default=0)
    foto                 = db.Column(db.String(255))
    ativo                = db.Column(db.Boolean, default=True, nullable=False)
    criado_em            = db.Column(db.DateTime, default=_utcnow)

    @property
    def quantidade_disponivel(self):
        return max(0, self.quantidade_estoque - (self.quantidade_reservada or 0))


# ── Agenda ─────────────────────────────────────────────────────────────────────

class ConfiguracaoAgenda(db.Model):
    __tablename__ = 'configuracao_agenda'
    __table_args__ = (
        db.UniqueConstraint('barbeiro_id', name='uq_configuracao_agenda_barbeiro'),
    )

    id                 = db.Column(db.Integer, primary_key=True)
    barbearia_id       = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False, index=True)
    barbeiro_id        = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=False)
    horario_abertura   = db.Column(db.Time, nullable=False)
    horario_fechamento = db.Column(db.Time, nullable=False)
    intervalo_minutos  = db.Column(db.Integer, nullable=False)
    loja_aberta        = db.Column(db.Boolean, default=True, nullable=False)
    atualizado_em      = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)


class Agendamento(TenantMixin, db.Model):
    """v2: sem servico_id — todos os serviços estão em AgendamentoServico."""
    __tablename__ = 'agendamentos'

    id               = db.Column(db.Integer, primary_key=True)
    cliente_id       = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False, index=True)
    barbeiro_id      = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=False, index=True)
    data_hora        = db.Column(db.DateTime, nullable=False)
    duracao_minutos  = db.Column(db.Integer, nullable=False)
    status           = db.Column(db.String(20), nullable=False)  # aguardando_pagamento, agendado, concluido, cancelado
    valor_total      = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    observacao       = db.Column(db.String(300))
    metodo_pagamento = db.Column(db.String(20))  # pix, local
    criado_em        = db.Column(db.DateTime, default=_utcnow)


class AgendamentoServico(db.Model):
    __tablename__ = 'agendamento_servicos'

    id               = db.Column(db.Integer, primary_key=True)
    agendamento_id   = db.Column(db.Integer, db.ForeignKey('agendamentos.id'), nullable=False, index=True)
    servico_id       = db.Column(db.Integer, db.ForeignKey('servicos.id'), nullable=False)
    quantidade       = db.Column(db.Integer, nullable=False, default=1)
    preco_unitario   = db.Column(db.Numeric(10, 2), nullable=False)
    is_plano         = db.Column(db.Boolean, nullable=False, default=False)
    cliente_plano_id = db.Column(db.Integer, db.ForeignKey('cliente_plano.id'), nullable=True)


class AgendamentoSolicitacaoPix(db.Model):
    """Comprovante PIX enviado pelo cliente para um agendamento público."""
    __tablename__ = 'agendamento_solicitacao_pix'

    id              = db.Column(db.Integer, primary_key=True)
    barbearia_id    = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False, index=True)
    agendamento_id  = db.Column(db.Integer, db.ForeignKey('agendamentos.id'), nullable=False, unique=True)
    comprovante_url = db.Column(db.String(255))
    status          = db.Column(db.String(20), nullable=False, default='pendente')  # pendente, aprovado, rejeitado
    motivo_rejeicao = db.Column(db.String(500))
    criado_em       = db.Column(db.DateTime, default=_utcnow)
    respondido_em   = db.Column(db.DateTime)


class HorarioBloqueado(TenantMixin, db.Model):
    __tablename__ = 'horarios_bloqueados'

    id               = db.Column(db.Integer, primary_key=True)
    barbeiro_id      = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=False, index=True)
    data_hora_inicio = db.Column(db.DateTime, nullable=False)
    data_hora_fim    = db.Column(db.DateTime, nullable=False)
    motivo           = db.Column(db.String(100))


class PausaBarbeiro(db.Model):
    """Pausas diárias recorrentes de um barbeiro (almoço, café, etc.)."""
    __tablename__ = 'pausa_barbeiro'

    id           = db.Column(db.Integer, primary_key=True)
    barbearia_id = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False)
    barbeiro_id  = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=False, index=True)
    hora_inicio  = db.Column(db.Time, nullable=False)
    hora_fim     = db.Column(db.Time, nullable=False)
    descricao    = db.Column(db.String(50))
    criado_em    = db.Column(db.DateTime, default=_utcnow)


# ── Atendimento / Caixa ────────────────────────────────────────────────────────

class ReservaProduto(db.Model):
    __tablename__ = 'reservas_produtos'

    id             = db.Column(db.Integer, primary_key=True)
    agendamento_id = db.Column(db.Integer, db.ForeignKey('agendamentos.id'), nullable=False, index=True)
    produto_id     = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    quantidade     = db.Column(db.Integer, nullable=False, default=1)
    status         = db.Column(db.String(20), nullable=False)  # reservado, confirmado, cancelado


class Atendimento(TenantMixin, db.Model):
    __tablename__ = 'atendimentos'

    id              = db.Column(db.Integer, primary_key=True)
    agendamento_id  = db.Column(db.Integer, db.ForeignKey('agendamentos.id'), nullable=False, unique=True)
    barbeiro_id     = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=False, index=True)
    cliente_id      = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    status_operacao = db.Column(db.String(20), nullable=False)  # efetuado, nao_efetuado
    total           = db.Column(db.Numeric(10, 2))
    criado_em       = db.Column(db.DateTime, default=_utcnow)


class AtendimentoItem(db.Model):
    __tablename__ = 'atendimento_itens'

    id             = db.Column(db.Integer, primary_key=True)
    atendimento_id = db.Column(db.Integer, db.ForeignKey('atendimentos.id'), nullable=False, index=True)
    tipo           = db.Column(db.String(20), nullable=False)  # servico, produto
    servico_id     = db.Column(db.Integer, db.ForeignKey('servicos.id'))
    produto_id     = db.Column(db.Integer, db.ForeignKey('produtos.id'))
    preco_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    quantidade     = db.Column(db.Integer, nullable=False, default=1)


class Pagamento(db.Model):
    __tablename__ = 'pagamentos'

    id                     = db.Column(db.Integer, primary_key=True)
    atendimento_id         = db.Column(db.Integer, db.ForeignKey('atendimentos.id'), nullable=False, index=True)
    forma_pagamento        = db.Column(db.String(30), nullable=False)  # pix, dinheiro, credito, debito
    valor                  = db.Column(db.Numeric(10, 2), nullable=False)
    status                 = db.Column(db.String(20), nullable=False, default='aprovado')
    gateway                = db.Column(db.String(30))
    gateway_transaction_id = db.Column(db.String(100))
    criado_em              = db.Column(db.DateTime, default=_utcnow)
    # ── P2: Integração de pagamento externo (Stripe / PayPal / Asaas) ─────────
    gateway_status   = db.Column(db.String(50))   # status retornado pelo gateway (ex: 'succeeded', 'pending')
    gateway_metadata = db.Column(db.Text)          # JSON raw da resposta do gateway (para reconciliação)


# ── Senhas / Liberações ────────────────────────────────────────────────────────

class SolicitacaoSenha(db.Model):
    __tablename__ = 'solicitacoes_senha'

    id           = db.Column(db.Integer, primary_key=True)
    usuario_id   = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    barbearia_id = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False)
    status       = db.Column(db.String(20), nullable=False, default='pendente')  # pendente, resolvido
    criado_em    = db.Column(db.DateTime, default=_utcnow)


class SolicitacaoLiberacao(TenantMixin, db.Model):
    __tablename__ = 'solicitacoes_liberacao'

    id               = db.Column(db.Integer, primary_key=True)
    barbeiro_id      = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=False, index=True)
    data             = db.Column(db.Date, nullable=False)
    hora_inicio      = db.Column(db.Time)   # null = dia inteiro
    hora_fim         = db.Column(db.Time)   # null = dia inteiro
    motivo           = db.Column(db.String(300))
    status           = db.Column(db.String(20), nullable=False, default='pendente')  # pendente, aprovado, rejeitado
    notificado       = db.Column(db.Boolean, default=False, nullable=False)
    data_solicitacao = db.Column(db.DateTime, default=_utcnow)
    data_resposta    = db.Column(db.DateTime)


# ── Planos ─────────────────────────────────────────────────────────────────────

class Plano(TenantMixin, db.Model):
    """v2: barbeiro_id nullable — NULL significa plano aberto (todos os barbeiros)."""
    __tablename__ = 'planos'

    id            = db.Column(db.Integer, primary_key=True)
    barbeiro_id   = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=True)
    nome          = db.Column(db.String(150), nullable=False)
    descricao     = db.Column(db.Text)
    preco_mensal  = db.Column(db.Numeric(10, 2), nullable=False)
    ativo         = db.Column(db.Boolean, default=True, nullable=False)
    criado_em     = db.Column(db.DateTime, default=_utcnow)
    atualizado_em = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)
    # ── P2: Planos configuráveis ──────────────────────────────────────────────
    trial_dias      = db.Column(db.Integer, nullable=False, default=0)   # 0 = sem trial
    max_assinaturas = db.Column(db.Integer)                              # NULL = ilimitado


class PlanoServico(db.Model):
    __tablename__ = 'plano_servicos'
    __table_args__ = (
        db.UniqueConstraint('plano_id', 'servico_id', name='uq_plano_servico'),
    )

    id                = db.Column(db.Integer, primary_key=True)
    plano_id          = db.Column(db.Integer, db.ForeignKey('planos.id'), nullable=False, index=True)
    servico_id        = db.Column(db.Integer, db.ForeignKey('servicos.id'), nullable=False)
    limite_uso_mensal = db.Column(db.Integer, nullable=False)  # 99999 = ilimitado (sentinela)
    dias_expiracao    = db.Column(db.Integer, nullable=False)
    ativo             = db.Column(db.Boolean, default=True, nullable=False)


class ClientePlano(db.Model):
    __tablename__ = 'cliente_plano'

    id           = db.Column(db.Integer, primary_key=True)
    barbearia_id = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False, index=True)
    cliente_id   = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False, index=True)
    plano_id     = db.Column(db.Integer, db.ForeignKey('planos.id'), nullable=False)
    barbeiro_id  = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=True)  # null = plano aberto
    data_inicio  = db.Column(db.Date, nullable=False)
    data_fim     = db.Column(db.Date)
    ativo        = db.Column(db.Boolean, default=True, nullable=False)
    criado_em    = db.Column(db.DateTime, default=_utcnow)
    # ── P2: Renovação automática ──────────────────────────────────────────────
    auto_renovar = db.Column(db.Boolean, nullable=False, default=False)


class ClientePlanoUso(db.Model):
    __tablename__ = 'cliente_plano_uso'

    id               = db.Column(db.Integer, primary_key=True)
    cliente_plano_id = db.Column(db.Integer, db.ForeignKey('cliente_plano.id'), nullable=False, index=True)
    servico_id       = db.Column(db.Integer, db.ForeignKey('servicos.id'), nullable=False)
    data_uso         = db.Column(db.Date, nullable=False)
    semana_do_mes    = db.Column(db.Integer, nullable=False)
    usado            = db.Column(db.Boolean, default=False, nullable=False)


class ClientePlanoSolicitacao(db.Model):
    __tablename__ = 'cliente_plano_solicitacao'

    id               = db.Column(db.Integer, primary_key=True)
    barbearia_id     = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False, index=True)
    cliente_id       = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    plano_id         = db.Column(db.Integer, db.ForeignKey('planos.id'), nullable=False)
    barbeiro_id      = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=True)  # null = plano aberto
    valor            = db.Column(db.Numeric(10, 2), nullable=False)
    comprovante_url  = db.Column(db.String(255))
    metodo_pagamento = db.Column(db.String(20), nullable=False, default='pix')
    status           = db.Column(db.String(20), nullable=False, default='pendente')  # pendente, aprovado, rejeitado
    criado_em        = db.Column(db.DateTime, default=_utcnow)
    aprovado_em      = db.Column(db.DateTime)
    motivo_rejeicao  = db.Column(db.String(500))


class PlanoBarbeiro(db.Model):
    __tablename__ = 'plano_barbeiros'
    __table_args__ = (
        db.UniqueConstraint('plano_id', 'barbeiro_id', name='uq_plano_barbeiro'),
    )

    id            = db.Column(db.Integer, primary_key=True)
    plano_id      = db.Column(db.Integer, db.ForeignKey('planos.id'), nullable=False, index=True)
    barbeiro_id   = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=False)
    barbearia_id  = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False)
    adicionado_em = db.Column(db.DateTime, default=_utcnow)


# ── VIP ────────────────────────────────────────────────────────────────────────

class VipNivel(TenantMixin, db.Model):
    __tablename__ = 'vip_niveis'
    __table_args__ = (
        db.UniqueConstraint('barbearia_id', 'nivel', name='uq_barbearia_nivel'),
    )

    id               = db.Column(db.Integer, primary_key=True)
    nivel            = db.Column(db.Integer, nullable=False)
    brinde_descricao = db.Column(db.Text, nullable=False)
    tipo_brinde      = db.Column(db.String(20), nullable=False)  # fisico, desconto
    valor_desconto   = db.Column(db.Numeric(10, 2))
    ativo            = db.Column(db.Boolean, default=True, nullable=False)
    modo_brinde_ativo = db.Column(db.Boolean, default=True, nullable=False)
    criado_em        = db.Column(db.DateTime, default=_utcnow)


class ClienteVip(db.Model):
    __tablename__ = 'cliente_vip'
    __table_args__ = (
        db.UniqueConstraint('cliente_id', 'barbearia_id', name='uq_cliente_barbearia_vip'),
    )

    id                     = db.Column(db.Integer, primary_key=True)
    cliente_id             = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False, index=True)
    barbearia_id           = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False)
    nivel_vip_atual        = db.Column(db.Integer, default=0, nullable=False)
    brindes_resgatados     = db.Column(db.Text, default='[]')  # JSON serializado
    data_proxima_renovacao = db.Column(db.Date)
    criado_em              = db.Column(db.DateTime, default=_utcnow)
    atualizado_em          = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)


# ── Feature Flags (v2: normalizado) ────────────────────────────────────────────

class FeatureMetadata(db.Model):
    """Catálogo de features disponíveis na plataforma. Populado por seed — não alterar via API."""
    __tablename__ = 'feature_metadata'

    id        = db.Column(db.Integer, primary_key=True)
    nome      = db.Column(db.String(50), unique=True, nullable=False)
    descricao = db.Column(db.String(200))

    flags = db.relationship('FeatureBarbearia', backref='feature')


class FeatureBarbearia(db.Model):
    """Flag ativo/inativo de uma feature específica para uma barbearia específica."""
    __tablename__ = 'feature_barbearia'
    __table_args__ = (
        db.UniqueConstraint('barbearia_id', 'feature_id', name='uq_feature_barbearia'),
    )

    id            = db.Column(db.Integer, primary_key=True)
    barbearia_id  = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False, index=True)
    feature_id    = db.Column(db.Integer, db.ForeignKey('feature_metadata.id'), nullable=False)
    ativo         = db.Column(db.Boolean, default=False, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)


# ── Auditoria / Customização ───────────────────────────────────────────────────

class AuditoriaLog(db.Model):
    __tablename__ = 'auditoria_log'

    id           = db.Column(db.Integer, primary_key=True)
    usuario_id   = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    barbearia_id = db.Column(db.Integer, db.ForeignKey('barbearias.id'))
    tipo_acao    = db.Column(db.String(50), nullable=False)   # create, edit, delete, login
    entidade     = db.Column(db.String(100), nullable=False)
    entidade_id  = db.Column(db.Integer)
    descricao    = db.Column(db.String(500), nullable=False)
    criado_em    = db.Column(db.DateTime, default=_utcnow)


class BarbeariaCustomizacao(db.Model):
    __tablename__ = 'barbearia_customizacao'

    id                    = db.Column(db.Integer, primary_key=True)
    barbearia_id          = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False, unique=True)
    cor_primaria          = db.Column(db.String(7), default='#BA7517')
    cor_secundaria        = db.Column(db.String(7), default='#1a1a1a')
    cor_acentuacao        = db.Column(db.String(7), default='#FFD700')
    texto_primario        = db.Column(db.String(7), default='#FFFFFF')
    texto_secundario      = db.Column(db.String(7), default='#CCCCCC')
    texto_terciario       = db.Column(db.String(7), default='#888888')
    botao_primario        = db.Column(db.String(7), default='#FFD700')
    botao_secundario      = db.Column(db.String(7), default='#555555')
    logo_filename              = db.Column(db.String(255))
    fundo_padrao_filename      = db.Column(db.String(255))
    logo_url                   = db.Column(db.String(500))
    imagem_capa_url            = db.Column(db.String(500))
    imagem_boas_vindas_url     = db.Column(db.String(500))
    fonte                      = db.Column(db.String(50), default='Inter')
    criado_em             = db.Column(db.DateTime, default=_utcnow)
    atualizado_em         = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)


# ── P2: Novas tabelas ──────────────────────────────────────────────────────────

class ClienteNota(db.Model):
    """
    Notas estruturadas por cliente — observações, alertas e preferências registradas
    pelo gestor ou barbeiro. Diferente de Cliente.observacoes (texto livre único),
    aqui cada nota tem autor, tipo e timestamp.
    Sem lógica de negócio — só persistência.
    """
    __tablename__ = 'cliente_notas'

    id              = db.Column(db.Integer, primary_key=True)
    barbearia_id    = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False, index=True)
    cliente_id      = db.Column(db.Integer, db.ForeignKey('clientes.id'),   nullable=False, index=True)
    autor_usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'),  nullable=True)
    tipo            = db.Column(db.String(30), nullable=False, default='observacao')
    # 'observacao' | 'alerta' | 'preferencia'
    conteudo        = db.Column(db.Text, nullable=False)
    criado_em       = db.Column(db.DateTime, default=_utcnow)


class FilaEspera(db.Model):
    """
    Cliente que aguarda uma vaga em determinado dia/barbeiro.
    Sem lógica de promoção — o gestor ou um job futuro aciona manualmente.
    """
    __tablename__ = 'fila_espera'

    id                    = db.Column(db.Integer, primary_key=True)
    barbearia_id          = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False, index=True)
    cliente_id            = db.Column(db.Integer, db.ForeignKey('clientes.id'),   nullable=False, index=True)
    barbeiro_preferido_id = db.Column(db.Integer, db.ForeignKey('barbeiros.id'),  nullable=True)
    servico_id            = db.Column(db.Integer, db.ForeignKey('servicos.id'),   nullable=True)
    data_preferida        = db.Column(db.Date, nullable=True)
    prioridade            = db.Column(db.Integer, nullable=False, default=0)   # maior = mais prioritário
    posicao               = db.Column(db.Integer, nullable=False, default=0)   # exibida ao cliente
    status                = db.Column(db.String(20), nullable=False, default='aguardando')
    # 'aguardando' | 'chamado' | 'atendido' | 'cancelado'
    chamado_em            = db.Column(db.DateTime)  # quando o gestor chamou o cliente
    criado_em             = db.Column(db.DateTime, default=_utcnow)


class BarbeiroComissaoServico(db.Model):
    """
    Override de comissão por serviço específico para um barbeiro.
    Quando presente, tem precedência sobre comissao_percentual / comissao_valor_fixo do Barbeiro.
    Sem lógica de cálculo — só armazenamento.
    """
    __tablename__ = 'barbeiro_comissao_servico'
    __table_args__ = (
        db.UniqueConstraint('barbeiro_id', 'servico_id', name='uq_comissao_barbeiro_servico'),
    )

    id                   = db.Column(db.Integer, primary_key=True)
    barbeiro_id          = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=False, index=True)
    servico_id           = db.Column(db.Integer, db.ForeignKey('servicos.id'),  nullable=False)
    barbearia_id         = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False, index=True)
    comissao_tipo        = db.Column(db.String(20), nullable=False, default='percentual')
    comissao_percentual  = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    comissao_valor_fixo  = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    criado_em            = db.Column(db.DateTime, default=_utcnow)
    atualizado_em        = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)


# ── Configuração de Agendamento por Tenant (A3: regras como configuração) ──────
# As rotas de agendamento lêem estas regras — nunca assumem valores fixos.
# Campo `tipo_recurso` reservado para Parte B (multi-segmento).

class ConfiguracaoAgendamento(db.Model):
    """Regras de agendamento configuráveis por tenant. Uma linha por barbearia."""
    __tablename__ = 'configuracao_agendamento'

    id                              = db.Column(db.Integer, primary_key=True)
    barbearia_id                    = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False, unique=True)
    cancelamento_horas_minimas      = db.Column(db.Integer, nullable=False, default=3)
    permite_multi_servico           = db.Column(db.Boolean, nullable=False, default=True)
    quick_booking_sem_login         = db.Column(db.Boolean, nullable=False, default=True)
    intervalo_slot_minutos          = db.Column(db.Integer, nullable=False, default=15)
    antecedencia_maxima_dias        = db.Column(db.Integer, nullable=False, default=60)
    # Antecedência de lembretes (A3: configurável por tenant, não cravar constante)
    notif_antecedencia_cliente_min  = db.Column(db.Integer, nullable=False, default=30)
    notif_antecedencia_barbeiro_min = db.Column(db.Integer, nullable=False, default=15)
    atualizado_em                   = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)


# ── Notificações in-app ────────────────────────────────────────────────────────

class Notificacao(db.Model):
    """
    Uma entrada = uma entrega em um canal.
    Canais suportados agora: 'in_app'.
    Canais preparados (stubs prontos, serviço não configurado): 'email', 'web_push'.
    Para adicionar um canal futuro: registrar despachante em app/utils/notificacoes.py — sem
    alterar a geração de notificações.
    """
    __tablename__ = 'notificacoes'

    id             = db.Column(db.Integer, primary_key=True)
    barbearia_id   = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False, index=True)
    usuario_id     = db.Column(db.Integer, db.ForeignKey('usuarios.id'),   nullable=False, index=True)
    agendamento_id = db.Column(db.Integer, db.ForeignKey('agendamentos.id'), nullable=True, index=True)
    tipo           = db.Column(db.String(50),  nullable=False)
    # 'lembrete_cliente', 'lembrete_barbeiro', 'confirmacao', 'cancelamento', 'custom'
    canal          = db.Column(db.String(20),  nullable=False, default='in_app')
    # 'in_app' | 'email' | 'web_push'
    titulo         = db.Column(db.String(200), nullable=False)
    corpo          = db.Column(db.String(1000), nullable=False)
    lida           = db.Column(db.Boolean, nullable=False, default=False)
    # lida=True só faz sentido para in_app; email/web_push usam enviada
    enviada        = db.Column(db.Boolean, nullable=False, default=False)
    criado_em      = db.Column(db.DateTime, default=_utcnow)
