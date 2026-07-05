import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Calendar, User, Scissors, Clock, CheckCircle, AlertCircle } from 'lucide-react'
import Layout from '../components/Layout'
import { showToast } from '../components/Layout'
import { api } from '../api'

const SLUG = window.BOS_SLUG || ''

function fmtMoeda(v) {
  return `R$ ${Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`
}

function hoje() {
  return new Date().toISOString().split('T')[0]
}

export default function Agendar() {
  const [step, setStep]             = useState(1) // 1=serviço, 2=barbeiro, 3=data/hora, 4=confirmar
  const [planoAtivo, setPlanoAtivo] = useState(null)
  const [servicos, setServicos]     = useState([])  // todos disponíveis
  const [barbeiros, setBarbeiros]   = useState([])
  const [slots, setSlots]           = useState([])
  const [motivoIndisponivel, setMotivoIndisponivel] = useState(null)

  const [servicoSel, setServicoSel]   = useState(null)
  const [barbeiroSel, setBarbeiroSel] = useState(null)
  const [dataSel, setDataSel]         = useState(hoje())
  const [horaSel, setHoraSel]         = useState(null)
  const [metodo, setMetodo]           = useState('local')
  const [obs, setObs]                 = useState('')
  const [cupom, setCupom]             = useState('')

  const [loadingSlots, setLoadingSlots] = useState(false)
  const [agendando, setAgendando]       = useState(false)
  const [loading, setLoading]           = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    Promise.all([
      api.get('/planos?ativo=true'),
      api.pub.get('/servicos'),
    ]).then(([assinaturas, svcs]) => {
      const ass = Array.isArray(assinaturas) ? assinaturas : []
      const plano = ass.find(a => a.ativo !== false) || null
      setPlanoAtivo(plano)
      setServicos(Array.isArray(svcs) ? svcs : [])
    }).finally(() => setLoading(false))
  }, [])

  // IDs de serviços liberados pelo plano ativo
  const idsLiberados = planoAtivo
    ? new Set(planoAtivo.servicos?.map(s => s.servico_id) || [])
    : null  // null = sem plano = todos

  const servicosFiltrados = planoAtivo
    ? servicos.filter(s => idsLiberados.has(s.id))
    : servicos

  // Ao selecionar serviço → buscar barbeiros
  const onSelectServico = async (sv) => {
    setServicoSel(sv)
    setBarbeiroSel(null)
    setHoraSel(null)
    setSlots([])
    try {
      const lista = await api.pub.get(`/barbeiros?servico_ids=${sv.id}`)
      setBarbeiros(Array.isArray(lista) ? lista : [])
    } catch {
      setBarbeiros([])
    }
    setStep(2)
  }

  // Ao selecionar barbeiro → buscar slots
  useEffect(() => {
    if (!barbeiroSel || !dataSel || !servicoSel) return
    setLoadingSlots(true)
    setSlots([])
    setMotivoIndisponivel(null)
    setHoraSel(null)
    api.pub.get(`/barbeiros/${barbeiroSel.id}/slots?data=${dataSel}&duracao=${servicoSel.duracao_minutos || 30}`)
      .then(r => {
        setSlots(Array.isArray(r?.slots) ? r.slots : [])
        setMotivoIndisponivel(r?.indisponivel ? r.motivo : null)
      })
      .catch(() => setSlots([]))
      .finally(() => setLoadingSlots(false))
  }, [barbeiroSel, dataSel, servicoSel])

  const onSelectBarbeiro = (br) => {
    setBarbeiroSel(br)
    setHoraSel(null)
    setStep(3)
  }

  const onSelectData = (d) => {
    setDataSel(d)
    setHoraSel(null)
  }

  const handleAgendar = async () => {
    if (!servicoSel || !barbeiroSel || !dataSel || !horaSel) {
      showToast('Preencha todos os campos', 'error')
      return
    }
    setAgendando(true)
    try {
      const dataHora = `${dataSel}T${horaSel}:00`
      await api.post('/agendamentos', {
        barbeiro_id:      barbeiroSel.id,
        data_hora:        dataHora,
        servicos:         [{ servico_id: servicoSel.id }],
        metodo_pagamento: metodo,
        observacao:       obs || null,
        cupom_codigo:     cupom || null,
      })
      showToast('Agendamento criado com sucesso!', 'success')
      navigate('/cliente/historico')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setAgendando(false)
    }
  }

  if (loading) return (
    <Layout title="Agendar">
      <div className="loading"><div className="spinner" /></div>
    </Layout>
  )

  return (
    <Layout title="Agendar">

      {/* Aviso de plano */}
      {planoAtivo ? (
        <div className="card" style={{ marginBottom: 20, display: 'flex', gap: 12, alignItems: 'flex-start', background: 'rgba(245,158,11,.05)', borderColor: 'rgba(245,158,11,.2)' }}>
          <CheckCircle size={18} color="var(--primary)" style={{ flexShrink: 0, marginTop: 1 }} />
          <div>
            <div style={{ fontWeight: 600, fontSize: 13 }}>Plano {planoAtivo.plano_nome} ativo</div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
              Mostrando apenas os serviços incluídos no seu plano ({planoAtivo.servicos?.length || 0} disponíveis)
            </div>
          </div>
        </div>
      ) : (
        <div className="card" style={{ marginBottom: 20, display: 'flex', gap: 12, alignItems: 'flex-start', borderColor: 'rgba(59,130,246,.2)' }}>
          <AlertCircle size={18} color="#93c5fd" style={{ flexShrink: 0, marginTop: 1 }} />
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>
            Sem plano ativo — todos os serviços disponíveis para agendamento avulso.
          </div>
        </div>
      )}

      {/* Steps */}
      <div className="steps">
        {[['Serviço', Scissors], ['Barbeiro', User], ['Data & Hora', Calendar], ['Confirmar', CheckCircle]].map(([label, Icon], i) => (
          <div key={label} className={`step ${step === i + 1 ? 'active' : ''}`} style={{ cursor: i + 1 < step ? 'pointer' : 'default' }} onClick={() => { if (i + 1 < step) setStep(i + 1) }}>
            <div className="step-num">{i + 1}</div>
            <Icon size={13} />
            <span style={{ fontSize: 11 }}>{label}</span>
          </div>
        ))}
      </div>

      {/* Step 1 — Serviço */}
      {step === 1 && (
        <div>
          <div className="section-header"><span className="section-title">Escolha o serviço</span></div>
          {servicosFiltrados.length === 0 ? (
            <div className="card empty">
              <Scissors size={32} style={{ margin: '0 auto 10px', opacity: .3 }} />
              <p>Nenhum serviço disponível para o seu plano</p>
            </div>
          ) : (
            <div className="grid-3">
              {servicosFiltrados.map(sv => (
                <div key={sv.id} className={`card`} style={{ cursor: 'pointer', transition: 'border-color .15s', borderColor: servicoSel?.id === sv.id ? 'var(--primary)' : 'var(--border)' }} onClick={() => onSelectServico(sv)}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                    <div style={{ background: 'rgba(245,158,11,.1)', borderRadius: 8, padding: 8 }}>
                      <Scissors size={16} color="var(--primary)" />
                    </div>
                    <span style={{ fontWeight: 600 }}>{sv.nome}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--muted)' }}>
                    <span><Clock size={11} style={{ verticalAlign: 'middle', marginRight: 3 }} />{sv.duracao_minutos || 30} min</span>
                    <span style={{ color: 'var(--primary)', fontWeight: 700 }}>{fmtMoeda(sv.preco)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Step 2 — Barbeiro */}
      {step === 2 && (
        <div>
          <div className="section-header">
            <span className="section-title">Escolha o profissional</span>
            <button className="btn btn-ghost btn-sm" onClick={() => setStep(1)}>← Voltar</button>
          </div>
          {barbeiros.length === 0 ? (
            <div className="card empty">
              <User size={32} style={{ margin: '0 auto 10px', opacity: .3 }} />
              <p>Nenhum profissional disponível para este serviço</p>
            </div>
          ) : (
            <div className="grid-3">
              {barbeiros.map(br => (
                <div key={br.id} className="card" style={{ cursor: 'pointer', borderColor: barbeiroSel?.id === br.id ? 'var(--primary)' : 'var(--border)' }} onClick={() => onSelectBarbeiro(br)}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div className="user-avatar" style={{ width: 40, height: 40, fontSize: 16 }}>
                      {(br.nome || br.usuario_nome || '?').charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div style={{ fontWeight: 600 }}>{br.nome || br.usuario_nome}</div>
                      {br.especialidade && <div style={{ fontSize: 11, color: 'var(--muted)' }}>{br.especialidade}</div>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Step 3 — Data & Hora */}
      {step === 3 && (
        <div>
          <div className="section-header">
            <span className="section-title">Escolha data e hora</span>
            <button className="btn btn-ghost btn-sm" onClick={() => setStep(2)}>← Voltar</button>
          </div>
          <div className="grid-2">
            <div>
              <div className="field">
                <label>Data</label>
                <input type="date" value={dataSel} min={hoje()} onChange={e => onSelectData(e.target.value)} />
              </div>
              <div style={{ marginTop: 6, fontSize: 12, color: 'var(--muted)' }}>
                Profissional: <strong style={{ color: 'var(--text)' }}>{barbeiroSel?.nome || barbeiroSel?.usuario_nome}</strong>
              </div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--muted2)', fontWeight: 700, textTransform: 'uppercase', marginBottom: 10 }}>Horários disponíveis</div>
              {loadingSlots ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--muted)', fontSize: 13 }}>
                  <div className="spinner" style={{ width: 20, height: 20, borderWidth: 2 }} />
                  Buscando horários...
                </div>
              ) : slots.length === 0 ? (
                <div className="empty" style={{ padding: '20px 0' }}>
                  <p>{motivoIndisponivel || 'Nenhum horário disponível nesta data'}</p>
                </div>
              ) : (
                <div className="slots-grid">
                  {slots.map(slot => (
                    <button key={slot} className={`slot-btn ${horaSel === slot ? 'selected' : ''}`} onClick={() => { setHoraSel(slot); setStep(4) }}>
                      {slot}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Step 4 — Confirmar */}
      {step === 4 && (
        <div>
          <div className="section-header">
            <span className="section-title">Confirmar agendamento</span>
            <button className="btn btn-ghost btn-sm" onClick={() => setStep(3)}>← Voltar</button>
          </div>

          <div className="card" style={{ marginBottom: 20 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              {[
                ['Serviço', servicoSel?.nome],
                ['Profissional', barbeiroSel?.nome || barbeiroSel?.usuario_nome],
                ['Data', dataSel ? new Date(dataSel + 'T12:00:00').toLocaleDateString('pt-BR') : ''],
                ['Hora', horaSel],
                ['Valor', fmtMoeda(servicoSel?.preco)],
                ['Duração', `${servicoSel?.duracao_minutos || 30} min`],
              ].map(([k, v]) => (
                <div key={k}>
                  <div style={{ fontSize: 11, color: 'var(--muted2)', fontWeight: 700, textTransform: 'uppercase' }}>{k}</div>
                  <div style={{ fontWeight: 600, marginTop: 3 }}>{v}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="card" style={{ marginBottom: 20 }}>
            <div className="field-row">
              <div className="field">
                <label>Forma de pagamento</label>
                <select value={metodo} onChange={e => setMetodo(e.target.value)}>
                  <option value="local">No local</option>
                  <option value="pix">PIX</option>
                  <option value="cartao">Cartão</option>
                  <option value="dinheiro">Dinheiro</option>
                </select>
              </div>
              <div className="field">
                <label>Cupom (opcional)</label>
                <input type="text" placeholder="CODIGO123" value={cupom} onChange={e => setCupom(e.target.value.toUpperCase())} />
              </div>
            </div>
            <div className="field">
              <label>Observação (opcional)</label>
              <textarea rows={2} placeholder="Ex: prefiro tesoura, alergia a produto X..." value={obs} onChange={e => setObs(e.target.value)} />
            </div>
          </div>

          <button
            className="btn btn-primary"
            style={{ width: '100%', padding: '12px', fontSize: 14 }}
            disabled={agendando}
            onClick={handleAgendar}
          >
            {agendando ? 'Agendando...' : 'Confirmar agendamento'}
          </button>
        </div>
      )}
    </Layout>
  )
}
