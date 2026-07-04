"""
Revogação de tokens JWT.

Bloco 1.2 — dois mecanismos complementares:
  - TokenRevogado: blacklist de jti individuais (logout de uma sessão).
  - Usuario.token_valido_apos: revogação em massa (todo token emitido antes
    desse timestamp deixa de ser aceito), usada quando o usuário é desativado,
    troca a senha, ou a barbearia inteira é desativada.
"""
from datetime import datetime, timezone


def revogar_todos_tokens(usuario, motivo: str) -> None:
    """Invalida (em massa) todos os JWTs já emitidos para este usuário.

    Não precisa conhecer os jtis emitidos: qualquer token com `iat` anterior
    a `token_valido_apos` passa a ser rejeitado em app/context.py.
    Não dá commit — quem chama decide o momento do commit.
    """
    usuario.token_valido_apos = datetime.now(timezone.utc)
