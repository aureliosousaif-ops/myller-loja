from django.contrib import admin

from core.models import ConfiguracaoLoja, NewsletterInscrito, PaginaInstitucional


@admin.register(ConfiguracaoLoja)
class ConfiguracaoLojaAdmin(admin.ModelAdmin):
    list_display = ["nome_loja", "email_contato", "whatsapp", "atualizado_em"]


@admin.register(NewsletterInscrito)
class NewsletterInscritoAdmin(admin.ModelAdmin):
    list_display = ["email", "nome", "ativo", "criado_em"]
    list_filter = ["ativo"]
    search_fields = ["email", "nome"]


@admin.register(PaginaInstitucional)
class PaginaInstitucionalAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("titulo",)}
    list_display = ["titulo", "slug", "ativa"]
