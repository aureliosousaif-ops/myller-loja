"""Modelos do carrinho de compras."""
from django.conf import settings
from django.db import models


class Carrinho(models.Model):
    """Carrinho persistido para usuário autenticado ou por chave de sessão."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name="carrinhos", verbose_name="Usuário",
    )
    chave_sessao = models.CharField(
        "Chave de sessão", max_length=64, blank=True, db_index=True
    )
    cupom_codigo = models.CharField("Cupom aplicado", max_length=60, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Carrinho"
        verbose_name_plural = "Carrinhos"
        ordering = ["-atualizado_em"]

    def __str__(self):
        dono = self.usuario.username if self.usuario else (self.chave_sessao or "anônimo")
        return f"Carrinho de {dono}"

    @property
    def itens_ativos(self):
        return self.itens.select_related("variacao__produto", "variacao__tamanho", "variacao__cor")

    @property
    def quantidade_total(self):
        return sum(item.quantidade for item in self.itens.all())

    @property
    def subtotal(self):
        return sum(item.total for item in self.itens.all())


class CarrinhoItem(models.Model):
    """Item do carrinho: produto em uma variação específica (tamanho + cor)."""

    carrinho = models.ForeignKey(Carrinho, on_delete=models.CASCADE, related_name="itens")
    variacao = models.ForeignKey(
        "produtos.Variacao", on_delete=models.CASCADE, related_name="itens_carrinho",
        verbose_name="Variação",
    )
    preco_unitario = models.DecimalField(
        "Preço unitário", max_digits=10, decimal_places=2,
        help_text="Preço congelado no momento da adição.",
    )
    quantidade = models.PositiveIntegerField("Quantidade", default=1)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Item do carrinho"
        verbose_name_plural = "Itens do carrinho"
        unique_together = ["carrinho", "variacao"]
        ordering = ["criado_em"]

    def __str__(self):
        return f"{self.variacao} x{self.quantidade}"

    @property
    def total(self):
        return self.preco_unitario * self.quantidade

    @property
    def estoque_disponivel(self):
        return self.variacao.estoque
