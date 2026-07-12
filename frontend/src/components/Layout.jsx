import { useState, useCallback, useEffect } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Star, Calendar, Gift, Clock, User, LogOut, Scissors
} from 'lucide-react'
import { api } from '../api'

const NOME = window.BOS_USUARIO || 'Cliente'
const BK_NOME = window.BOS_NOME || 'Barbearia'

// `feature: null` = sempre visível (funcionalidade nuclear, não é um
// toggle do catálogo). Itens com `feature` só aparecem se a barbearia
// tiver aquela feature ativa — mesmo padrão do NAV_POR_FEATURE do gestor.
const NAV = [
  { to: '/cliente/dashboard',  label: 'Dashboard',   Icon: LayoutDashboard, feature: null },
  { to: '/cliente/planos',     label: 'Meus Planos',  Icon: Star,           feature: 'planos' },
  { to: '/cliente/agendar',    label: 'Agendar',      Icon: Calendar,       feature: null },
  { to: '/cliente/beneficios', label: 'Benefícios',   Icon: Gift,           feature: 'vip_brindes' },
  { to: '/cliente/historico',  label: 'Histórico',    Icon: Clock,          feature: null },
  { to: '/cliente/perfil',     label: 'Meu Perfil',   Icon: User,           feature: null },
]

export let showToast = () => {}

export default function Layout({ children, title }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [toasts, setToasts] = useState([])
  const [features, setFeatures] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    api.features.listar().then(setFeatures).catch(() => setFeatures([]))
  }, [])

  // Enquanto features ainda não carregou, mostra só os itens sempre-ativos
  // (evita um "flash" de links que serão escondidos um instante depois).
  const navVisivel = NAV.filter(({ feature }) => {
    if (!feature) return true
    if (!features) return false
    return !!features.find(f => f.nome === feature)?.ativo
  })

  showToast = useCallback((msg, tipo = 'success') => {
    const id = Date.now()
    setToasts(prev => [...prev, { id, msg, tipo }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3200)
  }, [])

  const handleLogout = async () => {
    await api.logout()
  }

  const closeSidebar = () => setSidebarOpen(false)

  return (
    <div className="shell">
      <div className={`overlay ${sidebarOpen ? 'open' : ''}`} onClick={closeSidebar} />

      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <div className="sidebar-logo">
            <Scissors size={16} />
          </div>
          <div>
            <div className="sidebar-name">{BK_NOME}</div>
            <div className="sidebar-sub">Área do Cliente</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {navVisivel.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
              onClick={closeSidebar}
            >
              <Icon size={15} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="user-avatar">{NOME.charAt(0).toUpperCase()}</div>
          <div className="user-info">
            <div className="user-name">{NOME}</div>
            <div className="user-role">Cliente</div>
          </div>
          <button className="btn-logout" onClick={handleLogout} title="Sair">
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <button className="hamburger" onClick={() => setSidebarOpen(o => !o)}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
          <span className="topbar-title">{title}</span>
          <button className="btn-logout" onClick={handleLogout} title="Sair" style={{ marginLeft: 'auto' }}>
            <LogOut size={16} />
          </button>
        </header>

        <main className="content">
          {children}
        </main>
      </div>

      <div id="toast-root">
        {toasts.map(t => (
          <div key={t.id} className={`toast toast-${t.tipo}`}>{t.msg}</div>
        ))}
      </div>
    </div>
  )
}
