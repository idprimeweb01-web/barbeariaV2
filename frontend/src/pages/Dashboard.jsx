import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Calendar, CheckCircle, XCircle, Star, ChevronRight, Clock } from 'lucide-react'
import Layout from '../components/Layout'
import { api } from '../api'

function fmtData(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })
}

function fmtHora(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

function fmtDia(iso) {
  if (!iso) return ''
  return new Date(iso).getDate()
}

function fmtMes(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('pt-BR', { month: 'short' }).replace('.', '')
}

function statusBadge(status) {
  const map = {
    agendado:   { cls: 'badge-blue',   txt: 'Agendado' },
    concluido:  { cls: 'badge-green',  txt: 'Concluído' },
    cancelado:  { cls: 'badge-red',    txt: 'Cancelado' },
    aguardando_comprovante: { cls: 'badge-orange', txt: 'Aguard. comprovante' },
    aguardando_aprovacao:   { cls: 'badge-orange', txt: 'Aguard. aprovação' },
  }
  const { cls, txt } = map[status] || { cls: 'badge-gray', txt: status }
  return <span className={`badge ${cls}`}>{txt}</span>
}

export default function Dashboard() {
  const [dash, setDash] = useState(null)
  const [vip, setVip]   = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    Promise.all([
      api.get('/dashboard'),
      api.get('/vip').catch(() => null),
    ]).then(([d, v]) => {
      setDash(d)
      setVip(v)
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <Layout title="Dashboard">
      <div className="loading"><div className="spinner" /></div>
    </Layout>
  )

  const proximos = dash?.proximos_agendamentos || []
  const resumo   = dash?.historico_resumo || {}
  const planos   = Object.values(dash || {}).find(v => Array.isArray(v) && v.length >= 0 && v !== proximos) || dash?.planos_ativos || []

  return (
    <Layout title="Dashboard">

      {/* Métricas */}
      <div className="grid-4" style={{ marginBottom: 24 }}>
        <div className="metric-card">
          <div className="metric-label">Próx. agendamentos</div>
          <div className="metric-value">{proximos.length}</div>
          <div className="metric-sub">futuros confirmados</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Concluídos</div>
          <div className="metric-value">{resumo.total_concluidos ?? 0}</div>
          <div className="metric-sub">histórico total</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Cancelados</div>
          <div className="metric-value" style={{ color: '#f87171' }}>{resumo.total_cancelados ?? 0}</div>
          <div className="metric-sub">histórico total</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Nível VIP</div>
          <div className="metric-value" style={{ fontSize: 20 }}>
            {vip?.nivel_vip_atual > 0 ? `Nível ${vip.nivel_vip_atual}` : '—'}
          </div>
          <div className="metric-sub">{vip?.nivel_info?.brinde_descricao || 'Sem nível VIP'}</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>

        {/* Próximos agendamentos */}
        <div>
          <div className="section-header">
            <span className="section-title">Próximos agendamentos</span>
            <button className="btn btn-ghost btn-sm" onClick={() => navigate('/cliente/agendar')}>
              + Agendar
            </button>
          </div>
          {proximos.length === 0 ? (
            <div className="card empty">
              <Calendar size={32} style={{ margin: '0 auto 10px', opacity: .3 }} />
              <p>Nenhum agendamento futuro</p>
              <button className="btn btn-primary btn-sm" style={{ marginTop: 12 }} onClick={() => navigate('/cliente/agendar')}>
                Agendar agora
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {proximos.map(ag => (
                <div key={ag.id} className="ag-card">
                  <div className="ag-date">
                    <div className="ag-day">{fmtDia(ag.data_hora)}</div>
                    <div className="ag-month">{fmtMes(ag.data_hora)}</div>
                  </div>
                  <div className="ag-info">
                    <div className="ag-service">
                      {(ag.servicos || ag[Object.keys(ag).find(k => k.includes('servi'))] || []).join(', ') || '—'}
                    </div>
                    <div className="ag-detail">
                      {fmtHora(ag.data_hora)} &bull;{' '}
                      {ag.profissional || ag.barbeiro || '—'}
                    </div>
                  </div>
                  {statusBadge(ag.status)}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Planos ativos */}
        <div>
          <div className="section-header">
            <span className="section-title">Meus planos</span>
            <button className="btn btn-ghost btn-sm" onClick={() => navigate('/cliente/planos')}>
              Ver todos
            </button>
          </div>
          {planos.length === 0 ? (
            <div className="card empty">
              <Star size={32} style={{ margin: '0 auto 10px', opacity: .3 }} />
              <p>Nenhum plano ativo</p>
              <button className="btn btn-primary btn-sm" style={{ marginTop: 12 }} onClick={() => navigate('/cliente/planos')}>
                Ver planos
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {planos.map(p => (
                <div key={p.cliente_plano_id} className="card" style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                  <div style={{ background: 'rgba(245,158,11,.12)', borderRadius: 8, padding: '8px 10px' }}>
                    <Star size={18} color="var(--primary)" />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 700 }}>{p.plano_nome}</div>
                    <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                      {p.data_fim ? `Válido até ${fmtData(p.data_fim)}` : 'Sem data de expiração'}
                    </div>
                  </div>
                  <span className="badge badge-green">Ativo</span>
                </div>
              ))}
            </div>
          )}

          {/* VIP resumo */}
          {vip && vip.nivel_vip_atual > 0 && (
            <div className="card" style={{ marginTop: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                <Star size={16} color="var(--primary)" />
                <span style={{ fontWeight: 700 }}>Status VIP</span>
                <div className="vip-badge" style={{ marginLeft: 'auto' }}>Nível {vip.nivel_vip_atual}</div>
              </div>
              {vip.nivel_info && (
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                  Benefício: {vip.nivel_info.brinde_descricao}
                  {vip.nivel_info.tipo_brinde === 'desconto' && vip.nivel_info.valor_desconto && (
                    <span> ({vip.nivel_info.valor_desconto}% desconto)</span>
                  )}
                </div>
              )}
              {vip.data_proxima_renovacao && (
                <div style={{ fontSize: 11, color: 'var(--muted2)', marginTop: 4 }}>
                  Renovação: {fmtData(vip.data_proxima_renovacao)}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}
