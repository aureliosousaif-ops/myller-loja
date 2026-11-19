"""Serviços externos do núcleo (ViaCEP etc.)."""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def buscar_cep(cep):
    """Consulta o ViaCEP e normaliza o retorno. Retorna dict ou None."""
    try:
        resposta = requests.get(
            f"{settings.VIA_CEP_URL}/{cep}/json/",
            timeout=settings.FRETE_TIMEOUT,
        )
        if resposta.status_code != 200:
            return None
        dados = resposta.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("ViaCEP indisponível: %s", exc)
        return None

    if dados.get("erro"):
        return None

    return {
        "cep": dados.get("cep", ""),
        "logradouro": dados.get("logradouro", ""),
        "complemento": dados.get("complemento", ""),
        "bairro": dados.get("bairro", ""),
        "cidade": dados.get("localidade", ""),
        "estado": dados.get("uf", ""),
    }
