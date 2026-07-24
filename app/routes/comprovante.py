"""
Serve comprovantes PIX através de um token temporário assinado — nunca pela
URL real do Cloudinary (essas são previsíveis: ag_{id}.png, plano_sol_{id}.png,
e ficam publicamente acessíveis por padrão). Ver app/utils/comprovante_link.py
para como o token é gerado (só acontece dentro de rotas autenticadas que já
validam que o usuário tem acesso àquele agendamento/solicitação).
"""
import requests
from flask import Blueprint, Response, abort
from app.models import (
    AgendamentoSolicitacaoPix, ClientePlanoSolicitacao, SolicitacaoCompraProduto,
    ClienteDuvidaMensagemImagem,
)
from app.utils.comprovante_link import decodificar_token_comprovante

comprovante_bp = Blueprint('comprovante', __name__)

# Cada entrada: (função de busca, nome do atributo que guarda a URL real no
# Cloudinary) — a maioria usa "comprovante_url", mas ClienteDuvidaMensagemImagem
# usa "imagem_url" (não é um comprovante de pagamento, é um anexo de chat).
_BUSCA_POR_TIPO = {
    'agendamento': (
        lambda ref_id, barbearia_id: (
            AgendamentoSolicitacaoPix.query
            .filter_by(agendamento_id=ref_id, barbearia_id=barbearia_id)
            .first()
        ),
        'comprovante_url',
    ),
    'plano': (
        lambda ref_id, barbearia_id: (
            ClientePlanoSolicitacao.query
            .filter_by(id=ref_id, barbearia_id=barbearia_id)
            .first()
        ),
        'comprovante_url',
    ),
    'compra': (
        lambda ref_id, barbearia_id: (
            SolicitacaoCompraProduto.query
            .filter_by(id=ref_id, barbearia_id=barbearia_id)
            .first()
        ),
        'comprovante_url',
    ),
    # ref_id aqui é o id da IMAGEM (ClienteDuvidaMensagemImagem), não da
    # mensagem — uma mensagem pode ter até 3, cada uma com seu próprio link.
    'duvida_msg': (
        lambda ref_id, barbearia_id: (
            ClienteDuvidaMensagemImagem.query
            .filter_by(id=ref_id, barbearia_id=barbearia_id)
            .first()
        ),
        'imagem_url',
    ),
}


@comprovante_bp.get('/comprovante/<token>')
def servir_comprovante(token):
    try:
        payload = decodificar_token_comprovante(token)
    except ValueError:
        abort(410)  # link expirado — cliente/gestor precisa reabrir a tela pra gerar outro

    entrada = _BUSCA_POR_TIPO.get(payload.get('tipo'))
    if not entrada:
        abort(404)
    buscar, url_attr = entrada
    registro = buscar(payload['ref_id'], payload['barbearia_id'])
    url = getattr(registro, url_attr, None) if registro else None
    if not registro or not url:
        abort(404)

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        abort(502)

    return Response(
        resp.content,
        mimetype=resp.headers.get('Content-Type', 'image/png'),
        headers={'Cache-Control': 'private, max-age=0, no-store'},
    )
