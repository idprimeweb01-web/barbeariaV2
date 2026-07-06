const SLUG = window.BOS_SLUG || '';

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
  },

  planos: {
    listar:    ()        => _req('GET',  `/api/v1/pub/${SLUG}/planos`),
    solicitar: (id, body) => _req('POST', `/api/v1/pub/${SLUG}/planos/${id}/solicitar`, body),
  },

  logout: async () => {
    await fetch('/sair', { method: 'POST', credentials: 'same-origin' });
    window.location.href = `/b/${SLUG}/entrar`;
  },
};
