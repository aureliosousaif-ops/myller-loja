"""Serviço de estoque: baixa atômica para evitar venda de item indisponível."""
from django.db import transaction
from django.db.models import F

from estoque.models import MovimentoEstoque
from produtos.models import Variacao


class EstoqueInsuficiente(Exception):
    """Exceção levantada quando não há estoque suficiente."""

    def __init__(self, variacao, solicitado, disponivel):
        self.variacao = variacao
        self.solicitado = solicitado
        self.disponivel = disponivel
        super().__init__(
            f"Estoque insuficiente para {variacao}: solicitado {solicitado}, "
            f"disponível {disponivel}."
        )


def baixar_estoque(pedido, itens):
    """
    Baixa o estoque das variações dentro de uma transação atômica.

    `itens` é uma lista de objetos PedidoItem.
    Levanta EstoqueInsuficiente e reverte tudo em caso de falha.
    """
    with transaction.atomic():
        for item in itens:
            if not item.variacao_id:
                continue
            variacao = Variacao.objects.select_for_update().get(pk=item.variacao_id)
            if variacao.estoque < item.quantidade:
                raise EstoqueInsuficiente(variacao, item.quantidade, variacao.estoque)
            Variacao.objects.filter(pk=variacao.pk).update(
                estoque=F("estoque") - item.quantidade
            )
            MovimentoEstoque.objects.create(
                variacao=variacao,
                tipo=MovimentoEstoque.Tipo.SAIDA,
                quantidade=item.quantidade,
                saldo_apos=max(variacao.estoque - item.quantidade, 0),
                motivo=f"Venda — pedido {pedido.numero}",
                pedido=pedido,
            )


def repor_estoque(pedido):
    """Repor estoque em caso de cancelamento do pedido."""
    with transaction.atomic():
        for item in pedido.itens.all():
            if not item.variacao_id:
                continue
            variacao = Variacao.objects.select_for_update().get(pk=item.variacao_id)
            Variacao.objects.filter(pk=variacao.pk).update(
                estoque=F("estoque") + item.quantidade
            )
            MovimentoEstoque.objects.create(
                variacao=variacao,
                tipo=MovimentoEstoque.Tipo.DEVOLUCAO,
                quantidade=item.quantidade,
                saldo_apos=variacao.estoque + item.quantidade,
                motivo=f"Cancelamento — pedido {pedido.numero}",
                pedido=pedido,
            )


def registrar_entrada(variacao, quantidade, motivo="", usuario=None):
    """Registrar entrada manual de estoque (reposição)."""
    with transaction.atomic():
        variacao = Variacao.objects.select_for_update().get(pk=variacao.pk)
        Variacao.objects.filter(pk=variacao.pk).update(
            estoque=F("estoque") + quantidade
        )
        movimento = MovimentoEstoque.objects.create(
            variacao=variacao,
            tipo=MovimentoEstoque.Tipo.ENTRADA,
            quantidade=quantidade,
            saldo_apos=variacao.estoque + quantidade,
            motivo=motivo or "Entrada manual",
            usuario=usuario,
        )
        return movimento


def registrar_saida(variacao, quantidade, motivo="", usuario=None):
    """Registrar saída manual de estoque (ajuste, perda, amostra...).

    Atômico e seguro para pedidos simultâneos: trava a linha e valida o
    saldo dentro da transação, nunca deixando o estoque ficar negativo.
    """
    if quantidade <= 0:
        raise EstoqueInsuficiente(variacao, quantidade, variacao.estoque)
    with transaction.atomic():
        variacao = Variacao.objects.select_for_update().get(pk=variacao.pk)
        if variacao.estoque < quantidade:
            raise EstoqueInsuficiente(variacao, quantidade, variacao.estoque)
        Variacao.objects.filter(pk=variacao.pk).update(
            estoque=F("estoque") - quantidade
        )
        movimento = MovimentoEstoque.objects.create(
            variacao=variacao,
            tipo=MovimentoEstoque.Tipo.SAIDA,
            quantidade=quantidade,
            saldo_apos=variacao.estoque - quantidade,
            motivo=motivo or "Saída manual",
            usuario=usuario,
        )
        return movimento
