# Rótulos visíveis centralizados. Suporta dois modos:
#   L('chave')                  → rótulo estático (backward compat)
#   L.get(segmento_id, 'chave') → rótulo do DB por segmento (com cache)

# Rótulos padrão (segmento "barbearia" ou sem segmento configurado)
_STATIC: dict[str, str] = {
    'tenant':        'Barbearia',
    'tenants':       'Barbearias',
    'profissional':  'Barbeiro',
    'profissionais': 'Barbeiros',
    'servico':       'Serviço',
    'servicos':      'Serviços',
    'produto':       'Produto',
    'produtos':      'Produtos',
    'plano':         'Plano',
    'planos':        'Planos',
    'agendamento':   'Agendamento',
    'agendamentos':  'Agendamentos',
    'atendimento':   'Atendimento',
    'cliente':       'Cliente',
    'clientes':      'Clientes',
    'pagamento':     'Pagamento',
    'faturamento':   'Faturamento',
    'receita':       'Faturamento',
    'relatorio':     'Relatório',
    'comissao':      'Comissão',
    'dashboard':     'Dashboard',
}

# Mapeamento de chave → coluna no model SegmentoRotulo
_COL: dict[str, str] = {
    'tenant':        'rotulo_tenant',
    'tenants':       'rotulo_tenant_plural',
    'profissional':  'rotulo_profissional',
    'profissionais': 'rotulo_profissional_plural',
    'servico':       'rotulo_servico',
    'servicos':      'rotulo_servico_plural',
    'agendamento':   'rotulo_agendamento',
    'agendamentos':  'rotulo_agendamento_plural',
    'atendimento':   'rotulo_agendamento',
    'cliente':       'rotulo_cliente',
    'clientes':      'rotulo_cliente_plural',
    'produto':       'rotulo_produto',
    'produtos':      'rotulo_produto_plural',
    'plano':         'rotulo_plano',
    'planos':        'rotulo_plano_plural',
    'pagamento':     'rotulo_pagamento',
    'faturamento':   'rotulo_faturamento',
    'receita':       'rotulo_faturamento',
    'relatorio':     'rotulo_relatorio',
}

# Todas as colunas editáveis (ordem usada no formulário admin)
ROTULO_COLS: list[str] = [
    'rotulo_tenant',        'rotulo_tenant_plural',
    'rotulo_profissional',  'rotulo_profissional_plural',
    'rotulo_servico',       'rotulo_servico_plural',
    'rotulo_agendamento',   'rotulo_agendamento_plural',
    'rotulo_cliente',       'rotulo_cliente_plural',
    'rotulo_produto',       'rotulo_produto_plural',
    'rotulo_plano',         'rotulo_plano_plural',
    'rotulo_pagamento',     'rotulo_faturamento', 'rotulo_relatorio',
]

# Labels amigáveis para exibição no formulário
ROTULO_LABELS: dict[str, str] = {
    'rotulo_tenant':               'Estabelecimento (singular)',
    'rotulo_tenant_plural':        'Estabelecimento (plural)',
    'rotulo_profissional':         'Profissional (singular)',
    'rotulo_profissional_plural':  'Profissional (plural)',
    'rotulo_servico':              'Serviço (singular)',
    'rotulo_servico_plural':       'Serviço (plural)',
    'rotulo_agendamento':          'Agendamento (singular)',
    'rotulo_agendamento_plural':   'Agendamento (plural)',
    'rotulo_cliente':              'Cliente (singular)',
    'rotulo_cliente_plural':       'Cliente (plural)',
    'rotulo_produto':              'Produto (singular)',
    'rotulo_produto_plural':       'Produto (plural)',
    'rotulo_plano':                'Plano (singular)',
    'rotulo_plano_plural':         'Plano (plural)',
    'rotulo_pagamento':            'Pagamento',
    'rotulo_faturamento':          'Faturamento / Receita',
    'rotulo_relatorio':            'Relatório',
}


class _RotuloStore:
    """Sistema de rótulos dinâmicos por segmento com cache em memória."""

    _cache: dict[int, dict[str, str]] = {}

    def __call__(self, chave: str) -> str:
        """Rótulo estático — mantém compatibilidade com L('chave')."""
        return _STATIC.get(chave, chave)

    def get(self, segmento_id, chave: str) -> str:
        """Rótulo dinâmico do DB por segmento_id, com fallback estático."""
        if segmento_id is None:
            return _STATIC.get(chave, chave)
        rotulos = self._carregar(segmento_id)
        return rotulos.get(chave) or _STATIC.get(chave, chave)

    def todos(self, segmento_id) -> dict[str, str]:
        """Retorna dict completo de rótulos para um segmento_id."""
        base = dict(_STATIC)
        if segmento_id is not None:
            base.update(self._carregar(segmento_id))
        return base

    def _carregar(self, segmento_id: int) -> dict[str, str]:
        if segmento_id in self._cache:
            return self._cache[segmento_id]
        try:
            from app.models import SegmentoRotulo
            row = SegmentoRotulo.query.filter_by(segmento_id=segmento_id).first()
            d: dict[str, str] = {}
            if row:
                for chave, col in _COL.items():
                    val = getattr(row, col, None)
                    if val:
                        d[chave] = val
            self._cache[segmento_id] = d
            return d
        except Exception:
            return {}

    def invalidar(self, segmento_id=None):
        """Limpa cache. Chamar após editar rótulos no admin."""
        if segmento_id is None:
            self._cache.clear()
        else:
            self._cache.pop(segmento_id, None)


L = _RotuloStore()

# Backward compat: módulo exporta LABELS e LABEL_EXAMPLES para código legado
LABELS = _STATIC
LABEL_EXAMPLES: dict[str, str] = {
    'profissional': 'Escolha o {profissional} para o seu atendimento.',
    'servico':      '{servico} não encontrado.',
    'agendamento':  '{agendamento} confirmado para amanhã às 10h.',
    'cliente':      'Dados do {cliente} atualizados.',
}
