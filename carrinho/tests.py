"""Testes do app carrinho: adição, atualização, cupom e frete."""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from carrinho.models import Carrinho, CarrinhoItem
from myller.utilitarios_teste import criar_produto, primeira_variacao
from pedidos.models import CupomDesconto

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class CarrinhoBase(TestCase):
    def setUp(self):
        self.produto = criar_produto(nome="Camiseta", preco="100.00", estoque=5)
        self.variacao = primeira_variacao(self.produto)
        self.url_adicionar = reverse("carrinho:adicionar")

    def adicionar(self, quantidade=1, **extra):
        dados = {
            "variacao_id": self.variacao.pk,
            "quantidade": quantidade,
            "produto_slug": self.produto.slug,
        }
        dados.update(extra)
        return self.client.post(self.url_adicionar, dados, **AJAX)


class AdicaoTests(CarrinhoBase):
    def test_adicionar_item_cria_carrinho_e_item(self):
        resposta = self.adicionar(2)
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertTrue(dados["ok"])
        self.assertEqual(dados["carrinho_qtd"], 2)
        self.assertEqual(CarrinhoItem.objects.count(), 1)
        self.assertEqual(CarrinhoItem.objects.first().quantidade, 2)

    def test_adicionar_sem_variacao_e_recusado(self):
        resposta = self.client.post(
            self.url_adicionar, {"variacao_id": "", "quantidade": 1}, **AJAX
        )
        dados = resposta.json()
        self.assertFalse(dados["ok"])
        self.assertEqual(CarrinhoItem.objects.count(), 0)

    def test_adicionar_quantidade_acima_do_estoque_e_limitada(self):
        resposta = self.adicionar(99)
        self.assertTrue(resposta.json()["ok"])
        item = CarrinhoItem.objects.first()
        self.assertEqual(item.quantidade, 5)

    def test_adicionar_item_esgotado_e_recusado(self):
        esgotado = criar_produto(nome="Esgotado", estoque=0)
        resposta = self.client.post(
            self.url_adicionar,
            {"variacao_id": primeira_variacao(esgotado).pk, "quantidade": 1},
            **AJAX,
        )
        self.assertFalse(resposta.json()["ok"])
        self.assertEqual(CarrinhoItem.objects.count(), 0)

    def test_adicionar_produto_inexistente_e_recusado(self):
        resposta = self.client.post(
            self.url_adicionar, {"variacao_id": 999999, "quantidade": 1}, **AJAX
        )
        self.assertFalse(resposta.json()["ok"])

    def test_adicionar_acumula_quantidade_do_mesmo_item(self):
        self.adicionar(1)
        self.adicionar(2)
        self.assertEqual(CarrinhoItem.objects.count(), 1)
        self.assertEqual(CarrinhoItem.objects.first().quantidade, 3)

    def test_carrinho_do_visitante_nao_aparece_para_outro_visitante(self):
        self.adicionar(1)
        self.assertEqual(CarrinhoItem.objects.count(), 1)
        self.client.cookies.clear()  # simula uma nova sessão de outro visitante
        resposta = self.client.get(reverse("carrinho:pagina"))
        self.assertEqual(resposta.context["carrinho"], None)


class AtualizacaoTests(CarrinhoBase):
    def item(self):
        self.adicionar(2)
        return CarrinhoItem.objects.first()

    def test_atualizar_quantidade_via_ajax(self):
        item = self.item()
        resposta = self.client.post(
            reverse("carrinho:atualizar"),
            {"item_id": item.pk, "quantidade": 4},
            **AJAX,
        )
        dados = resposta.json()
        self.assertTrue(dados["ok"])
        self.assertEqual(dados["quantidades"][str(item.pk)], 4)
        self.assertEqual(dados["subtotal"], "400.00")

    def test_acao_aumentar_e_diminuir(self):
        item = self.item()
        url = reverse("carrinho:atualizar")
        self.client.post(url, {"item_id": item.pk, "acao": "aumentar"}, **AJAX)
        item.refresh_from_db()
        self.assertEqual(item.quantidade, 3)
        self.client.post(url, {"item_id": item.pk, "acao": "diminuir"}, **AJAX)
        item.refresh_from_db()
        self.assertEqual(item.quantidade, 2)

    def test_quantidade_zero_remove_o_item(self):
        item = self.item()
        self.client.post(
            reverse("carrinho:atualizar"),
            {"item_id": item.pk, "quantidade": 0},
            **AJAX,
        )
        self.assertFalse(CarrinhoItem.objects.filter(pk=item.pk).exists())

    def test_quantidade_maior_que_o_estoque_e_limitada(self):
        item = self.item()
        self.client.post(
            reverse("carrinho:atualizar"),
            {"item_id": item.pk, "quantidade": 500},
            **AJAX,
        )
        item.refresh_from_db()
        self.assertEqual(item.quantidade, 5)

    def test_remover_item(self):
        item = self.item()
        resposta = self.client.post(
            reverse("carrinho:remover"), {"item_id": item.pk}, **AJAX
        )
        self.assertTrue(resposta.json()["ok"])
        self.assertEqual(CarrinhoItem.objects.count(), 0)

    def test_limpar_carrinho(self):
        self.item()
        resposta = self.client.post(reverse("carrinho:limpar"), **AJAX)
        self.assertTrue(resposta.json()["ok"])
        self.assertEqual(CarrinhoItem.objects.count(), 0)

    def test_pagina_do_carrinho_renderiza_totais(self):
        self.item()
        resposta = self.client.get(reverse("carrinho:pagina"))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["totais"]["subtotal"], 200)


class CupomTests(CarrinhoBase):
    def setUp(self):
        super().setUp()
        self.cupom = CupomDesconto.objects.create(
            codigo="DESCONT10", tipo="percentual", valor=10, ativo=True
        )

    def test_aplicar_cupom_valido(self):
        self.adicionar(1)
        resposta = self.client.post(
            reverse("carrinho:cupom"), {"codigo": "descont10"}
        )
        self.assertEqual(resposta.status_code, 302)
        carrinho = Carrinho.objects.filter(usuario__isnull=True).first()
        self.assertEqual(carrinho.cupom_codigo, "DESCONT10")

    def test_cupom_invalido_nao_e_aplicado(self):
        self.adicionar(1)
        self.client.post(reverse("carrinho:cupom"), {"codigo": "NAOEXISTE"})
        carrinho = Carrinho.objects.filter(usuario__isnull=True).first()
        self.assertEqual(carrinho.cupom_codigo, "")

    def test_cupom_com_pedido_minimo_nao_e_aplicado(self):
        self.cupom.codigo = "MINIMO"
        self.cupom.pedido_minimo = 1000
        self.cupom.save()
        self.adicionar(1)  # subtotal 100
        self.client.post(reverse("carrinho:cupom"), {"codigo": "MINIMO"})
        carrinho = Carrinho.objects.filter(usuario__isnull=True).first()
        self.assertEqual(carrinho.cupom_codigo, "")

    def test_desconto_no_totais_do_pedido(self):
        from pedidos.services import calcular_totais_pedido

        totais = calcular_totais_pedido(
            subtotal=Decimal("200.00"), codigo_cupom="DESCONT10"
        )
        self.assertEqual(totais["desconto"], Decimal("20.00"))
        self.assertEqual(totais["total"], Decimal("180.00"))


class FreteTests(CarrinhoBase):
    def test_cep_invalido_retorna_400(self):
        self.adicionar(1)
        resposta = self.client.post(reverse("carrinho:api_frete"), {"cep": "123"})
        self.assertEqual(resposta.status_code, 400)

    def test_calculo_de_fretete_estimado_por_tabela(self):
        self.adicionar(1)
        resposta = self.client.post(
            reverse("carrinho:api_frete"), {"cep": "01310-100"}
        )
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertTrue(dados["ok"])
        self.assertGreater(float(dados["valor"]), 0)
        # Sem credenciais de API, o valor é sempre identificado como estimativa.
        self.assertTrue(dados["estimativa"])

    def test_frete_gratis_para_pedido_acima_do_limite(self):
        caro = criar_produto(nome="Produto Caro", preco="900.00")
        self.client.post(
            reverse("carrinho:adicionar"),
            {"variacao_id": primeira_variacao(caro).pk, "quantidade": 1},
            **AJAX,
        )
        resposta = self.client.post(
            reverse("carrinho:api_frete"), {"cep": "01310-100"}
        )
        dados = resposta.json()
        self.assertEqual(float(dados["valor"]), 0.0)
        self.assertTrue(dados["ok"])

    def test_frete_sem_carrinho_retorna_400(self):
        resposta = self.client.post(reverse("carrinho:api_frete"), {"cep": "01310100"})
        self.assertEqual(resposta.status_code, 400)
