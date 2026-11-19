"""Testes obrigatórios — fluxo completo de conta do cliente.

Cobre os itens 1 a 4 da tarefa: cadastro, login/logout, recuperação de
senha (fluxo real do Django) e área do cliente (/minha-conta/...).
"""
import re

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from myller.utilitarios_teste import criar_cliente, criar_usuario


def dados_validos(**extra):
    dados = {
        "first_name": "Carla",
        "last_name": "Mendes",
        "username": "carlamendes",
        "email": "carla@example.com",
        "telefone": "(11) 91234-5678",
        "password1": "senha-segura-123",
        "password2": "senha-segura-123",
        "aceite_termos": True,
    }
    dados.update(extra)
    return dados


class CadastroDeClienteTests(TestCase):
    """Item 1 — cadastro de cliente."""

    def test_cadastro_valido_cria_conta_e_autentica(self):
        resposta = self.client.post(reverse("usuarios:registro"), dados_validos())
        self.assertEqual(resposta.status_code, 302)
        usuario = User.objects.get(username="carlamendes")
        self.assertTrue(Cliente.objects.filter(usuario=usuario).exists())
        self.assertEqual(int(self.client.session["_auth_user_id"]), usuario.pk)

    def test_cadastro_sem_aceite_de_termos_e_rejeitado(self):
        dados = dados_validos()
        dados["aceite_termos"] = ""
        resposta = self.client.post(reverse("usuarios:registro"), dados)
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("aceite_termos", resposta.context["form"].errors)
        self.assertFalse(User.objects.filter(username="carlamendes").exists())

    def test_cadastro_com_email_duplicado_e_bloqueado(self):
        criar_usuario(username="outra", email="duplicado@example.com")
        dados = dados_validos(email="duplicado@example.com")
        resposta = self.client.post(reverse("usuarios:registro"), dados)
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("email", resposta.context["form"].errors)
        self.assertFalse(User.objects.filter(username="carlamendes").exists())


class LoginLogoutTests(TestCase):
    """Item 2 — login e logout."""

    def setUp(self):
        self.usuario = criar_usuario(
            username="carla", email="carla@example.com", senha="senha-segura-123"
        )
        criar_cliente(self.usuario)

    def test_login_com_e_mail_e_senha(self):
        resposta = self.client.post(
            reverse("usuarios:login"),
            {"username": "carla@example.com", "password": "senha-segura-123"},
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.usuario.pk)

    def test_login_senha_incorreta_nao_autentica(self):
        resposta = self.client.post(
            reverse("usuarios:login"),
            {"username": "carla", "password": "senha-errada"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_encerra_a_sessao(self):
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse("usuarios:logout"))
        self.assertEqual(resposta.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_com_opcao_manter_sessao(self):
        resposta = self.client.post(
            reverse("usuarios:login"),
            {
                "username": "carla",
                "password": "senha-segura-123",
                "lembrar": "on",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.usuario.pk)


class RecuperacaoDeSenhaTests(TestCase):
    """Item 3 — recuperação de senha com o fluxo real do Django."""

    def setUp(self):
        self.usuario = criar_usuario(
            username="perdida", email="perdida@example.com", senha="senha-antiga-123"
        )
        criar_cliente(self.usuario)

    def test_fluxo_completo_com_token_real(self):
        # 1. Solicita a redefinição
        resposta = self.client.post(
            reverse("usuarios:recuperar_senha"), {"email": self.usuario.email}
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

        # 2. O e-mail contém um link real do Django (uid + token) — nada falso
        corpo = mail.outbox[0].body
        correspondencia = re.search(
            r"(https?://\S+/senha/redefinir/[\w-]+/[\w-]+/)", corpo
        )
        self.assertIsNotNone(correspondencia, corpo)
        link = correspondencia.group(1)

        # 3. Acessa o link (guarda o token na sessão) e define a nova senha
        resposta = self.client.get(link, follow=True)
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(
            resposta, "usuarios/recuperar_senha_confirmar.html"
        )
        link_set = link.rsplit("/", 2)[0] + "/set-password/"
        resposta = self.client.post(
            link_set,
            {"new_password1": "senha-nova-12345", "new_password2": "senha-nova-12345"},
            follow=True,
        )
        self.assertEqual(resposta.status_code, 200)

        # 4. A senha antiga não funciona mais e a nova autentica
        self.assertFalse(
            self.client.login(username=self.usuario.username, password="senha-antiga-123")
        )
        self.assertTrue(
            self.client.login(username=self.usuario.username, password="senha-nova-12345")
        )

    def test_solicitacao_para_e_mail_inexistente_nao_revela_conta(self):
        resposta = self.client.post(
            reverse("usuarios:recuperar_senha"), {"email": "naoexiste@example.com"}
        )
        # Mesma resposta do fluxo válido — não vaza quais e-mails existem.
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)


class AreaDoClienteTests(TestCase):
    """Item 4 — rotas da área do cliente."""

    def setUp(self):
        self.usuario = criar_usuario(
            username="clientearea", email="area@example.com", senha="senha-forte-123"
        )
        criar_cliente(self.usuario)

    def test_rotas_da_area_do_cliente_renderizam_para_logado(self):
        rotas = [
            "/minha-conta/",
            "/minha-conta/perfil/",
            "/minha-conta/pedidos/",
            "/minha-conta/favoritos/",
            "/conta/",
            "/conta/enderecos/",
            "/conta/senha/",
        ]
        self.client.force_login(self.usuario)
        for rota in rotas:
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertEqual(resposta.status_code, 200, rota)

    def test_rotas_da_area_exigem_login(self):
        for rota in ("/minha-conta/", "/minha-conta/perfil/", "/minha-conta/pedidos/"):
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertEqual(resposta.status_code, 302, rota)
                self.assertIn(reverse("usuarios:login"), resposta.url)

    def test_pagina_favoritos_para_visitante_renderiza_aviso(self):
        resposta = self.client.get("/minha-conta/favoritos/")
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.context["autenticado"])
