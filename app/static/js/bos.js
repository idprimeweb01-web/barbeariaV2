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
        window.location.href = window.BOS_LOGIN_URL || '/entrar';
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

  // ── Modal de confirmação padrão (UX-01) ──────────────────────────────────
  // Substitui window.confirm() nativo, que cada tela reimplementava do seu
  // jeito (ou usava o confirm() do navegador, sem estilo nem contexto).
  // Auto-contido: injeta seu próprio CSS/DOM sob demanda, então funciona em
  // qualquer página que já carregue bos.js, sem precisar editar o HTML dela.

  function _escHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  let _estiloConfirmarInjetado = false;
  function _injetarEstiloConfirmar() {
    if (_estiloConfirmarInjetado) return;
    _estiloConfirmarInjetado = true;
    const style = document.createElement('style');
    style.textContent = `
      .bos-confirm-overlay {
        position: fixed; inset: 0; background: rgba(0,0,0,.6);
        display: flex; align-items: center; justify-content: center;
        z-index: 10000; padding: 16px;
      }
      .bos-confirm-box {
        background: #1e1e1e; border: 1px solid #2a2a2a; border-radius: 12px;
        padding: 22px; max-width: 380px; width: 100%;
        box-shadow: 0 12px 40px rgba(0,0,0,.4);
        font-family: inherit;
      }
      .bos-confirm-title { font-size: 15px; font-weight: 700; color: #eee; margin-bottom: 8px; }
      .bos-confirm-msg { font-size: 13px; color: #aaa; line-height: 1.5; white-space: pre-line; margin-bottom: 20px; }
      .bos-confirm-actions { display: flex; justify-content: flex-end; gap: 8px; }
      .bos-confirm-btn {
        padding: 9px 16px; border-radius: 8px; border: 1px solid #333;
        background: none; color: #ccc; font-size: 13px; font-weight: 600;
        cursor: pointer; font-family: inherit; transition: opacity .15s;
      }
      .bos-confirm-btn:hover { opacity: .8; }
      .bos-confirm-btn.bos-confirm-perigo { background: #dc2626; border-color: #dc2626; color: #fff; }
      .bos-confirm-btn.bos-confirm-ok { background: var(--cor-primaria, #f39c12); border-color: var(--cor-primaria, #f39c12); color: #fff; }
    `;
    document.head.appendChild(style);
  }

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

    /**
     * Modal de confirmação padrão (substitui window.confirm nativo).
     * Uso: if (!(await Bos.confirmar('Desativar "X"?'))) return;
     * Também aceita objeto: Bos.confirmar({mensagem, titulo, textoConfirmar,
     * textoCancelar, perigo}). `perigo` (default true) pinta o botão de
     * confirmar em vermelho; use `perigo: false` para ações não-destrutivas.
     * Mensagens com "\n\n" continuam quebrando linha (mesmo padrão do
     * confirm() nativo que estava sendo usado antes).
     */
    confirmar(msgOuOpcoes) {
      const opts = typeof msgOuOpcoes === 'string' ? { mensagem: msgOuOpcoes } : (msgOuOpcoes || {});
      const {
        titulo = 'Confirmar ação',
        mensagem = '',
        textoConfirmar = 'Confirmar',
        textoCancelar = 'Cancelar',
        perigo = true,
      } = opts;

      _injetarEstiloConfirmar();

      return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'bos-confirm-overlay';
        overlay.innerHTML = `
          <div class="bos-confirm-box">
            <div class="bos-confirm-title">${_escHtml(titulo)}</div>
            <div class="bos-confirm-msg">${_escHtml(mensagem)}</div>
            <div class="bos-confirm-actions">
              <button type="button" class="bos-confirm-btn bos-confirm-cancelar">${_escHtml(textoCancelar)}</button>
              <button type="button" class="bos-confirm-btn ${perigo ? 'bos-confirm-perigo' : 'bos-confirm-ok'}">${_escHtml(textoConfirmar)}</button>
            </div>
          </div>`;
        document.body.appendChild(overlay);

        const encerrar = (resultado) => {
          document.removeEventListener('keydown', onKey);
          overlay.remove();
          resolve(resultado);
        };
        function onKey(e) {
          if (e.key === 'Escape') encerrar(false);
        }

        overlay.querySelector('.bos-confirm-cancelar').addEventListener('click', () => encerrar(false));
        overlay.querySelector(perigo ? '.bos-confirm-perigo' : '.bos-confirm-ok')
          .addEventListener('click', () => encerrar(true));
        overlay.addEventListener('click', (e) => { if (e.target === overlay) encerrar(false); });
        document.addEventListener('keydown', onKey);
      });
    },

    async logout() {
      try {
        await fetch('/sair', { method: 'POST', credentials: 'same-origin' });
      } catch { /* silencioso */ }
      window.location.href = window.BOS_LOGIN_URL || '/entrar';
    },

    /**
     * Monta um link wa.me a partir de um telefone salvo no banco (só
     * dígitos, DDD+número, sem DDI — ver app/utils/telefone.py). Assume
     * Brasil (+55) quando o número não já vier com DDI (10-11 dígitos).
     */
    wa(telefone, mensagem) {
      let d = String(telefone || '').replace(/\D/g, '');
      if (!d) return null;
      if (d.length <= 11) d = '55' + d;
      const texto = mensagem ? `?text=${encodeURIComponent(mensagem)}` : '';
      return `https://wa.me/${d}${texto}`;
    },

    /**
     * "Hoje" em Brasília (UTC-3, sem horário de verão desde 2019) — não usa
     * new Date().toISOString() puro, que reflete o fuso do navegador/SO e
     * pode devolver o dia seguinte (ou anterior) perto da meia-noite,
     * mesma classe de bug documentada como DT-001 no projeto.
     */
    hojeBrasilia() {
      // Date.getTime() já é absoluto (epoch UTC) — não precisa (e não deve)
      // somar getTimezoneOffset(), que só serve pra converter a LEITURA
      // local de volta pra UTC. Só subtrai o offset fixo de Brasília.
      return new Date(Date.now() - 3 * 3600000).toISOString().split('T')[0];
    },
  };
})();
