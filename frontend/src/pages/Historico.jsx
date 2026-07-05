import { useEffect, useState } from 'react'
import { Clock, Calendar, XCircle, Filter } from 'lucide-react'
import Layout from '../components/Layout'
import { showToast } from '../components/Layout'
import { api } from '../api'

const SLUG = window.BOS_SLUG || ''

const STATUS_TABS = [
  { value: '',          label: 'Todos' },
  { value: 'agendado',  label: 'Agendados' },
  { value: 'concluido', label: 'Concluídos' },
  { value: 'cancelado', label: 'Cancelados' },
]

function statusBadge(status) {
  const map = {
    agendado:               { cls: 'badge-blue',   txt: 'Agendado' },
    concluido:              { cls: 'badge-green',  txt: 'Concluído' },
    cancelado:              { cls: 'badge-red',    txt: 'Cancelado' },
    aguardando_comprovante: { cls: 'badge-orange', txt: 'Aguard. comprovante' },
    aguardando_aprovacao:   { cls: 'badge-orange', txt: 'Aguard. aprovação' },
  }
  const { cls, txt } = map[status] || { cls: 'badge-gray', txt: status }
  return <span className={`badge ${cls}`}>{txt}</span>
}

function fmtMoeda(v) {
  return `R$ ${Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`
}

export default function Historico() {
  const [agendamentos, setAgendamentos] = useState([])
  const [statusFiltro, setStatusFiltro] = useState('')
  const [loading, setLoading]           = useState(true)
  const [cancelando, setCancelando]     = useState(null)
  const [pagina, setPagina]             = useState(1)
  const [totalPaginas, setTotalPaginas] = useState(1)

  const carregar = (status = '', page = 1) => {
    setLoading(true)
    const params = new URLSearchParams({ page, per_page: 50 })
    if (status) params.set('status', status)
    api.get(`/agendamentos?${params}`)
      .then(r => {
        setAgendamentos(Array.isArray(r?.dados) ? r.dados : [])
        setPagina(r?.page || 1)
        setTotalPaginas(r?.pages || 1)
      })
      .catch(() => setAgendamentos([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { carregar() }, [])

  const handleFiltro = (s) => {
    setStatusFiltro(s)
    carregar(s, 1)
  }

  const irPagina = (delta) => {
    const nova = pagina + delta
    if (nova < 1 || nova > totalPaginas) return
    carregar(statusFiltro, nova)
  }

  const handleCancelar = async (ag) => {
    if (!confirm('Cancelar este agendamento?')) return
    setCancelando(ag.id)
    try {
      await api.post(`/agendamentos/${ag.id}/cancelar`, {})
      showToast('Agendamento cancelado.', 'info')
      carregar(statusFiltro, pagina)
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setCancelando(null)
    }
  }

  return (
    <Layout title="Histórico">

      {/* Filtro */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        {STATUS_TABS.map(tab => (
          <button
            key={tab.value}
            className={`btn btn-sm ${statusFiltro === tab.value ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => handleFiltro(tab.value)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="loading"><div className="spinner" /></div>
      ) : agendamentos.length === 0 ? (
        <div className="card empty">
          <Clock size={36} style={{ margin: '0 auto 12px', opacity: .3 }} />
          <p>Nenhum agendamento encontrado</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Data / Hora</th>
                <th>Serviços</th>
                <th>Profissional</th>
                <th>Valor</th>
                <th>Pagamento</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {agendamentos.map(ag => {
                const data = ag.data_hora ? new Date(ag.data_hora) : null
                const dataStr = data ? data.toLocaleDateString('pt-BR') : '—'
                const horaStr = data ? data.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : ''
                const servicos = ag.servicos?.map(s => s.nome || `Serviço #${s.servico_id}`).join(', ') || '—'
                const podeCancelar = ag.status === 'agendado'
                return (
                  <tr key={ag.id}>
                    <td>
                      <div style={{ fontWeight: 600 }}>{dataStr}</div>
                      <div style={{ fontSize: 12, color: 'var(--muted)' }}>{horaStr}</div>
                    </td>
                    <td style={{ maxWidth: 180 }}>
                      <div style={{ fontSize: 13, color: 'var(--text)' }}>{servicos}</div>
                    </td>
                    <td style={{ color: 'var(--muted)', fontSize: 13 }}>
                      {ag.barbeiro_nome || '—'}
                    </td>
                    <td style={{ fontWeight: 600 }}>{fmtMoeda(ag.valor_total || ag.valor)}</td>
                    <td style={{ textTransform: 'capitalize', fontSize: 12, color: 'var(--muted)' }}>
                      {ag.metodo_pagamento || '—'}
                    </td>
                    <td>{statusBadge(ag.status)}</td>
                    <td>
                      {podeCancelar && (
                        <button
                          className="btn btn-danger btn-sm"
                          disabled={cancelando === ag.id}
                          onClick={() => handleCancelar(ag)}
                        >
                          {cancelando === ag.id ? '...' : <XCircle size={13} />}
                          {cancelando === ag.id ? '' : ' Cancelar'}
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {!loading && agendamentos.length > 0 && (
        <div className="pg-controls">
          <button className="btn btn-ghost btn-sm" disabled={pagina <= 1} onClick={() => irPagina(-1)}>&lt; Anterior</button>
          <span>Página {pagina} de {totalPaginas}</span>
          <button className="btn btn-ghost btn-sm" disabled={pagina >= totalPaginas} onClick={() => irPagina(1)}>Próxima &gt;</button>
        </div>
      )}
    </Layout>
  )
}
