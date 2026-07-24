import { useState } from 'react'
import { CheckCircle } from 'lucide-react'

// Tela pós-confirmação de pagamento via PIX: QR code, código copia-e-cola,
// e upload do comprovante. Genérico o bastante pra servir tanto o booking
// de agendamento quanto a assinatura de plano — cada chamador passa seu
// próprio `codigo` (copia-e-cola) e `uploadFn` (como enviar o arquivo).
export default function PixConfirmacao({ codigo, chavePix, titular, uploadFn, onFinalizar, showToast, labelFinalizar = 'Ir para meus agendamentos' }) {
  const [arquivo, setArquivo] = useState(null)
  const [preview, setPreview] = useState(null)
  const [enviando, setEnviando] = useState(false)
  const [enviado, setEnviado] = useState(false)

  const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(codigo)}`

  const handleArquivo = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setArquivo(file)
    const reader = new FileReader()
    reader.onload = (ev) => setPreview(ev.target.result)
    reader.readAsDataURL(file)
  }

  const copiarCodigo = () => {
    navigator.clipboard?.writeText(codigo)
      .then(() => showToast('Código PIX copiado!', 'info'))
  }

  const copiarChave = () => {
    navigator.clipboard?.writeText(chavePix)
      .then(() => showToast('Chave PIX copiada!', 'info'))
  }

  const enviarComprovante = async () => {
    if (!arquivo) { showToast('Selecione uma imagem do comprovante.', 'error'); return }
    setEnviando(true)
    try {
      await uploadFn(arquivo)
      setEnviado(true)
      showToast('Comprovante enviado!', 'success')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div>
      <div className="section-header">
        <span className="section-title">Pagamento via PIX</span>
      </div>

      <div className="card" style={{ marginBottom: 20, textAlign: 'center' }}>
        <img src={qrUrl} alt="QR Code PIX" style={{ borderRadius: 10, marginBottom: 14 }} />
        <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>Código copia-e-cola</div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'center' }}>
          <code style={{ fontSize: 12, background: 'var(--surface2)', padding: '8px 12px', borderRadius: 6, wordBreak: 'break-all', maxWidth: 280 }}>
            {codigo}
          </code>
        </div>
        <button className="btn btn-ghost btn-sm" style={{ marginTop: 10 }} onClick={copiarCodigo}>Copiar código</button>

        {chavePix && (
          <div style={{ marginTop: 16, paddingTop: 14, borderTop: '1px solid var(--border)', textAlign: 'left' }}>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 6 }}>
              Prefere digitar a chave manualmente no seu banco?
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: titular ? 6 : 0 }}>
              <code style={{ fontSize: 12, background: 'var(--surface2)', padding: '6px 10px', borderRadius: 6, wordBreak: 'break-all', flex: 1 }}>
                {chavePix}
              </code>
              <button className="btn btn-ghost btn-sm" onClick={copiarChave}>Copiar</button>
            </div>
            {titular && (
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>Titular: {titular}</div>
            )}
          </div>
        )}
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>📸 Enviar comprovante do PIX</div>
        <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 12 }}>
          Após pagar, envie o comprovante para agilizar a confirmação.
        </div>

        {enviado ? (
          <div style={{ color: '#4ade80', fontSize: 13, fontWeight: 700, textAlign: 'center', padding: '10px 0' }}>
            <CheckCircle size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} />
            Comprovante enviado com sucesso!
          </div>
        ) : (
          <>
            <label style={{
              display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer',
              border: '1.5px dashed var(--border)', borderRadius: 10, padding: 14,
            }}>
              <input type="file" accept="image/jpeg,image/png" style={{ display: 'none' }} onChange={handleArquivo} />
              <span style={{ fontSize: 13, fontWeight: 600 }}>
                {arquivo ? arquivo.name : 'Selecionar imagem (JPEG/PNG, máx. 5 MB)'}
              </span>
            </label>
            {preview && (
              <img src={preview} alt="preview" style={{ width: '100%', borderRadius: 10, marginTop: 10, maxHeight: 200, objectFit: 'contain', border: '1px solid var(--border)' }} />
            )}
            <button
              className="btn btn-primary"
              style={{ width: '100%', marginTop: 12 }}
              disabled={enviando}
              onClick={enviarComprovante}
            >
              {enviando ? 'Enviando…' : 'Enviar comprovante'}
            </button>
          </>
        )}
      </div>

      <button className="btn btn-ghost" style={{ width: '100%' }} onClick={onFinalizar}>
        {labelFinalizar}
      </button>
    </div>
  )
}
