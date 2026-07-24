const SLUG = window.BOS_SLUG || '';
let _featuresCache = null;

async function _req(method, url, body) {
  const opts = {
    method,
    credentials: 'same-origin',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  };

  let resp = await fetch(url, opts);

  if (resp.status === 401) {
    const renovar = await fetch('/entrar/renovar', { method: 'POST', credentials: 'same-origin' });
    if (renovar.ok) {
      resp = await fetch(url, opts);
    } else {
      window.location.href = `/b/${SLUG}/entrar`;
      return null;
    }
  }

  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.erro || data.error || `Erro ${resp.status}`);
  }

  return resp.json();
}

export const api = {
  get:   (path)       => _req('GET',   `/api/v1/cliente${path}`),
  post:  (path, body) => _req('POST',  `/api/v1/cliente${path}`, body),
  patch: (path, body) => _req('PATCH', `/api/v1/cliente${path}`, body),

  pub: {
    get:  (path) => _req('GET', `/api/v1/pub/${SLUG}${path}`),
    post: (path, body) => _req('POST', `/api/v1/pub/${SLUG}${path}`, body),
    // Multipart — não passa por _req (Content-Type é definido pelo browser,
    // com o boundary). Mesma rota pública usada pelo booking.html anônimo;
    // não exige login, então funciona igual pra cliente autenticado.
    uploadComprovante: async (agendamentoId, file) => {
      const fd = new FormData()
      fd.append('arquivo', file)
      const resp = await fetch(`/api/v1/pub/${SLUG}/agendamentos/${agendamentoId}/comprovante`, {
        method: 'POST', body: fd, credentials: 'same-origin',
      })
      const data = await resp.json().catch(() => ({}))
      if (!resp.ok) throw new Error(data.erro || data.error || `Erro ${resp.status}`)
      return data
    },
    uploadComprovantePlano: async (solicitacaoId, file) => {
      const fd = new FormData()
      fd.append('arquivo', file)
      const resp = await fetch(`/api/v1/pub/${SLUG}/planos/solicitacoes/${solicitacaoId}/comprovante`, {
        method: 'POST', body: fd, credentials: 'same-origin',
      })
      const data = await resp.json().catch(() => ({}))
      if (!resp.ok) throw new Error(data.erro || data.error || `Erro ${resp.status}`)
      return data
    },
  },

  planos: {
    listar:    ()        => _req('GET',  `/api/v1/pub/${SLUG}/planos`),
    solicitar: (id, body) => _req('POST', `/api/v1/pub/${SLUG}/planos/${id}/solicitar`, body),
  },

  produtos: {
    listar:        ()     => _req('GET',  `/api/v1/cliente/produtos`),
    listarPedidos: ()     => _req('GET',  `/api/v1/cliente/compras`),
    comprar:       (body) => _req('POST', `/api/v1/cliente/compras`, body),
    // Multipart — mesmo motivo do uploadComprovante de agendamento/plano.
    uploadComprovante: async (solicitacaoId, file) => {
      const fd = new FormData()
      fd.append('arquivo', file)
      const resp = await fetch(`/api/v1/cliente/compras/${solicitacaoId}/comprovante`, {
        method: 'POST', body: fd, credentials: 'same-origin',
      })
      const data = await resp.json().catch(() => ({}))
      if (!resp.ok) throw new Error(data.erro || data.error || `Erro ${resp.status}`)
      return data
    },
  },

  duvidas: {
    listar:      ()   => _req('GET', `/api/v1/cliente/duvidas`),
    detalhar:    (id) => _req('GET', `/api/v1/cliente/duvidas/${id}`),
    fechar:      (id) => _req('PUT', `/api/v1/cliente/duvidas/${id}/fechar`),
    funcionarios: ()  => _req('GET', `/api/v1/cliente/duvidas/funcionarios`),
    avaliar: (id, { nota, comentario }) => _req('POST', `/api/v1/cliente/duvidas/${id}/satisfacao`, { nota, comentario }),
    // Multipart (texto e/ou até 3 imagens) — mesmo motivo das demais uploads deste arquivo.
    criar: async ({ assunto, texto, categoria, prioridade, barbeiroId, imagens }) => {
      const fd = new FormData()
      if (assunto) fd.append('assunto', assunto)
      if (texto) fd.append('texto', texto)
      if (categoria) fd.append('categoria', categoria)
      if (prioridade) fd.append('prioridade', prioridade)
      if (barbeiroId) fd.append('barbeiro_id', barbeiroId)
      ;(imagens || []).forEach(f => fd.append('imagens', f))
      const resp = await fetch(`/api/v1/cliente/duvidas`, {
        method: 'POST', body: fd, credentials: 'same-origin',
      })
      const data = await resp.json().catch(() => ({}))
      if (!resp.ok) throw new Error(data.erro || data.error || `Erro ${resp.status}`)
      return data
    },
    responder: async (id, { texto, imagens }) => {
      const fd = new FormData()
      if (texto) fd.append('texto', texto)
      ;(imagens || []).forEach(f => fd.append('imagens', f))
      const resp = await fetch(`/api/v1/cliente/duvidas/${id}/mensagens`, {
        method: 'POST', body: fd, credentials: 'same-origin',
      })
      const data = await resp.json().catch(() => ({}))
      if (!resp.ok) throw new Error(data.erro || data.error || `Erro ${resp.status}`)
      return data
    },
  },

  notificacoes: {
    listar:           (perPage = 6) => _req('GET',   `/api/v1/cliente/notificacoes?per_page=${perPage}`),
    contador:         ()            => _req('GET',   `/api/v1/cliente/notificacoes/contador`),
    marcarLida:       (id)          => _req('PATCH', `/api/v1/cliente/notificacoes/${id}/lida`, {}),
    marcarTodasLidas: ()            => _req('POST',  `/api/v1/cliente/notificacoes/marcar-todas-lidas`, {}),
  },

  features: {
    // Memoizado: Layout + páginas pedem a mesma lista a cada navegação
    // (Layout remonta a cada troca de rota); features não mudam durante
    // a sessão então uma única chamada de rede basta.
    listar: () => {
      if (!_featuresCache) _featuresCache = _req('GET', `/api/v1/cliente/features`);
      return _featuresCache;
    },
  },

  logout: async () => {
    await fetch('/sair', { method: 'POST', credentials: 'same-origin' });
    window.location.href = `/b/${SLUG}/entrar`;
  },
};
