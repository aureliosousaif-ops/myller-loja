"""Modelos de pedidos, cupons e histórico de status."""
from django.conf import settings
from django.db import models
from django.urls import reverse


class PedidoStatus(models.TextChoices):
    AGUARDANDO_PAGAMENTO = "aguardando_pagamento", "Aguardando pagamento"
    PAGAMENTO_APROVADO = "pagamento_aprovado", "Pagamento aprovado"
    EM_PREPARACAO = "em_preparacao", "Em preparação"
    ENVIADO = "enviado", "Enviado"
    ENTREGUE = "entregue", "Entregue"
    CANCELADO = "cancelado", "Cancelado"


class CupomDesconto(models.Model):
    """Cupom de desconto promocional."""

    class Tipo(models.TextChoices):
        PERCENTUAL = "percentual", "Percentual"
        FIXO = "fixo", "Valor fixo"

    codigo = models.CharField("Código", max_length=40, unique=True)
    tipo = models.CharField("Tipo", max_length=12, choices=Tipo.choices, default=Tipo.PERCENTUAL)
    valor = models.DecimalField(
        "Valor", max_digits=8, decimal_places=2,
        help_text="Percentual (ex.: 10 = 10%) ou valor em R$ para cupom fixo.",
    )
    pedido_minimo = models.DecimalField(
        "Pedido mínimo (R$)", max_digits=10, decimal_places=2, default=0
    )
    inicio = models.DateTimeField("Válido a partir de", null=True, blank=True)
    fim = models.DateTimeField("Válido até", null=True, blank=True)
    usos_max = models.PositiveIntegerField("Máximo de usos (0 = ilimitado)", default=0)
    usos = models.PositiveIntegerField("Usos", default=0, editable=False)
    ativo = models.BooleanField("Ativo", default=True)
    descricao = models.CharField("Descrição", max_length=200, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cupom de desconto"
        verbose_name_plural = "Cupons de desconto"
        ordering = ["-criado_em"]

    def __str__(self):
        return self.codigo

    def save(self, *args, **kwargs):
        self.codigo = self.codigo.upper().strip()
        super().save(*args, **kwargs)

    def validar(self, subtotal):
        """Retorna mensagem de erro ou None se o cupom for válido."""
        from django.utils import timezone

        if not self.ativo:
            return "Este cupom está desativado."
        agora = timezone.now()
        if self.inicio and agora < self.inicio:
            return "Este cupom ainda não está válido."
        if self.fim and agora > self.fim:
            return "Este cupom expirou."
        if self.usos_max and self.usos >= self.usos_max:
            return "Este cupom atingiu o limite de usos."
        if self.pedido_minimo and subtotal < self.pedido_minimo:
            return (
                f"Pedido mínimo de R$ {self.pedido_minimo:.2f} para usar este cupom."
            )
        return None

    def calcular_desconto(self, subtotal):
        """Valor do desconto para um dado subtotal."""
        if self.tipo == self.Tipo.PERCENTUAL:
            desconto = subtotal * (self.valor / 100)
        else:
            desconto = self.valor
        desconto = min(desconto, subtotal)
        return max(desconto, 0)


class Pedido(models.Model):
    """Pedido da loja (compra finalizada no checkout)."""

    numero = models.CharField("Número do pedido", max_length=20, unique=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="pedidos", verbose_name="Usuário",
    )
    cliente = models.ForeignKey(
        "clientes.Cliente", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="pedidos", verbose_name="Cliente",
    )
    chave_sessao = models.CharField("Chave de sessão (pedido visitante)", max_length=64, blank=True)

    # Identificação
    nome = models.CharField("Nome completo", max_length=160)
    email = models.EmailField("E-mail")
    telefone = models.CharField("Telefone", max_length=20)

    # Endereço de entrega (snapshot)
    cep = models.CharField("CEP", max_length=9)
    logradouro = models.CharField("Logradouro", max_length=200)
    endereco_numero = models.CharField("Número", max_length=20, blank=True)
    complemento = models.CharField("Complemento", max_length=120, blank=True)
    bairro = models.CharField("Bairro", max_length=100)
    cidade = models.CharField("Cidade", max_length=100)
    estado = models.CharField("Estado (UF)", max_length=2)

    # Valores
    subtotal = models.DecimalField("Subtotal", max_digits=10, decimal_places=2, default=0)
    frete = models.DecimalField("Frete", max_digits=10, decimal_places=2, default=0)
    desconto = models.DecimalField("Desconto", max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField("Total", max_digits=10, decimal_places=2, default=0)
    cupom = models.ForeignKey(
        CupomDesconto, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="pedidos", verbose_name="Cupom",
    )

    status = models.CharField(
        "Status", max_length=30, choices=PedidoStatus.choices,
        default=PedidoStatus.AGUARDANDO_PAGAMENTO,
    )
    metodo_entrega = models.CharField("Método de entrega", max_length=60, blank=True)
    observacao = models.TextField("Observação", blank=True)
    prazo_entrega = models.CharField("Prazo de entrega", max_length=80, blank=True)

    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name="pedidos_alterados", verbose_name="Alterado por",
    )

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Pedido {self.numero} — {self.nome}"

    def get_absolute_url(self):
        return reverse("pedidos:detalhe", kwargs={"numero": self.numero})

    @property
    def total_itens(self):
        return sum(item.quantidade for item in self.itens.all())

    @property
    def pode_ser_cancelado(self):
        return self.status in (
            PedidoStatus.AGUARDANDO_PAGAMENTO,
            PedidoStatus.PAGAMENTO_APROVADO,
            PedidoStatus.EM_PREPARACAO,
        )

    @property
    def status_atual_classe(self):
        return {
            PedidoStatus.AGUARDANDO_PAGAMENTO: "warning",
            PedidoStatus.PAGAMENTO_APROVADO: "info",
            PedidoStatus.EM_PREPARACAO: "primary",
            PedidoStatus.ENVIADO: "myller-blue-light",
            PedidoStatus.ENTREGUE: "success",
            PedidoStatus.CANCELADO: "danger",
        }.get(self.status, "secondary")

    @property
    def progresso_etapas(self):
        """Percentual aproximado do rastreamento do pedido."""
        ordem = [
            PedidoStatus.AGUARDANDO_PAGAMENTO,
            PedidoStatus.PAGAMENTO_APROVADO,
            PedidoStatus.EM_PREPARACAO,
            PedidoStatus.ENVIADO,
            PedidoStatus.ENTREGUE,
        ]
        if self.status == PedidoStatus.CANCELADO:
            return 0
        if self.status in ordem:
            return int((ordem.index(self.status) + 1) / len(ordem) * 100)
        return 0


class PedidoItem(models.Model):
    """Item comprado (snapshot do produto no momento da compra)."""

    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="itens")
    produto = models.ForeignKey(
        "produtos.Produto", on_delete=models.SET_NULL, null=True,
        related_name="pedidos", verbose_name="Produto",
    )
    variacao = models.ForeignKey(
        "produtos.Variacao", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="pedidos", verbose_name="Variação",
    )
    nome = models.CharField("Nome do produto", max_length=200)
    tamanho_nome = models.CharField("Tamanho", max_length=30, blank=True)
    cor_nome = models.CharField("Cor", max_length=60, blank=True)
    sku = models.CharField("SKU", max_length=80, blank=True)
    preco_unitario = models.DecimalField("Preço unitário", max_digits=10, decimal_places=2)
    quantidade = models.PositiveIntegerField("Quantidade")
    subtotal = models.DecimalField("Subtotal", max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Item do pedido"
        verbose_name_plural = "Itens do pedido"
        ordering = ["id"]

    def __str__(self):
        return f"{self.nome} x{self.quantidade}"

    @property
    def variacao_display(self):
        partes = [p for p in [self.tamanho_nome, self.cor_nome] if p]
        return " / ".join(partes)


class HistoricoStatus(models.Model):
    """Histórico de alterações de status do pedido (acompanhamento)."""

    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="historico")
    status = models.CharField("Status", max_length=30, choices=PedidoStatus.choices)
    observacao = models.CharField("Observação", max_length=240, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, verbose_name="Usuário",
    )
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Histórico de status"
        verbose_name_plural = "Históricos de status"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.pedido.numero} → {self.get_status_display()}"
