"""Testes do app favoritos: alternar via API e listagem."""
from django.test import TestCase
from django.urls import reverse

from favoritos.models import Favorito
from myller.utilitarios_teste import criar_produto, criar_usuario

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class FavoritosTests(TestCase):
    def setUp(self):
        self.produto = criar_produto(nome="Camiseta Favorita")
        self.usuario = criar_usuario(username="desejante", email="d@myller.com")
        self.url = reverse("favoritos:alternar")

    def test_visitante_recebe_401(self):
        resposta = self.client.post(
            self.url, {"produto_id": self.produto.pk}, **AJAX
        )
        self.assertEqual(resposta.status_code, 401)
        self.assertTrue(resposta.json()["login_necessario"])
        self.assertEqual(Favorito.objects.count(), 0)

    def test_adicionar_aos_favoritos(self):
        self.client.force_login(self.usuario)
        resposta = self.client.post(
            self.url, {"produto_id": self.produto.pk}, **AJAX
        )
        dados = resposta.json()
        self.assertTrue(dados["ok"])
        self.assertTrue(dados["adicionado"])
        self.assertTrue(
            Favorito.objects.filter(
                usuario=self.usuario, produto=self.produto
            ).exists()
        )

    def test_remover_dos_favoritos(self):
        Favorito.objects.create(usuario=self.usuario, produto=self.produto)
        self.client.force_login(self.usuario)
        resposta = self.client.post(
            self.url, {"produto_id": self.produto.pk}, **AJAX
        )
        self.assertFalse(resposta.json()["adicionado"])
        self.assertEqual(Favorito.objects.count(), 0)

    def test_produto_inexistente_retorna_404(self):
        self.client.force_login(self.usuario)
        resposta = self.client.post(self.url, {"produto_id": 999999}, **AJAX)
        self.assertEqual(resposta.status_code, 404)

    def test_produto_em_rascunho_nao_pode_ser_favoritado(self):
        from produtos.models import Produto

        oculto = criar_produto(nome="Oculto", status=Produto.Status.RASCUNHO)
        self.client.force_login(self.usuario)
        resposta = self.client.post(
            self.url, {"produto_id": oculto.pk}, **AJAX
        )
        self.assertEqual(resposta.status_code, 404)

    def test_pagina_de_favoritos_para_logado(self):
        Favorito.objects.create(usuario=self.usuario, produto=self.produto)
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("favoritos:lista"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Camiseta Favorita")

    def test_pagina_de_favoritos_para_visitante(self):
        resposta = self.client.get(reverse("favoritos:lista"))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(list(resposta.context["favoritos"]), [])
