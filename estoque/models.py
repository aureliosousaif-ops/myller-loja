"""Modelos de controle de estoque."""
from django.db import models


class MovimentoEstoque(models.Model):
    """Histórico de entradas, saídas e ajustes de estoque."""

    class Tipo(models.TextChoices):
        ENTRADA = "entrada", "Entrada"
        SAIDA = "saida", "Saída"
        AJUSTE = "ajuste", "Ajuste"
        RESERVA = "reserva", "Reserva"
        DEVOLUCAO = "devolucao", "Devolução"

    variacao = models.ForeignKey(
        "produtos.Variacao", on_delete=models.CASCADE, related_name="movimentos",
        verbose_name="Variação",
    )
    tipo = models.CharField("Tipo", max_length=12, choices=Tipo.choices)
    quantidade = models.PositiveIntegerField("Quantidade")
    saldo_apos = models.PositiveIntegerField("Saldo após o movimento", default=0)
    motivo = models.CharField("Motivo", max_length=200, blank=True)
    pedido = models.ForeignKey(
        "pedidos.Pedido", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="movimentos_estoque", verbose_name="Pedido",
    )
    usuario = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="movimentos_estoque", verbose_name="Usuário",
    )
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Movimento de estoque"
        verbose_name_plural = "Movimentos de estoque"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.variacao} ({self.quantidade})"
