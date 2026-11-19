"""Testes do app estoque: baixa atômica, reposição e movimentos."""
from django.test import TestCase

from estoque.models import MovimentoEstoque
from estoque.services import (
    EstoqueInsuficiente,
    baixar_estoque,
    registrar_entrada,
    repor_estoque,
)
from myller.utilitarios_teste import criar_produto, primeira_variacao
from pedidos.models import HistoricoStatus, Pedido, PedidoItem, PedidoStatus
from pedidos.services import alterar_status_pedido, criar_pedido

def _item_pedido(pedido, variacao, quantidade):
    return PedidoItem(
        pedido=pedido,
        produto=variacao.produto,
        variacao=variacao,
        nome=variacao.produto.nome,
        tamanho_nome=variacao.tamanho.nome,
        cor_nome=variacao.cor.nome,
        sku=variacao.produto.sku,
        preco_unitario=variacao.preco_unitario,
        quantidade=quantidade,
        subtotal=variacao.preco_unitario * quantidade,
    )


class BaixaDeEstoqueTests(TestCase):
    def setUp(self):
        self.produto = criar_produto(nome="Camiseta", estoque=10)
        self.variacao = primeira_variacao(self.produto)

    def _pedido(self):
        return Pedido.objects.create(
            numero="MYL-TESTE-001", nome="Teste", email="t@example.com",
            telefone="(11) 99999-0000", cep="01310-100",
            logradouro="Rua A", endereco_numero="1", bairro="Centro",
            cidade="São Paulo", estado="SP", total=100,
        )

    def test_baixa_decrementa_o_estoque(self):
        pedido = self._pedido()
        baixar_estoque(pedido, [_item_pedido(pedido, self.variacao, 3)])
        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, 7)

    def test_baixa_registra_movimento_de_saida(self):
        pedido = self._pedido()
        baixar_estoque(pedido, [_item_pedido(pedido, self.variacao, 3)])
        movimento = MovimentoEstoque.objects.get()
        self.assertEqual(movimento.tipo, MovimentoEstoque.Tipo.SAIDA)
        self.assertEqual(movimento.quantidade, 3)
        self.assertEqual(movimento.saldo_apos, 7)
        self.assertEqual(movimento.pedido, pedido)

    def test_estoque_insuficiente_leanta_excecao_sem_baixar_nada(self):
        pedido = self._pedido()
        with self.assertRaises(EstoqueInsuficiente) as contexto:
            baixar_estoque(pedido, [_item_pedido(pedido, self.variacao, 50)])
        self.assertEqual(contexto.exception.disponivel, 10)
        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, 10)
        self.assertEqual(MovimentoEstoque.objects.count(), 0)

    def test_repor_estoque_devolve_a_quantidade(self):
        pedido = self._pedido()
        baixar_estoque(pedido, [_item_pedido(pedido, self.variacao, 4)])
        item = _item_pedido(pedido, self.variacao, 4)
        item.save()
        repor_estoque(pedido)
        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, 10)
        self.assertEqual(
            MovimentoEstoque.objects.filter(
                tipo=MovimentoEstoque.Tipo.DEVOLUCAO
            ).count(),
            1,
        )

    def test_registrar_entrada_aumenta_saldo(self):
        registrar_entrada(self.variacao, 5, motivo="Reposição de fornecedor")
        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, 15)
        movimento = MovimentoEstoque.objects.get()
        self.assertEqual(movimento.tipo, MovimentoEstoque.Tipo.ENTRADA)


class IntegracaoPedidoEstoqueTests(TestCase):
    def setUp(self):
        self.produto = criar_produto(nome="Camiseta", estoque=8)
        self.variacao = primeira_variacao(self.produto)

    def _dados(self, quantidade=2):
        preco = self.variacao.preco_unitario * quantidade
        return {
            "nome": "Comprador", "email": "compra@example.com",
            "telefone": "(11) 98888-8888", "cep": "01310-100",
            "logradouro": "Av. Paulista", "numero": "100",
            "complemento": "", "bairro": "Bela Vista",
            "cidade": "São Paulo", "estado": "SP",
            "subtotal": preco, "frete": 0, "desconto": 0, "total": preco,
            "metodo_entrega": "Entrega estimada", "prazo_entrega": "7 dias úteis",
            "observacao": "",
        }, quantidade

    def test_criar_pedido_baixa_estoque_e_registra_historico(self):
        dados, quantidade = self._dados()
        pedido = Pedido.objects.create(
            numero="MYL-INT-1", nome=dados["nome"], email=dados["email"],
            telefone=dados["telefone"], cep=dados["cep"],
            logradouro=dados["logradouro"], endereco_numero=dados["numero"],
            bairro=dados["bairro"], cidade=dados["cidade"],
            estado=dados["estado"], total=dados["total"],
        )
        item = _item_pedido(pedido, self.variacao, quantidade)
        baixar_estoque(pedido, [item])
        item.save()

        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, 6)
        self.assertEqual(pedido.status, PedidoStatus.AGUARDANDO_PAGAMENTO)

    def test_cancelamento_devolve_o_estoque(self):
        dados, quantidade = self._dados(quantidade=3)
        pedido = Pedido.objects.create(
            numero="MYL-INT-2", nome=dados["nome"], email=dados["email"],
            telefone=dados["telefone"], cep=dados["cep"],
            logradouro=dados["logradouro"], endereco_numero=dados["numero"],
            bairro=dados["bairro"], cidade=dados["cidade"],
            estado=dados["estado"], total=dados["total"],
        )
        item = _item_pedido(pedido, self.variacao, quantidade)
        baixar_estoque(pedido, [item])
        item.save()
        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, 5)

        alterar_status_pedido(
            pedido, PedidoStatus.CANCELADO, observacao="Teste de cancelamento"
        )
        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, 8)
        self.assertTrue(
            HistoricoStatus.objects.filter(
                pedido=pedido, status=PedidoStatus.CANCELADO
            ).exists()
        )

    def test_estoque_insuficiente_impede_o_pedido(self):
        from carrinho.models import Carrinho, CarrinhoItem

        carrinho = Carrinho.objects.create(chave_sessao="sessao-teste")
        CarrinhoItem.objects.create(
            carrinho=carrinho, variacao=self.variacao,
            preco_unitario=self.variacao.preco_unitario, quantidade=99,
        )
        dados, _ = self._dados()
        pedido, erro = criar_pedido(carrinho=carrinho, dados=dados)
        self.assertIsNone(pedido)
        self.assertIn("Estoque insuficiente", erro)
        self.variacao.refresh_from_db()
        self.assertEqual(self.variacao.estoque, 8)
        self.assertEqual(Pedido.objects.count(), 0)
