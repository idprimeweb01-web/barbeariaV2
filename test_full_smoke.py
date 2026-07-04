"""
Teste completo de smoke test — login real + varredura de endpoints por perfil.
Roda contra um servidor Flask já em execução em http://127.0.0.1:5000.
NAO faz commit, NAO altera dados além do que os próprios endpoints fazem
(somente leituras e uma cancelacao reversivel de teste sao evitadas).
"""
import sys
import requests

BASE = 'http://127.0.0.1:5000'

LOGINS = {
    'super_admin': ('adm@barbearia.com', '123456'),
    'gestor':      ('winner@gestor.com', '123456'),
    'barbeiro':    ('winner@barber.com', '123456'),
}

results = []


def check(method, sess, path, expect, label, **kw):
    url = BASE + path
    try:
        r = sess.request(method, url, timeout=10, **kw)
    except Exception as e:
        results.append((label, method, path, 'EXC', str(e)))
        return None
    ok = r.status_code in expect if isinstance(expect, (list, tuple, set)) else r.status_code == expect
    status = 'OK' if ok else 'FAIL'
    results.append((label, method, path, status, r.status_code))
    return r


def login(perfil):
    email, senha = LOGINS[perfil]
    s = requests.Session()
    r = s.post(f'{BASE}/entrar', json={'email': email, 'senha': senha, 'lembrar': False}, timeout=10)
    if r.status_code != 200:
        print(f'LOGIN FAIL {perfil}: {r.status_code} {r.text}')
        sys.exit(1)
    print(f'login {perfil} -> OK ({r.json().get("redirect")})')
    return s


def test_super(s):
    label = 'SUPER'
    check('GET', s, '/super/', 200, label)
    check('GET', s, '/super/dashboard', 200, label)
    check('GET', s, '/super/barbearias', 200, label)
    check('GET', s, '/super/gestores', 200, label)
    check('GET', s, '/super/relatorios', 200, label)
    check('GET', s, '/super/features', 200, label)
    check('GET', s, '/super/auditoria', 200, label)
    check('GET', s, '/super/segmentos', 200, label)

    check('GET', s, '/api/v1/super/dashboard', 200, label)
    check('GET', s, '/api/v1/super/barbearias', 200, label)
    check('GET', s, '/api/v1/super/gestores', 200, label)
    check('GET', s, '/api/v1/super/features-metadata', (200, 404), label)
    check('GET', s, '/api/v1/super/auditoria', (200, 404), label)
    check('GET', s, '/api/v1/super/segmentos', (200, 404), label)


def test_gestor(s):
    label = 'GESTOR'
    check('GET', s, '/gestor/', 200, label)
    check('GET', s, '/gestor/dashboard', 200, label)
    check('GET', s, '/gestor/barbeiros', 200, label)
    check('GET', s, '/gestor/servicos', 200, label)
    check('GET', s, '/gestor/produtos', 200, label)
    check('GET', s, '/gestor/agenda', 200, label)
    check('GET', s, '/gestor/clientes', 200, label)
    check('GET', s, '/gestor/cupons', 200, label)
    check('GET', s, '/gestor/relatorios', 200, label)
    check('GET', s, '/gestor/planos', 200, label)
    check('GET', s, '/gestor/vip', 200, label)
    check('GET', s, '/gestor/pix-approval', 200, label)
    check('GET', s, '/gestor/configuracoes/pix', 200, label)

    check('GET', s, '/api/v1/gestor/dashboard', 200, label)
    check('GET', s, '/api/v1/gestor/barbeiros', 200, label)
    check('GET', s, '/api/v1/gestor/servicos', 200, label)
    check('GET', s, '/api/v1/gestor/produtos', 200, label)
    check('GET', s, '/api/v1/gestor/clientes', 200, label)
    check('GET', s, '/api/v1/gestor/cupons', (200, 403), label)  # 403 esperado se feature 'cupons' desativada
    check('GET', s, '/api/v1/gestor/planos', 200, label)
    check('GET', s, '/api/v1/gestor/planos/solicitacoes', 200, label)
    check('GET', s, '/api/v1/gestor/relatorios/agendamentos', 200, label)
    check('GET', s, '/api/v1/gestor/agendamentos', (200, 404), label)
    check('GET', s, '/api/v1/gestor/agenda', (200, 404), label)
    check('GET', s, '/api/v1/gestor/vip', (200, 404), label)
    check('GET', s, '/api/v1/gestor/vip/niveis', (200, 404), label)
    check('GET', s, '/api/v1/gestor/pix/pendentes', (200, 404), label)


def test_barbeiro(s):
    label = 'BARBEIRO'
    check('GET', s, '/barbeiro/', 200, label)
    check('GET', s, '/barbeiro/dashboard', 200, label)
    check('GET', s, '/barbeiro/agendamentos', 200, label)
    check('GET', s, '/barbeiro/horario', 200, label)
    check('GET', s, '/barbeiro/clientes', 200, label)
    check('GET', s, '/barbeiro/agenda', 200, label)
    check('GET', s, '/barbeiro/perfil', 200, label)
    check('GET', s, '/barbeiro/produtos', 200, label)
    check('GET', s, '/barbeiro/configuracoes', 200, label)
    check('GET', s, '/barbeiro/redefinicoes', 200, label)

    check('GET', s, '/api/v1/barbeiro/dashboard', (200, 404), label)
    check('GET', s, '/api/v1/barbeiro/agendamentos', 200, label)
    check('GET', s, '/api/v1/barbeiro/horario', (200, 404), label)
    check('GET', s, '/api/v1/barbeiro/clientes', (200, 404), label)
    check('GET', s, '/api/v1/barbeiro/perfil', (200, 404), label)
    check('GET', s, '/api/v1/barbeiro/produtos', (200, 404), label)


def test_publico_e_cliente():
    label = 'PUBLICO'
    s = requests.Session()
    check('GET', s, '/', (200, 404), label)
    check('GET', s, '/entrar', 200, label)
    check('GET', s, '/b/winner-barbershop', (200, 404), label)
    check('GET', s, '/b/winner-barbershop/entrar', (200, 404), label)
    check('GET', s, '/b/winner-barbershop/cadastro', (200, 404), label)
    check('GET', s, '/b/inexistente-slug', 404, label)


def test_cross_role_denied():
    """Confere que perfis nao acessam areas alheias (403/401/302). Nao segue redirects."""
    label = 'ISOLAMENTO'
    s = login('barbeiro')
    check('GET', s, '/api/v1/gestor/dashboard', (401, 403), label)
    check('GET', s, '/api/v1/super/dashboard', (401, 403), label)
    check('GET', s, '/gestor/dashboard', (302, 401, 403), label, allow_redirects=False)

    s = login('gestor')
    check('GET', s, '/api/v1/super/dashboard', (401, 403), label)
    check('GET', s, '/barbeiro/dashboard', (302, 401, 403), label, allow_redirects=False)


def main():
    s_super = login('super_admin')
    test_super(s_super)

    s_gestor = login('gestor')
    test_gestor(s_gestor)

    s_barbeiro = login('barbeiro')
    test_barbeiro(s_barbeiro)

    test_publico_e_cliente()
    test_cross_role_denied()

    print('\n--- RESULTADOS ---')
    fails = [r for r in results if r[3] not in ('OK',)]
    for label, method, path, status, code in results:
        marker = 'x' if status != 'OK' else ' '
        print(f'[{marker}] {label:10s} {method:6s} {path:50s} -> {status} ({code})')

    print(f'\nTotal: {len(results)}  |  OK: {len(results) - len(fails)}  |  FAIL/EXC: {len(fails)}')
    if fails:
        sys.exit(1)


if __name__ == '__main__':
    main()
