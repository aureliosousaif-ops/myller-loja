"""URLs do projeto MYLLER."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as servir_arquivo

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", include("core.urls")),
    path("", include("usuarios.urls")),
    path("", include("clientes.urls")),
    path("", include("produtos.urls")),
    path("", include("carrinho.urls")),
    path("", include("pedidos.urls")),
    path("", include("pagamentos.urls")),
    path("", include("favoritos.urls")),
    path("", include("dashboard.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif settings.SERVE_MEDIA:
    # Produção: a loja serve as imagens de produtos/categorias via Django
    # (ver settings.SERVE_MEDIA — pendência de migração para S3).
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            servir_arquivo,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]

# Páginas de erro customizadas em desenvolvimento.
handler404 = "core.views.pagina_nao_encontrada"
handler500 = "core.views.erro_interno"
