import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Star, Gift, CheckCircle, Award, TrendingUp } from 'lucide-react'
import Layout from '../components/Layout'
import { FeatureGate } from '../components/FeatureGate'
import { RecursoIndisponivel } from '../components/RecursoIndisponivel'
import { api } from '../api'

export default function Beneficios() {
  const [planos, setPlanos] = useState([])
  const [vip, setVip]       = useState(null)
  const [features, setFeatures] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    Promise.all([
      api.get('/planos?ativo=true'),
      api.get('/vip').catch(() => null),
      api.features.listar(),
    ]).then(([p, v, feats]) => {
      setPlanos(Array.isArray(p) ? p : [])
      setVip(v)
      setFeatures(Array.isArray(feats) ? feats : [])
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <Layout title="Benefícios">
      <div className="loading"><div className="spinner" /></div>
    </Layout>
  )

  const temPlano = planos.length > 0
  const nivelVip = vip?.nivel_vip_atual || 0

  return (
    <Layout title="Benefícios">
    <FeatureGate features={features} feature="vip_brindes" fallback={<RecursoIndisponivel />}>

      {/* VIP Status */}
      <div className="card" style={{ marginBottom: 24, background: nivelVip > 0 ? 'rgba(245,158,11,.04)' : 'var(--surface)', borderColor: nivelVip > 0 ? 'rgba(245,158,11,.3)' : 'var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: nivelVip > 0 ? 16 : 0 }}>
          <div style={{ background: nivelVip > 0 ? 'rgba(245,158,11,.15)' : 'rgba(255,255,255,.05)', borderRadius: 12, padding: 14 }}>
            <Award size={24} color={nivelVip > 0 ? 'var(--primary)' : '#555'} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <span style={{ fontWeight: 700, fontSize: 16 }}>Programa VIP</span>
              {nivelVip > 0 && (
                <div className="vip-badge">
                  <Star size={12} /> Nível {nivelVip}
                </div>
              )}
            </div>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>
              {nivelVip === 0
                ? 'Complete atendimentos para alcançar níveis VIP e desbloquear benefícios exclusivos'
                : vip?.nivel_info?.brinde_descricao || 'Benefício VIP ativo'}
            </div>
          </div>
        </div>

        {vip?.nivel_info && nivelVip > 0 && (
          <div style={{ padding: '12px 14px', background: 'rgba(245,158,11,.08)', borderRadius: 8, display: 'flex', gap: 12, alignItems: 'center' }}>
            <Gift size={16} color="var(--primary)" />
            <div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>Seu benefício atual</div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
                {vip.nivel_info.tipo_brinde === 'desconto'
                  ? `${vip.nivel_info.valor_desconto}% de desconto nos serviços`
                  : vip.nivel_info.brinde_descricao}
              </div>
            </div>
          </div>
        )}

        {vip?.data_proxima_renovacao && (
          <div style={{ marginTop: 10, fontSize: 11, color: 'var(--muted2)' }}>
            Próxima renovação: {new Date(vip.data_proxima_renovacao).toLocaleDateString('pt-BR')}
          </div>
        )}
      </div>

      {/* Planos ativos e seus benefícios */}
      <div className="section-header">
        <span className="section-title">Benefícios do plano</span>
        {!temPlano && (
          <button className="btn btn-primary btn-sm" onClick={() => navigate('/cliente/planos')}>
            Ver planos
          </button>
        )}
      </div>

      {!temPlano ? (
        <div className="card empty" style={{ marginBottom: 24 }}>
          <Star size={32} style={{ margin: '0 auto 10px', opacity: .3 }} />
          <p>Você não tem nenhum plano ativo</p>
          <p style={{ fontSize: 12, marginTop: 6 }}>Assine um plano para desbloquear benefícios exclusivos</p>
          <button className="btn btn-primary btn-sm" style={{ marginTop: 14 }} onClick={() => navigate('/cliente/planos')}>
            Conhecer planos
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginBottom: 24 }}>
          {planos.map(cp => (
            <div key={cp.id} className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 15 }}>{cp.plano_nome}</div>
                  <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
                    {cp.data_fim
                      ? `Válido até ${new Date(cp.data_fim).toLocaleDateString('pt-BR')}`
                      : 'Sem expiração definida'}
                  </div>
                </div>
                <span className="badge badge-green">Ativo</span>
              </div>

              {cp.servicos?.length > 0 ? (
                <div>
                  <div style={{ fontSize: 11, color: 'var(--muted2)', fontWeight: 700, textTransform: 'uppercase', marginBottom: 10 }}>
                    Serviços incluídos ({cp.servicos.length})
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {cp.servicos.map(sv => {
                      const restante = sv.ilimitado ? null : sv.restante ?? (sv.limite_uso_mensal - sv.uso_mes_atual)
                      const pct = sv.ilimitado ? 0 : sv.limite_uso_mensal > 0 ? (sv.uso_mes_atual / sv.limite_uso_mensal) * 100 : 0
                      return (
                        <div key={sv.servico_id}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                            <div style={{ background: 'rgba(245,158,11,.1)', borderRadius: 6, padding: '4px 6px' }}>
                              <CheckCircle size={13} color="var(--primary)" />
                            </div>
                            <span style={{ fontWeight: 600, flex: 1 }}>{sv.nome}</span>
                            <span style={{ fontSize: 12, color: sv.ilimitado ? '#4ade80' : pct >= 85 ? '#f87171' : 'var(--muted)' }}>
                              {sv.ilimitado ? '∞ Ilimitado' : `${sv.uso_mes_atual}/${sv.limite_uso_mensal} usados`}
                            </span>
                          </div>
                          {!sv.ilimitado && sv.limite_uso_mensal > 0 && (
                            <>
                              <div className="progress-bar">
                                <div className={`progress-fill ${pct >= 85 ? 'danger' : ''}`} style={{ width: `${Math.min(pct, 100)}%` }} />
                              </div>
                              {restante !== null && (
                                <div style={{ fontSize: 11, color: 'var(--muted2)', marginTop: 3 }}>
                                  {restante > 0 ? `${restante} restante${restante !== 1 ? 's' : ''} este mês` : 'Limite atingido este mês'}
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              ) : (
                <div style={{ color: 'var(--muted)', fontSize: 13 }}>Nenhum serviço detalhado disponível</div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Call to action: upgrade */}
      {temPlano && (
        <div className="card" style={{ borderColor: 'rgba(245,158,11,.2)', background: 'rgba(245,158,11,.03)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <TrendingUp size={20} color="var(--primary)" />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700 }}>Quer mais benefícios?</div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
                Faça upgrade para um plano superior e desbloqueie mais serviços e agendamentos
              </div>
            </div>
            <button className="btn btn-primary btn-sm" onClick={() => navigate('/cliente/planos')}>
              Ver planos
            </button>
          </div>
        </div>
      )}
    </FeatureGate>
    </Layout>
  )
}
