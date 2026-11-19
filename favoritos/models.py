"""Modelo de favoritos (lista de desejos)."""
from django.conf import settings
from django.db import models


class Favorito(models.Model):
    """Produto favoritado por um usuário autenticado."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="favoritos", verbose_name="Usuário",
    )
    produto = models.ForeignKey(
        "produtos.Produto", on_delete=models.CASCADE,
        related_name="favoritado_por", verbose_name="Produto",
    )
    criado_em = models.DateTimeField("Adicionado em", auto_now_add=True)

    class Meta:
        verbose_name = "Favorito"
        verbose_name_plural = "Favoritos"
        unique_together = ["usuario", "produto"]
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.usuario.username} ❤ {self.produto.nome}"
