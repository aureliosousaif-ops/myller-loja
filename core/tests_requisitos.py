"""Testes obrigatórios — responsividade das interfaces e funcionamento das URLs.

Itens 11 e 12 da tarefa. A validação visual em múltiplas larguras é feita
também manualmente/ferramenta de navegador; aqui garantimos os contratos
servidos (viewport, menu mobile, media queries e rotas).
"""
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from myller.utilitarios_teste import criar_cliente, criar_staff, criar_usuario

BASE_DIR = Path(__file__).resolve().parent.parent


def _ler(caminho_relativo):
    return (BASE_DIR / caminho_relativo).read_text(encoding="utf-8")


class ResponsividadeTests(TestCase):
    """Item 11 — interfaces responsivas (menu mobile + breakpoints)."""

    def test_loja_publica_tem_viewport_e_menu_mobile(self):
        html = _ler("templates/base.html")
        self.assertIn('name="viewport"', html)
        self.assertIn('id="menuMobile"', html)
        self.assertIn("data-bs-toggle=\"offcanvas\"", html)

    def test_painel_tem_viewport_e_menu_lateral_mobile(self):
        html = _ler("templates/dashboard/base_painel.html")
        self.assertIn('name="viewport"', html)
        self.assertIn('id="abreSidebar"', html)
        self.assertIn('id="painelSidebar"', html)

    def test_folhas_de_estilo_tem_breakpoints(self):
        painel = _ler("static/css/painel.css")
        loja = _ler("static/css/myller.css")
        componentes = _ler("static/css/componentes.css")
        self.assertIn("@media (max-width: 991.98px)", painel)
        self.assertIn("@media (max-width: 575.98px)", painel)
        self.assertIn("@media (max-width: 767.98px)", loja)
        self.assertIn("@media (max-width: 480px)", componentes)

    def test_paginas_da_loja_e_do_painel_renderizam_com_viewport(self):
        criar_staff()
        cliente = criar_usuario(username="resp", email="resp@myller.com")
        criar_cliente(cliente)

        self.client.force_login(cliente)
        resposta = self.client.get("/minha-conta/")
        self.assertContains(resposta, 'name="viewport"')

        self.client.force_login(criar_staff(username="resp_staff"))
        resposta = self.client.get("/painel/")
        self.assertContains(resposta, 'name="viewport"')
        self.assertContains(resposta, 'id="abreSidebar"')

    def test_tabelas_do_painel_sao_acessiveis_em_mobile(self):
        """As telas de listagem usam a tabela responsiva do painel."""
        self.client.force_login(criar_staff(username="resp_staff2"))
        for rota in ("/painel/produtos/", "/painel/pedidos/", "/painel/clientes/"):
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertContains(resposta, "tabela-painel")


class FuncionamentoDasURLsTests(TestCase):
    """Item 12 — todas as URLs principais respondem corretamente."""

    ROTAS_PUBLICAS = [
        "/",
        "/produtos/",
        "/entrar/",
        "/cadastro/",
        "/senha/redefinir/",
        "/carrinho/",
        "/favoritos/",
        "/minha-conta/favoritos/",
    ]

    ROTAS_ANONIMAS_PROTEGIDAS = [
        "/minha-conta/",
        "/minha-conta/perfil/",
        "/minha-conta/pedidos/",
        "/painel/",
        "/painel/produtos/",
        "/painel/pedidos/",
        "/painel/clientes/",
        "/painel/estoque/",
        "/painel/relatorios/",
        "/painel/configuracoes/",
        "/painel/cupons/",
        "/painel/categorias/",
        "/painel/newsletter/",
    ]

    def test_rotas_publicas_retornam_200(self):
        for rota in self.ROTAS_PUBLICAS:
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertEqual(resposta.status_code, 200, rota)

    def test_rotas_protegidas_redirecionam_para_login(self):
        for rota in self.ROTAS_ANONIMAS_PROTEGIDAS:
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertEqual(resposta.status_code, 302, rota)
                self.assertIn("/entrar/", resposta.url, rota)

    def test_urls_nomeadas_resolvem_sem_erro(self):
        esperadas = [
            ("core:home", {}), ("usuarios:login", {}), ("usuarios:registro", {}),
            ("usuarios:recuperar_senha", {}), ("clientes:perfil", {}),
            ("clientes:meus_pedidos", {}), ("favoritos:lista", {}),
            ("dashboard:home", {}), ("dashboard:produtos", {}),
            ("dashboard:produto_novo", {}), ("dashboard:pedidos", {}),
            ("dashboard:clientes", {}), ("dashboard:categorias", {}),
            ("dashboard:estoque", {}), ("dashboard:cupons", {}),
            ("dashboard:relatorios", {}), ("dashboard:configuracoes", {}),
            ("produtos:lista", {}), ("carrinho:pagina", {}),
        ]
        for nome, kwargs in esperadas:
            with self.subTest(url=nome):
                self.assertTrue(reverse(nome, kwargs=kwargs).startswith("/"))

    def test_area_do_cliente_responde_para_logado(self):
        usuario = criar_usuario(username="urlscliente", email="urls@myller.com")
        criar_cliente(usuario)
        self.client.force_login(usuario)
        for nome in ("clientes:perfil", "clientes:editar_perfil",
                     "clientes:enderecos", "clientes:meus_pedidos",
                     "clientes:alterar_senha", "favoritos:lista"):
            with self.subTest(url=nome):
                resposta = self.client.get(reverse(nome))
                self.assertEqual(resposta.status_code, 200, nome)

    def test_painel_responde_para_proprietario(self):
        self.client.force_login(criar_staff(username="urlsstaff"))
        for nome in ("dashboard:home", "dashboard:produtos",
                     "dashboard:produto_novo", "dashboard:pedidos",
                     "dashboard:clientes", "dashboard:categorias",
                     "dashboard:estoque", "dashboard:cupons",
                     "dashboard:relatorios", "dashboard:configuracoes",
                     "dashboard:newsletter"):
            with self.subTest(url=nome):
                resposta = self.client.get(reverse(nome))
                self.assertEqual(resposta.status_code, 200, nome)

    def test_sair_e_post(self):
        usuario = criar_usuario(username="sairstaff", email="sair@myller.com")
        self.client.force_login(usuario)
        resposta = self.client.post(reverse("usuarios:logout"))
        self.assertEqual(resposta.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_rota_desconhecida_retorna_404(self):
        resposta = self.client.get("/rota-que-nao-existe/")
        self.assertEqual(resposta.status_code, 404)
