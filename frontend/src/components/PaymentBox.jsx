import { FeatureGate } from './FeatureGate'

/**
 * PaymentBox — seletor de forma de pagamento. PIX só aparece quando a
 * feature 'pix_integrado' está ativa para a barbearia (gate real no
 * backend também — ver _criar_agendamento_core, app/routes/pub/agendamento.py).
 */
export default function PaymentBox({ metodo, setMetodo, features }) {
  return (
    <div className="field">
      <label>Forma de pagamento</label>
      <select value={metodo} onChange={e => setMetodo(e.target.value)}>
        <option value="local">No local</option>
        <FeatureGate features={features} feature="pix_integrado">
          <option value="pix">PIX</option>
        </FeatureGate>
        <option value="cartao">Cartão</option>
        <option value="dinheiro">Dinheiro</option>
      </select>
    </div>
  )
}
