"""Validadores compartilhados de campos de formulário (CONS-01)."""
from app.exceptions import APIError

SENHA_MIN_CHARS = 8


def validar_senha(senha: str, campo: str = 'senha') -> None:
    """Levanta APIError se `senha` não tiver o mínimo de caracteres exigido.
    Centraliza a política de senha usada em toda criação/troca (cliente,
    gestor, barbeiro, super_admin) — antes cada rota tinha seu próprio
    mínimo (6 ou 8), deixando o perfil com mais acesso a caixa/dados
    (barbeiro) com a política mais fraca."""
    if not senha or len(senha) < SENHA_MIN_CHARS:
        raise APIError(f'"{campo}" deve ter no mínimo {SENHA_MIN_CHARS} caracteres.')
