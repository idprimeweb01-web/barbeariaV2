# Achados extras — encontrados no caminho, fora do escopo do bloco atual

Registrados conforme a regra 3 da Fase 2 ("não altere nada fora do escopo do
bloco atual — anote e siga"). Nenhum destes foi corrigido.

## 1. `RELATORIO_BLOCO_04.txt` corrompido (working tree)

Durante a organização dos commits do trabalho pendente, a linha 17 desse
arquivo apareceu com uma listagem de path (~150 nomes de arquivo/diretório
tipo `barberos/app/... barberos/migrations/...`) inserida no meio do texto
— claramente o resultado de algum comando anterior (provavelmente um
redirecionamento ou `sed` malsucedido rodado numa sessão passada) que
sobrescreveu parte do conteúdo original em vez de só editar a linha
pretendida.

**Não commitado de propósito** — deixado exatamente como estava na working
tree, sem alteração. É um arquivo de relatório histórico (não é lido pelo
app em runtime), então não afeta a aplicação, só o próprio arquivo de texto.

**Ação sugerida quando for conveniente:** restaurar a linha 17 a partir do
histórico do git (`git log -- RELATORIO_BLOCO_04.txt`, pegar a versão do
commit anterior) ou reescrever manualmente — é só decidir e eu faço.

## 2. Dois scripts de regressão com falha pré-existente (não relacionada a nenhum bloco desta sessão)

Rodados como parte da suíte de regressão do Bloco 1 (cookie Secure) — ambas
as falhas já existiam antes de eu tocar em qualquer código desta Fase 2,
confirmado porque nenhuma delas toca cookie/autenticação:

- **`teste_frente1_completa.py`** — trava em `testar_relatorios_avancados`
  (`AttributeError: 'NoneType' object has no attribute 'id'`) porque busca
  `FeatureMetadata.query.filter_by(nome='relatorios_avancados')` e essa
  feature não existe mais no seed atual — o próprio `app/seeds.py:25` tem um
  comentário confirmando que `'relatorios_avancados'` foi removida do
  catálogo atual. Script desatualizado, não reflete mais o produto.
- **`teste_v1_2_pdv_vip_reset.py`** — trava em `testar_limite_plano`
  (`KeyError: 'solicitacao_id'`) porque o tenant que o próprio script cria
  não tem a feature `pix_integrado` habilitada, e a rota de solicitar plano
  responde 403 "PIX não está disponível para este estabelecimento" em vez
  de 201. Gap no setup do script, não um bug do app.

**Ação sugerida quando for conveniente:** atualizar os dois scripts (remover
o teste de `relatorios_avancados` ou trocar por uma feature que ainda
existe; habilitar `pix_integrado` no setup do tenant de teste do segundo
script) — não fiz isso agora porque scripts de teste não fazem parte do
escopo de nenhum bloco da Fase 2.
