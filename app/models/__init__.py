from datetime import datetime, timezone
from app.extensions import db
from app.models.mixins import TenantMixin
from app.utils.tz import naive_brasilia

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
    # ── Multi-segmento (Parte B) ───────────────────────────────────────────────
    segmento_id      = db.Column(db.Integer, db.ForeignKey('segmentos.id'), nullable=True)


# ── Segmento e Rótulos Dinâmicos ──────────────────────────────────────────────

class Segmento(db.Model):
    __tablename__ = 'segmentos'

    id    = db.Column(db.Integer, primary_key=True)
    nome  = db.Column(db.String(100), nullable=False)
    chave = db.Column(db.String(50), unique=True, nullable=False, index=True)


class SegmentoRotulo(db.Model):
    __tablename__ = 'segmento_rotulos'

    id          = db.Column(db.Integer, primary_key=True)
    segmento_id = db.Column(db.Integer, db.ForeignKey('segmentos.id'), unique=True, nullable=False)

    rotulo_tenant        = db.Column(db.String(50), default='Estabelecimento')
    rotulo_tenant_plural = db.Column(db.String(50), default='Estabelecimentos')

    rotulo_profissional        = db.Column(db.String(50), default='Profissional')
    rotulo_profissional_plural = db.Column(db.String(50), default='Profissionais')

    rotulo_servico        = db.Column(db.String(50), default='Serviço')
    rotulo_servico_plural = db.Column(db.String(50), default='Serviços')

    rotulo_agendamento        = db.Column(db.String(50), default='Agendamento')
    rotulo_agendamento_plural = db.Column(db.String(50), default='Agendamentos')

    rotulo_cliente        = db.Column(db.String(50), default='Cliente')
    rotulo_cliente_plural = db.Column(db.String(50), default='Clientes')

    rotulo_produto        = db.Column(db.String(50), default='Produto')
    rotulo_produto_plural = db.Column(db.String(50), default='Produtos')

    rotulo_plano        = db.Column(db.String(50), default='Plano')
    rotulo_plano_plural = db.Column(db.String(50), default='Planos')

    rotulo_pagamento   = db.Column(db.String(50), default='Pagamento')
    rotulo_faturamento = db.Column(db.String(50), default='Faturamento')
    rotulo_relatorio   = db.Column(db.String(50), default='Relatório')

    atualizado_em = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)


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
    # ── Bloco 1.2: revogação em massa de tokens ────────────────────────────────
    # Qualquer JWT com claim `iat` anterior a este timestamp é considerado inválido.
    token_valido_apos = db.Column(db.DateTime, nullable=True)

    barbeiro = db.relationship('Barbeiro', backref='usuario', uselist=False)
    cliente  = db.relationship('Cliente',  backref='usuario', uselist=False)


class TokenRevogado(db.Model):
    """Blacklist de JWTs individuais revogados (logout). Ver também
    Usuario.token_valido_apos para revogação em massa (desativação de conta/tenant)."""
    __tablename__ = 'tokens_revogados'

    id           = db.Column(db.Integer, primary_key=True)
    jti          = db.Column(db.String(64), unique=True, nullable=False, index=True)
    usuario_id   = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True, index=True)
    tipo         = db.Column(db.String(10))  # 'access' | 'refresh'
    revogado_em  = db.Column(db.DateTime, default=_utcnow)
    motivo       = db.Column(db.String(100))  # 'logout', 'usuario_desativado', 'tenant_desativado'


class Barbeiro(db.Model):
    __tablename__ = 'barbeiros'
    __table_args__ = (
        db.CheckConstraint(
            'comissao_percentual >= 0 AND comissao_percentual <= 100',
            name='ck_barbeiros_comissao_percentual_range',
        ),
    )

    id                        = db.Column(db.Integer, primary_key=True)
    barbearia_id              = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False, index=True)
    usuario_id                = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
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
    usuario_id      = db.Column(db.Integer, db.ForeignKey('usuarios.id'), index=True)
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
    servico_id  = db.Column(db.Integer, db.ForeignKey('servicos.id'), nullable=False, index=True)


class CategoriaProduto(TenantMixin, db.Model):
    """Categorias de produto do catálogo (Script 18/Bloco 6.4)."""
    __tablename__ = 'categoria_produto'
    __table_args__ = (
        db.UniqueConstraint('barbearia_id', 'nome', name='uq_categoria_produto_barbearia_nome'),
    )

    id    = db.Column(db.Integer, primary_key=True)
    nome  = db.Column(db.String(80), nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)


class Produto(TenantMixin, db.Model):
    __tablename__ = 'produtos'
    __table_args__ = (
        db.CheckConstraint('quantidade_estoque >= 0', name='ck_produtos_quantidade_estoque_positivo'),
        db.CheckConstraint('quantidade_reservada >= 0', name='ck_produtos_quantidade_reservada_positivo'),
        db.CheckConstraint('custo_unitario >= 0', name='ck_produtos_custo_unitario_positivo'),
        db.CheckConstraint('estoque_minimo >= 0', name='ck_produtos_estoque_minimo_positivo'),
    )

    id                   = db.Column(db.Integer, primary_key=True)
    nome                 = db.Column(db.String(100), nullable=False)
    categoria            = db.Column(db.String(50))  # legado (texto livre) — mantido por compatibilidade, ver categoria_id
    categoria_id         = db.Column(db.Integer, db.ForeignKey('categoria_produto.id'), nullable=True, index=True)
    marca                = db.Column(db.String(80))
    preco                = db.Column(db.Numeric(10, 2), nullable=False)
    custo_unitario       = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    codigo_barras        = db.Column(db.String(50))
    quantidade_estoque   = db.Column(db.Integer, nullable=False, default=0)
    quantidade_reservada = db.Column(db.Integer, nullable=False, default=0)
    estoque_minimo       = db.Column(db.Integer, nullable=False, default=0)
    foto                 = db.Column(db.String(255))  # legado — ver foto_url (Cloudinary, Script 18)
    foto_url             = db.Column(db.String(300))
    ativo                = db.Column(db.Boolean, default=True, nullable=False)
    criado_em            = db.Column(db.DateTime, default=_utcnow)

    @property
    def quantidade_disponivel(self):
        return max(0, self.quantidade_estoque - (self.quantidade_reservada or 0))


class MovimentacaoEstoque(TenantMixin, db.Model):
    """Auditoria de toda entrada/saída de estoque (Script 18). quantidade
    sempre positiva (magnitude) — tipo + a função do serviço que gravou
    decidem a direção. Ver app.constants.TipoMovimentacaoEstoque."""
    __tablename__ = 'movimentacao_estoque'
    __table_args__ = (
        db.CheckConstraint('quantidade > 0', name='ck_movimentacao_estoque_quantidade_positiva'),
        db.CheckConstraint(
            "tipo IN ('entrada','saida_venda','saida_uso','ajuste')",
            name='ck_movimentacao_estoque_tipo_valido',
        ),
    )

    id                          = db.Column(db.Integer, primary_key=True)
    produto_id                  = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False, index=True)
    tipo                        = db.Column(db.String(20), nullable=False)  # entrada, saida_venda, saida_uso, ajuste
    quantidade                  = db.Column(db.Integer, nullable=False)
    quantidade_apos             = db.Column(db.Integer, nullable=False)  # snapshot do estoque após a movimentação
    motivo                      = db.Column(db.String(200))
    usuario_id                  = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    referencia_venda_id         = db.Column(db.Integer, db.ForeignKey('venda.id'), nullable=True)
    referencia_atendimento_id   = db.Column(db.Integer, db.ForeignKey('atendimentos.id'), nullable=True)
    criado_em                   = db.Column(db.DateTime, default=naive_brasilia)


class Venda(TenantMixin, db.Model):
    """Venda avulsa de produto (sem agendamento) — Script 18."""
    __tablename__ = 'venda'
    __table_args__ = (
        db.CheckConstraint('valor_total >= 0', name='ck_venda_valor_total_positivo'),
        db.CheckConstraint("status IN ('concluida','cancelada')", name='ck_venda_status_valido'),
        db.CheckConstraint("metodo_pagamento IN ('pix','dinheiro','cartao')", name='ck_venda_metodo_pagamento_valido'),
    )

    id                    = db.Column(db.Integer, primary_key=True)
    cliente_id            = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=True)
    cliente_nome_livre     = db.Column(db.String(100), nullable=True)  # venda pra quem não é cliente cadastrado
    barbeiro_id           = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=True)  # quem vendeu → comissão
    usuario_registro_id   = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    metodo_pagamento      = db.Column(db.String(20), nullable=False)  # pix, dinheiro, cartao
    status                = db.Column(db.String(20), nullable=False, default='concluida')  # concluida, cancelada
    valor_total           = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    criado_em             = db.Column(db.DateTime, default=naive_brasilia)


class VendaItem(db.Model):
    __tablename__ = 'venda_item'
    __table_args__ = (
        db.CheckConstraint('quantidade > 0', name='ck_venda_item_quantidade_positiva'),
    )

    id                       = db.Column(db.Integer, primary_key=True)
    venda_id                 = db.Column(db.Integer, db.ForeignKey('venda.id'), nullable=False, index=True)
    produto_id               = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    quantidade               = db.Column(db.Integer, nullable=False)
    preco_unitario           = db.Column(db.Numeric(10, 2), nullable=False)
    custo_unitario_snapshot  = db.Column(db.Numeric(10, 2), nullable=False, default=0)  # margem histórica
    comissao_valor           = db.Column(db.Numeric(10, 2), nullable=False, default=0)


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
    loja_aberta               = db.Column(db.Boolean, default=True, nullable=False)
    permite_horario_barbeiro  = db.Column(db.Boolean, default=False, nullable=False)
    atualizado_em             = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)


class Agendamento(TenantMixin, db.Model):
    """v2: sem servico_id — todos os serviços estão em AgendamentoServico."""
    __tablename__ = 'agendamentos'
    __table_args__ = (
        # status: VARCHAR(30) no banco desde a migration a3f8c2e1d047 — o model
        # ficou desatualizado em String(20) até o Bloco 2.1 corrigir (o maior
        # valor válido, 'aguardando_transferencia', tem 24 chars).
        db.CheckConstraint(
            "status IN ('agendado','concluido','cancelado','em_atendimento',"
            "'aguardando_comprovante','aguardando_aprovacao','aguardando_pagamento',"
            "'nao_realizado','aguardando_transferencia')",
            name='ck_agendamentos_status_valido',
        ),
        db.CheckConstraint('valor_total >= 0', name='ck_agendamentos_valor_total_positivo'),
        db.CheckConstraint('valor_desconto >= 0', name='ck_agendamentos_valor_desconto_positivo'),
    )

    id               = db.Column(db.Integer, primary_key=True)
    cliente_id       = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False, index=True)
    barbeiro_id      = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=False, index=True)
    data_hora        = db.Column(db.DateTime, nullable=False)
    duracao_minutos  = db.Column(db.Integer, nullable=False)
    # Valores válidos: ver ck_agendamentos_status_valido acima.
    status           = db.Column(db.String(30), nullable=False)
    valor_total      = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    observacao       = db.Column(db.String(300))
    metodo_pagamento = db.Column(db.String(20), nullable=False, default='local')  # pix, local
    criado_em        = db.Column(db.DateTime, default=_utcnow)
    # ── Cupons de desconto ────────────────────────────────────────────────────
    cupom_id         = db.Column(db.Integer, db.ForeignKey('cupons.id'), nullable=True, index=True)
    valor_desconto   = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    # ── Bloco 5.1: relationship somente-leitura para eager loading (selectinload).
    # viewonly=True — o código continua criando AgendamentoServico via
    # `agendamento_id=ag.id` explícito, não via `ag.itens.append(...)`; isso
    # aqui é só pra permitir carregar em lote, nunca pra escrever.
    itens = db.relationship('AgendamentoServico', viewonly=True, lazy='select')


class AgendamentoServico(db.Model):
    __tablename__ = 'agendamento_servicos'

    id               = db.Column(db.Integer, primary_key=True)
    agendamento_id   = db.Column(db.Integer, db.ForeignKey('agendamentos.id'), nullable=False, index=True)
    servico_id       = db.Column(db.Integer, db.ForeignKey('servicos.id'), nullable=False)
    quantidade       = db.Column(db.Integer, nullable=False, default=1)
    preco_unitario   = db.Column(db.Numeric(10, 2), nullable=False)
    is_plano         = db.Column(db.Boolean, nullable=False, default=False)
    cliente_plano_id = db.Column(db.Integer, db.ForeignKey('cliente_plano.id'), nullable=True, index=True)

    # ── Bloco 5.1: idem, somente-leitura, sem backref no Servico.
    servico = db.relationship('Servico', viewonly=True, lazy='select')


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


class TransferenciaAgendamento(TenantMixin, db.Model):
    """Fila/auditoria de transferência de agendamento entre barbeiros (Script 17).
    barbeiro_origem_id preserva o histórico mesmo depois do barbeiro ser
    desativado; barbeiro_destino_id só é preenchido quando alguém assume
    (mural) ou o gestor transfere diretamente."""
    __tablename__ = 'transferencia_agendamento'

    id                 = db.Column(db.Integer, primary_key=True)
    agendamento_id     = db.Column(db.Integer, db.ForeignKey('agendamentos.id'), nullable=False, index=True)
    barbeiro_origem_id  = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=False)
    barbeiro_destino_id = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=True)
    motivo             = db.Column(db.String(200), nullable=False)
    # pendente, concluida, reagendada, cancelada — ver app.constants.StatusTransferencia
    status             = db.Column(db.String(20), nullable=False, default='pendente')
    # Diferente do padrão UTC de criado_em/atualizado_em: aqui os timestamps
    # aparecem direto nas telas de "aguardando transferência" (gestor/mural
    # do barbeiro), então usam Brasília como qualquer outra lógica de negócio.
    criado_em          = db.Column(db.DateTime, default=naive_brasilia)
    concluido_em       = db.Column(db.DateTime)


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
    cliente_id      = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False, index=True)
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
    """v1.2: estendida com token/código/expiração — antes só tinha status, sem
    nenhuma rota consumindo (órfã). Fluxo: gera token+código, hierarquia encaminha
    manualmente (sem e-mail), usuário confirma o código antes de expirar em 72h."""
    __tablename__ = 'solicitacoes_senha'
    __table_args__ = (
        db.Index('ix_solicitacoes_senha_usuario_id', 'usuario_id'),
        db.Index('ix_solicitacoes_senha_expira_em', 'expira_em'),
    )

    id            = db.Column(db.Integer, primary_key=True)
    usuario_id    = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    barbearia_id  = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False)
    status        = db.Column(db.String(20), nullable=False, default='pendente')  # pendente, resolvido
    token         = db.Column(db.String(256), nullable=False, unique=True)
    codigo_novo   = db.Column(db.String(20), nullable=False)
    tentativas    = db.Column(db.Integer, nullable=False, default=0)
    expira_em     = db.Column(db.DateTime, nullable=False)
    confirmado_em = db.Column(db.DateTime, nullable=True)
    criado_em     = db.Column(db.DateTime, default=_utcnow)


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
    barbeiro_id   = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=True, index=True)
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
    servico_id        = db.Column(db.Integer, db.ForeignKey('servicos.id'), nullable=False, index=True)
    limite_uso_mensal = db.Column(db.Integer, nullable=False)  # 99999 = ilimitado (sentinela)
    dias_expiracao    = db.Column(db.Integer, nullable=False)
    ativo             = db.Column(db.Boolean, default=True, nullable=False)


class ClientePlano(db.Model):
    __tablename__ = 'cliente_plano'

    id           = db.Column(db.Integer, primary_key=True)
    barbearia_id = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False, index=True)
    cliente_id   = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False, index=True)
    plano_id     = db.Column(db.Integer, db.ForeignKey('planos.id'), nullable=False, index=True)
    barbeiro_id  = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=True)  # null = plano aberto
    data_inicio  = db.Column(db.Date, nullable=False)
    data_fim     = db.Column(db.Date)
    ativo        = db.Column(db.Boolean, default=True, nullable=False)
    criado_em    = db.Column(db.DateTime, default=_utcnow)
    # ── P2: Renovação automática ──────────────────────────────────────────────
    auto_renovar = db.Column(db.Boolean, nullable=False, default=False)
    # ── Bloco 2.1: rastreabilidade + trava anti-dupla-aprovação (Script 07) ───
    solicitacao_id = db.Column(
        db.Integer,
        db.ForeignKey('cliente_plano_solicitacao.id'),
        nullable=True,
        unique=True,
    )


class ClientePlanoUso(db.Model):
    __tablename__ = 'cliente_plano_uso'
    __table_args__ = (
        db.UniqueConstraint(
            'cliente_plano_id', 'servico_id', 'data_uso',
            name='uq_plano_uso_dia',
        ),
    )

    id               = db.Column(db.Integer, primary_key=True)
    cliente_plano_id = db.Column(db.Integer, db.ForeignKey('cliente_plano.id'), nullable=False, index=True)
    servico_id       = db.Column(db.Integer, db.ForeignKey('servicos.id'), nullable=False, index=True)
    data_uso         = db.Column(db.Date, nullable=False)
    semana_do_mes    = db.Column(db.Integer, nullable=False)
    usado            = db.Column(db.Boolean, default=False, nullable=False)


class ClientePlanoSolicitacao(db.Model):
    __tablename__ = 'cliente_plano_solicitacao'

    id               = db.Column(db.Integer, primary_key=True)
    barbearia_id     = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False, index=True)
    cliente_id       = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False, index=True)
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
    # v1.2: meses consecutivos de plano ativo, usado pela regra de VIP leveling
    # (1º mês → nível 1, 2º mês consecutivo → nível 2, etc). data_proxima_renovacao
    # dobra como janela de tolerância pós-cancelamento — não precisa de coluna nova.
    meses_consecutivos     = db.Column(db.Integer, default=0, nullable=False)
    criado_em              = db.Column(db.DateTime, default=_utcnow)
    atualizado_em          = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)


# ── Cupons de desconto ────────────────────────────────────────────────────────

class Cupom(TenantMixin, db.Model):
    __tablename__ = 'cupons'
    __table_args__ = (
        db.UniqueConstraint('barbearia_id', 'codigo', name='uq_cupom_barbearia_codigo'),
        db.CheckConstraint('valor_desconto >= 0', name='ck_cupons_valor_desconto_positivo'),
        db.CheckConstraint('quantidade_usos >= 0', name='ck_cupons_quantidade_usos_positivo'),
        db.CheckConstraint(
            "tipo_desconto IN ('percentual','valor_fixo')",
            name='ck_cupons_tipo_desconto_valido',
        ),
        db.CheckConstraint(
            "tipo_desconto != 'percentual' OR valor_desconto <= 100",
            name='ck_cupons_percentual_max_100',
        ),
    )

    id                      = db.Column(db.Integer, primary_key=True)
    nome                    = db.Column(db.String(100), nullable=False)
    codigo                  = db.Column(db.String(30), nullable=False)
    tipo_desconto           = db.Column(db.String(20), nullable=False)  # percentual, valor_fixo
    valor_desconto          = db.Column(db.Numeric(10, 2), nullable=False)
    data_expiracao          = db.Column(db.Date, nullable=False)
    quantidade_maxima_usos  = db.Column(db.Integer)  # NULL = ilimitado
    quantidade_usos         = db.Column(db.Integer, nullable=False, default=0)
    ativo                   = db.Column(db.Boolean, nullable=False, default=True)
    criado_em               = db.Column(db.DateTime, default=_utcnow)
    atualizado_em           = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)


# ── Feature Flags (v2: normalizado) ────────────────────────────────────────────

class FeatureMetadata(db.Model):
    """Catálogo de features disponíveis na plataforma. Populado por seed — não alterar via API."""
    __tablename__ = 'feature_metadata'

    id               = db.Column(db.Integer, primary_key=True)
    nome             = db.Column(db.String(50), unique=True, nullable=False)
    descricao        = db.Column(db.String(200))
    # Script 18: quando uma feature NOVA é inserida pelo seed com isto True,
    # todas as barbearias JÁ EXISTENTES ganham FeatureBarbearia(ativo=True)
    # automaticamente (só na criação da feature — nunca reativa algo que o
    # gestor tenha desligado manualmente depois). Não afeta features
    # antigas, que continuam nascendo desligadas por padrão como sempre.
    ativo_por_padrao = db.Column(db.Boolean, nullable=False, default=False)

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


class SegmentoFeaturePadrao(db.Model):
    """Define quais features nascem ativas por padrão para barbearias de um segmento.
    Aplicado em criar_barbearia() por cima do FeatureMetadata.ativo_por_padrao global."""
    __tablename__ = 'segmento_feature_padrao'
    __table_args__ = (
        db.UniqueConstraint('segmento_id', 'feature_id', name='uq_segmento_feature_padrao'),
    )

    id               = db.Column(db.Integer, primary_key=True)
    segmento_id      = db.Column(db.Integer, db.ForeignKey('segmentos.id'), nullable=False, index=True)
    feature_id       = db.Column(db.Integer, db.ForeignKey('feature_metadata.id'), nullable=False)
    ativo_por_padrao = db.Column(db.Boolean, nullable=False, default=False)
    atualizado_em    = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    segmento = db.relationship('Segmento', backref='features_padrao')
    feature  = db.relationship('FeatureMetadata', backref='segmento_padroes')


# ── Auditoria / Customização ───────────────────────────────────────────────────

class AuditoriaLog(db.Model):
    __tablename__ = 'auditoria_log'

    id           = db.Column(db.Integer, primary_key=True)
    usuario_id   = db.Column(db.Integer, db.ForeignKey('usuarios.id'), index=True)
    barbearia_id = db.Column(db.Integer, db.ForeignKey('barbearias.id'), index=True)
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


# ── VIP: histórico de mudanças (v1.2) ───────────────────────────────────────────

class ClienteVipHistorico(TenantMixin, db.Model):
    """Histórico de mudanças de nível VIP: upgrade, downgrade, aviso de vencimento,
    cancelamento, reativação. Consultado direto por cliente_id — sem relationship
    ORM com ClienteVip (não há FK entre as duas, cliente_id já identifica o tenant)."""
    __tablename__ = 'cliente_vip_historico'

    id             = db.Column(db.Integer, primary_key=True)
    cliente_id     = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False, index=True)
    evento_tipo    = db.Column(db.String(50), nullable=False)
    # UPGRADE, DOWNGRADE, AVISO_VENCIMENTO, CANCELAMENTO, REATIVACAO
    nivel_anterior = db.Column(db.Integer)
    nivel_novo     = db.Column(db.Integer)
    descricao      = db.Column(db.Text)
    criado_em      = db.Column(db.DateTime, default=_utcnow, index=True)


# ── PDV / Caixa diário do barbeiro (v1.2) ───────────────────────────────────────
# Caixa por DIA (não por agendamento) — diferente do módulo Atendimento/caixa.py
# legado, que é código morto (checkout por agendamento, nunca registrado). Abre na
# 1ª venda do dia; fechamento é responsabilidade da rota (Parte 2), não deste model.

class BarbeiroCaixa(TenantMixin, db.Model):
    """Caixa diária de um barbeiro: soma das vendas avulsas do dia."""
    __tablename__ = 'barbeiro_caixa'
    __table_args__ = (
        db.UniqueConstraint('barbeiro_id', 'data', name='uq_barbeiro_caixa_data'),
        db.CheckConstraint('total >= 0', name='ck_barbeiro_caixa_total_positivo'),
    )

    id         = db.Column(db.Integer, primary_key=True)
    barbeiro_id = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=False, index=True)
    aberto_em  = db.Column(db.DateTime, default=_utcnow, nullable=False)
    fechado_em = db.Column(db.DateTime, nullable=True)
    total      = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    data       = db.Column(db.Date, nullable=False)


class ItemCaixa(TenantMixin, db.Model):
    """Item vendido dentro de uma caixa diária: produto + desconto + forma de pagamento.
    agendamento_id é opcional — só correlação, não vínculo de negócio."""
    __tablename__ = 'item_caixa'
    __table_args__ = (
        db.CheckConstraint('quantidade > 0', name='ck_item_caixa_quantidade_positiva'),
        db.CheckConstraint('preco >= 0', name='ck_item_caixa_preco_positivo'),
        db.CheckConstraint(
            'desconto_percentual >= 0 AND desconto_percentual <= 100',
            name='ck_item_caixa_desconto_range',
        ),
        db.CheckConstraint(
            "forma_pagamento IN ('pix','dinheiro','cartao')",
            name='ck_item_caixa_forma_pagamento_valida',
        ),
    )

    id                  = db.Column(db.Integer, primary_key=True)
    caixa_id            = db.Column(db.Integer, db.ForeignKey('barbeiro_caixa.id'), nullable=False, index=True)
    produto_id          = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False, index=True)
    quantidade          = db.Column(db.Integer, default=1, nullable=False)
    preco               = db.Column(db.Numeric(10, 2), nullable=False)
    desconto_percentual = db.Column(db.Numeric(5, 2), default=0, nullable=False)
    forma_pagamento     = db.Column(db.String(20), nullable=False)  # pix, dinheiro, cartao
    agendamento_id      = db.Column(db.Integer, db.ForeignKey('agendamentos.id'), nullable=True)
    criado_em           = db.Column(db.DateTime, default=_utcnow, nullable=False)

    caixa = db.relationship('BarbeiroCaixa', backref='itens')

    @property
    def subtotal(self):
        """Valor sem desconto."""
        return float(self.preco) * self.quantidade

    @property
    def desconto_valor(self):
        """Valor de desconto aplicado."""
        return round(self.subtotal * float(self.desconto_percentual) / 100, 2)

    @property
    def total(self):
        """Valor final (com desconto)."""
        return round(self.subtotal - self.desconto_valor, 2)
