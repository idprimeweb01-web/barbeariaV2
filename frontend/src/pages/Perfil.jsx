import { useEffect, useState } from 'react'
import { User, Mail, Phone, Save, LogOut } from 'lucide-react'
import Layout from '../components/Layout'
import { showToast } from '../components/Layout'
import { api } from '../api'

export default function Perfil() {
  const [perfil, setPerfil]     = useState(null)
  const [loading, setLoading]   = useState(true)
  const [salvando, setSalvando] = useState(false)
  const [form, setForm]         = useState({ nome: '', telefone: '', email: '' })
  const [editando, setEditando] = useState(false)

  useEffect(() => {
    api.get('/perfil').then(p => {
      setPerfil(p)
      setForm({ nome: p.nome || '', telefone: p.telefone || '', email: p.email || '' })
    }).finally(() => setLoading(false))
  }, [])

  const handleSalvar = async (e) => {
    e.preventDefault()
    setSalvando(true)
    try {
      const atualizado = await api.patch('/perfil', {
        nome:     form.nome.trim(),
        telefone: form.telefone.trim(),
        email:    form.email.trim() || null,
      })
      setPerfil(atualizado)
      setForm({ nome: atualizado.nome || '', telefone: atualizado.telefone || '', email: atualizado.email || '' })
      setEditando(false)
      showToast('Perfil atualizado!', 'success')
      // Atualiza o nome na UI sem recarregar
      window.BOS_USUARIO = atualizado.nome
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setSalvando(false)
    }
  }

  const handleLogout = () => api.logout()

  if (loading) return (
    <Layout title="Meu Perfil">
      <div className="loading"><div className="spinner" /></div>
    </Layout>
  )

  return (
    <Layout title="Meu Perfil">
      <div style={{ maxWidth: 600 }}>

        {/* Avatar + nome */}
        <div className="card" style={{ marginBottom: 20, display: 'flex', alignItems: 'center', gap: 20 }}>
          <div style={{ width: 64, height: 64, borderRadius: '50%', background: 'rgba(245,158,11,.15)', border: '2px solid rgba(245,158,11,.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26, fontWeight: 800, color: 'var(--primary)' }}>
            {(perfil?.nome || 'C').charAt(0).toUpperCase()}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 20, fontWeight: 700 }}>{perfil?.nome}</div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>{perfil?.email || perfil?.telefone}</div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={() => setEditando(e => !e)}>
            {editando ? 'Cancelar' : 'Editar'}
          </button>
        </div>

        {/* Formulário */}
        <div className="card" style={{ marginBottom: 20 }}>
          <div style={{ fontWeight: 700, marginBottom: 16 }}>Dados pessoais</div>

          {editando ? (
            <form onSubmit={handleSalvar}>
              <div className="field">
                <label>Nome completo</label>
                <input
                  type="text"
                  value={form.nome}
                  onChange={e => setForm(f => ({ ...f, nome: e.target.value }))}
                  required
                />
              </div>
              <div className="field">
                <label>Telefone</label>
                <input
                  type="tel"
                  value={form.telefone}
                  onChange={e => setForm(f => ({ ...f, telefone: e.target.value }))}
                  placeholder="(11) 99999-9999"
                />
              </div>
              <div className="field">
                <label>E-mail</label>
                <input
                  type="email"
                  value={form.email}
                  onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                  placeholder="seu@email.com"
                />
              </div>
              <button type="submit" className="btn btn-primary" disabled={salvando} style={{ width: '100%' }}>
                <Save size={14} />
                {salvando ? 'Salvando...' : 'Salvar alterações'}
              </button>
            </form>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {[
                { Icon: User,  label: 'Nome',     value: perfil?.nome },
                { Icon: Phone, label: 'Telefone', value: perfil?.telefone },
                { Icon: Mail,  label: 'E-mail',   value: perfil?.email || '—' },
              ].map(({ Icon, label, value }) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{ background: 'var(--surface2)', borderRadius: 8, padding: 8, flexShrink: 0 }}>
                    <Icon size={14} color="var(--muted)" />
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--muted2)', fontWeight: 700, textTransform: 'uppercase' }}>{label}</div>
                    <div style={{ fontSize: 14, fontWeight: 600 }}>{value || '—'}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Sair */}
        <div className="card" style={{ borderColor: 'rgba(220,38,38,.2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontWeight: 600 }}>Sair da conta</div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>Encerrar a sessão atual</div>
            </div>
            <button className="btn btn-danger" onClick={handleLogout}>
              <LogOut size={14} />
              Sair
            </button>
          </div>
        </div>
      </div>
    </Layout>
  )
}
