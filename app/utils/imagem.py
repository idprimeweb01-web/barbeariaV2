"""
Validação de upload de imagem (magic bytes) — Script 18.

Mesmo padrão já usado em pub/agendamento.py (comprovante PIX) e
super/barbearias.py (customização), extraído aqui para o novo upload de
foto de produto reaproveitar sem duplicar pela 3ª vez. Os dois usos
antigos não foram tocados (fora do escopo deste bloco).
"""
from app.exceptions import APIError

TIPOS_IMAGEM_VALIDOS = {'image/jpeg', 'image/jpg', 'image/png', 'image/webp'}
MAX_BYTES_IMAGEM = 5 * 1024 * 1024  # 5 MB


def validar_magic_bytes_imagem(arq):
    arq.stream.seek(0)
    header = arq.stream.read(12)
    arq.stream.seek(0)
    e_jpeg = header[:3] == b'\xff\xd8\xff'
    e_png  = header[:8] == b'\x89PNG\r\n\x1a\n'
    e_webp = header[:4] == b'RIFF' and header[8:12] == b'WEBP'
    if not (e_jpeg or e_png or e_webp):
        raise APIError('Arquivo não é JPG, PNG ou WebP válido.', 400)


def validar_upload_imagem(arq):
    """Validação completa (mimetype + tamanho + magic bytes) — chamar antes do upload."""
    if not arq or not arq.filename:
        raise APIError('Nenhum arquivo enviado.')
    if arq.mimetype not in TIPOS_IMAGEM_VALIDOS:
        raise APIError('Tipo não permitido. Use JPG, PNG ou WebP.')
    arq.seek(0, 2)
    if arq.tell() > MAX_BYTES_IMAGEM:
        raise APIError('Arquivo muito grande. Máximo 5 MB.')
    arq.seek(0)
    validar_magic_bytes_imagem(arq)
