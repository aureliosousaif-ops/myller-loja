"""Testes do app produtos: catálogo, filtros, detalhe, busca e avaliações."""
from django.test import TestCase
from django.urls import reverse

from categorias.models import Categoria
from favoritos.models import Favorito
from myller.utilitarios_teste import (
    criar_categoria,
    criar_cliente,
    criar_produto,
    criar_usuario,
    primeira_variacao,
)
from produtos.models import Avaliacao, Produto


class CatalogoTests(TestCase):
    def setUp(self):
        self.categoria = criar_categoria(nome="Masculino")
        self.produto = criar_produto(
            nome="Camiseta Preta", categoria=self.categoria
        )

    def test_lista_mostra_produtos_publicados(self):
        resposta = self.client.get(reverse("produtos:lista"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Camiseta Preta")

    def test_lista_oculta_produtos_em_rascunho(self):
        criar_produto(nome="Rascunho Secreto", status=Produto.Status.RASCUNHO)
        resposta = self.client.get(reverse("produtos:lista"))
        self.assertNotContains(resposta, "Rascunho Secreto")

    def test_filtro_de_promocao(self):
        criar_produto(nome="Promoção Especial", promo="99.90")
        resposta = self.client.get(reverse("produtos:lista") + "?promocao=1")
        self.assertContains(resposta, "Promoção Especial")
        self.assertNotContains(resposta, "Camiseta Preta")

    def test_filtro_de_novidade(self):
        criar_produto(nome="Lançamento Total", eh_novidade=False)
        resposta = self.client.get(reverse("produtos:lista") + "?novidade=1")
        self.assertContains(resposta, "Camiseta Preta")
        self.assertNotContains(resposta, "Lançamento Total")

    def test_ordenacao_por_preco(self):
        criar_produto(nome="Barato", preco="49.90")
        resposta = self.client.get(reverse("produtos:lista") + "?ordem=preco_asc")
        primeiro = resposta.context["produtos"][0]
        self.assertEqual(primeiro.nome, "Barato")

    def test_filtro_por_categoria_na_url(self):
        outra = criar_categoria(nome="Feminino")
        criar_produto(nome="Vestido Azul", categoria=outra)
        resposta = self.client.get(
            reverse("produtos:lista") + f"?categoria={self.categoria.slug}"
        )
        self.assertContains(resposta, "Camiseta Preta")
        self.assertNotContains(resposta, "Vestido Azul")

    def test_filtro_por_tamanho(self):
        resposta = self.client.get(
            reverse("produtos:lista") + "?tamanho=M"
        )
        self.assertContains(resposta, "Camiseta Preta")

    def test_pagina_de_categoria_inclui_subcategorias(self):
        sub = criar_categoria(nome="Camisetas", pai=self.categoria)
        criar_produto(nome="Camiseta Filha", categoria=sub)
        resposta = self.client.get(
            reverse("produtos:categoria", kwargs={"slug": self.categoria.slug})
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Camiseta Filha")
        self.assertContains(resposta, "Camiseta Preta")

    def test_categoria_inexistente_retorna_404(self):
        resposta = self.client.get(
            reverse("produtos:categoria", kwargs={"slug": "nao-existe"})
        )
        self.assertEqual(resposta.status_code, 404)


class DetalheProdutoTests(TestCase):
    def setUp(self):
        self.produto = criar_produto(nome="Camiseta Essencial")
        self.url = reverse("produtos:detalhe", kwargs={"slug": self.produto.slug})

    def test_detalhe_retorna_200(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "produtos/detalhe.html")

    def test_detalhe_incrementa_visualizacoes(self):
        self.client.get(self.url)
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.visualizacoes, 1)

    def test_detalhe_de_produto_rascunho_retorna_404(self):
        rascunho = criar_produto(nome="Oculto", status=Produto.Status.RASCUNHO)
        resposta = self.client.get(
            reverse("produtos:detalhe", kwargs={"slug": rascunho.slug})
        )
        self.assertEqual(resposta.status_code, 404)

    def test_detalhe_exibe_mapa_de_variacoes(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context["mapa_variacoes"], {
            "M|Branco": {
                "id": primeira_variacao(self.produto).pk,
                "estoque": 10,
                "ativo": True,
                "preco": "149.90",
            }
        })


class BuscaTests(TestCase):
    def setUp(self):
        self.produto = criar_produto(nome="Tênis Running")
        criar_produto(nome="Calça Jeans")

    def test_busca_por_nome(self):
        resposta = self.client.get(reverse("produtos:busca") + "?q=tênis")
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Tênis Running")
        self.assertNotContains(resposta, "Calça Jeans")

    def test_busca_sem_resultados(self):
        resposta = self.client.get(reverse("produtos:busca") + "?q=xyz-inexistente")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(list(resposta.context["produtos"]), [])

    def test_api_de_busca_sugere_produtos(self):
        resposta = self.client.get(reverse("produtos:api_busca") + "?q=tênis")
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertTrue(dados["ok"])
        self.assertEqual(dados["resultados"][0]["nome"], "Tênis Running")

    def test_api_de_busca_curta_retorna_vazio(self):
        resposta = self.client.get(reverse("produtos:api_busca") + "?q=a")
        self.assertEqual(resposta.json()["resultados"], [])


class AvaliacaoTests(TestCase):
    def setUp(self):
        self.produto = criar_produto(nome="Camiseta Avaliada")
        self.usuario = criar_usuario(username="avaliador", email="av@myller.com")
        criar_cliente(self.usuario)
        self.url = reverse(
            "produtos:avaliar", kwargs={"slug": self.produto.slug}
        )

    def test_avaliar_requer_login(self):
        resposta = self.client.post(self.url, {"nota": 5, "comentario": "Ótima peça!"})
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("usuarios:login"), resposta.url)

    def test_avaliar_cria_avaliacao(self):
        self.client.force_login(self.usuario)
        resposta = self.client.post(
            self.url, {"nota": 5, "comentario": "Ótima peça, recomendo!"}
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Avaliacao.objects.count(), 1)
        self.assertEqual(self.produto.nota_media, 5)

    def test_avaliar_nota_invalida_nao_cria_registro(self):
        self.client.force_login(self.usuario)
        self.client.post(self.url, {"nota": 9, "comentario": "Texto válido aqui"})
        self.assertEqual(Avaliacao.objects.count(), 0)

    def test_avaliar_comentario_curto_nao_cria_registro(self):
        self.client.force_login(self.usuario)
        self.client.post(self.url, {"nota": 5, "comentario": "ok"})
        self.assertEqual(Avaliacao.objects.count(), 0)


class FavoritosNosCardsTests(TestCase):
    def test_card_marca_favoritado(self):
        produto = criar_produto(nome="Favoritado")
        usuario = criar_usuario(username="fã", email="fa@myller.com")
        Favorito.objects.create(usuario=usuario, produto=produto)
        self.client.force_login(usuario)
        resposta = self.client.get(reverse("produtos:lista"))
        self.assertContains(resposta, 'data-favorito="%d"' % produto.pk)
        self.assertIn(produto.pk, resposta.context["favoritos_ids"])
