"""Testes do app usuarios: cadastro, login, logout e recuperação de senha."""
from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from carrinho.models import Carrinho
from clientes.models import Cliente
from myller.utilitarios_teste import criar_usuario, primeira_variacao, criar_produto


class CadastroTests(TestCase):
    def dados_validos(self):
        return {
            "first_name": "Ana",
            "last_name": "Souza",
            "username": "anasouza",
            "email": "ana@example.com",
            "telefone": "(11) 98888-7777",
            "password1": "senha-segura-123",
            "password2": "senha-segura-123",
            "aceite_termos": True,
        }

    def test_cadastro_cria_usuario_cliente_e_autentica(self):
        resposta = self.client.post(reverse("usuarios:registro"), self.dados_validos())
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, reverse("clientes:perfil"))

        usuario = User.objects.get(username="anasouza")
        self.assertEqual(usuario.email, "ana@example.com")
        self.assertTrue(Cliente.objects.filter(usuario=usuario).exists())
        self.assertEqual(
            Cliente.objects.get(usuario=usuario).telefone, "(11) 98888-7777"
        )
        self.assertEqual(int(self.client.session["_auth_user_id"]), usuario.pk)

    def test_cadastro_com_email_duplicado_e_rejeitado(self):
        criar_usuario(username="existente", email="duplicado@example.com")
        dados = self.dados_validos()
        dados["email"] = "duplicado@example.com"
        resposta = self.client.post(reverse("usuarios:registro"), dados)
        self.assertEqual(resposta.status_code, 200)
        self.assertFormError(
            resposta.context["form"], "email",
            "Já existe uma conta com este e-mail.",
        )

    def test_cadastro_com_senhas_divergentes_e_rejeitado(self):
        dados = self.dados_validos()
        dados["password2"] = "outra-senha-123"
        resposta = self.client.post(reverse("usuarios:registro"), dados)
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context["form"].errors)
        self.assertFalse(User.objects.filter(username="anasouza").exists())

    def test_cadastro_valido_mescla_carrinho_da_sessao(self):
        produto = criar_produto(estoque=5)
        self.client.post(
            reverse("carrinho:adicionar"),
            {"variacao_id": primeira_variacao(produto).pk, "quantidade": 2},
        )
        self.assertEqual(Carrinho.objects.filter(usuario__isnull=True).count(), 1)

        self.client.post(reverse("usuarios:registro"), self.dados_validos())
        usuario = User.objects.get(username="anasouza")
        carrinho_usuario = Carrinho.objects.filter(usuario=usuario).first()
        self.assertIsNotNone(carrinho_usuario)
        self.assertEqual(carrinho_usuario.quantidade_total, 2)
        self.assertEqual(Carrinho.objects.filter(usuario__isnull=True).count(), 0)


class LoginTests(TestCase):
    def setUp(self):
        self.usuario = criar_usuario(
            username="joao", email="joao@example.com", senha="senha-forte-123"
        )

    def test_login_com_usuario(self):
        resposta = self.client.post(
            reverse("usuarios:login"),
            {"username": "joao", "password": "senha-forte-123"},
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.usuario.pk)

    def test_login_com_email(self):
        resposta = self.client.post(
            reverse("usuarios:login"),
            {"username": "joao@example.com", "password": "senha-forte-123"},
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.usuario.pk)

    def test_login_com_senha_incorreta(self):
        resposta = self.client.post(
            reverse("usuarios:login"),
            {"username": "joao", "password": "senha-errada"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout(self):
        self.client.login(username="joao", password="senha-forte-123")
        resposta = self.client.post(reverse("usuarios:logout"))
        self.assertEqual(resposta.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)


class RecuperarSenhaTests(TestCase):
    def setUp(self):
        self.usuario = criar_usuario(
            username="perda", email="perda@example.com", senha="senha-forte-123"
        )

    def test_solicitacao_de_redefinicao_envia_e_mail(self):
        resposta = self.client.post(
            reverse("usuarios:recuperar_senha"), {"email": "perda@example.com"}
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.usuario.email, mail.outbox[0].to)

    def test_paginas_de_redefinicao_renderizam(self):
        for nome in (
            "usuarios:recuperar_senha",
            "usuarios:recuperar_senha_feito",
            "usuarios:recuperar_senha_completo",
        ):
            resposta = self.client.get(reverse(nome))
            self.assertEqual(resposta.status_code, 200, nome)
