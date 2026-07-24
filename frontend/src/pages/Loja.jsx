import { useEffect, useState } from 'react'
import { ShoppingBag, Plus, Minus, Package } from 'lucide-react'
import Layout from '../components/Layout'
import { showToast } from '../components/Layout'
import { FeatureGate } from '../components/FeatureGate'
import { RecursoIndisponivel } from '../components/RecursoIndisponivel'
import PixConfirmacao from '../components/PixConfirmacao'
import { api } from '../api'

function fmtMoeda(v) {
  return `R$ ${Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`
}

function fmtData(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('pt-BR')
}

function StatusBadge({ status }) {
  const map = {
    pendente:  { cls: 'badge-orange', txt: 'Pendente' },
    aprovada:  { cls: 'badge-green',  txt: 'Aprovada' },
    rejeitada: { cls: 'badge-red',    txt: 'Rejeitada' },
  }
  const { cls, txt } = map[status] || { cls: 'badge-gray', txt: status }
  return <span className={`badge ${cls}`}>{txt}</span>
}

export default function Loja() {
  const [produtos, setProdutos]     = useState([])
  const [pedidos, setPedidos]       = useState([])
  const [features, setFeatures]     = useState([])
  const [loading, setLoading]       = useState(true)
  const [carrinho, setCarrinho]     = useState({}) // { produto_id: quantidade }
  const [cupom, setCupom]           = useState('')
  const [metodo, setMetodo]         = useState('pix')
  const [enviando, setEnviando]     = useState(false)
  const [pixPendente, setPixPendente] = useState(null) // { solicitacaoId, codigo }

  useEffect(() => {
    Promise.all([
      api.produtos.listar(),
      api.produtos.listarPedidos(),
      api.features.listar(),
    ]).then(([prods, peds, feats]) => {
      setProdutos(Array.isArray(prods) ? prods : [])
      setPedidos(Array.isArray(peds) ? peds : [])
      const feats2 = Array.isArray(feats) ? feats : []
      setFeatures(feats2)
      const pixAtivo = !!feats2.find(f => f.nome === 'pix_integrado')?.ativo
      if (!pixAtivo) setMetodo('dinheiro')
    }).finally(() => setLoading(false))
  }, [])

  const alterarQtd = (produtoId, delta, max) => {
    setCarrinho(prev => {
      const atual = prev[produtoId] || 0
      const nova = Math.max(0, Math.min(max, atual + delta))
      const copia = { ...prev }
      if (nova === 0) delete copia[produtoId]
      else copia[produtoId] = nova
      return copia
    })
  }

  const itensCarrinho = Object.entries(carrinho).map(([produtoId, quantidade]) => {
    const p = produtos.find(x => x.id === Number(produtoId))
    return { produto: p, quantidade }
  }).filter(i => i.produto)

  const subtotal = itensCarrinho.reduce((soma, i) => soma + i.produto.preco * i.quantidade, 0)

  const limparCarrinho = () => {
    setCarrinho({})
    setCupom('')
  }

  const handleComprar = async () => {
    if (!itensCarrinho.length) { showToast('Adicione ao menos um produto ao carrinho.', 'error'); return }
    setEnviando(true)
    try {
      const res = await api.produtos.comprar({
        itens: itensCarrinho.map(i => ({ produto_id: i.produto.id, quantidade: i.quantidade })),
        metodo_pagamento: metodo,
        cupom_codigo: cupom.trim() || null,
      })
      const peds = await api.produtos.listarPedidos()
      setPedidos(Array.isArray(peds) ? peds : [])
      limparCarrinho()
      if (res.pix_copia_cola) {
        setPixPendente({
          solicitacaoId: res.solicitacao_id,
          codigo: res.pix_copia_cola,
          chavePix: res.chave_pix,
          titular: res.pix_nome_titular,
        })
      } else {
        showToast(res.mensagem || 'Pedido enviado! Aguarde a aprovação do estabelecimento.', 'success')
      }
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setEnviando(false)
    }
  }

  if (loading) return (
    <Layout title="Loja">
      <div className="loading"><div className="spinner" /></div>
    </Layout>
  )

  if (pixPendente) return (
    <Layout title="Loja">
      <PixConfirmacao
        codigo={pixPendente.codigo}
        chavePix={pixPendente.chavePix}
        titular={pixPendente.titular}
        uploadFn={(file) => api.produtos.uploadComprovante(pixPendente.solicitacaoId, file)}
        showToast={showToast}
        labelFinalizar="Voltar para a loja"
        onFinalizar={() => setPixPendente(null)}
      />
    </Layout>
  )

  return (
    <Layout title="Loja">
    <FeatureGate features={features} feature="produtos_venda" fallback={<RecursoIndisponivel />}>

      <div className="section-header">
        <span className="section-title">Produtos disponíveis</span>
      </div>

      {produtos.length === 0 ? (
        <div className="card empty" style={{ marginBottom: 24 }}>
          <Package size={32} style={{ margin: '0 auto 10px', opacity: .3 }} />
          <p>Nenhum produto disponível no momento</p>
        </div>
      ) : (
        <div className="grid-3" style={{ marginBottom: 24 }}>
          {produtos.map(p => {
            const qtd = carrinho[p.id] || 0
            const esgotado = p.quantidade_disponivel <= 0
            return (
              <div key={p.id} className="card" style={{ opacity: esgotado ? .5 : 1 }}>
                {p.foto_url && (
                  <img src={p.foto_url} alt={p.nome} style={{ width: '100%', height: 120, objectFit: 'cover', borderRadius: 8, marginBottom: 10 }} />
                )}
                <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 4 }}>{p.nome}</div>
                <div style={{ color: 'var(--primary)', fontWeight: 800, fontSize: 15, marginBottom: 8 }}>{fmtMoeda(p.preco)}</div>

                {esgotado ? (
                  <span className="badge badge-gray">Sem estoque</span>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, justifyContent: 'space-between' }}>
                    <button className="btn btn-ghost btn-sm" disabled={qtd === 0} onClick={() => alterarQtd(p.id, -1, p.quantidade_disponivel)}>
                      <Minus size={14} />
                    </button>
                    <span style={{ fontWeight: 700, minWidth: 20, textAlign: 'center' }}>{qtd}</span>
                    <button className="btn btn-ghost btn-sm" disabled={qtd >= p.quantidade_disponivel} onClick={() => alterarQtd(p.id, 1, p.quantidade_disponivel)}>
                      <Plus size={14} />
                    </button>
                  </div>
                )}
                <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 6 }}>{p.quantidade_disponivel} em estoque</div>
              </div>
            )
          })}
        </div>
      )}

      {itensCarrinho.length > 0 && (
        <div className="card" style={{ marginBottom: 28 }}>
          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <ShoppingBag size={16} /> Seu carrinho
          </div>
          {itensCarrinho.map(i => (
            <div key={i.produto.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 6 }}>
              <span>{i.quantidade}× {i.produto.nome}</span>
              <span>{fmtMoeda(i.produto.preco * i.quantidade)}</span>
            </div>
          ))}
          <div style={{ borderTop: '1px solid var(--border)', marginTop: 10, paddingTop: 10, display: 'flex', justifyContent: 'space-between', fontWeight: 700 }}>
            <span>Total</span>
            <span>{fmtMoeda(subtotal)}</span>
          </div>

          <div className="field" style={{ marginTop: 16 }}>
            <label>Cupom (opcional)</label>
            <input type="text" placeholder="CODIGO123" value={cupom} onChange={e => setCupom(e.target.value.toUpperCase())} />
          </div>

          <div className="field" style={{ marginBottom: 16 }}>
            <label>Forma de pagamento</label>
            <select
              value={metodo}
              onChange={e => setMetodo(e.target.value)}
              style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', padding: '8px 10px', fontSize: 13, width: '100%' }}
            >
              <FeatureGate features={features} feature="pix_integrado">
                <option value="pix">PIX</option>
              </FeatureGate>
              <option value="dinheiro">Dinheiro (pago na loja)</option>
              <option value="cartao">Cartão (pago na loja)</option>
            </select>
          </div>

          <button className="btn btn-primary" style={{ width: '100%' }} disabled={enviando} onClick={handleComprar}>
            {enviando ? 'Enviando…' : `Finalizar pedido — ${fmtMoeda(subtotal)}`}
          </button>
        </div>
      )}

      {pedidos.length > 0 && (
        <>
          <div className="section-header">
            <span className="section-title">Meus pedidos</span>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Itens</th>
                  <th>Valor</th>
                  <th>Pagamento</th>
                  <th>Data</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {pedidos.map(s => (
                  <tr key={s.id}>
                    <td>{s.itens.map(it => `${it.quantidade}× ${it.produto_nome || '?'}`).join(', ')}</td>
                    <td>
                      {fmtMoeda(s.valor_total)}
                      {s.valor_desconto > 0 && (
                        <div style={{ fontSize: 11, color: '#4ade80' }}>− {fmtMoeda(s.valor_desconto)} ({s.cupom_codigo})</div>
                      )}
                    </td>
                    <td style={{ textTransform: 'capitalize' }}>{s.metodo_pagamento}</td>
                    <td style={{ color: 'var(--muted)', fontSize: 12 }}>{fmtData(s.criado_em)}</td>
                    <td>
                      <StatusBadge status={s.status} />
                      {s.status === 'rejeitada' && s.motivo_rejeicao && (
                        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>{s.motivo_rejeicao}</div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

    </FeatureGate>
    </Layout>
  )
}
