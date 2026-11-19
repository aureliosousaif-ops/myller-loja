"""Testes obrigatórios do painel do proprietário (itens 5 a 10 da tarefa).

Bloqueio para clientes, acesso do proprietário, CRUD de produtos,
atualização de estoque, atualização de pedidos e proteção de dados.
"""
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from categorias.models import Categoria
from clientes.models import Cliente
from dashboard.models import RegistroAcao
from estoque.models import MovimentoEstoque
from estoque.services import EstoqueInsuficiente, registrar_saida
from myller.utilitarios_teste import (
    criar_cliente,
    criar_produto,
    criar_staff,
    criar_usuario,
    primeira_variacao,
)
from pedidos.models import Pedido, PedidoStatus
from produtos.models import Produto


def _pedido_com_item(variacao, quantidade=1, status=PedidoStatus.AGUARDANDO_PAGAMENTO,
                     chave="requisitos"):
    from carrinho.models import Carrinho, CarrinhoItem
    from pedidos.services import criar_pedido

    carrinho = Carrinho.objects.create(chave_sessao=f"{chave}-{variacao.pk}")
    CarrinhoItem.objects.create(
        carrinho=carrinho, variacao=variacao,
        preco_unitario=variacao.preco_unitario, quantidade=quantidade,
    )
    pedido, erro = criar_pedido(
        carrinho=carrinho,
        dados={
            "nome": "Cliente Teste", "email": "cliente@teste.com",
            "telefone": "(11) 96666-5555", "cep": "01310-100",
            "logradouro": "Av. Paulista", "numero": "900", "complemento": "",
            "bairro": "Bela Vista", "cidade": "São Paulo", "estado": "SP",
            "subtotal": variacao.preco_unitario * quantidade,
            "frete": Decimal("0.00"), "desconto": Decimal("0.00"),
            "total": variacao.preco_unitario * quantidade,
            "metodo_entrega": "Entrega estimada",
            "prazo_entrega": "7 dias úteis", "observacao": "",
        },
    )
    assert erro is None, erro
    if status != PedidoStatus.AGUARDANDO_PAGAMENTO:
        pedido.status = status
        pedido.save(update_fields=["status"])
    return pedido


# ------------------------------------------------------------------ Item 5
class BloqueioAdminParaClientesTests(TestCase):
    """Clientes comuns nunca acessam funcionalidades administrativas."""

    def setUp(self):
        self.cliente = criar_usuario(username="comumx", email="comumx@myller.com")
        criar_cliente(self.cliente)
        self.categoria = Categoria.objects.create(nome="Bloqueio")

    def test_cliente_comum_e_redirecionado_para_a_loja(self):
        self.client.force_login(self.cliente)
        for rota in ("/painel/", "/painel/produtos/", "/painel/relatorios/",
                     "/painel/configuracoes/", "/painel/clientes/"):
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertEqual(resposta.status_code, 302, rota)
                self.assertEqual(resposta.url, reverse("core:home"), rota)

    def test_cliente_comum_nao_cadastra_produto_no_servidor(self):
        self.client.force_login(self.cliente)
        antes = Produto.objects.count()
        resposta = self.client.post(
            reverse("dashboard:produto_novo"),
            {"nome": "Intruso", "categoria": self.categoria.pk,
             "descricao": "x", "preco": "10", "status": "publicado"},
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, reverse("core:home"))
        self.assertEqual(Produto.objects.count(), antes)

    def test_cliente_comum_nao_altera_status_de_pedido(self):
        produto = criar_produto(estoque=5)
        pedido = _pedido_com_item(primeira_variacao(produto))
        self.client.force_login(self.cliente)
        resposta = self.client.post(
            reverse("dashboard:pedido_atualizar_status",
                    kwargs={"numero": pedido.numero}),
            {"status": PedidoStatus.ENTREGUE},
        )
        self.assertEqual(resposta.status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, PedidoStatus.AGUARDANDO_PAGAMENTO)

    def test_django_admin_bloqueado_para_cliente_comum(self):
        self.client.force_login(self.cliente)
        # A rota raiz pode exibir apenas a tela de login do admin…
        resposta = self.client.get("/django-admin/")
        self.assertIn(resposta.status_code, (200, 302))
        if resposta.status_code == 200:
            self.assertTemplateUsed(resposta, "admin/login.html")
        # …e o painel do Django Admin em si é negado no servidor.
        resposta = self.client.get("/django-admin/produtos/produto/")
        self.assertNotEqual(resposta.status_code, 200)

    def test_visitante_e_enviado_para_o_login_com_next(self):
        resposta = self.client.get("/painel/")
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("usuarios:login"), resposta.url)
        self.assertIn("next=", resposta.url)


# ------------------------------------------------------------------ Item 6
class AcessoDoProprietarioTests(TestCase):
    """Somente staff/superusuário ou grupo autorizado entra no painel."""

    def test_superuser_acessa_o_painel(self):
        staff = criar_staff(username="dono")
        self.client.force_login(staff)
        resposta = self.client.get("/painel/")
        self.assertEqual(resposta.status_code, 200)

    def test_membro_do_grupo_proprietarios_acessa_o_painel(self):
        dono = criar_usuario(username="dono_grupo", email="dono@myller.com")
        grupo, _ = Group.objects.get_or_create(name="proprietarios")
        dono.groups.add(grupo)
        # sem is_staff: o acesso vem do grupo, no servidor
        self.assertFalse(dono.is_staff)
        self.client.force_login(dono)
        for rota in ("/painel/", "/painel/produtos/", "/painel/pedidos/",
                     "/painel/relatorios/", "/painel/estoque/"):
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertEqual(resposta.status_code, 200, rota)

    def test_grupo_desconhecido_nao_dacesso(self):
        usuario = criar_usuario(username="fora_do_grupo", email="fora@myller.com")
        Group.objects.get_or_create(name="marketing")
        self.client.force_login(usuario)
        resposta = self.client.get("/painel/")
        self.assertEqual(resposta.status_code, 302)


# ------------------------------------------------------------------ Item 7
class CRUDDeProdutosTests(TestCase):
    """Cadastro, edição, publicação e exclusão de produtos."""

    def setUp(self):
        self.staff = criar_staff()
        self.client.force_login(self.staff)
        self.categoria = Categoria.objects.create(nome="Vestidos")

    def _dados(self, **extra):
        dados = {
            "nome": "Vestido MYLLER",
            "categoria": self.categoria.pk,
            "resumo": "Resumo",
            "descricao": "Descrição completa do vestido.",
            "preco": "259.90",
            "preco_promocional": "",
            "sku": "",
            "status": "publicado",
            "eh_novidade": "on",
            "peso_kg": "0.5",
            "variacoes-TOTAL_FORMS": "1",
            "variacoes-INITIAL_FORMS": "0",
            "variacoes-MIN_NUM_FORMS": "0",
            "variacoes-MAX_NUM_FORMS": "1000",
            "variacoes-0-tamanho": "",
            "variacoes-0-cor": "",
            "variacoes-0-sku": "",
            "variacoes-0-preco_adicional": "0",
            "variacoes-0-estoque": "",
            "variacoes-0-ativa": "",
        }
        dados.update(extra)
        return dados

    def test_criar_editar_e_excluir_produto(self):
        # Cria
        resposta = self.client.post(reverse("dashboard:produto_novo"), self._dados())
        self.assertEqual(resposta.status_code, 302, resposta.content[:800])
        produto = Produto.objects.get(nome="Vestido MYLLER")
        self.assertEqual(produto.status, Produto.Status.PUBLICADO)

        # Editar
        resposta = self.client.post(
            reverse("dashboard:produto_editar", kwargs={"pk": produto.pk}),
            self._dados(nome="Vestido MYLLER Premium", preco="299.90"),
        )
        self.assertEqual(resposta.status_code, 302, resposta.content[:1200])
        produto.refresh_from_db()
        self.assertEqual(produto.nome, "Vestido MYLLER Premium")
        self.assertEqual(str(produto.preco), "299.90")

        # Excluir (só via POST, com confirmação no front)
        resposta = self.client.post(
            reverse("dashboard:produto_excluir", kwargs={"pk": produto.pk})
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(Produto.objects.filter(pk=produto.pk).exists())

    def test_ativar_e_desativar_produto(self):
        produto = criar_produto(nome="Blusa", status=Produto.Status.RASCUNHO)
        self.client.post(reverse("dashboard:produto_toggle", kwargs={"pk": produto.pk}))
        produto.refresh_from_db()
        self.assertEqual(produto.status, Produto.Status.PUBLICADO)
        self.client.post(reverse("dashboard:produto_toggle", kwargs={"pk": produto.pk}))
        produto.refresh_from_db()
        self.assertEqual(produto.status, Produto.Status.RASCUNHO)

    def test_exclusao_de_produto_requer_post(self):
        produto = criar_produto(nome="Protegido")
        resposta = self.client.get(
            reverse("dashboard:produto_excluir", kwargs={"pk": produto.pk})
        )
        self.assertEqual(resposta.status_code, 405)
        self.assertTrue(Produto.objects.filter(pk=produto.pk).exists())


# ------------------------------------------------------------------ Item 8
class AtualizacaoDeEstoqueTests(TestCase):
    """Entradas e saídas consistentes, sem estoque negativo."""

    def setUp(self):
        self.staff = criar_staff()
        self.client.force_login(self.staff)
        self.produto = criar_produto(nome="Camiseta Estoque", estoque=10)
        self.variacao = primeira_variacao(self.produto)

    def test_entrada_aumenta_e_registra_historico(self):
        resposta = self.client.post(
            reverse("dashboard:estoque"),
            {"tipo": "entrada", "variacao": self.variacao.pk,
             "quantidade": "5", "motivo": "Reposição"},
        )
        self.assertEqual(resposta.status_code, 302)
        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, 15)
        movimento = MovimentoEstoque.objects.latest("criado_em")
        self.assertEqual(movimento.tipo, MovimentoEstoque.Tipo.ENTRADA)
        self.assertEqual(movimento.usuario, self.staff)

    def test_saida_diminui_e_registra_historico(self):
        resposta = self.client.post(
            reverse("dashboard:estoque"),
            {"tipo": "saida", "variacao": self.variacao.pk,
             "quantidade": "3", "motivo": "Ajuste de inventário"},
        )
        self.assertEqual(resposta.status_code, 302)
        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, 7)
        movimento = MovimentoEstoque.objects.latest("criado_em")
        self.assertEqual(movimento.tipo, MovimentoEstoque.Tipo.SAIDA)

    def test_saida_acima_do_estoque_e_rejeitada(self):
        antes = self.variacao.estoque
        resposta = self.client.post(
            reverse("dashboard:estoque"),
            {"tipo": "saida", "variacao": self.variacao.pk,
             "quantidade": "999", "motivo": "Excesso"},
            follow=True,
        )
        self.assertContains(resposta, "Estoque insuficiente")
        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, antes)

    def test_service_de_saida_nunca_deixa_estoque_negativo(self):
        with self.assertRaises(EstoqueInsuficiente):
            registrar_saida(self.variacao, 500, motivo="testes")
        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, 10)

    def test_filtros_do_historico_funcionam(self):
        self.client.post(
            reverse("dashboard:estoque"),
            {"tipo": "entrada", "variacao": self.variacao.pk,
             "quantidade": "2", "motivo": "Filtro"},
        )
        resposta = self.client.get(
            reverse("dashboard:estoque"),
            {"tipo": "entrada", "produto": str(self.produto.pk)},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.context["movimentos"]), 1)

    def test_pedidos_simultaneos_nao_estouram_o_estoque(self):
        """Duas saídas concorrentes: a segunda falha se não sobra saldo."""
        registrar_saida(self.variacao, 8, motivo="primeira")
        with self.assertRaises(EstoqueInsuficiente):
            registrar_saida(self.variacao, 5, motivo="segunda")
        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, 2)


# ------------------------------------------------------------------ Item 9
class AtualizacaoDePedidosTests(TestCase):
    """Status de pedidos pelo painel, sem marcar pagamento manualmente."""

    def setUp(self):
        self.staff = criar_staff()
        self.client.force_login(self.staff)
        self.produto = criar_produto(nome="Camiseta Pedido", estoque=5)
        self.pedido = _pedido_com_item(primeira_variacao(self.produto))

    def test_atualizar_status_para_em_preparacao(self):
        resposta = self.client.post(
            reverse("dashboard:pedido_atualizar_status",
                    kwargs={"numero": self.pedido.numero}),
            {"status": PedidoStatus.EM_PREPARACAO, "observacao": "separado"},
        )
        self.assertEqual(resposta.status_code, 302)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, PedidoStatus.EM_PREPARACAO)
        self.assertTrue(
            self.pedido.historico.filter(status=PedidoStatus.EM_PREPARACAO).exists()
        )

    def test_pagamento_aprovado_nao_pode_ser_marcado_manualmente(self):
        resposta = self.client.post(
            reverse("dashboard:pedido_atualizar_status",
                    kwargs={"numero": self.pedido.numero}),
            {"status": PedidoStatus.PAGAMENTO_APROVADO},
        )
        self.assertEqual(resposta.status_code, 302)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, PedidoStatus.AGUARDANDO_PAGAMENTO)

    def test_opcao_pagamento_aprovado_nao_aparece_no_formulario(self):
        from dashboard.forms import PedidoStatusForm

        form = PedidoStatusForm()
        valores = [valor for valor, _ in form.fields["status"].choices]
        self.assertNotIn(PedidoStatus.PAGAMENTO_APROVADO, valores)
        self.assertIn(PedidoStatus.ENTREGUE, valores)


# ----------------------------------------------------------------- Item 10
class ProtecaoDeDadosDeOutrosClientesTests(TestCase):
    """Um cliente nunca vê nem altera dados de outro cliente."""

    def setUp(self):
        self.staff = criar_staff()
        self.cliente_a = criar_usuario(username="clienteA", email="a@myller.com")
        self.cliente_b = criar_usuario(username="clienteB", email="b@myller.com")
        self.cliente_b.is_active = True
        self.cliente_b.save()
        self.cliente_b_obj = criar_cliente(self.cliente_b)
        criar_cliente(self.cliente_a)
        self.produto = criar_produto(nome="Peça", estoque=5)
        self.pedido_b = _pedido_com_item(
            primeira_variacao(self.produto), chave="pedidob"
        )
        # vincula o pedido ao cliente B
        self.pedido_b.usuario = self.cliente_b
        self.pedido_b.cliente = self.cliente_b_obj
        self.pedido_b.save(update_fields=["usuario", "cliente"])

    def test_cliente_nao_acessa_o_painel_de_clientes(self):
        self.client.force_login(self.cliente_a)
        resposta = self.client.get("/painel/clientes/")
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, reverse("core:home"))

    def test_cliente_nao_desativa_conta_de_outro_cliente(self):
        self.client.force_login(self.cliente_a)
        resposta = self.client.post(
            reverse("dashboard:cliente_status", kwargs={"pk": self.cliente_b_obj.pk})
        )
        self.assertEqual(resposta.status_code, 302)
        self.cliente_b.refresh_from_db()
        self.assertTrue(self.cliente_b.is_active)

    def test_pedidos_de_outro_cliente_nao_aparecem_na_minha_conta(self):
        self.client.force_login(self.cliente_a)
        resposta = self.client.get("/minha-conta/pedidos/")
        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, self.pedido_b.numero)
        numeros = [p.numero for p in resposta.context["pedidos"]]
        self.assertNotIn(self.pedido_b.numero, numeros)

    def test_cliente_nao_ve_o_detalhe_de_outro_cliente_no_painel(self):
        self.client.force_login(self.cliente_a)
        resposta = self.client.get(
            reverse("dashboard:cliente_detalhe", kwargs={"pk": self.cliente_b_obj.pk})
        )
        self.assertEqual(resposta.status_code, 302)

    def test_nenhum_template_da_loja_exibe_senha(self):
        """Senhas nunca aparecem em nenhuma página (só hash no banco)."""
        self.client.force_login(self.cliente_a)
        for rota in ("/minha-conta/", "/minha-conta/perfil/", "/conta/"):
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertNotContains(resposta, 'type="password"')
                self.assertNotContains(resposta, self.cliente_a.password)


class TrilhaDeAuditoriaTests(TestCase):
    """Ações administrativas importantes ficam registradas."""

    def setUp(self):
        self.staff = criar_staff()
        self.client.force_login(self.staff)
        self.categoria = Categoria.objects.create(nome="Auditoria")

    def test_acoes_de_painel_sao_registradas(self):
        dados = {
            "nome": "Produto Auditado", "categoria": self.categoria.pk,
            "resumo": "r", "descricao": "d", "preco": "50",
            "preco_promocional": "", "sku": "", "status": "rascunho",
            "eh_novidade": "on", "peso_kg": "0.5",
            "variacoes-TOTAL_FORMS": "1", "variacoes-INITIAL_FORMS": "0",
            "variacoes-MIN_NUM_FORMS": "0", "variacoes-MAX_NUM_FORMS": "1000",
            "variacoes-0-tamanho": "", "variacoes-0-cor": "",
            "variacoes-0-sku": "", "variacoes-0-preco_adicional": "0",
            "variacoes-0-estoque": "", "variacoes-0-ativa": "",
        }
        self.client.post(reverse("dashboard:produto_novo"), dados)
        registro = RegistroAcao.objects.filter(acao="Produto criado").first()
        self.assertIsNotNone(registro)
        self.assertEqual(registro.usuario, self.staff)
        self.assertIn("Produto Auditado", registro.objeto)
        # nunca grava senha
        self.assertNotIn("senha", registro.detalhes.lower())


class RelatoriosDoPainelTests(TestCase):
    """Página de relatórios com dados reais e exportação CSV."""

    def setUp(self):
        self.staff = criar_staff()
        self.client.force_login(self.staff)
        self.produto = criar_produto(nome="Peça Relatório", estoque=5)
        self.pedido = _pedido_com_item(
            primeira_variacao(self.produto), chave="relatorio"
        )

    def test_pagina_relatorios_renderiza_com_kpis_reais(self):
        resposta = self.client.get("/painel/relatorios/")
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "dashboard/relatorios.html")
        self.assertEqual(resposta.context["kpi"]["qtd_vendas"], 1)

    def test_exportacao_csv_dos_pedidos(self):
        resposta = self.client.get(
            "/painel/relatorios/", {"formato": "csv"}
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("text/csv", resposta["Content-Type"])
        self.assertIn(self.pedido.numero, resposta.content.decode("utf-8"))
