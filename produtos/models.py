"""Modelos de produtos, variações, imagens e avaliações."""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Tamanho(models.Model):
    """Tamanhos gerenciáveis pelo painel (PP, P, M, G, GG...)."""

    nome = models.CharField("Nome", max_length=30, unique=True)
    ordem = models.PositiveIntegerField("Ordem", default=0)
    ativo = models.BooleanField("Ativo", default=True)

    class Meta:
        verbose_name = "Tamanho"
        verbose_name_plural = "Tamanhos"
        ordering = ["ordem", "nome"]

    def __str__(self):
        return self.nome


class Cor(models.Model):
    """Cores gerenciáveis pelo painel."""

    nome = models.CharField("Nome", max_length=60, unique=True)
    codigo_hex = models.CharField("Código hexadecimal", max_length=7, default="#275B85")
    ativa = models.BooleanField("Ativa", default=True)

    class Meta:
        verbose_name = "Cor"
        verbose_name_plural = "Cores"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Produto(models.Model):
    """Produto da loja."""

    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        PUBLICADO = "publicado", "Publicado"

    nome = models.CharField("Nome", max_length=200)
    slug = models.SlugField("Slug", max_length=220, unique=True, blank=True)
    categoria = models.ForeignKey(
        "categorias.Categoria", on_delete=models.PROTECT, related_name="produtos",
        verbose_name="Categoria",
    )
    descricao = models.TextField("Descrição")
    resumo = models.CharField("Resumo", max_length=255, blank=True,
                              help_text="Texto curto exibido nos cards.")
    preco = models.DecimalField("Preço", max_digits=10, decimal_places=2)
    preco_promocional = models.DecimalField(
        "Preço promocional", max_digits=10, decimal_places=2, null=True, blank=True
    )
    sku = models.CharField("SKU", max_length=60, unique=True, blank=True)
    status = models.CharField("Status", max_length=12, choices=Status.choices, default=Status.RASCUNHO)
    destaque_home = models.BooleanField("Destaque na homepage", default=False)
    eh_novidade = models.BooleanField("Marcar como novidade", default=True)
    demonstracao = models.BooleanField(
        "Produto demonstrativo", default=False,
        help_text="Marcado automaticamente pelo seed: conteúdo fictício para demonstração da loja.",
    )
    peso_kg = models.DecimalField("Peso (kg)", max_digits=6, decimal_places=2, default=0.5)
    visualizacoes = models.PositiveIntegerField("Visualizações", default=0)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        ordering = ["-criado_em"]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nome)
            slug = base
            n = 1
            while Produto.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f"{base}-{n}"
            self.slug = slug
        if not self.sku:
            base = f"MYL-{slugify(self.nome)[:16].upper()}"
            sku = base
            n = 1
            while (
                Produto.objects.filter(sku=sku).exclude(pk=self.pk).exists()
                or not sku
            ):
                n += 1
                sku = f"{base}-{n}"
            self.sku = sku
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("produtos:detalhe", kwargs={"slug": self.slug})

    # ------------------------------------------------------------- Propriedades
    @property
    def publicado(self):
        return self.status == self.Status.PUBLICADO

    @property
    def em_promocao(self):
        return self.preco_promocional is not None and self.preco_promocional < self.preco

    @property
    def preco_final(self):
        return self.preco_promocional if self.em_promocao else self.preco

    @property
    def percentual_desconto(self):
        if not self.em_promocao:
            return 0
        return round((1 - float(self.preco_promocional) / float(self.preco)) * 100)

    @property
    def imagem_principal(self):
        img = self.imagens.order_by("ordem", "id").first()
        return img.imagem if img else None

    @property
    def imagem_secundaria(self):
        """Segunda imagem da galeria — usada no efeito hover dos cards."""
        imgs = list(self.imagens.order_by("ordem", "id")[:2])
        return imgs[1].imagem if len(imgs) > 1 else None

    @property
    def opcoes_rapidas(self):
        """Opções (tamanho, cor, id e estoque) para a compra rápida no card."""
        tamanhos, cores, mapa = [], [], {}
        vistos_t, vistos_c = set(), set()
        for v in self.variacoes.filter(ativa=True, estoque__gt=0).select_related(
            "tamanho", "cor"
        ):
            if v.tamanho.nome not in vistos_t:
                vistos_t.add(v.tamanho.nome)
                tamanhos.append(v.tamanho.nome)
            if v.cor.nome not in vistos_c:
                vistos_c.add(v.cor.nome)
                cores.append({"nome": v.cor.nome, "hex": v.cor.codigo_hex})
            mapa[f"{v.tamanho.nome}|{v.cor.nome}"] = {
                "id": v.pk, "estoque": v.estoque, "preco": str(v.preco_unitario),
            }
        return {
            "produto": self.get_absolute_url(),
            "nome": self.nome,
            "categoria": self.categoria.nome if self.categoria_id else "",
            "imagem": self.imagem_principal.url if self.imagem_principal else "",
            "preco": str(self.preco_final),
            "preco_original": str(self.preco) if self.em_promocao else "",
            "tamanhos": tamanhos,
            "cores": cores,
            "mapa": mapa,
        }

    @property
    def id_opcoes(self):
        """Identificador único do bloco JSON de compra rápida no card."""
        return f"opcoes-{self.pk}"

    @property
    def cores_card(self):
        """Amostras de cor (máx. 4) exibidas visualmente no card."""
        amostras = []
        vistos = set()
        for v in self.variacoes.filter(
            ativa=True, estoque__gt=0, cor__ativa=True
        ).select_related("cor")[:12]:
            if v.cor.nome in vistos:
                continue
            vistos.add(v.cor.nome)
            amostras.append({"nome": v.cor.nome, "hex": v.cor.codigo_hex})
            if len(amostras) >= 4:
                break
        return amostras

    @property
    def estoque_total(self):
        return sum(v.estoque for v in self.variacoes.filter(ativa=True))

    @property
    def disponivel(self):
        return self.publicado and self.estoque_total > 0

    @property
    def nota_media(self):
        return self.avaliacoes.filter(ativa=True).aggregate(models.Avg("nota"))["nota__avg"]

    @property
    def total_avaliacoes(self):
        return self.avaliacoes.filter(ativa=True).count()

    @property
    def tamanhos_disponiveis(self):
        ids = (
            self.variacoes.filter(ativa=True, estoque__gt=0)
            .values_list("tamanho_id", flat=True)
            .distinct()
        )
        return Tamanho.objects.filter(id__in=ids).order_by("ordem")

    @property
    def cores_disponiveis(self):
        ids = (
            self.variacoes.filter(ativa=True, estoque__gt=0)
            .values_list("cor_id", flat=True)
            .distinct()
        )
        return Cor.objects.filter(id__in=ids).order_by("nome")

    @property
    def tem_estoque_baixo(self):
        return 0 < self.estoque_total <= 5


class ProdutoImagem(models.Model):
    """Galeria de imagens do produto."""

    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="imagens")
    imagem = models.ImageField("Imagem", upload_to="produtos/")
    alt = models.CharField("Texto alternativo", max_length=200, blank=True)
    ordem = models.PositiveIntegerField("Ordem", default=0)

    class Meta:
        verbose_name = "Imagem do produto"
        verbose_name_plural = "Imagens dos produtos"
        ordering = ["ordem", "id"]

    def __str__(self):
        return f"Imagem de {self.produto.nome}"

    @property
    def texto_alt(self):
        return self.alt or self.produto.nome


class Variacao(models.Model):
    """Variação de produto (tamanho + cor) com controle individual de estoque."""

    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="variacoes")
    tamanho = models.ForeignKey(Tamanho, on_delete=models.PROTECT, related_name="variacoes")
    cor = models.ForeignKey(Cor, on_delete=models.PROTECT, related_name="variacoes")
    sku = models.CharField("SKU da variação", max_length=80, blank=True)
    preco_adicional = models.DecimalField(
        "Preço adicional", max_digits=8, decimal_places=2, default=0
    )
    estoque = models.PositiveIntegerField("Estoque", default=0)
    ativa = models.BooleanField("Ativa", default=True)

    class Meta:
        verbose_name = "Variação de produto"
        verbose_name_plural = "Variações de produto"
        unique_together = ["produto", "tamanho", "cor"]
        ordering = ["produto", "tamanho__ordem", "cor__nome"]

    def __str__(self):
        return f"{self.produto.nome} — {self.tamanho}/{self.cor}"

    @property
    def disponivel(self):
        return self.ativa and self.estoque > 0

    @property
    def preco_unitario(self):
        return self.produto.preco_final + self.preco_adicional


class Avaliacao(models.Model):
    """Avaliação de produto por cliente autenticado."""

    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="avaliacoes")
    cliente = models.ForeignKey(
        "clientes.Cliente", on_delete=models.CASCADE, related_name="avaliacoes"
    )
    nota = models.PositiveSmallIntegerField(
        "Nota", validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comentario = models.TextField("Comentário")
    ativa = models.BooleanField("Ativa", default=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Avaliação"
        verbose_name_plural = "Avaliações"
        unique_together = ["produto", "cliente"]
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.produto.nome} — {self.nota}★ ({self.cliente})"
