"""Modelos de categorias."""
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Categoria(models.Model):
    """Categoria hierárquica de produtos (ex.: Feminino > Vestidos)."""

    nome = models.CharField("Nome", max_length=100, unique=True)
    slug = models.SlugField("Slug", max_length=120, unique=True, blank=True)
    descricao = models.TextField("Descrição", blank=True)
    imagem = models.ImageField("Imagem", upload_to="categorias/", blank=True)
    icone = models.CharField(
        "Ícone (Bootstrap Icons)", max_length=60, blank=True,
        help_text="Ex.: bi-shirt, bi-gender-ambiguous",
    )
    pai = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True,
        related_name="filhas", verbose_name="Categoria pai",
    )
    ordem = models.PositiveIntegerField("Ordem de exibição", default=0)
    ativa = models.BooleanField("Ativa", default=True)
    mostrar_home = models.BooleanField("Exibir na homepage", default=True)
    meta_title = models.CharField("Meta title", max_length=160, blank=True)
    meta_description = models.CharField("Meta description", max_length=160, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        ordering = ["ordem", "nome"]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nome)
            slug = base
            n = 1
            while Categoria.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f"{base}-{n}"
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("produtos:categoria", kwargs={"slug": self.slug})

    @property
    def total_produtos(self):
        from produtos.models import Produto

        return Produto.objects.filter(
            categoria=self, status=Produto.Status.PUBLICADO
        ).count()

    @property
    def categorias_filhas(self):
        return self.filhas.filter(ativa=True)
