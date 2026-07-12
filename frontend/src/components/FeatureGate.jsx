/**
 * FeatureGate — mostra/esconde conteúdo baseado em feature ativa.
 *
 * Adaptado ao padrão real deste projeto: não existe window.BOS_FEATURES
 * nem Context/Redux — cada página busca suas features via
 * `api.features.listar()` (GET /api/v1/cliente/features) e guarda o
 * resultado (array de {nome, descricao, ativo}) em estado local. Por isso
 * FeatureGate recebe esse array como prop, em vez de ler de um global.
 *
 * Uso:
 *   <FeatureGate features={features} feature="pix_integrado">
 *     <PaymentBox ... />
 *   </FeatureGate>
 *
 * Se a feature não existir na lista (nome errado, ou desativada) ou a
 * lista ainda não tiver carregado, retorna `fallback` (default: null).
 */
export function FeatureGate({ features, feature, children, fallback = null }) {
  const ativa = Array.isArray(features)
    ? features.find(f => f.nome === feature)?.ativo
    : false

  return ativa ? children : fallback
}
