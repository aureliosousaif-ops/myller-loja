"""Testes do app core: home, páginas institucionais, newsletter e ViaCEP."""
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from core.models import NewsletterInscrito, PaginaInstitucional
from myller.utilitarios_teste import criar_produto


class HomeTests(TestCase):
    def test_home_retorna_200(self):
        resposta = self.client.get(reverse("core:home"))
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "core/home.html")

    def test_home_exibe_produtos_em_destaque(self):
        criar_produto(nome="Produto Destaque", destaque_home=True)
        resposta = self.client.get(reverse("core:home"))
        self.assertContains(resposta, "Produto Destaque")

    def test_home_mostra_secoes_de_novidade_e_promocao(self):
        criar_produto(nome="Novidade Quente", eh_novidade=True)
        criar_produto(nome="Promoção Quente", promo="99.90")
        resposta = self.client.get(reverse("core:home"))
        self.assertContains(resposta, "Novidade Quente")
        self.assertContains(resposta, "Promoção Quente")

    def test_home_exibe_categorias(self):
        from myller.utilitarios_teste import criar_categoria

        criar_categoria(nome="Masculino")
        resposta = self.client.get(reverse("core:home"))
        self.assertContains(resposta, "Masculino")


class PaginaInstitucionalTests(TestCase):
    def test_pagina_publicada_renderiza(self):
        PaginaInstitucional.objects.create(
            titulo="Sobre", slug="sobre",
            conteudo="<p>Texto institucional.</p>",
        )
        resposta = self.client.get(reverse("core:pagina", kwargs={"slug": "sobre"}))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Texto institucional")

    def test_pagina_inativa_retorna_404(self):
        PaginaInstitucional.objects.create(
            titulo="Interna", slug="interna", conteudo="x", ativa=False
        )
        resposta = self.client.get(reverse("core:pagina", kwargs={"slug": "interna"}))
        self.assertEqual(resposta.status_code, 404)

    def test_pagina_desconhecida_retorna_404(self):
        resposta = self.client.get(reverse("core:pagina", kwargs={"slug": "nao-existe"}))
        self.assertEqual(resposta.status_code, 404)


class NewsletterTests(TestCase):
    def test_inscricao_valida_cria_registro(self):
        resposta = self.client.post(
            reverse("core:newsletter"), {"email": "novo@myller.com.br"}
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(
            NewsletterInscrito.objects.filter(email="novo@myller.com.br").exists()
        )

    def test_inscricao_repetida_nao_duplica(self):
        self.client.post(reverse("core:newsletter"), {"email": "dup@myller.com.br"})
        self.client.post(reverse("core:newsletter"), {"email": "dup@myller.com.br"})
        self.assertEqual(
            NewsletterInscrito.objects.filter(email="dup@myller.com.br").count(), 1
        )

    def test_inscricao_sem_email_nao_cria_registro(self):
        self.client.post(reverse("core:newsletter"), {"email": ""})
        self.assertEqual(NewsletterInscrito.objects.count(), 0)


class ApiCepTests(TestCase):
    def test_cep_invalido_retorna_400(self):
        resposta = self.client.get(reverse("core:api_cep", kwargs={"cep": "123"}))
        self.assertEqual(resposta.status_code, 400)

    @patch("core.services.buscar_cep")
    def test_cep_valido_retorna_endereco(self, mock_buscar):
        mock_buscar.return_value = {
            "cep": "01310-100",
            "logradouro": "Avenida Paulista",
            "bairro": "Bela Vista",
            "cidade": "São Paulo",
            "estado": "SP",
            "complemento": "",
        }
        resposta = self.client.get(reverse("core:api_cep", kwargs={"cep": "01310100"}))
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()["ok"])
        self.assertEqual(resposta.json()["endereco"]["cidade"], "São Paulo")

    @patch("core.services.buscar_cep")
    def test_cep_nao_encontrado_retorna_404(self, mock_buscar):
        mock_buscar.return_value = None
        resposta = self.client.get(reverse("core:api_cep", kwargs={"cep": "99999999"}))
        self.assertEqual(resposta.status_code, 404)
