// Mesma lógica do helper Bos.wa (app/static/js/bos.js) — telefone salvo é só
// dígitos, DDD+número, sem DDI (ver app/utils/telefone.py). Assume Brasil
// (+55) quando o número não já vier com DDI (10-11 dígitos).
export function waLink(telefone, mensagem) {
  let d = String(telefone || '').replace(/\D/g, '')
  if (!d) return null
  if (d.length <= 11) d = '55' + d
  const texto = mensagem ? `?text=${encodeURIComponent(mensagem)}` : ''
  return `https://wa.me/${d}${texto}`
}
