from django.contrib import admin

from categorias.models import Categoria


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ["nome", "pai", "ordem", "ativa", "mostrar_home"]
    list_filter = ["ativa", "mostrar_home"]
    prepopulated_fields = {"slug": ("nome",)}
    search_fields = ["nome"]
