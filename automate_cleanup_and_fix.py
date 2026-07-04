"""
Fase 1.1 — Remover código morto V1.

Baseado em ANALISE_ARQUITETURA_V1_V2.txt e docs/Roadmap.md.
Remove apenas o que está 100% confirmado como morto (sem import vivo,
sem render_template vivo). NÃO remove caixa.py/vip.py nem os templates
"híbridos" (rota viva mas JS legado) — esses dependem de decisão de
produto registrada em docs/Roadmap.md.

Roda em modo dry-run por padrão. Use --apply para executar de verdade.
"""
import argparse
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

DEAD_ROUTES = [
    "app/routes/agenda.py",
    "app/routes/auditoria.py",
    "app/routes/catalogo.py",
    "app/routes/cliente_perfil.py",
    "app/routes/clientes.py",
    "app/routes/customizacao.py",
    "app/routes/features.py",
    "app/routes/gestor_admin.py",
    "app/routes/planos.py",
    "app/routes/publica.py",
    "app/routes/relatorios.py",
    "app/routes/super_admin.py",
    "app/routes/upload.py",
]

ORPHAN_TEMPLATES = [
    "app/templates/cliente/login.html",
    "app/templates/cliente/checkout_pix.html",
    "app/templates/cliente/checkout_plano.html",
    "app/templates/cliente/comprar_plano.html",
    "app/templates/cliente/meu_plano.html",
    "app/templates/cliente/vip_status.html",
    "app/templates/staff/placeholder.html",
    "app/templates/super/em_construcao.html",
]

LEGACY_JS = [
    "app/static/js/api.js",
    "app/static/js/upload-widget.js",
]

# Mantidos de propósito — ver docs/Roadmap.md "decisão em aberto":
HELD_BACK = [
    "app/routes/caixa.py   (PDV/checkout — sem equivalente V2)",
    "app/routes/vip.py     (CRUD de níveis VIP pelo gestor — sem equivalente V2)",
]

ALL_TARGETS = DEAD_ROUTES + ORPHAN_TEMPLATES + LEGACY_JS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="executa a remoção de verdade")
    args = parser.parse_args()

    print("=== Fase 1.1 — Remover código morto V1 ===\n")

    removed, missing = [], []
    for rel in ALL_TARGETS:
        path = os.path.join(ROOT, rel)
        if os.path.exists(path):
            removed.append(rel)
        else:
            missing.append(rel)

    print(f"Arquivos a remover ({len(removed)}):")
    for r in removed:
        print(f"  - {r}")

    if missing:
        print(f"\nAVISO — não encontrados (já removidos antes?) ({len(missing)}):")
        for m in missing:
            print(f"  - {m}")

    print(f"\nMantidos de propósito (decisão de produto pendente):")
    for h in HELD_BACK:
        print(f"  - {h}")

    if not args.apply:
        print("\n[dry-run] Nenhum arquivo foi removido. Rode com --apply para executar.")
        return

    for rel in removed:
        os.remove(os.path.join(ROOT, rel))

    print(f"\n{len(removed)} arquivo(s) removido(s).")


if __name__ == "__main__":
    main()
