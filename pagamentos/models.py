"""Modelo de pagamentos vinculados aos pedidos."""
from django.db import models


class Pagamento(models.Model):
    """Registro de pagamento (pode haver várias tentativas por pedido)."""

    class Gateway(models.TextChoices):
        MERCADOPAGO = "mercadopago", "Mercado Pago"
        STRIPE = "stripe", "Stripe"
        NENHUM = "nenhum", "Não configurado"

    class Metodo(models.TextChoices):
        PIX = "pix", "PIX"
        CARTAO = "cartao", "Cartão"
        BOLETO = "boleto", "Boleto"
        OUTRO = "outro", "Outro"

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        APROVADO = "aprovado", "Aprovado"
        RECUSADO = "recusado", "Recusado"
        EXPIRADO = "expirado", "Expirado"
        ESTORNADO = "estornado", "Estornado"

    pedido = models.ForeignKey(
        "pedidos.Pedido", on_delete=models.CASCADE,
        related_name="pagamentos", verbose_name="Pedido",
    )
    gateway = models.CharField(
        "Gateway", max_length=20, choices=Gateway.choices, default=Gateway.NENHUM
    )
    metodo = models.CharField(
        "Método", max_length=12, choices=Metodo.choices, default=Metodo.OUTRO
    )
    status = models.CharField(
        "Status", max_length=12, choices=Status.choices, default=Status.PENDENTE
    )
    valor = models.DecimalField("Valor", max_digits=10, decimal_places=2)
    externo_id = models.CharField(
        "ID externo", max_length=160, blank=True, db_index=True,
        help_text="ID da transação no gateway.",
    )
    link_pagamento = models.URLField("Link de pagamento", blank=True)
    codigo_pix = models.TextField("Código Pix (copia e cola)", blank=True)
    payload = models.JSONField("Resposta do gateway", default=dict, blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Pagamento"
        verbose_name_plural = "Pagamentos"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Pagamento {self.get_gateway_display()} — {self.pedido.numero} ({self.get_status_display()})"

    @property
    def status_classe(self):
        return {
            self.Status.PENDENTE: "warning",
            self.Status.APROVADO: "success",
            self.Status.RECUSADO: "danger",
            self.Status.EXPIRADO: "secondary",
            self.Status.ESTORNADO: "info",
        }.get(self.status, "secondary")
