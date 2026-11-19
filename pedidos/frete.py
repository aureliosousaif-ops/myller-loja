"""
Cálculo de frete com camada preparada para APIs de entrega.

Backends:
  - tabela:      fallback sem credenciais, usa os valores das Configurações da Loja.
  - melhorenvio: integração preparada (requer MELHOR_ENVIO_TOKEN no .env).
  - correios:    integração preparada (requer contrato e senha no .env).

O backend é escolhido pela variável de ambiente FRETE_BACKEND.
Quando a API não está configurada, o sistema usa a tabela da loja e
identifica o valor como "estimativa" — nada é apresentado como cotação real.
"""
import logging
import os
from decimal import Decimal

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class FreteError(Exception):
    pass


def _peso_total(carrinho_ou_itens):
    itens = getattr(carrinho_ou_itens, "itens", None)
    if itens is None:
        itens = carrinho_ou_itens
    elif hasattr(itens, "all"):  # RelatedManager do Django
        itens = itens.all()
    peso = Decimal("0.00")
    for item in itens:
        produto = getattr(item.variacao, "produto", None)
        if produto and produto.peso_kg:
            peso += produto.peso_kg * item.quantidade
    return peso or Decimal("0.50")


def calcular_frete(carrinho, cep_destino):
    """
    Calcula o frete para o carrinho.

    Retorna dict: {valor, prazo, transportadora, origem, estimativa, mensagem}
    origem: 'api' (cotação real) ou 'tabela' (estimativa).
    """
    if not cep_destino or len("".join(ch for ch in str(cep_destino) if ch.isdigit())) != 8:
        return {
            "valor": Decimal("0.00"),
            "prazo": "",
            "transportadora": "",
            "origem": "invalido",
            "estimativa": True,
            "mensagem": "Informe um CEP válido com 8 dígitos.",
        }

    cep = "".join(ch for ch in str(cep_destino) if ch.isdigit())
    peso = _peso_total(carrinho)

    backend = getattr(settings, "FRETE_BACKEND", "tabela")
    if backend == "melhorenvio" and settings.MELHOR_ENVIO_TOKEN:
        try:
            return _cotar_melhor_envio(cep, peso, carrinho)
        except Exception as exc:  # noqa: BLE001 — degrada para tabela em falha de API
            logger.warning("Melhor Envio indisponível, usando tabela: %s", exc)
    elif backend == "correios" and settings.CORREIOS_CONTRATO:
        try:
            return _cotar_correios(cep, peso)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Correios indisponível, usando tabela: %s", exc)

    return _tabela(carrinho, cep, peso)


def _tabela(carrinho, cep, peso):
    """Fallback: frete configurado nas Configurações da Loja."""
    from core.models import ConfiguracaoLoja

    loja = ConfiguracaoLoja.carregar()
    subtotal = carrinho.subtotal

    if loja.frete_gratis_acima and subtotal >= Decimal(str(loja.frete_gratis_acima)):
        return {
            "valor": Decimal("0.00"),
            "prazo": f"{loja.frete_prazo_dias} dias úteis",
            "transportadora": "Frete grátis",
            "origem": "tabela",
            "estimativa": True,
            "mensagem": "Frete grátis para esta compra.",
        }

    quilos_excedentes = max(int(peso - 1), 0)
    valor = Decimal(str(loja.frete_valor_base)) + (
        Decimal(str(loja.frete_por_kg)) * quilos_excedentes
    )

    return {
        "valor": valor.quantize(Decimal("0.01")),
        "prazo": f"{loja.frete_prazo_dias} dias úteis",
        "transportadora": "Entrega estimada",
        "origem": "tabela",
        "estimativa": True,
        "mensagem": loja.prazo_estimado_observacao,
    }


def _cotar_melhor_envio(cep, peso, carrinho):
    """Cotação real via Melhor Envio (requer MELHOR_ENVIO_TOKEN)."""
    loja_cep = "01310100"  # CEP de origem padrão (ajustável no .env)
    origem = "".join(ch for ch in os.getenv("FRETE_CEP_ORIGEM", loja_cep) if ch.isdigit())

    resposta = requests.post(
        "https://api.melhorenvio.com.br/me/shipment/quote",
        headers={
            "Authorization": f"Bearer {settings.MELHOR_ENVIO_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "from": {"postal_code": origem},
            "to": {"postal_code": cep},
            "products": [
                {
                    "id": str(item.variacao_id),
                    "width": 20,
                    "height": 15,
                    "length": 5,
                    "weight": float(item.variacao.produto.peso_kg or 0.5),
                    "insurance_value": float(item.total),
                    "quantity": item.quantidade,
                }
                for item in carrinho.itens.all()
            ],
        },
        timeout=settings.FRETE_TIMEOUT,
    )
    resposta.raise_for_status()
    dados = resposta.json()
    servico = dados[0] if isinstance(dados, list) and dados else dados

    return {
        "valor": Decimal(str(servico.get("price", 0))),
        "prazo": f"{servico.get('delivery_time', 0)} dias úteis",
        "transportadora": servico.get("company", {}).get("name", "Melhor Envio"),
        "origem": "api",
        "estimativa": False,
        "mensagem": "Cotação em tempo real.",
    }


def _cotar_correios(cep, peso):
    """Cotação real via API dos Correios (contrato)."""
    resposta = requests.post(
        "http://ws.correios.com.br/calculador/PrecoPrazo/v1/CalcularPrazo",
        headers={"Content-Type": "application/json"},
        json={
            "sCepOrigem": "".join(ch for ch in os.getenv("FRETE_CEP_ORIGEM", "01310100") if ch.isdigit()),
            "sCepDestino": cep,
            "nVlPeso": float(peso),
            "nVlLargura": 20,
            "nVlAltura": 15,
            "nVlComprimento": 25,
            "sCdServico": ["04010", "04510"],  # PAC e SEDEX
            "nVlValorDeclarado": 0,
            "CdEmpresa": settings.CORREIOS_CONTRATO,
            "sDsSenha": settings.CORREIOS_SENHA,
        },
        timeout=settings.FRETE_TIMEOUT,
    )
    resposta.raise_for_status()
    dados = resposta.json()
    servicos = dados.get("Servicos", {}).get("cServico", [])
    if not servicos:
        raise FreteError("Nenhum serviço disponível para o CEP informado.")
    servico = servicos[0]

    return {
        "valor": Decimal(str(servico.get("Valor", "0").replace(",", "."))),
        "prazo": f"{servico.get('PrazoEntrega', 0)} dias úteis",
        "transportadora": servico.get("DsServico", "Correios"),
        "origem": "api",
        "estimativa": False,
        "mensagem": "Cotação em tempo real.",
    }
