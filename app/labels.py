# Rótulos visíveis centralizados para o segmento atual (barbearia).
# Quando o campo `segmento` existir no modelo Tenant (Parte B), este
# dicionário será selecionado dinamicamente. Por ora é fixo.
#
# Cada entrada: (texto_visivel, frase_exemplo)
# A frase_exemplo alimenta a futura tela de edição de rótulos (Parte B, B5).

_ENTRIES: dict[str, tuple[str, str]] = {
    'tenant':       ('Barbearia',   'Sua {tenant} está pronta para receber agendamentos.'),
    'tenants':      ('Barbearias',  'Gerencie todas as {tenants} da plataforma.'),
    'profissional': ('Barbeiro',    'Escolha o {profissional} para o seu atendimento.'),
    'profissionais':('Barbeiros',   'Veja a agenda dos {profissionais} disponíveis.'),
    'servico':      ('Serviço',     '{servico} não encontrado.'),
    'servicos':     ('Serviços',    'Selecione os {servicos} desejados.'),
    'produto':      ('Produto',     '{produto} fora de estoque.'),
    'plano':        ('Plano',       'Seu {plano} vence em 3 dias.'),
    'agendamento':  ('Agendamento', '{agendamento} confirmado para amanhã às 10h.'),
    'atendimento':  ('Atendimento', '{atendimento} concluído com sucesso.'),
    'cliente':      ('Cliente',     'Dados do {cliente} atualizados.'),
    'receita':      ('Receita',     '{receita} do mês: R$ 1.200,00.'),
    'comissao':     ('Comissão',    '{comissao} acumulada este mês: R$ 240,00.'),
    'dashboard':    ('Dashboard',   'Bem-vindo ao {dashboard} da sua {tenant}.'),
}

LABELS: dict[str, str] = {k: v[0] for k, v in _ENTRIES.items()}
LABEL_EXAMPLES: dict[str, str] = {k: v[1] for k, v in _ENTRIES.items()}


def L(chave: str) -> str:
    """Retorna o rótulo visível para a chave informada."""
    return LABELS.get(chave, chave)
