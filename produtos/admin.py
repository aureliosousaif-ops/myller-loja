from django.contrib import admin

from produtos.models import Avaliacao, Cor, Produto, ProdutoImagem, Tamanho, Variacao


class ProdutoImagemInline(admin.TabularInline):
    model = ProdutoImagem
    extra = 2
    fields = ["imagem", "alt", "ordem"]


class VariacaoInline(admin.TabularInline):
    model = Variacao
    extra = 1
    fields = ["tamanho", "cor", "sku", "preco_adicional", "estoque", "ativa"]


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ["nome", "categoria", "preco", "preco_promocional", "status", "estoque_resumo", "criado_em"]
    list_filter = ["status", "categoria", "destaque_home", "eh_novidade"]
    search_fields = ["nome", "sku", "descricao"]
    prepopulated_fields = {"slug": ("nome",)}
    inlines = [ProdutoImagemInline, VariacaoInline]
    actions = ["publicar", "despublicar"]

    @admin.display(description="Estoque")
    def estoque_resumo(self, obj):
        return obj.estoque_total

    @admin.action(description="Publicar produtos selecionados")
    def publicar(self, request, queryset):
        queryset.update(status=Produto.Status.PUBLICADO)

    @admin.action(description="Despublicar produtos selecionados")
    def despublicar(self, request, queryset):
        queryset.update(status=Produto.Status.RASCUNHO)


@admin.register(Tamanho)
class TamanhoAdmin(admin.ModelAdmin):
    list_display = ["nome", "ordem", "ativo"]
    list_editable = ["ordem", "ativo"]


@admin.register(Cor)
class CorAdmin(admin.ModelAdmin):
    list_display = ["nome", "codigo_hex", "ativa"]
    list_editable = ["codigo_hex", "ativa"]


@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = ["produto", "cliente", "nota", "ativa", "criado_em"]
    list_filter = ["nota", "ativa"]
