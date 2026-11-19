"""
Camada abstrata de pagamentos.

Adaptadores reais: Mercado Pago e Stripe (selecionável via PAYMENT_GATEWAY no .env).

REGRA DO PROJETO: nenhuma aprovação é simulada. O status "Pagamento aprovado"
só é aplicado quando o gateway informa, via resposta da API ou webhook assinado,
que a transação foi aprovada. Sem credenciais, o pedido permanece
"Aguardando pagamento" e a interface informa a necessidade de configuração.
"""
import hashlib
import hmac
import json
import logging
from abc import ABC, abstractmethod

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class GatewayError(Exception):
    """Erro de comunicação com o gateway."""


class GatewayNaoConfigurado(Exception):
    """O gateway escolhido não possui credenciais no .env."""


class BaseGateway(ABC):
    """Contrato comum a todos os gateways de pagamento."""

    nome = "base"
    rotulo = "Gateway"

    @classmethod
    def configurado(cls) -> bool:
        raise NotImplementedError

    @abstractmethod
    def iniciar_pagamento(self, pedido, request):
        """
        Cria a cobrança real no gateway.

        Retorna dict:
          ok (bool), mensagem (str), link (str), metodo (str), externo_id (str)
        """

    @abstractmethod
    def processar_webhook(self, request):
        """
        Processa o webhook assinado do gateway.

        Retorna dict: {ok, pedido_numero, status, detalhe}
        """


class NenhumGateway(BaseGateway):
    """Sem gateway configurado: nenhuma aprovação é simulada."""

    nome = "nenhum"
    rotulo = "Gateway não configurado"

    @classmethod
    def configurado(cls):
        return True  # disponível por padrão, mas não realiza cobranças

    def iniciar_pagamento(self, pedido, request):
        return {
            "ok": False,
            "mensagem": (
                "O gateway de pagamento ainda não foi configurado. "
                "Defina PAYMENT_GATEWAY e as credenciais no arquivo .env "
                "(Mercado Pago ou Stripe). Seu pedido foi registrado e "
                "permanece aguardando pagamento."
            ),
            "link": "",
            "metodo": "outro",
            "externo_id": "",
        }

    def processar_webhook(self, request):
        return {"ok": False, "mensagem": "Nenhum gateway configurado."}


class MercadoPagoGateway(BaseGateway):
    """Integração real com o Mercado Pago (PIX e cartão)."""

    nome = "mercadopago"
    rotulo = "Mercado Pago"
    API = "https://api.mercadopago.com"

    @classmethod
    def configurado(cls):
        return bool(settings.MERCADOPAGO_ACCESS_TOKEN)

    @property
    def _headers(self):
        return {
            "Authorization": f"Bearer {settings.MERCADOPAGO_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

    def iniciar_pagamento(self, pedido, request):
        from pagamentos.models import Pagamento

        if not self.configurado():
            raise GatewayNaoConfigurado(
                "MERCADOPAGO_ACCESS_TOKEN não configurado no .env."
            )

        site = _site_url(request)
        preferencia = {
            "items": [
                {
                    "id": item.sku or str(item.pk),
                    "title": item.nome,
                    "quantity": int(item.quantidade),
                    "unit_price": float(item.preco_unitario),
                    "currency_id": "BRL",
                }
                for item in pedido.itens.all()
            ],
            "payer": {"email": pedido.email, "name": pedido.nome},
            "external_reference": pedido.numero,
            "notification_url": f"{site}/webhooks/mercadopago/",
            "back_urls": {
                "success": f"{site}{pedido.get_absolute_url()}",
                "failure": f"{site}{pedido.get_absolute_url()}",
                "pending": f"{site}{pedido.get_absolute_url()}",
            },
            "auto_return": "approved",
        }
        if pedido.desconto and pedido.cupom:
            preferencia["coupons"] = [{"code": pedido.cupom.codigo}]

        try:
            resposta = requests.post(
                f"{self.API}/checkout/preferences",
                headers=self._headers,
                json=preferencia,
                timeout=settings.FRETE_TIMEOUT,
            )
        except requests.RequestException as exc:
            logger.error("Mercado Pago indisponível: %s", exc)
            raise GatewayError(f"Falha ao contatar o Mercado Pago: {exc}") from exc

        if resposta.status_code >= 400:
            detalhe = resposta.text[:500]
            logger.error("Mercado Pago recusou a preferência: %s", detalhe)
            raise GatewayError(f"Mercado Pago retornou erro {resposta.status_code}.")

        dados = resposta.json()
        pagamento = Pagamento.objects.create(
            pedido=pedido,
            gateway=Pagamento.Gateway.MERCADOPAGO,
            metodo=Pagamento.Metodo.OUTRO,
            status=Pagamento.Status.PENDENTE,
            valor=pedido.total,
            externo_id=dados.get("id", ""),
            link_pagamento=dados.get("init_point", ""),
            payload=dados,
        )
        return {
            "ok": True,
            "mensagem": "Cobrança criada no Mercado Pago.",
            "link": dados.get("init_point", ""),
            "metodo": "outro",
            "externo_id": dados.get("id", ""),
            "pagamento": pagamento,
        }

    def processar_webhook(self, request):
        """Webhook do Mercado Pago: consulta a API real para confirmar o status."""
        from pagamentos.models import Pagamento
        from pedidos.models import Pedido, PedidoStatus
        from pedidos.services import alterar_status_pedido

        assinatura = request.headers.get("x-signature", "")
        if settings.MERCADOPAGO_WEBHOOK_SECRET:
            # Com segredo configurado, a assinatura é obrigatória e validada.
            if not assinatura or not self._validar_assinatura(request):
                return {"ok": False, "mensagem": "Assinatura inválida."}

        # O corpo é lido primeiro: depois de request.POST o stream já consumido.
        body = _corpo_json(request)
        payment_id = request.GET.get("data.id") or request.POST.get("data.id")
        if not payment_id:
            payment_id = (body.get("data") or {}).get("id")

        if not payment_id:
            return {"ok": False, "mensagem": "ID do pagamento ausente."}

        try:
            resposta = requests.get(
                f"{self.API}/v1/payments/{payment_id}",
                headers=self._headers,
                timeout=settings.FRETE_TIMEOUT,
            )
            resposta.raise_for_status()
            pagamento_dados = resposta.json()
        except requests.RequestException as exc:
            logger.error("Falha ao consultar pagamento %s: %s", payment_id, exc)
            return {"ok": False, "mensagem": f"Falha na consulta: {exc}"}

        referencia = pagamento_dados.get("external_reference", "")
        status_mp = pagamento_dados.get("status", "")
        logger.info("Webhook MP: pedido %s status %s", referencia, status_mp)

        pedido = Pedido.objects.filter(numero=referencia).first()
        if pedido is None:
            return {"ok": False, "mensagem": "Pedido não encontrado."}

        registro = Pagamento.objects.filter(
            externo_id=str(pagamento_dados.get("id", ""))
        ).first() or Pagamento.objects.filter(pedido=pedido).first()

        status_map = {
            "approved": (Pagamento.Status.APROVADO, PedidoStatus.PAGAMENTO_APROVADO),
            "pending": (Pagamento.Status.PENDENTE, None),
            "in_process": (Pagamento.Status.PENDENTE, None),
            "rejected": (Pagamento.Status.RECUSADO, None),
            "cancelled": (Pagamento.Status.RECUSADO, None),
            "refunded": (Pagamento.Status.ESTORNADO, None),
            "charged_back": (Pagamento.Status.ESTORNADO, None),
        }
        status_pag, status_pedido = status_map.get(
            status_mp, (Pagamento.Status.PENDENTE, None)
        )

        if registro:
            registro.status = status_pag
            metodo = pagamento_dados.get("payment_method_id", "")
            if pagamento_dados.get("payment_type_id") == "account_money" or "pix" in str(metodo).lower():
                registro.metodo = Pagamento.Metodo.PIX
            elif metodo:
                registro.metodo = Pagamento.Metodo.CARTAO
            registro.payload = pagamento_dados
            registro.save(update_fields=["status", "metodo", "payload", "atualizado_em"])

        # Único caminho de aprovação: informação real do gateway.
        if status_pag == Pagamento.Status.APROVADO and status_pedido:
            if pedido.status != status_pedido:
                alterar_status_pedido(
                    pedido, status_pedido,
                    observacao=f"Pagamento aprovado via Mercado Pago (ID {payment_id}).",
                )
        elif status_pag == Pagamento.Status.RECUSADO and registro:
            alterar_status_pedido(
                pedido, PedidoStatus.AGUARDANDO_PAGAMENTO,
                observacao="Pagamento recusado pelo gateway.",
            )

        return {"ok": True, "pedido_numero": referencia, "status": status_mp}

    def _validar_assinatura(self, request):
        """Validação do header x-signature (HMAC-SHA256) quando houver segredo."""
        assinatura = request.headers.get("x-signature", "")
        manifesto = request.GET.get("manifest", "")
        if not assinatura or not manifesto:
            return False
        esperado = hmac.new(
            settings.MERCADOPAGO_WEBHOOK_SECRET.encode(),
            manifesto.encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(esperado, assinatura.split("=")[-1].strip())


class StripeGateway(BaseGateway):
    """Integração real com a Stripe (Checkout Sessions — cartão e PIX)."""

    nome = "stripe"
    rotulo = "Stripe"
    API = "https://api.stripe.com/v1"

    @classmethod
    def configurado(cls):
        return bool(settings.STRIPE_SECRET_KEY)

    @property
    def _headers(self):
        return {
            "Authorization": f"Bearer {settings.STRIPE_SECRET_KEY}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def iniciar_pagamento(self, pedido, request):
        from pagamentos.models import Pagamento

        if not self.configurado():
            raise GatewayNaoConfigurado("STRIPE_SECRET_KEY não configurado no .env.")

        site = _site_url(request)
        dados = {
            "mode": "payment",
            "success_url": f"{site}{pedido.get_absolute_url()}?checkout=success",
            "cancel_url": f"{site}{pedido.get_absolute_url()}?checkout=cancel",
            "customer_email": pedido.email,
            "client_reference_id": pedido.numero,
            "metadata[pedido]": pedido.numero,
        }
        for indice, item in enumerate(pedido.itens.all()):
            dados[f"line_items[{indice}][quantity]"] = str(item.quantidade)
            dados[f"line_items[{indice}][price_data][currency]"] = "BRL"
            dados[f"line_items[{indice}][price_data][unit_amount]"] = str(
                int(round(float(item.preco_unitario) * 100))
            )
            dados[f"line_items[{indice}][price_data][product_data][name]"] = item.nome
        if pedido.frete:
            indice = len(list(pedido.itens.all()))
            dados[f"line_items[{indice}][quantity]"] = "1"
            dados[f"line_items[{indice}][price_data][currency]"] = "BRL"
            dados[f"line_items[{indice}][price_data][unit_amount]"] = str(
                int(round(float(pedido.frete) * 100))
            )
            dados[f"line_items[{indice}][price_data][product_data][name]"] = "Frete"

        try:
            resposta = requests.post(
                f"{self.API}/checkout/sessions",
                headers=self._headers,
                data=dados,
                timeout=settings.FRETE_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise GatewayError(f"Falha ao contatar a Stripe: {exc}") from exc

        if resposta.status_code >= 400:
            logger.error("Stripe recusou a sessão: %s", resposta.text[:500])
            raise GatewayError(f"Stripe retornou erro {resposta.status_code}.")

        sessao = resposta.json()
        pagamento = Pagamento.objects.create(
            pedido=pedido,
            gateway=Pagamento.Gateway.STRIPE,
            metodo=Pagamento.Metodo.CARTAO,
            status=Pagamento.Status.PENDENTE,
            valor=pedido.total,
            externo_id=sessao.get("id", ""),
            link_pagamento=sessao.get("url", ""),
            payload=sessao,
        )
        return {
            "ok": True,
            "mensagem": "Sessão de pagamento criada na Stripe.",
            "link": sessao.get("url", ""),
            "metodo": "cartao",
            "externo_id": sessao.get("id", ""),
            "pagamento": pagamento,
        }

    def processar_webhook(self, request):
        """Webhook da Stripe com verificação de assinatura (HMAC-SHA256)."""
        from pagamentos.models import Pagamento
        from pedidos.models import Pedido, PedidoStatus
        from pedidos.services import alterar_status_pedido

        if not settings.STRIPE_WEBHOOK_SECRET:
            return {"ok": False, "mensagem": "STRIPE_WEBHOOK_SECRET não configurado."}

        assinatura = request.headers.get("Stripe-Signature", "")
        corpo = request.body
        if not _validar_stripe(assinatura, corpo, settings.STRIPE_WEBHOOK_SECRET):
            return {"ok": False, "mensagem": "Assinatura do webhook inválida."}

        try:
            evento = json.loads(corpo.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {"ok": False, "mensagem": "Payload inválido."}

        tipo = evento.get("type", "")
        objeto = evento.get("data", {}).get("object", {})
        referencia = objeto.get("client_reference_id") or objeto.get("metadata", {}).get("pedido", "")

        if tipo in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            pedido = Pedido.objects.filter(numero=referencia).first()
            if pedido is None:
                return {"ok": False, "mensagem": "Pedido não encontrado."}
            pagamento = Pagamento.objects.filter(externo_id=objeto.get("id", "")).first()
            if pagamento:
                pagamento.status = Pagamento.Status.APROVADO
                pagamento.payload = objeto
                pagamento.save(update_fields=["status", "payload", "atualizado_em"])
            if pedido.status != PedidoStatus.PAGAMENTO_APROVADO:
                alterar_status_pedido(
                    pedido, PedidoStatus.PAGAMENTO_APROVADO,
                    observacao=f"Pagamento aprovado via Stripe ({tipo}).",
                )
            return {"ok": True, "pedido_numero": referencia, "status": "approved"}

        if tipo == "checkout.session.expired":
            pedido = Pedido.objects.filter(numero=referencia).first()
            if pedido:
                Pagamento.objects.filter(
                    externo_id=objeto.get("id", "")
                ).update(status=Pagamento.Status.EXPIRADO)
            return {"ok": True, "pedido_numero": referencia, "status": "expired"}

        return {"ok": True, "mensagem": f"Evento {tipo} recebido e ignorado."}


def _validar_stripe(assinatura_header, corpo, segredo):
    """Validação de assinatura no formato Stripe: t=...,v1=..."""
    try:
        elementos = dict(
            par.split("=", 1) for par in assinatura_header.split(",") if "=" in par
        )
        timestamp = elementos["t"]
        assinatura_recebida = elementos["v1"]
    except (KeyError, ValueError):
        return False

    if isinstance(corpo, bytes):
        corpo_texto = corpo.decode("utf-8", errors="replace")
    else:
        corpo_texto = str(corpo)
    manifesto = f"{timestamp}.{corpo_texto}"
    esperado = hmac.new(segredo.encode(), manifesto.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, assinatura_recebida)


def _site_url(request):
    if request is not None and request.build_absolute_uri:
        try:
            base = request.build_absolute_uri("/")
            return str(base).rstrip("/")
        except Exception:  # noqa: BLE001
            pass
    return settings.SITE_URL


def _corpo_json(request):
    try:
        return json.loads(request.body.decode("utf-8")) or {}
    except (ValueError, UnicodeDecodeError, AttributeError):
        return {}


def obter_gateway():
    """Retorna a instância do gateway configurado em PAYMENT_GATEWAY."""
    nome = getattr(settings, "PAYMENT_GATEWAY", "none").lower()
    mapa = {
        "mercadopago": MercadoPagoGateway,
        "mp": MercadoPagoGateway,
        "stripe": StripeGateway,
    }
    classe = mapa.get(nome, NenhumGateway)
    return classe()


def gateway_atual_info():
    """Informações do gateway para exibição na interface."""
    gateway = obter_gateway()
    configurado = gateway.configurado() and gateway.nome != "nenhum"
    return {
        "nome": gateway.nome,
        "rotulo": gateway.rotulo,
        "configurado": configurado,
        "aceita_pix": configurado,
        "aceita_cartao": configurado,
    }
