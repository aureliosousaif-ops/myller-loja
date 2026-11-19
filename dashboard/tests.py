"""Testes do app dashboard: permissões, páginas e ações do painel."""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from categorias.models import Categoria
from core.models import ConfiguracaoLoja
from estoque.models import MovimentoEstoque
from myller.utilitarios_teste import (
    criar_cliente,
    criar_produto,
    criar_staff,
    criar_usuario,
    primeira_variacao,
)
from pedidos.models import CupomDesconto, Pedido, PedidoStatus
from produtos.models import Produto

ROTAS_GET = [
    "dashboard:home",
    "dashboard:produtos",
    "dashboard:produto_novo",
    "dashboard:pedidos",
    "dashboard:clientes",
    "dashboard:categorias",
    "dashboard:cupons",
    "dashboard:estoque",
    "dashboard:newsletter",
    "dashboard:configuracoes",
]


class PermissaoTests(TestCase):
    def test_anonimo_e_redirecionado_para_o_login(self):
        resposta = self.client.get(reverse("dashboard:home"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("usuarios:login"), resposta.url)
        self.assertIn("next=", resposta.url)

    def test_anonimo_preserva_o_destino_original(self):
        resposta = self.client.get(reverse("dashboard:produtos"))
        self.assertIn("next=/painel/produtos/", resposta.url)

    def test_usuario_comum_nao_entra_no_painel(self):
        usuario = criar_usuario(username="comum", email="comum@myller.com")
        self.client.force_login(usuario)
        resposta = self.client.get(reverse("dashboard:home"))
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, reverse("core:home"))

    def test_staff_entra_no_painel(self):
        staff = criar_staff()
        self.client.force_login(staff)
        resposta = self.client.get(reverse("dashboard:home"))
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "dashboard/home.html")

    def test_mensagem_de_aviso_para_visitante(self):
        resposta = self.client.get(reverse("dashboard:home"), follow=True)
        mensagens = [m.message for m in resposta.context["messages"]]
        self.assertIn("Entre com uma conta de administrador.", mensagens)


class PaginasDoPainelTests(TestCase):
    def setUp(self):
        self.staff = criar_staff()
        self.client.force_login(self.staff)

    def test_todas_as_paginas_renderizam(self):
        for nome in ROTAS_GET:
            with self.subTest(url=nome):
                resposta = self.client.get(reverse(nome))
                self.assertEqual(resposta.status_code, 200, nome)

    def test_pagina_de_produto_para_edicao(self):
        produto = criar_produto(nome="Produto Editado")
        resposta = self.client.get(
            reverse("dashboard:produto_editar", kwargs={"pk": produto.pk})
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["produto"], produto)

    def test_detalhe_de_pedido(self):
        produto = criar_produto(nome="Camiseta", estoque=5)
        variacao = primeira_variacao(produto)
        pedido = _pedido_com_item(variacao, quantidade=1)
        resposta = self.client.get(
            reverse("dashboard:pedido_detalhe", kwargs={"numero": pedido.numero})
        )
        self.assertEqual(resposta.status_code, 200)

    def test_detalhe_de_cliente(self):
        usuario = criar_usuario(username="clientex", email="cx@myller.com")
        cliente = criar_cliente(usuario)
        resposta = self.client.get(
            reverse("dashboard:cliente_detalhe", kwargs={"pk": cliente.pk})
        )
        self.assertEqual(resposta.status_code, 200)

    def test_pedido_inexistente_retorna_404(self):
        resposta = self.client.get(
            reverse("dashboard:pedido_detalhe", kwargs={"numero": "MYL-NAO"})
        )
        self.assertEqual(resposta.status_code, 404)


def _pedido_com_item(variacao, quantidade=1, status=PedidoStatus.AGUARDANDO_PAGAMENTO):
    from carrinho.models import Carrinho, CarrinhoItem
    from pedidos.services import criar_pedido

    carrinho = Carrinho.objects.create(chave_sessao=f"painel-{variacao.pk}")
    CarrinhoItem.objects.create(
        carrinho=carrinho, variacao=variacao,
        preco_unitario=variacao.preco_unitario, quantidade=quantidade,
    )
    pedido, erro = criar_pedido(
        carrinho=carrinho,
        dados={
            "nome": "Cliente Painel", "email": "painel@example.com",
            "telefone": "(11) 97777-6666", "cep": "01310-100",
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


class ProdutoNoPainelTests(TestCase):
    def setUp(self):
        self.staff = criar_staff()
        self.client.force_login(self.staff)
        self.categoria = Categoria.objects.create(nome="Masculino")

    def _dados_produto(self, **extra):
        dados = {
            "nome": "Camiseta Nova",
            "categoria": self.categoria.pk,
            "resumo": "Resumo curto",
            "descricao": "Descrição detalhada do produto.",
            "preco": "199.90",
            "preco_promocional": "",
            "sku": "",
            "status": "publicado",
            "destaque_home": "on",
            "eh_novidade": "on",
            "peso_kg": "0.5",
            # prefixo padrão do inline formset = nome do related_name ("variacoes")
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

    def test_criar_produto_com_variacao(self):
        from produtos.models import Cor, Tamanho

        tamanho = Tamanho.objects.create(nome="G", ordem=4)
        cor = Cor.objects.create(nome="Preto", codigo_hex="#1A1A1A")
        dados = self._dados_produto(
            **{
                "variacoes-0-tamanho": tamanho.pk,
                "variacoes-0-cor": cor.pk,
                "variacoes-0-estoque": "7",
                "variacoes-0-ativa": "on",
            }
        )
        resposta = self.client.post(reverse("dashboard:produto_novo"), dados)
        self.assertEqual(resposta.status_code, 302, resposta.content[:1500])
        produto = Produto.objects.get(nome="Camiseta Nova")
        self.assertEqual(produto.status, Produto.Status.PUBLICADO)
        self.assertEqual(produto.estoque_total, 7)
        self.assertEqual(produto.variacoes.count(), 1)

    def test_criar_produto_com_preco_invalido_retorna_erros(self):
        resposta = self.client.post(
            reverse("dashboard:produto_novo"),
            self._dados_produto(preco="0", preco_promocional="999"),
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context["form"].errors)
        self.assertEqual(Produto.objects.count(), 0)

    def test_publicar_e_despublicar_produto(self):
        produto = criar_produto(nome="Alternar Status")
        resposta = self.client.post(
            reverse("dashboard:produto_toggle", kwargs={"pk": produto.pk})
        )
        self.assertEqual(resposta.status_code, 302)
        produto.refresh_from_db()
        self.assertEqual(produto.status, Produto.Status.RASCUNHO)

    def test_excluir_produto(self):
        produto = criar_produto(nome="Para Excluir")
        resposta = self.client.post(
            reverse("dashboard:produto_excluir", kwargs={"pk": produto.pk})
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(Produto.objects.filter(pk=produto.pk).exists())

    def test_exclusao_requer_post(self):
        produto = criar_produto(nome="Sem POST")
        resposta = self.client.get(
            reverse("dashboard:produto_excluir", kwargs={"pk": produto.pk})
        )
        self.assertEqual(resposta.status_code, 405)


class PedidoNoPainelTests(TestCase):
    def setUp(self):
        self.staff = criar_staff()
        self.client.force_login(self.staff)
        self.produto = criar_produto(nome="Camiseta", estoque=5)
        self.variacao = primeira_variacao(self.produto)
        self.pedido = _pedido_com_item(self.variacao, quantidade=2)

    def test_alterar_status_para_em_preparacao(self):
        resposta = self.client.post(
            reverse("dashboard:pedido_atualizar_status",
                    kwargs={"numero": self.pedido.numero}),
            {"status": "em_preparacao", "observacao": "Separado"},
        )
        self.assertEqual(resposta.status_code, 302)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, PedidoStatus.EM_PREPARACAO)
        self.assertEqual(self.pedido.atualizado_por, self.staff)
        self.assertTrue(self.pedido.historico.filter(status="em_preparacao").exists())

    def test_cancelar_pedido_devolve_o_estoque(self):
        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, 3)
        self.client.post(
            reverse("dashboard:pedido_atualizar_status",
                    kwargs={"numero": self.pedido.numero}),
            {"status": "cancelado", "observacao": "Cliente desistiu"},
        )
        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, 5)
        self.assertEqual(
            MovimentoEstoque.objects.filter(
                tipo=MovimentoEstoque.Tipo.DEVOLUCAO
            ).count(),
            1,
        )

    def test_status_invalido_nao_altera_o_pedido(self):
        self.client.post(
            reverse("dashboard:pedido_atualizar_status",
                    kwargs={"numero": self.pedido.numero}),
            {"status": "inventado"},
        )
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, PedidoStatus.AGUARDANDO_PAGAMENTO)


class EstoqueNoPainelTests(TestCase):
    def setUp(self):
        self.staff = criar_staff()
        self.client.force_login(self.staff)
        self.produto = criar_produto(nome="Camiseta", estoque=5)
        self.variacao = primeira_variacao(self.produto)

    def test_registrar_entrada_pelo_painel(self):
        resposta = self.client.post(
            reverse("dashboard:estoque"),
            {
                "variacao": self.variacao.pk,
                "quantidade": "10",
                "motivo": "Reposição do fornecedor",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, 15)
        movimento = MovimentoEstoque.objects.get()
        self.assertEqual(movimento.tipo, MovimentoEstoque.Tipo.ENTRADA)
        self.assertEqual(movimento.usuario, self.staff)

    def test_entrada_com_quantidade_invalida_retorna_erros(self):
        resposta = self.client.post(
            reverse("dashboard:estoque"),
            {"variacao": self.variacao.pk, "quantidade": "0"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context["form"].errors)
        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, 5)


class CategoriaNoPainelTests(TestCase):
    def setUp(self):
        self.staff = criar_staff()
        self.client.force_login(self.staff)

    def test_criar_categoria(self):
        resposta = self.client.post(
            reverse("dashboard:categoria_nova"),
            {
                "nome": "Acessórios", "slug": "acessorios", "descricao": "",
                "icone": "bi-watch", "pai": "", "ordem": "10",
                "ativa": "on", "mostrar_home": "on",
                "meta_title": "", "meta_description": "",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(Categoria.objects.filter(nome="Acessórios").exists())

    def test_categoria_com_produtos_nao_e_excluida(self):
        criar_produto(nome="Preso na Categoria")
        categoria = Categoria.objects.get(nome="Masculino")
        resposta = self.client.post(
            reverse("dashboard:categoria_excluir", kwargs={"pk": categoria.pk})
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(Categoria.objects.filter(pk=categoria.pk).exists())

    def test_categoria_vazia_e_excluida(self):
        categoria = Categoria.objects.create(nome="Descartável")
        self.client.post(
            reverse("dashboard:categoria_excluir", kwargs={"pk": categoria.pk})
        )
        self.assertFalse(Categoria.objects.filter(pk=categoria.pk).exists())


class CupomNoPainelTests(TestCase):
    def setUp(self):
        self.staff = criar_staff()
        self.client.force_login(self.staff)

    def test_criar_cupom(self):
        resposta = self.client.post(
            reverse("dashboard:cupom_novo"),
            {
                "codigo": "blackfriday", "tipo": "percentual", "valor": "15",
                "pedido_minimo": "0", "inicio": "", "fim": "",
                "usos_max": "0", "ativo": "on", "descricao": "Promoção",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        cupom = CupomDesconto.objects.get()
        self.assertEqual(cupom.codigo, "BLACKFRIDAY")  # normalizado em maiúsculas

    def test_cupom_com_tipo_invalido_retorna_erros(self):
        resposta = self.client.post(
            reverse("dashboard:cupom_novo"),
            {
                "codigo": "ERRADO", "tipo": "inventado", "valor": "10",
                "pedido_minimo": "0", "inicio": "", "fim": "",
                "usos_max": "0", "ativo": "on",
            },
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context["form"].errors)
        self.assertFalse(CupomDesconto.objects.filter(codigo="ERRADO").exists())

    def test_excluir_cupom(self):
        cupom = CupomDesconto.objects.create(
            codigo="APAGA", tipo="fixo", valor=10, ativo=True
        )
        self.client.post(
            reverse("dashboard:cupom_excluir", kwargs={"pk": cupom.pk})
        )
        self.assertFalse(CupomDesconto.objects.filter(pk=cupom.pk).exists())


class ConfiguracoesTests(TestCase):
    def setUp(self):
        self.staff = criar_staff()
        self.client.force_login(self.staff)

    def test_atualizar_configuracoes_da_loja(self):
        loja = ConfiguracaoLoja.carregar()
        dados = {
            "nome_loja": "MYLLER Store",
            "banner_titulo": "Nova estação",
            "banner_subtitulo": "Coleção verão",
            "banner_texto": "",
            "banner_botao_texto": "Ver coleção",
            "banner_botao_link": "/produtos/",
            "frase_apresentacao": "Texto de apresentação.",
            "titulo_categorias": "Categorias",
            "titulo_mais_vendidos": "Mais vendidos",
            "titulo_novidades": "Novidades",
            "titulo_promocoes": "Promoções",
            "newsletter_titulo": "Newsletter",
            "newsletter_texto": "Receba novidades.",
            "email_contato": "contato@example.com",
            "telefone_contato": "(11) 4002-8922",
            "whatsapp": "1140028922",
            "horario_atendimento": "Seg a sex",
            "cnpj": "12.345.678/0001-90",
            "endereco_loja": "Av. Paulista, 1000",
            "instagram": "https://instagram.com/myller",
            "facebook": "",
            "tiktok": "",
            "youtube": "",
            "frete_valor_base": "19.90",
            "frete_prazo_dias": "7",
            "frete_gratis_acima": "399.00",
            "frete_por_kg": "4.50",
            "prazo_estimado_observacao": "Prazos estimados.",
            "meta_description": "Descrição SEO.",
        }
        resposta = self.client.post(reverse("dashboard:configuracoes"), dados)
        self.assertEqual(resposta.status_code, 302)
        loja.refresh_from_db()
        self.assertEqual(loja.nome_loja, "MYLLER Store")
        self.assertEqual(loja.whatsapp, "1140028922")

    def test_configuracoes_invalidas_re_renderizam_com_erros(self):
        resposta = self.client.post(
            reverse("dashboard:configuracoes"),
            {"nome_loja": "", "email_contato": "nao-e-email"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context["form"].errors)


class NewsletterNoPainelTests(TestCase):
    def test_listagem_de_inscritos(self):
        from core.models import NewsletterInscrito

        NewsletterInscrito.objects.create(email="fã@myller.com", nome="Fã")
        staff = criar_staff()
        self.client.force_login(staff)
        resposta = self.client.get(reverse("dashboard:newsletter"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "fã@myller.com")
