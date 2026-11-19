"""Testes do app clientes: perfil, endereços e meus pedidos."""
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente, Endereco
from myller.utilitarios_teste import criar_cliente, criar_usuario


class PerfilTests(TestCase):
    def setUp(self):
        self.usuario = criar_usuario(username="ana", email="ana@example.com")
        self.cliente = criar_cliente(self.usuario)
        self.client.force_login(self.usuario)

    def test_perfil_requer_login(self):
        self.client.logout()
        resposta = self.client.get(reverse("clientes:perfil"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("usuarios:login"), resposta.url)

    def test_pagina_de_perfil_renderiza(self):
        resposta = self.client.get(reverse("clientes:perfil"))
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "clientes/perfil.html")

    def test_editar_perfil_atualiza_usuario_e_cliente(self):
        resposta = self.client.post(
            reverse("clientes:editar_perfil"),
            {
                "first_name": "Ana Maria",
                "last_name": "Silva",
                "email": "ana@example.com",
                "cpf": "123.456.789-00",
                "telefone": "(11) 91234-5678",
                "aceita_newsletter": "on",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        self.usuario.refresh_from_db()
        self.cliente.refresh_from_db()
        self.assertEqual(self.usuario.first_name, "Ana Maria")
        self.assertEqual(self.cliente.telefone, "(11) 91234-5678")

    def test_editar_perfil_com_email_de_outro_usuario_e_rejeitado(self):
        criar_usuario(username="outro", email="outro@example.com")
        resposta = self.client.post(
            reverse("clientes:editar_perfil"),
            {
                "first_name": "Ana",
                "last_name": "Silva",
                "email": "outro@example.com",
                "cpf": "",
                "telefone": "",
            },
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context["form"].errors)


class EnderecoTests(TestCase):
    def setUp(self):
        self.usuario = criar_usuario(username="carlos", email="carlos@example.com")
        self.cliente = criar_cliente(self.usuario)
        self.client.force_login(self.usuario)

    def dados_endereco(self, **extra):
        dados = {
            "apelido": "Casa",
            "destinatario": "Carlos",
            "cep": "01310-100",
            "logradouro": "Avenida Paulista",
            "numero": "1000",
            "complemento": "",
            "bairro": "Bela Vista",
            "cidade": "São Paulo",
            "estado": "SP",
            "padrao": "on",
        }
        dados.update(extra)
        return dados

    def test_listagem_de_enderecos(self):
        resposta = self.client.get(reverse("clientes:enderecos"))
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "clientes/enderecos.html")

    def test_criar_endereco(self):
        resposta = self.client.post(
            reverse("clientes:endereco_novo"), self.dados_endereco()
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Endereco.objects.filter(cliente=self.cliente).count(), 1)

    def test_cep_invalido_e_rejeitado(self):
        resposta = self.client.post(
            reverse("clientes:endereco_novo"), self.dados_endereco(cep="123")
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("cep", resposta.context["form"].errors)
        self.assertEqual(Endereco.objects.count(), 0)

    def test_editar_endereco(self):
        endereco = Endereco.objects.create(
            cliente=self.cliente, cep="01310-100", logradouro="Rua A",
            numero="1", bairro="Centro", cidade="São Paulo", estado="SP",
        )
        resposta = self.client.post(
            reverse("clientes:endereco_editar", kwargs={"pk": endereco.pk}),
            self.dados_endereco(logradouro="Rua B", numero="22", padrao=""),
        )
        self.assertEqual(resposta.status_code, 302)
        endereco.refresh_from_db()
        self.assertEqual(endereco.logradouro, "Rua B")

    def test_marcar_endereco_padrao_desmarca_os_demas(self):
        primeiro = Endereco.objects.create(
            cliente=self.cliente, cep="01310-100", logradouro="Rua A",
            numero="1", bairro="Centro", cidade="São Paulo", estado="SP",
            padrao=True,
        )
        segundo = Endereco.objects.create(
            cliente=self.cliente, cep="02000-000", logradouro="Rua C",
            numero="2", bairro="Centro", cidade="São Paulo", estado="SP",
        )
        self.client.post(reverse("clientes:endereco_padrao", kwargs={"pk": segundo.pk}))
        segundo.refresh_from_db()
        primeiro.refresh_from_db()
        self.assertTrue(segundo.padrao)
        self.assertFalse(primeiro.padrao)

    def test_excluir_endereco(self):
        endereco = Endereco.objects.create(
            cliente=self.cliente, cep="01310-100", logradouro="Rua A",
            numero="1", bairro="Centro", cidade="São Paulo", estado="SP",
        )
        resposta = self.client.post(
            reverse("clientes:endereco_excluir", kwargs={"pk": endereco.pk})
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(Endereco.objects.filter(pk=endereco.pk).exists())

    def test_endereco_de_outro_usuario_nao_e_editado(self):
        outro_usuario = criar_usuario(username="intruso", email="intruso@example.com")
        outro_cliente = criar_cliente(outro_usuario)
        endereco_alheio = Endereco.objects.create(
            cliente=outro_cliente, cep="01310-100", logradouro="Rua Alheia",
            numero="9", bairro="Centro", cidade="São Paulo", estado="SP",
        )
        resposta = self.client.post(
            reverse("clientes:endereco_editar", kwargs={"pk": endereco_alheio.pk}),
            self.dados_endereco(logradouro="Invadida"),
        )
        self.assertEqual(resposta.status_code, 404)
        endereco_alheio.refresh_from_db()
        self.assertEqual(endereco_alheio.logradouro, "Rua Alheia")


class MeusPedidosTests(TestCase):
    def test_meus_pedidos_requer_login(self):
        resposta = self.client.get(reverse("clientes:meus_pedidos"))
        self.assertEqual(resposta.status_code, 302)

    def test_meus_pedidos_renderiza_para_logado(self):
        usuario = criar_usuario(username="comprador", email="c@example.com")
        self.client.force_login(usuario)
        resposta = self.client.get(reverse("clientes:meus_pedidos"))
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "clientes/meus_pedidos.html")
