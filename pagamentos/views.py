"""Webhooks dos gateways de pagamento (aprovados apenas via gateway real)."""
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from pagamentos.gateways import obter_gateway

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def webhook_mercadopago(request):
    """Recebe notificações do Mercado Pago e valida contra a API."""
    gateway = obter_gateway()
    if gateway.nome != "mercadopago":
        return JsonResponse({"ok": False, "erro": "Gateway Mercado Pago não configurado."}, status=400)
    resultado = gateway.processar_webhook(request)
    logger.info("Webhook Mercado Pago: %s", resultado)
    status = 200 if resultado.get("ok") else 400
    return JsonResponse(resultado, status=status)


@csrf_exempt
@require_POST
def webhook_stripe(request):
    """Recebe eventos da Stripe com verificação de assinatura."""
    gateway = obter_gateway()
    if gateway.nome != "stripe":
        return JsonResponse({"ok": False, "erro": "Gateway Stripe não configurado."}, status=400)
    resultado = gateway.processar_webhook(request)
    logger.info("Webhook Stripe: %s", resultado)
    status = 200 if resultado.get("ok") else 400
    return JsonResponse(resultado, status=status)
