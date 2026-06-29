"""
Teste automatizado das 8 rotas do gestor.

Fluxo:
  1. Login como super_admin
  2. Cria barbearia + gestor de teste (idempotente via slug fixo)
  3. Login como gestor
  4. Testa GET de cada tela HTML do gestor
  5. Testa GET de cada endpoint de API do gestor
  6. Salva resultado em teste_gestor.txt
"""

import sys
import io
import json
import time
import requests
from datetime import datetime

# Força UTF-8 no stdout (Windows pode usar cp1252 por padrão)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE   = "http://127.0.0.1:5000"
SLUG   = "teste-auto"
EMAIL  = "gestor.teste@barbearia-auto.com"
SENHA  = "Teste@123"

OK  = "[OK] "
ERR = "[ERRO]"
WRN = "[AVISO]"

linhas = []

def log(msg):
    print(msg)
    linhas.append(msg)

# ── Helpers ───────────────────────────────────────────────────────────────────

def checar(label, r, esperado=200, checar_json=False):
    """Verifica status code e opcionalmente se resposta é JSON válido."""
    ok = r.status_code == esperado
    if ok and checar_json:
        try:
            r.json()
        except Exception:
            ok = False
    icone = OK if ok else ERR
    detalhe = ""
    if not ok:
        try:
            body = r.json()
            detalhe = f" → {body.get('erro', body)}"
        except Exception:
            detalhe = f" → HTTP {r.status_code}"
    log(f"  {icone} {label}{detalhe}")
    return ok


def login(sess, email, senha):
    r = sess.post(f"{BASE}/entrar", json={"email": email, "senha": senha})
    if r.status_code != 200:
        return False, r.json().get("erro", "falha no login")
    redir = r.json().get("redirect", "")
    return True, redir


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

log("=" * 60)
log(f"  TESTE GESTOR — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
log("=" * 60)
log("")

# ── 1. Verificar servidor ─────────────────────────────────────────────────────
log("[ 1 ] Verificando servidor…")
try:
    r = requests.get(f"{BASE}/entrar", timeout=5)
    checar("GET /entrar (servidor UP)", r, 200)
except requests.ConnectionError:
    log(f"  {ERR} Servidor não responde em {BASE}")
    log("       Suba com: python wsgi.py")
    sys.exit(1)

log("")

# ── 2. Login super_admin ──────────────────────────────────────────────────────
log("[ 2 ] Login como super_admin…")
sess_super = requests.Session()
ok, redir = login(sess_super, "adm@barbearia.com", "123456")
if not ok:
    log(f"  {ERR} Login super_admin falhou: {redir}")
    sys.exit(1)
if "/super" not in redir:
    log(f"  {WRN} Redirect inesperado: {redir}  (continuando mesmo assim)")
else:
    log(f"  {OK} Login super_admin — redirect: {redir}")

log("")

# ── 3. Criar barbearia de teste ───────────────────────────────────────────────
log("[ 3 ] Criando barbearia de teste…")

payload_barb = {
    "nome":             "Barbearia Teste Auto",
    "slug":             SLUG,
    "nome_exibicao":    "Teste Auto",
    "gestor_nome":      "Gestor Teste",
    "gestor_email":     EMAIL,
    "gestor_telefone":  "11999990001",
    "gestor_senha":     SENHA,
}

r = sess_super.post(f"{BASE}/api/v1/super/barbearias", json=payload_barb)

if r.status_code == 201:
    barb_id = r.json()["barbearia"]["id"]
    log(f"  {OK} Barbearia criada — id={barb_id}, slug={SLUG}")

elif r.status_code == 409:
    # Já existe — busca o id pelo slug
    log(f"  {WRN} Slug '{SLUG}' já existe. Reutilizando…")
    r2 = sess_super.get(f"{BASE}/api/v1/super/barbearias")
    barbs = r2.json() if r2.status_code == 200 else []
    match = next((b for b in barbs if b["slug"] == SLUG), None)
    if not match:
        log(f"  {ERR} Não encontrou barbearia com slug={SLUG}")
        sys.exit(1)
    barb_id = match["id"]
    log(f"  {OK} Barbearia existente — id={barb_id}")

else:
    log(f"  {ERR} Criar barbearia falhou: HTTP {r.status_code} — {r.text[:200]}")
    sys.exit(1)

log("")

# ── 4. Login como gestor ──────────────────────────────────────────────────────
log("[ 4 ] Login como gestor…")
sess_gestor = requests.Session()
ok, redir = login(sess_gestor, EMAIL, SENHA)
if not ok:
    log(f"  {ERR} Login gestor falhou: {redir}")
    sys.exit(1)
log(f"  {OK} Login gestor — redirect: {redir}")

log("")

# ── 5. Rotas de TELA (HTML) ───────────────────────────────────────────────────
log("[ 5 ] Rotas de tela (GET HTML) — espera HTTP 200:")

rotas_tela = [
    ("Dashboard",   "/gestor/dashboard"),
    ("Agenda",      "/gestor/agenda"),
    ("Funcionários","/gestor/barbeiros"),
    ("Serviços",    "/gestor/servicos"),
    ("Produtos",    "/gestor/produtos"),
    ("Planos",      "/gestor/planos"),
    ("Relatórios",  "/gestor/relatorios"),
    ("Clientes",    "/gestor/clientes"),
]

tela_ok = 0
for nome, rota in rotas_tela:
    try:
        r = sess_gestor.get(f"{BASE}{rota}", allow_redirects=True, timeout=8)
        if r.status_code == 200 and (b"<!DOCTYPE" in r.content[:300] or b"<html" in r.content[:300]):
            log(f"  {OK} {nome} ({rota})")
            tela_ok += 1
        elif "entrar" in r.url:
            log(f"  {ERR} {nome} ({rota}) — redirecionou para login (sessão inválida?)")
        else:
            log(f"  {ERR} {nome} ({rota}) — HTTP {r.status_code} | {r.text[:80]}")
    except Exception as ex:
        log(f"  {ERR} {nome} ({rota}) — exceção: {ex}")

log("")

# ── 6. Endpoints de API ───────────────────────────────────────────────────────
log("[ 6 ] Endpoints de API (GET JSON) — espera HTTP 200 + JSON:")

hoje = datetime.now().strftime("%Y-%m-%d")
rotas_api = [
    ("API Dashboard",    f"/api/v1/gestor/dashboard"),
    ("API Agendamentos", f"/api/v1/gestor/agendamentos?data={hoje}"),
    ("API Barbeiros",    f"/api/v1/gestor/barbeiros"),
    ("API Serviços",     f"/api/v1/gestor/servicos"),
    ("API Produtos",     f"/api/v1/gestor/produtos"),
    ("API Planos",       f"/api/v1/gestor/planos"),
    ("API Relatórios",   f"/api/v1/gestor/relatorios/agendamentos?de={hoje}&ate={hoje}"),
    ("API Clientes",     f"/api/v1/gestor/clientes"),
]

api_ok = 0
for nome, rota in rotas_api:
    r = sess_gestor.get(f"{BASE}{rota}")
    ok_r = r.status_code == 200
    ok_j = False
    if ok_r:
        try:
            data = r.json()
            ok_j = True
            tipo = "lista" if isinstance(data, list) else f"dict({list(data.keys())[:3]})"
        except Exception:
            tipo = "JSON inválido"
    if ok_r and ok_j:
        log(f"  {OK} {nome} — {tipo}")
        api_ok += 1
    else:
        try:
            erro = r.json().get("erro", r.text[:120])
        except Exception:
            erro = r.text[:120]
        log(f"  {ERR} {nome} — HTTP {r.status_code}: {erro}")

log("")

# ── Resumo ────────────────────────────────────────────────────────────────────
log("=" * 60)
log(f"  RESULTADO FINAL")
log("=" * 60)
total_tela = len(rotas_tela)
total_api  = len(rotas_api)
log(f"  Telas  : {tela_ok}/{total_tela} {OK if tela_ok == total_tela else ERR}")
log(f"  APIs   : {api_ok}/{total_api}  {OK if api_ok == total_api else ERR}")
log(f"  Total  : {tela_ok + api_ok}/{total_tela + total_api}")
log("")

if tela_ok == total_tela and api_ok == total_api:
    log(f"  {OK} TUDO OK — LEVA 1 operacional!")
else:
    log(f"  {ERR} Há falhas — verifique acima.")

log("=" * 60)

# ── Salvar arquivo ────────────────────────────────────────────────────────────
out = r"c:\Users\ceno\Desktop\barbearia caio\barberos\teste_gestor.txt"
with open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(linhas) + "\n")

print(f"\n  Resultado salvo em: {out}")
