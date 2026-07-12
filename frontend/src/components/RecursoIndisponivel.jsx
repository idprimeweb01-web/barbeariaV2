import { AlertCircle } from 'lucide-react'

// Fallback exibido quando o cliente acessa direto por URL uma página cuja
// feature foi desativada para esta barbearia (o link já some do menu, isto
// cobre o acesso direto).
export function RecursoIndisponivel() {
  return (
    <div className="card empty">
      <AlertCircle size={32} style={{ margin: '0 auto 10px', opacity: .3 }} />
      <p>Recurso não disponível</p>
      <p style={{ fontSize: 12, marginTop: 6 }}>Este estabelecimento não oferece esse recurso no momento.</p>
    </div>
  )
}
