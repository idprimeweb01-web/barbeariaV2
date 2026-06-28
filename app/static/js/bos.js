/**
 * Bos — cliente HTTP autenticado por cookie (bos_at / bos_rt).
 * Cookies HttpOnly são enviados automaticamente pelo browser em toda
 * requisição same-origin. Não usa localStorage.
 *
 * Uso:
 *   const data = await Bos.get('/gestor/barbeiros');
 *   await Bos.post('/gestor/barbeiros', { nome: 'João' });
 *   Bos.logout();
 */
const Bos = (() => {
  const BASE = '/api/v1';

  async function _renovar() {
    try {
      const r = await fetch('/entrar/renovar', {
        method: 'POST',
        credentials: 'same-origin',
      });
      return r.ok;
    } catch {
      return false;
    }
  }

  async function _fetch(url, opts = {}) {
    let resp = await fetch(url, { credentials: 'same-origin', ...opts });

    if (resp.status === 401) {
      const renovado = await _renovar();
      if (!renovado) {
        window.location.href = '/entrar';
        return null;
      }
      resp = await fetch(url, { credentials: 'same-origin', ...opts });
    }

    return resp;
  }

  async function _json(url, opts = {}) {
    const resp = await _fetch(url, opts);
    if (!resp) return null;

    let data;
    try { data = await resp.json(); } catch { data = {}; }

    if (!resp.ok) {
      const err = new Error(data.erro || data.message || `HTTP ${resp.status}`);
      err.status = resp.status;
      err.data   = data;
      throw err;
    }
    return data;
  }

  const JSON_H = { 'Content-Type': 'application/json' };

  return {
    get(path) {
      return _json(`${BASE}${path}`);
    },

    post(path, body) {
      return _json(`${BASE}${path}`, {
        method: 'POST',
        headers: JSON_H,
        body: JSON.stringify(body),
      });
    },

    patch(path, body) {
      return _json(`${BASE}${path}`, {
        method: 'PATCH',
        headers: JSON_H,
        body: JSON.stringify(body),
      });
    },

    put(path, body) {
      return _json(`${BASE}${path}`, {
        method: 'PUT',
        headers: JSON_H,
        body: JSON.stringify(body),
      });
    },

    delete(path) {
      return _json(`${BASE}${path}`, { method: 'DELETE' });
    },

    /** Multipart upload — não passa Content-Type (browser define o boundary). */
    upload(path, formData) {
      return _json(`${BASE}${path}`, { method: 'POST', body: formData });
    },

    async logout() {
      try {
        await fetch('/sair', { method: 'POST', credentials: 'same-origin' });
      } catch { /* silencioso */ }
      window.location.href = '/entrar';
    },
  };
})();
