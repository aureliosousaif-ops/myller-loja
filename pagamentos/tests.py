"""Testes do app pagamentos: seleção de gateway e webhooks assinados."""
import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from myller.utilitarios_teste import criar_produto, dados_checkout, primeira_variacao
from pagamentos.gateways import (
    MercadoPagoGateway,
    NenhumGateway,
    StripeGateway,
    gateway_atual_info,
    obter_gateway,
)
from pagamentos.models import Pagamento
from carrinho.models import Carrinho, CarrinhoItem
from pedidos.models import Pedido, PedidoStatus
from pedidos.services import criar_pedido


def _pedido(status=PedidoStatus.AGUARDANDO_PAGAMENTO, numero="MYL-PGTO-1"):
    produto = criar_produto(nome="Camiseta", preco="100.00", estoque=10)
    variacao = primeira_variacao(produto)
    carrinho = Carrinho.objects.create(chave_sessao=f"sessao-{numero}")
    CarrinhoItem.objects.create(
        carrinho=carrinho, variacao=variacao,
        preco_unitario=Decimal("100.00"), quantidade=1,
    )
    pedido, erro = criar_pedido(
        carrinho=carrinho,
        dados=dados_checkout(
            subtotal=Decimal("100.00"), frete=Decimal("0.00"),
            desconto=Decimal("0.00"), total=Decimal("100.00"),
        ),
    )
    assert erro is None, erro
    if status != PedidoStatus.AGUARDANDO_PAGAMENTO:
        pedido.status = status
        pedido.save(update_fields=["status"])
    return pedido


class SelecaoDeGatewayTests(TestCase):
    @override_settings(PAYMENT_GATEWAY="none")
    def test_padrao_e_o_gateway_nenhum(self):
        self.assertIsInstance(obter_gateway(), NenhumGateway)

    @override_settings(PAYMENT_GATEWAY="mercadopago")
    def test_selecao_do_mercado_pago(self):
        self.assertIsInstance(obter_gateway(), MercadoPagoGateway)

    @override_settings(PAYMENT_GATEWAY="stripe")
    def test_selecao_da_stripe(self):
        self.assertIsInstance(obter_gateway(), StripeGateway)

    @override_settings(PAYMENT_GATEWAY="desconhecido")
    def test_gateway_desconhecido_cai_para_nenhum(self):
        self.assertIsInstance(obter_gateway(), NenhumGateway)

    @override_settings(PAYMENT_GATEWAY="mercadopago", MERCADOPAGO_ACCESS_TOKEN="")
    def test_mercado_pago_sem_token_nao_esta_configurado(self):
        self.assertFalse(MercadoPagoGateway.configurado())
        info = gateway_atual_info()
        self.assertFalse(info["configurado"])

    @override_settings(PAYMENT_GATEWAY="stripe", STRIPE_SECRET_KEY="")
    def test_stripe_sem_chave_nao_esta_configurado(self):
        self.assertFalse(StripeGateway.configurado())

    @override_settings(
        PAYMENT_GATEWAY="mercadopago", MERCADOPAGO_ACCESS_TOKEN="TESTE-123"
    )
    def test_mercado_pago_com_token_esta_configurado(self):
        self.assertTrue(MercadoPagoGateway.configurado())
        self.assertTrue(gateway_atual_info()["configurado"])


class NenhumGatewayTests(TestCase):
    @override_settings(PAYMENT_GATEWAY="none")
    def test_nunca_retorna_link_de_pagamento(self):
        pedido = _pedido()
        gateway = obter_gateway()
        request = RequestFactory().get("/")
        resultado = gateway.iniciar_pagamento(pedido, request)
        self.assertFalse(resultado["ok"])
        self.assertEqual(resultado["link"], "")

    @override_settings(PAYMENT_GATEWAY="none")
    def test_pedido_permanece_aguardando_pagamento(self):
        pedido = _pedido()
        gateway = obter_gateway()
        request = RequestFactory().get("/")
        gateway.iniciar_pagamento(pedido, request)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, PedidoStatus.AGUARDANDO_PAGAMENTO)
        self.assertEqual(Pagamento.objects.count(), 0)

    @override_settings(PAYMENT_GATEWAY="none")
    def test_webhook_nao_aprova_nada(self):
        request = RequestFactory().post(
            reverse("pagamentos:webhook_mercadopago"), {}
        )
        resultado = NenhumGateway().processar_webhook(request)
        self.assertFalse(resultado["ok"])


@override_settings(
    PAYMENT_GATEWAY="stripe", STRIPE_WEBHOOK_SECRET="whsec_segredo_teste"
)
class WebhookStripeTests(TestCase):
    def _assinatura(self, corpo, segredo="whsec_segredo_teste", timestamp=1700000000):
        manifesto = f"{timestamp}.{corpo}"
        valor = hmac.new(
            segredo.encode(), manifesto.encode(), hashlib.sha256
        ).hexdigest()
        return f"t={timestamp},v1={valor}"

    def _evento(self, pedido, tipo="checkout.session.completed"):
        return json.dumps(
            {
                "type": tipo,
                "data": {
                    "object": {
                        "id": "cs_teste_123",
                        "client_reference_id": pedido.numero,
                        "metadata": {"pedido": pedido.numero},
                    }
                },
            }
        )

    def test_assinatura_invalida_retorna_400_sem_aprovar(self):
        pedido = _pedido()
        corpo = self._evento(pedido)
        resposta = self.client.post(
            reverse("pagamentos:webhook_stripe"),
            data=corpo,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1700000000,v1=assinatura-errada",
        )
        self.assertEqual(resposta.status_code, 400)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, PedidoStatus.AGUARDANDO_PAGAMENTO)

    def test_sem_assinatura_retorna_400(self):
        pedido = _pedido()
        resposta = self.client.post(
            reverse("pagamentos:webhook_stripe"),
            data=self._evento(pedido),
            content_type="application/json",
        )
        self.assertEqual(resposta.status_code, 400)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, PedidoStatus.AGUARDANDO_PAGAMENTO)

    def test_assinatura_valida_aprova_o_pedido(self):
        pedido = _pedido()
        Pagamento.objects.create(
            pedido=pedido, gateway="stripe", metodo="cartao",
            status=Pagamento.Status.PENDENTE, valor=pedido.total,
            externo_id="cs_teste_123",
        )
        corpo = self._evento(pedido)
        resposta = self.client.post(
            reverse("pagamentos:webhook_stripe"),
            data=corpo,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=self._assinatura(corpo),
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["status"], "approved")

        pedido.refresh_from_db()
        self.assertEqual(pedido.status, PedidoStatus.PAGAMENTO_APROVADO)
        pagamento = Pagamento.objects.get()
        self.assertEqual(pagamento.status, Pagamento.Status.APROVADO)
        # histórico registrado
        self.assertTrue(
            pedido.historico.filter(status=PedidoStatus.PAGAMENTO_APROVADO).exists()
        )

    def test_evento_de_expiracao_nao_aprova(self):
        pedido = _pedido()
        corpo = self._evento(pedido, tipo="checkout.session.expired")
        resposta = self.client.post(
            reverse("pagamentos:webhook_stripe"),
            data=corpo,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=self._assinatura(corpo),
        )
        self.assertEqual(resposta.status_code, 200)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, PedidoStatus.AGUARDANDO_PAGAMENTO)

    def test_evento_desconhecido_e_ignorado(self):
        pedido = _pedido()
        corpo = self._evento(pedido, tipo="invoice.paid")
        resposta = self.client.post(
            reverse("pagamentos:webhook_stripe"),
            data=corpo,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=self._assinatura(corpo),
        )
        self.assertEqual(resposta.status_code, 200)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, PedidoStatus.AGUARDANDO_PAGAMENTO)


@override_settings(
    PAYMENT_GATEWAY="mercadopago",
    MERCADOPAGO_ACCESS_TOKEN="TESTE-TOKEN",
    MERCADOPAGO_WEBHOOK_SECRET="",
)
class WebhookMercadoPagoTests(TestCase):
    def _resposta_api(self, dados):
        resposta = MagicMock()
        resposta.status_code = 200
        resposta.json.return_value = dados
        resposta.raise_for_status.return_value = None
        return resposta

    def test_webhook_sem_gateway_mercado_pago_retorna_400(self):
        with override_settings(PAYMENT_GATEWAY="none"):
            resposta = self.client.post(
                reverse("pagamentos:webhook_mercadopago"), {"data.id": "1"}
            )
        self.assertEqual(resposta.status_code, 400)

    @patch("pagamentos.gateways.requests.get")
    def test_pagamento_aprovado_na_api_aprova_o_pedido(self, mock_get):
        pedido = _pedido()
        Pagamento.objects.create(
            pedido=pedido, gateway="mercadopago", metodo="outro",
            status=Pagamento.Status.PENDENTE, valor=pedido.total,
            externo_id="12345",
        )
        mock_get.return_value = self._resposta_api({
            "id": "12345",
            "status": "approved",
            "external_reference": pedido.numero,
            "payment_method_id": "pix",
            "payment_type_id": "account_money",
        })

        resposta = self.client.post(
            reverse("pagamentos:webhook_mercadopago") + "?data.id=12345"
        )
        self.assertEqual(resposta.status_code, 200)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, PedidoStatus.PAGAMENTO_APROVADO)
        Pagamento.objects.get().refresh_from_db()
        self.assertEqual(Pagamento.objects.get().status, Pagamento.Status.APROVADO)

    @patch("pagamentos.gateways.requests.get")
    def test_pagamento_pendente_nao_altera_o_pedido(self, mock_get):
        pedido = _pedido()
        mock_get.return_value = self._resposta_api({
            "id": "999",
            "status": "pending",
            "external_reference": pedido.numero,
            "payment_method_id": "visa",
            "payment_type_id": "credit_card",
        })
        resposta = self.client.post(
            reverse("pagamentos:webhook_mercadopago") + "?data.id=999"
        )
        self.assertEqual(resposta.status_code, 200)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, PedidoStatus.AGUARDANDO_PAGAMENTO)

    @patch("pagamentos.gateways.requests.get")
    def test_pagamento_recusado_mantem_aguardando(self, mock_get):
        pedido = _pedido()
        Pagamento.objects.create(
            pedido=pedido, gateway="mercadopago", metodo="cartao",
            status=Pagamento.Status.PENDENTE, valor=pedido.total,
            externo_id="555",
        )
        mock_get.return_value = self._resposta_api({
            "id": "555",
            "status": "rejected",
            "external_reference": pedido.numero,
            "payment_method_id": "visa",
            "payment_type_id": "credit_card",
        })
        self.client.post(reverse("pagamentos:webhook_mercadopago") + "?data.id=555")
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, PedidoStatus.AGUARDANDO_PAGAMENTO)

    def test_sem_id_de_pagamento_retorna_400(self):
        resposta = self.client.post(reverse("pagamentos:webhook_mercadopago"))
        self.assertEqual(resposta.status_code, 400)


@override_settings(
    PAYMENT_GATEWAY="mercadopago",
    MERCADOPAGO_ACCESS_TOKEN="TESTE-TOKEN",
    MERCADOPAGO_WEBHOOK_SECRET="super-segredo",
)
class AssinaturaMercadoPagoTests(TestCase):
    def _assinatura(self, manifesto, segredo="super-segredo"):
        return hmac.new(
            segredo.encode(), manifesto.encode(), hashlib.sha256
        ).hexdigest()

    @patch("pagamentos.gateways.requests.get")
    def test_assinatura_invalida_e_rejeitada(self, mock_get):
        pedido = _pedido()
        resposta = self.client.post(
            reverse("pagamentos:webhook_mercadopago") + "?data.id=1&manifest=abc",
            HTTP_X_SIGNATURE="v1=assinatura-errada",
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("Assinatura", resposta.json()["mensagem"])
        mock_get.assert_not_called()
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, PedidoStatus.AGUARDANDO_PAGAMENTO)

    @patch("pagamentos.gateways.requests.get")
    def test_sem_assinatura_com_secreto_configurado_e_rejeitado(self, mock_get):
        pedido = _pedido()
        resposta = self.client.post(
            reverse("pagamentos:webhook_mercadopago") + "?data.id=1"
        )
        self.assertEqual(resposta.status_code, 400)
        mock_get.assert_not_called()
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, PedidoStatus.AGUARDANDO_PAGAMENTO)

    @patch("pagamentos.gateways.requests.get")
    def test_assinatura_valida_permite_consulta_na_api(self, mock_get):
        pedido = _pedido()
        # o Mercado Pago assina o valor do parâmetro `manifest`
        manifesto = "data.id=1"
        corpo = MagicMock()
        corpo.status_code = 200
        corpo.json.return_value = {
            "id": "1",
            "status": "pending",
            "external_reference": pedido.numero,
            "payment_method_id": "pix",
        }
        corpo.raise_for_status.return_value = None
        mock_get.return_value = corpo

        resposta = self.client.post(
            reverse("pagamentos:webhook_mercadopago")
            + f"?data.id=1&manifest={manifesto}",
            HTTP_X_SIGNATURE=f"v1={self._assinatura(manifesto)}",
        )
        self.assertEqual(resposta.status_code, 200)
        mock_get.assert_called_once()
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, PedidoStatus.AGUARDANDO_PAGAMENTO)
