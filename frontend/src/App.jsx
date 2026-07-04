import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Dashboard  from './pages/Dashboard'
import Planos     from './pages/Planos'
import Agendar    from './pages/Agendar'
import Beneficios from './pages/Beneficios'
import Historico  from './pages/Historico'
import Perfil     from './pages/Perfil'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/cliente/dashboard"  element={<Dashboard />} />
        <Route path="/cliente/planos"     element={<Planos />} />
        <Route path="/cliente/agendar"    element={<Agendar />} />
        <Route path="/cliente/beneficios" element={<Beneficios />} />
        <Route path="/cliente/historico"  element={<Historico />} />
        <Route path="/cliente/perfil"     element={<Perfil />} />
        <Route path="*" element={<Navigate to="/cliente/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
