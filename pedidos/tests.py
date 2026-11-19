"""Testes do app pedidos: checkout, totais, acompanhamento e cancelamento."""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from carrinho.models import Carrinho, CarrinhoItem
from estoque.models import MovimentoEstoque
from myller.utilitarios_teste import (
    criar_cliente,
    criar_produto,
    criar_usuario,
    dados_checkout,
    primeira_variacao,
)
from pedidos.models import HistoricoStatus, Pedido, PedidoStatus
from pedidos.services import alterar_status_pedido, calcular_totais_pedido, criar_pedido

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class TotaisPedidoTests(TestCase):
    def test_totais_sem_cupom(self):
        totais = calcular_totais_pedido(
            subtotal=Decimal("250.00"), frete=Decimal("19.90")
        )
        self.assertEqual(totais["desconto"], Decimal("0.00"))
        self.assertEqual(totais["total"], Decimal("269.90"))

    def test_totais_com_cupom_percentual(self):
        from pedidos.models import CupomDesconto

        CupomDesconto.objects.create(
            codigo="ONZE", tipo="percentual", valor=10, ativo=True
        )
        totais = calcular_totais_pedido(
            subtotal=Decimal("200.00"), codigo_cupom="ONZE"
        )
        self.assertEqual(totais["desconto"], Decimal("20.00"))
        self.assertEqual(totais["total"], Decimal("180.00"))

    def test_totais_com_cupom_fixo(self):
        from pedidos.models import CupomDesconto

        CupomDesconto.objects.create(
            codigo="VALE30", tipo="fixo", valor=30, ativo=True
        )
        totais = calcular_totais_pedido(
            subtotal=Decimal("150.00"), codigo_cupom="VALE30"
        )
        self.assertEqual(totais["desconto"], Decimal("30"))

    def test_desconto_nunca_supera_o_subtotal(self):
        from pedidos.models import CupomDesconto

        CupomDesconto.objects.create(
            codigo="GIGANTE", tipo="fixo", valor=999, ativo=True
        )
        totais = calcular_totais_pedido(
            subtotal=Decimal("50.00"), codigo_cupom="GIGANTE"
        )
        self.assertEqual(totais["total"], Decimal("0.00"))

    def test_cupom_inexistente_nao_aplica_desconto(self):
        totais = calcular_totais_pedido(
            subtotal=Decimal("100.00"), codigo_cupom="NAOEXISTE"
        )
        self.assertEqual(totais["desconto"], Decimal("0.00"))
        self.assertEqual(totais["cupom_mensagem"], "Cupom inválido.")


class CriacaoDePedidoTests(TestCase):
    def setUp(self):
        self.produto = criar_produto(nome="Camiseta", preco="100.00", estoque=6)
        self.variacao = primeira_variacao(self.produto)

    def _montar_carrinho(self, chave="sessao-pedido", quantidade=2):
        carrinho = Carrinho.objects.create(chave_sessao=chave)
        CarrinhoItem.objects.create(
            carrinho=carrinho, variacao=self.variacao,
            preco_unitario=self.variacao.preco_unitario, quantidade=quantidade,
        )
        return carrinho

    def _dados(self, **extra):
        return dados_checkout(
            subtotal=Decimal("200.00"), frete=Decimal("19.90"),
            desconto=Decimal("0.00"), total=Decimal("219.90"),
            metodo_entrega="Entrega estimada", prazo_entrega="7 dias úteis",
            **extra,
        )

    def test_criar_pedido_com_sucesso(self):
        carrinho = self._montar_carrinho()
        pedido, erro = criar_pedido(carrinho=carrinho, dados=self._dados())
        self.assertIsNone(erro)
        self.assertEqual(pedido.status, PedidoStatus.AGUARDANDO_PAGAMENTO)
        self.assertEqual(pedido.itens.count(), 1)
        self.assertEqual(pedido.total, Decimal("219.90"))
        self.assertEqual(HistoricoStatus.objects.filter(pedido=pedido).count(), 1)

    def test_criar_pedido_baixa_estoque_e_limpa_o_carrinho(self):
        carrinho = self._montar_carrinho(quantidade=2)
        criar_pedido(carrinho=carrinho, dados=self._dados())
        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, 4)
        self.assertEqual(CarrinhoItem.objects.count(), 0)
        self.assertEqual(MovimentoEstoque.objects.filter(
            tipo=MovimentoEstoque.Tipo.SAIDA
        ).count(), 1)

    def test_pedido_com_carrinho_vazio_retorna_erro(self):
        carrinho = Carrinho.objects.create(chave_sessao="vazio")
        pedido, erro = criar_pedido(carrinho=carrinho, dados=self._dados())
        self.assertIsNone(pedido)
        self.assertEqual(erro, "Seu carrinho está vazio.")

    def test_pedido_com_estoque_insuficiente_retorna_erro(self):
        carrinho = self._montar_carrinho(quantidade=60)
        pedido, erro = criar_pedido(carrinho=carrinho, dados=self._dados())
        self.assertIsNone(pedido)
        self.assertIn("Estoque insuficiente", erro)
        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, 6)

    def test_gerar_numero_pedido_e_unico(self):
        from pedidos.services import gerar_numero_pedido

        primeiro = gerar_numero_pedido()
        Pedido.objects.create(
            numero=primeiro, nome="A", email="a@example.com", telefone="1",
            cep="01310-100", logradouro="Rua", endereco_numero="1",
            bairro="Centro", cidade="São Paulo", estado="SP",
        )
        segundo = gerar_numero_pedido()
        self.assertNotEqual(primeiro, segundo)


class CheckoutViewTests(TestCase):
    def setUp(self):
        self.produto = criar_produto(nome="Camiseta", preco="100.00", estoque=6)
        self.variacao = primeira_variacao(self.produto)

    def _adicionar(self, quantidade=2):
        return self.client.post(
            reverse("carrinho:adicionar"),
            {"variacao_id": self.variacao.pk, "quantidade": quantidade},
            **AJAX,
    )

    def test_checkout_sem_carrinho_redireciona(self):
        resposta = self.client.get(reverse("pedidos:checkout"))
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, reverse("carrinho:pagina"))

    def test_checkout_get_renderiza_formulario(self):
        self._adicionar()
        resposta = self.client.get(reverse("pedidos:checkout"))
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "pedidos/checkout.html")

    def test_finalizar_compra_visitante_cria_pedido_aguardando_pagamento(self):
        self._adicionar(2)
        resposta = self.client.post(reverse("pedidos:checkout"), dados_checkout())
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "pedidos/confirmacao.html")

        pedido = Pedido.objects.get()
        self.assertEqual(pedido.status, PedidoStatus.AGUARDANDO_PAGAMENTO)
        self.assertEqual(pedido.usuario, None)
        self.assertTrue(pedido.chave_sessao)
        self.assertEqual(pedido.total, Decimal("200.00"))
        # estoque baixado e carrinho limpo
        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, 4)
        self.assertEqual(CarrinhoItem.objects.count(), 0)
        # nenhum pagamento aprovado foi criado
        self.assertFalse(hasattr(pedido, "pagamentos") and pedido.pagamentos.exists())

    def test_finalizar_compra_com_formulario_invalido_nao_cria_pedido(self):
        self._adicionar()
        dados = dados_checkout(cep="123", estado="")
        resposta = self.client.post(reverse("pedidos:checkout"), dados)
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context["form"].errors)
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertEqual(CarrinhoItem.objects.count(), 1)

    def test_finalizar_compra_logado_vincula_o_cliente(self):
        usuario = criar_usuario(username="dona", email="dona@myller.com")
        cliente = criar_cliente(usuario)
        self.client.force_login(usuario)
        self._adicionar(1)
        self.client.post(reverse("pedidos:checkout"), dados_checkout())
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.usuario, usuario)
        self.assertEqual(pedido.cliente, cliente)


class AcompanhamentoPedidoTests(TestCase):
    def setUp(self):
        self.usuario = criar_usuario(
            username="dono", email="dono@myller.com", senha="senha-forte-123"
        )
        criar_cliente(self.usuario)
        self.produto = criar_produto(nome="Camiseta", preco="100.00", estoque=6)
        self.variacao = primeira_variacao(self.produto)
        carrinho = Carrinho.objects.create(chave_sessao="sessao-dono")
        CarrinhoItem.objects.create(
            carrinho=carrinho, variacao=self.variacao,
            preco_unitario=Decimal("100.00"), quantidade=1,
        )
        self.pedido, erro = criar_pedido(
            carrinho=carrinho,
            dados=dados_checkout(
                subtotal=Decimal("100.00"), frete=Decimal("0.00"),
                desconto=Decimal("0.00"), total=Decimal("100.00"),
            ),
            usuario=self.usuario,
        )
        self.assertIsNone(erro)
        self.url = reverse("pedidos:detalhe", kwargs={"numero": self.pedido.numero})

    def test_dono_acessa_o_pedido(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "pedidos/detalhe.html")

    def test_visitante_com_mesma_sessao_acessa_o_pedido(self):
        # o pedido foi criado sem chave de sessão, então o dono é quem tem acesso
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 302)

    def test_outro_usuario_nao_acessa_o_pedido(self):
        intruso = criar_usuario(username="intruso", email="i@myller.com")
        self.client.force_login(intruso)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, reverse("core:home"))

    def test_staff_acessa_qualquer_pedido(self):
        from myller.utilitarios_teste import criar_staff

        staff = criar_staff()
        self.client.force_login(staff)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)

    def test_api_de_status_retorna_o_status_atual(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(
            reverse("pedidos:api_status", kwargs={"numero": self.pedido.numero})
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            resposta.json()["status"], PedidoStatus.AGUARDANDO_PAGAMENTO
        )

    def test_api_de_status_negado_para_terceiros(self):
        intruso = criar_usuario(username="outro", email="o@myller.com")
        self.client.force_login(intruso)
        resposta = self.client.get(
            reverse("pedidos:api_status", kwargs={"numero": self.pedido.numero})
        )
        self.assertEqual(resposta.status_code, 403)

    def test_cancelamento_pelo_cliente_devolve_estoque(self):
        self.client.force_login(self.usuario)
        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, 5)

        resposta = self.client.post(
            reverse("pedidos:cancelar", kwargs={"numero": self.pedido.numero})
        )
        self.assertEqual(resposta.status_code, 302)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, PedidoStatus.CANCELADO)
        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, 6)

    def test_pedido_entregue_nao_pode_ser_cancelado(self):
        alterar_status_pedido(self.pedido, PedidoStatus.ENTREGUE)
        self.client.force_login(self.usuario)
        self.client.post(
            reverse("pedidos:cancelar", kwargs={"numero": self.pedido.numero})
        )
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, PedidoStatus.ENTREGUE)

    def test_pedido_inexistente_retorna_404(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(
            reverse("pedidos:detalhe", kwargs={"numero": "MYL-NAO-EXISTE"})
        )
        self.assertEqual(resposta.status_code, 404)
