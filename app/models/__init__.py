from app import db
from datetime import datetime


class Barbearia(db.Model):
    __tablename__ = 'barbearias'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome        = db.Column(db.String(150), nullable=False)
    slug        = db.Column(db.String(50), unique=True, nullable=False)
    ativo       = db.Column(db.Boolean, default=True)
    criado_em   = db.Column(db.DateTime, default=datetime.utcnow)

    # Tema visual
    nome_exibicao = db.Column(db.String(150), nullable=True)
    cor_primaria  = db.Column(db.String(7),  default='#BA7517')
    cor_fundo     = db.Column(db.String(7),  default='#1a1a1a')
    cor_card      = db.Column(db.String(7),  default='#2a2a2a')
    logo_url      = db.Column(db.String(255))
    fonte         = db.Column(db.String(50), default='Inter')

    # Booking
    url_agendamento = db.Column(db.String(255), nullable=True)

    chave_pix = db.Column(db.String(255), nullable=True)


class Usuario(db.Model):
    __tablename__ = 'usuarios'

    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    barbearia_id = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=True)
    nome         = db.Column(db.String(100), nullable=False)
    telefone     = db.Column(db.String(20), nullable=False)
    email        = db.Column(db.String(100))
    senha        = db.Column(db.String(255))
    perfil       = db.Column(db.String(20), nullable=False)  # super_admin, gestor, barbeiro, cliente
    ativo        = db.Column(db.Boolean, default=True)
    criado_em    = db.Column(db.DateTime, default=datetime.utcnow)

    barbeiro = db.relationship('Barbeiro', backref='usuario', uselist=False)
    cliente  = db.relationship('Cliente',  backref='usuario', uselist=False)


class Barbeiro(db.Model):
    __tablename__ = 'barbeiros'

    id                   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    barbearia_id         = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=True)
    usuario_id           = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    foto                 = db.Column(db.String(255))
    comissao_percentual  = db.Column(db.Numeric(5, 2), nullable=False)
    bio                  = db.Column(db.String(300))
    ativo                = db.Column(db.Boolean, default=True)

    servicos          = db.relationship('BarbeiroServico', backref='barbeiro')
    configuracao_agenda = db.relationship('ConfiguracaoAgenda', backref='barbeiro', uselist=False)


class Cliente(db.Model):
    __tablename__ = 'clientes'
    __table_args__ = (
        db.UniqueConstraint('barbearia_id', 'telefone', name='uq_cliente_barbearia_telefone'),
    )

    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    barbearia_id = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=True)
    usuario_id   = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    nome         = db.Column(db.String(100), nullable=False)
    telefone     = db.Column(db.String(20), nullable=False)
    email        = db.Column(db.String(150), nullable=True)
    foto         = db.Column(db.String(255))
    observacoes  = db.Column(db.Text)
    ativo        = db.Column(db.Boolean, nullable=False, default=True)
    criado_em    = db.Column(db.DateTime, default=datetime.utcnow)

    senha_hash       = db.Column(db.String(255), nullable=True)
    ultimo_acesso    = db.Column(db.DateTime, nullable=True)
    primeira_visita  = db.Column(db.Date, nullable=True)


class Servico(db.Model):
    __tablename__ = 'servicos'

    id                = db.Column(db.Integer, primary_key=True, autoincrement=True)
    barbearia_id      = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=True)
    nome              = db.Column(db.String(100), nullable=False)
    descricao         = db.Column(db.String(300))
    duracao_minutos   = db.Column(db.Integer, nullable=False)
    preco             = db.Column(db.Numeric(10, 2), nullable=False)
    foto              = db.Column(db.String(255), nullable=True)
    ativo             = db.Column(db.Boolean, default=True)


class BarbeiroServico(db.Model):
    __tablename__ = 'barbeiro_servicos'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    barbeiro_id = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=False)
    servico_id  = db.Column(db.Integer, db.ForeignKey('servicos.id'), nullable=False)


class ConfiguracaoAgenda(db.Model):
    __tablename__ = 'configuracao_agenda'
    __table_args__ = (
        db.UniqueConstraint('barbeiro_id', name='uq_configuracao_agenda_barbeiro'),
    )

    id                  = db.Column(db.Integer, primary_key=True, autoincrement=True)
    barbearia_id        = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=True)
    barbeiro_id         = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=False)
    horario_abertura    = db.Column(db.Time, nullable=False)
    horario_fechamento  = db.Column(db.Time, nullable=False)
    intervalo_minutos   = db.Column(db.Integer, nullable=False)
    loja_aberta         = db.Column(db.Boolean, default=True)
    atualizado_em       = db.Column(db.DateTime, default=datetime.utcnow)


class Agendamento(db.Model):
    __tablename__ = 'agendamentos'

    id               = db.Column(db.Integer, primary_key=True, autoincrement=True)
    barbearia_id     = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=True)
    cliente_id       = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    barbeiro_id      = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=False)
    servico_id       = db.Column(db.Integer, db.ForeignKey('servicos.id'), nullable=False)
    data_hora        = db.Column(db.DateTime, nullable=False)
    duracao_minutos  = db.Column(db.Integer, nullable=False)
    status           = db.Column(db.String(20), nullable=False)  # agendado, concluido, cancelado
    observacao       = db.Column(db.String(300))
    criado_em        = db.Column(db.DateTime, default=datetime.utcnow)


class AgendamentoServico(db.Model):
    """Todos os serviços de um agendamento (suporta múltiplos)."""
    __tablename__ = 'agendamento_servicos'

    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    agendamento_id = db.Column(db.Integer, db.ForeignKey('agendamentos.id'), nullable=False)
    servico_id     = db.Column(db.Integer, db.ForeignKey('servicos.id'),     nullable=False)
    quantidade     = db.Column(db.Integer, nullable=False, default=1)
    preco_unitario = db.Column(db.Numeric(10, 2), nullable=False)


class HorarioBloqueado(db.Model):
    __tablename__ = 'horarios_bloqueados'

    id               = db.Column(db.Integer, primary_key=True, autoincrement=True)
    barbearia_id     = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=True)
    barbeiro_id      = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=False)
    data_hora_inicio = db.Column(db.DateTime, nullable=False)
    data_hora_fim    = db.Column(db.DateTime, nullable=False)
    motivo           = db.Column(db.String(100))


class Produto(db.Model):
    __tablename__ = 'produtos'

    id                   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    barbearia_id         = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=True)
    nome                 = db.Column(db.String(100), nullable=False)
    categoria            = db.Column(db.String(50))
    preco                = db.Column(db.Numeric(10, 2), nullable=False)
    quantidade_estoque   = db.Column(db.Integer, nullable=False, default=0)
    quantidade_reservada = db.Column(db.Integer, nullable=False, default=0)
    foto                 = db.Column(db.String(255))
    ativo                = db.Column(db.Boolean, default=True)
    criado_em            = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def quantidade_disponivel(self):
        return max(0, self.quantidade_estoque - (self.quantidade_reservada or 0))


class ReservaProduto(db.Model):
    __tablename__ = 'reservas_produtos'

    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    agendamento_id = db.Column(db.Integer, db.ForeignKey('agendamentos.id'), nullable=False)
    produto_id     = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    quantidade     = db.Column(db.Integer, nullable=False, default=1)
    status         = db.Column(db.String(20), nullable=False)  # reservado, confirmado, cancelado


class Atendimento(db.Model):
    __tablename__ = 'atendimentos'

    id               = db.Column(db.Integer, primary_key=True, autoincrement=True)
    barbearia_id     = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=True)
    agendamento_id   = db.Column(db.Integer, db.ForeignKey('agendamentos.id'), nullable=False)
    barbeiro_id      = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=False)
    cliente_id       = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    status_operacao  = db.Column(db.String(20), nullable=False)  # efetuado, nao_efetuado
    total            = db.Column(db.Numeric(10, 2))
    criado_em        = db.Column(db.DateTime, default=datetime.utcnow)


class AtendimentoItem(db.Model):
    __tablename__ = 'atendimento_itens'

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    atendimento_id  = db.Column(db.Integer, db.ForeignKey('atendimentos.id'), nullable=False)
    tipo            = db.Column(db.String(20), nullable=False)  # servico, produto
    servico_id      = db.Column(db.Integer, db.ForeignKey('servicos.id'))
    produto_id      = db.Column(db.Integer, db.ForeignKey('produtos.id'))
    preco_unitario  = db.Column(db.Numeric(10, 2), nullable=False)
    quantidade      = db.Column(db.Integer, nullable=False, default=1)


class Pagamento(db.Model):
    __tablename__ = 'pagamentos'

    id                     = db.Column(db.Integer, primary_key=True, autoincrement=True)
    atendimento_id         = db.Column(db.Integer, db.ForeignKey('atendimentos.id'), nullable=False)
    forma_pagamento        = db.Column(db.String(30), nullable=False)  # pix, dinheiro, credito, debito
    valor                  = db.Column(db.Numeric(10, 2), nullable=False)
    status                 = db.Column(db.String(20), nullable=False, default='aprovado')
    gateway                = db.Column(db.String(30))
    gateway_transaction_id = db.Column(db.String(100))
    criado_em              = db.Column(db.DateTime, default=datetime.utcnow)


class SolicitacaoSenha(db.Model):
    __tablename__ = 'solicitacoes_senha'

    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    usuario_id   = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    barbearia_id = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False)
    status       = db.Column(db.String(20), nullable=False, default='pendente')  # pendente, resolvido
    criado_em    = db.Column(db.DateTime, default=datetime.utcnow)


class SolicitacaoLiberacao(db.Model):
    __tablename__ = 'solicitacoes_liberacao'

    id               = db.Column(db.Integer, primary_key=True, autoincrement=True)
    barbearia_id     = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False)
    barbeiro_id      = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=False)
    data             = db.Column(db.Date, nullable=False)
    hora_inicio      = db.Column(db.Time)          # null = dia inteiro
    hora_fim         = db.Column(db.Time)          # null = dia inteiro
    motivo           = db.Column(db.String(300))
    status           = db.Column(db.String(20), nullable=False, default='pendente')  # pendente, aprovado, rejeitado
    notificado       = db.Column(db.Boolean, default=False)   # barbeiro foi notificado da resposta
    data_solicitacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_resposta    = db.Column(db.DateTime)


class Plano(db.Model):
    __tablename__ = 'planos'

    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    barbearia_id  = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False)
    barbeiro_id   = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=False)
    nome          = db.Column(db.String(150), nullable=False)
    descricao     = db.Column(db.Text, nullable=True)
    preco_mensal  = db.Column(db.Numeric(10, 2), nullable=False)
    ativo         = db.Column(db.Boolean, default=True)
    criado_em     = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PlanoServico(db.Model):
    __tablename__ = 'plano_servicos'
    __table_args__ = (
        db.UniqueConstraint('plano_id', 'servico_id', name='uq_plano_servico'),
    )

    id                  = db.Column(db.Integer, primary_key=True, autoincrement=True)
    plano_id            = db.Column(db.Integer, db.ForeignKey('planos.id'), nullable=False)
    servico_id          = db.Column(db.Integer, db.ForeignKey('servicos.id'), nullable=False)
    limite_uso_mensal   = db.Column(db.Integer, nullable=False)
    dias_expiracao      = db.Column(db.Integer, nullable=False)
    ativo               = db.Column(db.Boolean, default=True)


class ClientePlano(db.Model):
    __tablename__ = 'cliente_plano'

    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cliente_id   = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    plano_id     = db.Column(db.Integer, db.ForeignKey('planos.id'), nullable=False)
    barbeiro_id  = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=False)
    barbearia_id = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False)
    data_inicio  = db.Column(db.Date, nullable=False)
    data_fim     = db.Column(db.Date, nullable=True)
    ativo        = db.Column(db.Boolean, default=True)
    criado_em    = db.Column(db.DateTime, default=datetime.utcnow)


class ClientePlanoUso(db.Model):
    __tablename__ = 'cliente_plano_uso'

    id                = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cliente_plano_id  = db.Column(db.Integer, db.ForeignKey('cliente_plano.id'), nullable=False)
    servico_id        = db.Column(db.Integer, db.ForeignKey('servicos.id'), nullable=False)
    data_uso          = db.Column(db.Date, nullable=False)
    semana_do_mes     = db.Column(db.Integer, nullable=False)  # valores 1..4/5
    usado             = db.Column(db.Boolean, default=False)


class ClientePlanoSolicitacao(db.Model):
    __tablename__ = 'cliente_plano_solicitacao'

    id               = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cliente_id       = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    plano_id         = db.Column(db.Integer, db.ForeignKey('planos.id'), nullable=False)
    barbeiro_id      = db.Column(db.Integer, db.ForeignKey('barbeiros.id'), nullable=False)
    barbearia_id     = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False)
    valor            = db.Column(db.Numeric(10, 2), nullable=False)
    comprovante_url  = db.Column(db.String(255), nullable=True)  # URL do Cloudinary
    status           = db.Column(db.String(20), nullable=False, default='pendente')  # pendente, aprovado, rejeitado
    criado_em        = db.Column(db.DateTime, default=datetime.utcnow)
    aprovado_em      = db.Column(db.DateTime, nullable=True)


class VipNivel(db.Model):
    __tablename__ = 'vip_niveis'
    __table_args__ = (
        db.UniqueConstraint('barbearia_id', 'nivel', name='uq_barbearia_nivel'),
    )

    id                = db.Column(db.Integer, primary_key=True, autoincrement=True)
    barbearia_id      = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False)
    nivel             = db.Column(db.Integer, nullable=False)
    brinde_descricao  = db.Column(db.Text, nullable=False)
    tipo_brinde       = db.Column(db.String(20), nullable=False)  # fisico, desconto
    valor_desconto    = db.Column(db.Numeric(10, 2), nullable=True)
    ativo             = db.Column(db.Boolean, default=True)
    criado_em         = db.Column(db.DateTime, default=datetime.utcnow)


class ClienteVip(db.Model):
    __tablename__ = 'cliente_vip'
    __table_args__ = (
        db.UniqueConstraint('cliente_id', 'barbearia_id', name='uq_cliente_barbearia_vip'),
    )

    id                      = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cliente_id              = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    barbearia_id            = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False)
    nivel_vip_atual         = db.Column(db.Integer, default=0)
    brindes_resgatados      = db.Column(db.Text, nullable=True, default='[]')  # JSON serializado como texto
    data_proxima_renovacao  = db.Column(db.Date, nullable=True)
    criado_em               = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em           = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FeatureBarbearia(db.Model):
    __tablename__ = 'feature_barbearia'

    id                     = db.Column(db.Integer, primary_key=True, autoincrement=True)
    barbearia_id           = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False, unique=True)
    planos                 = db.Column(db.Boolean, default=False)
    relatorios_avancados   = db.Column(db.Boolean, default=False)
    vip_brindes            = db.Column(db.Boolean, default=False)
    agendamento_login      = db.Column(db.Boolean, default=False)
    historico_cliente      = db.Column(db.Boolean, default=False)
    cupons                 = db.Column(db.Boolean, default=False)
    fila_espera            = db.Column(db.Boolean, default=False)
    comissao               = db.Column(db.Boolean, default=False)
    notificacoes           = db.Column(db.Boolean, default=False)
    pix_integrado          = db.Column(db.Boolean, default=False)
    criado_em              = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em          = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BarbeariaCustomizacao(db.Model):
    __tablename__ = 'barbearia_customizacao'

    id                      = db.Column(db.Integer, primary_key=True, autoincrement=True)
    barbearia_id            = db.Column(db.Integer, db.ForeignKey('barbearias.id'), nullable=False, unique=True)
    cor_primaria            = db.Column(db.String(7), default='#BA7517')
    cor_secundaria          = db.Column(db.String(7), default='#1a1a1a')
    cor_acentuacao          = db.Column(db.String(7), default='#FFD700')
    texto_primario          = db.Column(db.String(7), default='#FFFFFF')
    texto_secundario        = db.Column(db.String(7), default='#CCCCCC')
    texto_terciario         = db.Column(db.String(7), default='#888888')
    botao_primario          = db.Column(db.String(7), default='#FFD700')
    botao_secundario        = db.Column(db.String(7), default='#555555')
    logo_filename           = db.Column(db.String(255), nullable=True)
    fundo_padrao_filename   = db.Column(db.String(255), nullable=True)
    fonte                   = db.Column(db.String(50), default='Inter')
    criado_em               = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em           = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
