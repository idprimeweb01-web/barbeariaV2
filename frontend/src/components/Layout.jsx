import { useState, useCallback } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Star, Calendar, Gift, Clock, User, LogOut, Scissors
} from 'lucide-react'
import { api } from '../api'

const NOME = window.BOS_USUARIO || 'Cliente'
const BK_NOME = window.BOS_NOME || 'Barbearia'

const NAV = [
  { to: '/cliente/dashboard',  label: 'Dashboard',   Icon: LayoutDashboard },
  { to: '/cliente/planos',     label: 'Meus Planos',  Icon: Star },
  { to: '/cliente/agendar',    label: 'Agendar',      Icon: Calendar },
  { to: '/cliente/beneficios', label: 'Benefícios',   Icon: Gift },
  { to: '/cliente/historico',  label: 'Histórico',    Icon: Clock },
  { to: '/cliente/perfil',     label: 'Meu Perfil',   Icon: User },
]

export let showToast = () => {}

export default function Layout({ children, title }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [toasts, setToasts] = useState([])
  const navigate = useNavigate()

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
          {NAV.map(({ to, label, Icon }) => (
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
