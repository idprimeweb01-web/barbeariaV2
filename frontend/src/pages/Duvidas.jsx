import { useEffect, useRef, useState } from 'react'
import { MessageCircle, Send, Paperclip, X, ArrowLeft, Plus, Star } from 'lucide-react'
import Layout from '../components/Layout'
import { showToast } from '../components/Layout'
import { FeatureGate } from '../components/FeatureGate'
import { RecursoIndisponivel } from '../components/RecursoIndisponivel'
import { api } from '../api'

const CATEGORIA_META = {
  duvida:      { icone: '❓', label: 'Dúvida' },
  erro:        { icone: '🐛', label: 'Erro / Bug' },
  financeiro:  { icone: '💰', label: 'Financeiro' },
  sugestao:    { icone: '💡', label: 'Sugestão' },
  treinamento: { icone: '🎓', label: 'Treinamento' },
  integracao:  { icone: '🔌', label: 'Integração' },
  conta:       { icone: '🔐', label: 'Conta/Acesso' },
  outro:       { icone: '📋', label: 'Outro' },
}
const PRIORIDADE_META = {
  baixa:   { label: 'Baixa',   cls: 'badge-gray' },
  normal:  { label: 'Normal',  cls: 'badge-blue' },
  alta:    { label: 'Alta',    cls: 'badge-orange' },
  urgente: { label: 'Urgente', cls: 'badge-red' },
}
const STATUS_META = {
  pendente:  { label: 'Pendente',  cls: 'badge-orange' },
  concluida: { label: 'Concluída', cls: 'badge-green' },
  cancelada: { label: 'Cancelada', cls: 'badge-gray' },
}
const MAX_IMAGENS = 3

function fmtDataHora(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('pt-BR') + ' ' + d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

function BadgeCategoria({ categoria }) {
  const m = CATEGORIA_META[categoria] || { icone: '📋', label: categoria }
  return <span className="badge badge-gray">{m.icone} {m.label}</span>
}
function BadgePrioridade({ prioridade }) {
  const m = PRIORIDADE_META[prioridade] || { label: prioridade, cls: 'badge-gray' }
  return <span className={`badge ${m.cls}`}>{m.label}</span>
}
function BadgeStatus({ status }) {
  const m = STATUS_META[status] || { label: status, cls: 'badge-gray' }
  return <span className={`badge ${m.cls}`}>{m.label}</span>
}

function PreviewsImagens({ arquivos, onRemover }) {
  if (!arquivos.length) return null
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
      {arquivos.map((file, i) => (
        <div key={i} style={{ position: 'relative', display: 'inline-block' }}>
          <img src={URL.createObjectURL(file)} alt="preview" style={{ width: 64, height: 64, objectFit: 'cover', borderRadius: 8, display: 'block' }} />
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            style={{ position: 'absolute', top: -8, right: -8, padding: 4, borderRadius: '50%' }}
            onClick={() => onRemover(i)}
          >
            <X size={12} />
          </button>
        </div>
      ))}
    </div>
  )
}

function SeletorImagens({ arquivos, setArquivos }) {
  const adicionar = (fileList) => {
    const restante = MAX_IMAGENS - arquivos.length
    if (restante <= 0) { showToast(`Máximo de ${MAX_IMAGENS} imagens por mensagem.`, 'error'); return }
    setArquivos([...arquivos, ...Array.from(fileList).slice(0, restante)])
  }
  return (
    <>
      <PreviewsImagens arquivos={arquivos} onRemover={(i) => setArquivos(arquivos.filter((_, idx) => idx !== i))} />
      {arquivos.length < MAX_IMAGENS && (
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple
          onChange={e => { adicionar(e.target.files); e.target.value = '' }}
        />
      )}
    </>
  )
}

function NovaDuvida({ onCancelar, onCriada }) {
  const [assunto, setAssunto] = useState('')
  const [texto, setTexto] = useState('')
  const [categoria, setCategoria] = useState('duvida')
  const [prioridade, setPrioridade] = useState('normal')
  const [barbeiroId, setBarbeiroId] = useState('')
  const [funcionarios, setFuncionarios] = useState([])
  const [imagens, setImagens] = useState([])
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    api.duvidas.funcionarios().then(f => setFuncionarios(Array.isArray(f) ? f : [])).catch(() => {})
  }, [])

  const enviar = async () => {
    if (!texto.trim() && !imagens.length) { showToast('Escreva uma mensagem ou anexe uma imagem.', 'error'); return }
    setEnviando(true)
    try {
      const r = await api.duvidas.criar({
        assunto: assunto.trim(), texto: texto.trim(), categoria, prioridade,
        barbeiroId: categoria === 'erro' ? '' : barbeiroId, imagens,
      })
      showToast('Dúvida enviada.', 'success')
      onCriada(r.duvida_id)
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="card">
      <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 14 }}>Nova dúvida</div>
      <div className="field">
        <label>Categoria</label>
        <select value={categoria} onChange={e => setCategoria(e.target.value)}>
          {Object.entries(CATEGORIA_META).map(([k, m]) => <option key={k} value={k}>{m.icone} {m.label}</option>)}
        </select>
      </div>
      <div className="field">
        <label>Prioridade sugerida</label>
        <select value={prioridade} onChange={e => setPrioridade(e.target.value)}>
          {Object.entries(PRIORIDADE_META).map(([k, m]) => <option key={k} value={k}>{m.label}</option>)}
        </select>
      </div>
      {funcionarios.length > 0 && (
        <div className="field">
          <label>Direcionar para</label>
          <select value={categoria === 'erro' ? '' : barbeiroId} onChange={e => setBarbeiroId(e.target.value)} disabled={categoria === 'erro'}>
            <option value="">Equipe (fila geral)</option>
            {funcionarios.map(f => <option key={f.id} value={f.id}>{f.nome}</option>)}
          </select>
          {categoria === 'erro' && (
            <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>Tickets de erro/bug sempre vão direto pra equipe.</div>
          )}
        </div>
      )}
      <div className="field">
        <label>Assunto (opcional)</label>
        <input type="text" value={assunto} onChange={e => setAssunto(e.target.value)} maxLength={150} placeholder="Ex: Dúvida sobre pagamento" />
      </div>
      <div className="field">
        <label>Mensagem</label>
        <textarea rows={4} value={texto} onChange={e => setTexto(e.target.value)} maxLength={2000} placeholder="Descreva sua dúvida…" />
      </div>
      <div className="field">
        <label>Anexar imagens (opcional, até 3)</label>
        <SeletorImagens arquivos={imagens} setArquivos={setImagens} />
      </div>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 8 }}>
        <button className="btn btn-ghost" onClick={onCancelar} disabled={enviando}>Cancelar</button>
        <button className="btn btn-primary" onClick={enviar} disabled={enviando}>{enviando ? 'Enviando…' : 'Enviar'}</button>
      </div>
    </div>
  )
}

function CsatPrompt({ duvidaId, onAvaliado, onDispensar }) {
  const [nota, setNota] = useState(0)
  const [comentario, setComentario] = useState('')
  const [enviando, setEnviando] = useState(false)

  const enviar = async () => {
    if (!nota) { showToast('Escolha uma nota de 1 a 5.', 'error'); return }
    setEnviando(true)
    try {
      await api.duvidas.avaliar(duvidaId, { nota, comentario: comentario.trim() })
      showToast('Obrigado pela avaliação!', 'success')
      onAvaliado()
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="card" style={{ marginBottom: 12, background: 'var(--surface2)' }}>
      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 8 }}>Como foi o atendimento dessa dúvida?</div>
      <div style={{ display: 'flex', gap: 4, marginBottom: 10 }}>
        {[1, 2, 3, 4, 5].map(n => (
          <button
            key={n}
            type="button"
            onClick={() => setNota(n)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2 }}
            title={`${n}/5`}
          >
            <Star size={22} fill={n <= nota ? '#f59e0b' : 'none'} color={n <= nota ? '#f59e0b' : 'var(--muted)'} />
          </button>
        ))}
      </div>
      <textarea
        rows={2}
        placeholder="Comentário (opcional)"
        value={comentario}
        onChange={e => setComentario(e.target.value)}
        maxLength={500}
        style={{ marginBottom: 10 }}
      />
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <button className="btn btn-ghost btn-sm" onClick={onDispensar} disabled={enviando}>Agora não</button>
        <button className="btn btn-primary btn-sm" onClick={enviar} disabled={enviando}>{enviando ? 'Enviando…' : 'Enviar avaliação'}</button>
      </div>
    </div>
  )
}

function Conversa({ duvidaId, onVoltar, onAtualizado }) {
  const [duvida, setDuvida] = useState(null)
  const [loading, setLoading] = useState(true)
  const [texto, setTexto] = useState('')
  const [imagens, setImagens] = useState([])
  const [enviando, setEnviando] = useState(false)
  const [csatDispensado, setCsatDispensado] = useState(false)
  const fimRef = useRef(null)

  const carregar = () => {
    api.duvidas.detalhar(duvidaId)
      .then(d => {
        setDuvida(d)
        setTimeout(() => fimRef.current?.scrollIntoView({ block: 'end' }), 50)
      })
      .catch(e => showToast(e.message, 'error'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { carregar() }, [duvidaId]) // eslint-disable-line react-hooks/exhaustive-deps

  const enviar = async () => {
    if (!texto.trim() && !imagens.length) return
    setEnviando(true)
    try {
      await api.duvidas.responder(duvidaId, { texto: texto.trim(), imagens })
      setTexto('')
      setImagens([])
      carregar()
      onAtualizado?.()
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setEnviando(false)
    }
  }

  const encerrar = async () => {
    try {
      await api.duvidas.fechar(duvidaId)
      showToast('Dúvida encerrada.', 'success')
      carregar()
      onAtualizado?.()
    } catch (e) {
      showToast(e.message, 'error')
    }
  }

  if (loading || !duvida) return (
    <div className="loading"><div className="spinner" /></div>
  )

  const mostrarCsat = duvida.status === 'concluida' && duvida.nota_satisfacao == null && !csatDispensado

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '70vh' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, borderBottom: '1px solid var(--border)', paddingBottom: 10, flexWrap: 'wrap' }}>
        <button className="btn btn-ghost btn-sm" onClick={onVoltar}><ArrowLeft size={16} /></button>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: 14 }}>{duvida.assunto || 'Dúvida sem assunto'}</div>
          <div style={{ display: 'flex', gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
            <BadgeCategoria categoria={duvida.categoria} />
            <BadgePrioridade prioridade={duvida.prioridade} />
            <BadgeStatus status={duvida.status} />
          </div>
        </div>
        {duvida.status === 'pendente' && (
          <button className="btn btn-ghost btn-sm" onClick={encerrar}>Encerrar</button>
        )}
      </div>

      {mostrarCsat && (
        <CsatPrompt
          duvidaId={duvidaId}
          onAvaliado={carregar}
          onDispensar={() => setCsatDispensado(true)}
        />
      )}

      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10, padding: '4px 2px' }}>
        {duvida.mensagens.map(m => (
          <div
            key={m.id}
            style={{
              alignSelf: m.autor_tipo === 'cliente' ? 'flex-end' : 'flex-start',
              maxWidth: '75%',
              background: m.autor_tipo === 'cliente' ? 'var(--primary)' : 'var(--surface2)',
              color: m.autor_tipo === 'cliente' ? '#1a1a1a' : 'var(--text)',
              borderRadius: 12,
              padding: '8px 12px',
            }}
          >
            <div style={{ fontSize: 10, fontWeight: 700, opacity: .7, marginBottom: 3, textTransform: 'uppercase' }}>{m.autor_tipo}</div>
            {m.texto && <div style={{ fontSize: 13, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{m.texto}</div>}
            {(m.imagens || []).map((url, i) => (
              <a key={i} href={url} target="_blank" rel="noopener noreferrer">
                <img src={url} alt="anexo" style={{ maxWidth: 140, borderRadius: 8, marginTop: 6, marginRight: 4, display: 'inline-block' }} />
              </a>
            ))}
            <div style={{ fontSize: 10, opacity: .7, marginTop: 4, textAlign: 'right' }}>{fmtDataHora(m.criado_em)}</div>
          </div>
        ))}
        <div ref={fimRef} />
      </div>

      {duvida.status !== 'cancelada' ? (
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 10, marginTop: 10 }}>
          <PreviewsImagens arquivos={imagens} onRemover={(i) => setImagens(imagens.filter((_, idx) => idx !== i))} />
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
            <label className="btn btn-ghost btn-sm" style={{ cursor: 'pointer', flexShrink: 0 }}>
              <Paperclip size={16} />
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                multiple
                style={{ display: 'none' }}
                onChange={e => {
                  const restante = MAX_IMAGENS - imagens.length
                  if (restante > 0) setImagens([...imagens, ...Array.from(e.target.files).slice(0, restante)])
                  e.target.value = ''
                }}
              />
            </label>
            <textarea
              rows={2}
              value={texto}
              onChange={e => setTexto(e.target.value)}
              maxLength={2000}
              placeholder="Digite sua mensagem…"
              style={{ flex: 1, resize: 'none' }}
            />
            <button className="btn btn-primary btn-sm" onClick={enviar} disabled={enviando} style={{ flexShrink: 0 }}>
              <Send size={16} />
            </button>
          </div>
        </div>
      ) : (
        <div style={{ textAlign: 'center', color: 'var(--muted)', fontSize: 12, paddingTop: 10, borderTop: '1px solid var(--border)' }}>
          Este ticket foi cancelado.
        </div>
      )}
    </div>
  )
}

export default function Duvidas() {
  const [features, setFeatures] = useState([])
  const [threads, setThreads] = useState([])
  const [loading, setLoading] = useState(true)
  const [duvidaAberta, setDuvidaAberta] = useState(() => {
    const id = new URLSearchParams(window.location.search).get('id')
    return id ? Number(id) : null
  })
  const [novaAberta, setNovaAberta] = useState(false)

  const carregarThreads = () => {
    api.duvidas.listar().then(r => setThreads(r.dados || [])).catch(() => {})
  }

  useEffect(() => {
    Promise.all([api.features.listar(), api.duvidas.listar()])
      .then(([feats, r]) => {
        setFeatures(Array.isArray(feats) ? feats : [])
        setThreads(r.dados || [])
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <Layout title="Dúvidas">
      <div className="loading"><div className="spinner" /></div>
    </Layout>
  )

  return (
    <Layout title="Dúvidas">
      <FeatureGate features={features} feature="duvidas_cliente" fallback={<RecursoIndisponivel />}>
        {duvidaAberta ? (
          <Conversa
            duvidaId={duvidaAberta}
            onVoltar={() => { setDuvidaAberta(null); carregarThreads() }}
            onAtualizado={carregarThreads}
          />
        ) : novaAberta ? (
          <NovaDuvida
            onCancelar={() => setNovaAberta(false)}
            onCriada={(id) => { setNovaAberta(false); carregarThreads(); setDuvidaAberta(id) }}
          />
        ) : (
          <>
            <div className="section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="section-title">Minhas dúvidas</span>
              <button className="btn btn-primary btn-sm" onClick={() => setNovaAberta(true)}>
                <Plus size={14} /> Nova dúvida
              </button>
            </div>
            {threads.length === 0 ? (
              <div className="card empty" style={{ marginTop: 12 }}>
                <MessageCircle size={32} style={{ margin: '0 auto 10px', opacity: .3 }} />
                <p>Nenhuma dúvida enviada ainda</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}>
                {threads.map(d => (
                  <div
                    key={d.id}
                    className="card"
                    style={{ cursor: 'pointer', position: 'relative' }}
                    onClick={() => setDuvidaAberta(d.id)}
                  >
                    {d.nao_lida_cliente && (
                      <span style={{ position: 'absolute', top: 12, right: 12, width: 9, height: 9, borderRadius: '50%', background: '#ef4444' }} />
                    )}
                    <div style={{ display: 'flex', gap: 6, marginBottom: 6, flexWrap: 'wrap' }}>
                      <BadgeCategoria categoria={d.categoria} />
                      <BadgePrioridade prioridade={d.prioridade} />
                      <BadgeStatus status={d.status} />
                      {d.nota_satisfacao && <span className="badge badge-green">⭐ {d.nota_satisfacao}/5</span>}
                    </div>
                    <div style={{ fontWeight: 700, fontSize: 14 }}>{d.assunto || 'Dúvida sem assunto'}</div>
                    <div style={{ fontSize: 12, color: 'var(--muted)', margin: '4px 0' }}>{d.ultima_mensagem_preview || '—'}</div>
                    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                      <span style={{ fontSize: 11, color: 'var(--muted)' }}>{fmtDataHora(d.ultima_mensagem_em)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </FeatureGate>
    </Layout>
  )
}
