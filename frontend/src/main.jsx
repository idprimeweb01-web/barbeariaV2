import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles/index.css'

// Theme token: cor_primaria da barbearia (BarbeariaCustomizacao) sobrescreve
// o --primary fixo do CSS — mesma ideia do tema dinâmico que gestor/barbeiro/
// super já têm via GET /gestor/barbearia/tema, só que aplicado 1x aqui em vez
// de por página (window.BOS_COR_PRIMARIA vem do server em cliente/app.html).
if (window.BOS_COR_PRIMARIA) {
  document.documentElement.style.setProperty('--primary', window.BOS_COR_PRIMARIA)
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
