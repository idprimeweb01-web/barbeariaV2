import { useEffect, useState } from 'react'
import { Star, CheckCircle, Clock, XCircle } from 'lucide-react'
import Layout from '../components/Layout'
import { showToast } from '../components/Layout'
import { FeatureGate } from '../components/FeatureGate'
import { api } from '../api'

function fmtData(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('pt-BR')
}

function fmtMoeda(v) {
  return `R$ ${Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`
}

function StatusBadge({ status }) {
  const map = {
    pendente:  { cls: 'badge-orange', txt: 'Pendente' },
    aprovado:  { cls: 'badge-green',  txt: 'Aprovado' },
    rejeitado: { cls: 'badge-red',    txt: 'Rejeitado' },
  }
  const { cls, txt } = map[status] || { cls: 'badge-gray', txt: status }
  return <span className={`badge ${cls}`}>{txt}</span>
}

export default function Planos() {
  const [assinaturas, setAssinaturas]   = useState([])
  const [planosDisp,  setPlanosDisp]    = useState([])
  const [solicitacoes, setSolicitacoes] = useState([])
  const [loading, setLoading]           = useState(true)
  const [solicitando, setSolicitando]   = useState(null)
  const [metodo, setMetodo]             = useState('pix')
  const [features, setFeatures]         = useState([])

  useEffect(() => {
    Promise.all([
      api.get('/planos?ativo=true'),
      api.planos.listar(),
      api.get('/planos/solicitacoes'),
      api.features.listar(),
    ]).then(([ass, disp, sols, feats]) => {
      setAssinaturas(Array.isArray(ass) ? ass : [])
      setPlanosDisp(Array.isArray(disp) ? disp : [])
      setSolicitacoes(Array.isArray(sols) ? sols : [])
      const feats2 = Array.isArray(feats) ? feats : []
      setFeatures(feats2)
      const ativo = !!feats2.find(f => f.nome === 'pix_integrado')?.ativo
      if (!ativo) setMetodo('dinheiro')
    }).finally(() => setLoading(false))
  }, [])

  const idsAtivos = new Set(assinaturas.map(a => a.plano_id))

  const handleSolicitar = async (plano) => {
    setSolicitando(plano.id)
    try {
      const res = await api.planos.solicitar(plano.id, { metodo_pagamento: metodo })
      showToast(`Solicitação enviada! ${res.pix_info || ''}`, 'success')
      const sols = await api.get('/planos/solicitacoes')
      setSolicitacoes(Array.isArray(sols) ? sols : [])
      if (res.pix_copia_cola) {
        navigator.clipboard?.writeText(res.pix_copia_cola)
          .then(() => showToast('Código PIX copiado!', 'info'))
      }
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setSolicitando(null)
    }
  }

  const handleCancelar = async (id) => {
    if (!confirm('Cancelar esta assinatura?')) return
    try {
      await api.post(`/planos/${id}/cancelar`, {})
      showToast('Assinatura cancelada.', 'info')
      const ass = await api.get('/planos?ativo=true')
      setAssinaturas(Array.isArray(ass) ? ass : [])
    } catch (e) {
      showToast(e.message, 'error')
    }
  }

  if (loading) return (
    <Layout title="Meus Planos">
      <div className="loading"><div className="spinner" /></div>
    </Layout>
  )

  return (
    <Layout title="Meus Planos">

      {/* Assinaturas ativas */}
      <div className="section-header">
        <span className="section-title">Assinaturas ativas</span>
      </div>

      {assinaturas.length === 0 ? (
        <div className="card empty" style={{ marginBottom: 24 }}>
          <Star size={32} style={{ margin: '0 auto 10px', opacity: .3 }} />
          <p>Nenhuma assinatura ativa no momento</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 28 }}>
          {assinaturas.map(cp => (
            <div key={cp.id} className="plan-card active">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                <div>
                  <div className="plan-name">{cp.plano_nome}</div>
                  <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
                    {cp.data_inicio ? `Desde ${fmtData(cp.data_inicio)}` : ''}
                    {cp.data_fim ? ` · Até ${fmtData(cp.data_fim)}` : ''}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span className="badge badge-green">Ativo</span>
                  <button
                    className="btn btn-danger btn-sm"
                    onClick={() => handleCancelar(cp.id)}
                  >
                    Cancelar
                  </button>
                </div>
              </div>

              {cp.servicos?.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, color: 'var(--muted2)', fontWeight: 700, textTransform: 'uppercase', marginBottom: 8 }}>Serviços incluídos</div>
                  {cp.servicos.map(sv => {
                    const pct = sv.ilimitado ? 0 : sv.limite_uso_mensal > 0 ? (sv.uso_mes_atual / sv.limite_uso_mensal) * 100 : 0
                    const danger = pct >= 85
                    return (
                      <div key={sv.servico_id} style={{ marginBottom: 10 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 4 }}>
                          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <CheckCircle size={13} color="var(--primary)" />
                            {sv.nome}
                          </span>
                          <span style={{ color: danger ? '#f87171' : 'var(--muted)', fontSize: 12 }}>
                            {sv.ilimitado ? 'Ilimitado' : `${sv.uso_mes_atual}/${sv.limite_uso_mensal} este mês`}
                          </span>
                        </div>
                        {!sv.ilimitado && sv.limite_uso_mensal > 0 && (
                          <div className="progress-bar">
                            <div className={`progress-fill ${danger ? 'danger' : ''}`} style={{ width: `${Math.min(pct, 100)}%` }} />
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Planos disponíveis */}
      {planosDisp.length > 0 && (
        <>
          <div className="section-header">
            <span className="section-title">Planos disponíveis</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, color: 'var(--muted)' }}>Pagamento:</span>
              <select
                value={metodo}
                onChange={e => setMetodo(e.target.value)}
                style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', padding: '4px 8px', fontSize: 12 }}
              >
                <FeatureGate features={features} feature="pix_integrado">
                  <option value="pix">PIX</option>
                </FeatureGate>
                <option value="dinheiro">Dinheiro</option>
                <option value="cartao">Cartão</option>
              </select>
            </div>
          </div>

          <div className="grid-3" style={{ marginBottom: 28 }}>
            {planosDisp.map(p => {
              const jaAtivo = idsAtivos.has(p.id)
              const pendente = solicitacoes.some(s => s.plano_id === p.id && s.status === 'pendente')
              return (
                <div key={p.id} className={`plan-card ${jaAtivo ? 'active' : ''}`}>
                  <div className="plan-name">{p.nome}</div>
                  {p.descricao && <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>{p.descricao}</div>}
                  <div>
                    <span className="plan-price">{fmtMoeda(p.preco_mensal)}</span>
                    <span className="plan-period"> /mês</span>
                  </div>

                  {p.servicos?.length > 0 && (
                    <ul className="plan-services">
                      {p.servicos.map(sv => (
                        <li key={sv.servico_id}>
                          <CheckCircle size={13} color="var(--primary)" />
                          <span>{sv.nome}</span>
                          <span style={{ color: 'var(--muted)', fontSize: 11, marginLeft: 'auto' }}>
                            {sv.ilimitado ? '∞' : sv.limite_uso_mensal ? `${sv.limite_uso_mensal}×/mês` : ''}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}

                  <div style={{ marginTop: 16 }}>
                    {jaAtivo ? (
                      <span className="badge badge-green">Plano atual</span>
                    ) : pendente ? (
                      <span className="badge badge-orange">Aguardando aprovação</span>
                    ) : (
                      <button
                        className="btn btn-primary"
                        style={{ width: '100%' }}
                        disabled={solicitando === p.id}
                        onClick={() => handleSolicitar(p)}
                      >
                        {solicitando === p.id ? 'Enviando...' : 'Assinar'}
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}

      {/* Histórico de solicitações */}
      {solicitacoes.length > 0 && (
        <>
          <div className="section-header">
            <span className="section-title">Histórico de solicitações</span>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Plano</th>
                  <th>Valor</th>
                  <th>Pagamento</th>
                  <th>Data</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {solicitacoes.map(s => (
                  <tr key={s.id}>
                    <td style={{ fontWeight: 600 }}>{s.plano_nome || `#${s.plano_id}`}</td>
                    <td>{fmtMoeda(s.valor)}</td>
                    <td style={{ textTransform: 'capitalize' }}>{s.metodo_pagamento}</td>
                    <td style={{ color: 'var(--muted)', fontSize: 12 }}>
                      {s.criado_em ? new Date(s.criado_em).toLocaleDateString('pt-BR') : '—'}
                    </td>
                    <td><StatusBadge status={s.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Layout>
  )
}
