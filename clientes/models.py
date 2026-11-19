"""Modelos de clientes e endereços."""
from django.conf import settings
from django.db import models


class Cliente(models.Model):
    """Perfil do cliente vinculado ao usuário do Django."""

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="cliente", verbose_name="Usuário",
    )
    cpf = models.CharField("CPF", max_length=14, blank=True)
    telefone = models.CharField("Telefone", max_length=20, blank=True)
    data_nascimento = models.DateField("Data de nascimento", null=True, blank=True)
    foto = models.ImageField("Foto", upload_to="clientes/fotos/", blank=True)
    aceita_newsletter = models.BooleanField("Receber novidades", default=True)
    criado_em = models.DateTimeField("Cadastrado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["-criado_em"]

    def __str__(self):
        return self.nome_completo or self.usuario.username

    @property
    def nome_completo(self):
        return f"{self.usuario.first_name} {self.usuario.last_name}".strip()

    @property
    def nome_exibicao(self):
        return self.nome_completo or self.usuario.username

    @property
    def total_pedidos(self):
        return self.pedidos.count()

    @property
    def total_gasto(self):
        from django.db.models import Sum

        from pedidos.models import Pedido, PedidoStatus

        valores = self.pedidos.exclude(status=PedidoStatus.CANCELADO).aggregate(
            total=Sum("total")
        )
        return valores["total"] or 0

    def endereco_padrao(self):
        return self.enderecos.filter(padrao=True).first() or self.enderecos.first()


class Endereco(models.Model):
    """Endereço de entrega do cliente."""

    ESTADOS_BR = [
        (uf, uf)
        for uf in [
            "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
            "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
            "RS", "RO", "RR", "SC", "SP", "SE", "TO",
        ]
    ]

    cliente = models.ForeignKey(
        Cliente, on_delete=models.CASCADE, related_name="enderecos",
        verbose_name="Cliente",
    )
    apelido = models.CharField("Apelido (ex.: Casa)", max_length=40, default="Principal")
    destinatario = models.CharField("Nome do destinatário", max_length=160, blank=True)
    cep = models.CharField("CEP", max_length=9)
    logradouro = models.CharField("Logradouro", max_length=200)
    numero = models.CharField("Número", max_length=20)
    complemento = models.CharField("Complemento", max_length=120, blank=True)
    bairro = models.CharField("Bairro", max_length=100)
    cidade = models.CharField("Cidade", max_length=100)
    estado = models.CharField("Estado (UF)", max_length=2, choices=ESTADOS_BR)
    padrao = models.BooleanField("Endereço padrão", default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Endereço"
        verbose_name_plural = "Endereços"
        ordering = ["-padrao", "-criado_em"]

    def __str__(self):
        return f"{self.logradouro}, {self.numero} — {self.cidade}/{self.estado}"

    @property
    def linha_completa(self):
        comp = f" — {self.complemento}" if self.complemento else ""
        return (
            f"{self.logradouro}, {self.numero}{comp} — {self.bairro}, "
            f"{self.cidade}/{self.estado}, CEP {self.cep}"
        )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.padrao:
            Endereco.objects.filter(cliente=self.cliente).exclude(pk=self.pk).update(
                padrao=False
            )
