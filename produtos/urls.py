from django.urls import path

from produtos import views

app_name = "produtos"

urlpatterns = [
    path("produtos/", views.lista_produtos, name="lista"),
    path("categoria/<slug:slug>/", views.categoria_detalhe, name="categoria"),
    path("produto/<slug:slug>/", views.detalhe_produto, name="detalhe"),
    path("produto/<slug:slug>/avaliar/", views.avaliar, name="avaliar"),
    path("busca/", views.busca, name="busca"),
    path("api/busca/", views.api_busca, name="api_busca"),
]
