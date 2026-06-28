import re

_PIX_ACENTOS = str.maketrans(
    'áàâãäéèêëíìîïóòôõöúùûüçñÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ',
    'aaaaaeeeeiiiiooooouuuucnAAAAAEEEEIIIIOOOOOUUUUCN',
)


def _sanitizar(texto, tamanho_max):
    texto = (texto or '').translate(_PIX_ACENTOS)
    texto = re.sub(r'[^A-Za-z0-9 ]', '', texto).strip().upper()
    return texto[:tamanho_max]


def _crc16(payload: str) -> str:
    """CRC16-CCITT (poly 0x1021, init 0xFFFF) — exigido pelo padrão BR Code do Pix."""
    crc = 0xFFFF
    for byte in payload.encode('utf-8'):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f'{crc:04X}'


def _campo(id_, valor):
    valor = str(valor)
    return f'{id_}{len(valor):02d}{valor}'


def gerar_pix_copia_cola(chave, nome_titular, cidade, valor=None, txid=None):
    """Gera o payload EMV/BR Code ('Pix Copia e Cola') com valor opcional embutido.
    Não gera QR Code — apenas o texto que o app do banco reconhece ao colar."""
    chave = (chave or '').strip()
    if not chave:
        raise ValueError('chave_pix é obrigatória para gerar o código Pix.')

    nome = _sanitizar(nome_titular, 25) or 'NA'
    cid  = _sanitizar(cidade, 15) or 'NA'
    tx   = re.sub(r'[^A-Za-z0-9]', '', (txid or '')).strip()[:25] or '***'

    conta_pix = _campo('00', 'BR.GOV.BCB.PIX') + _campo('01', chave)

    payload = (
        _campo('00', '01') +
        _campo('26', conta_pix) +
        _campo('52', '0000') +
        _campo('53', '986')
    )
    if valor is not None:
        payload += _campo('54', f'{float(valor):.2f}')
    payload += (
        _campo('58', 'BR') +
        _campo('59', nome) +
        _campo('60', cid) +
        _campo('62', _campo('05', tx))
    )

    payload += '6304'
    return payload + _crc16(payload)
