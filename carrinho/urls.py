from django.urls import path

from carrinho import views

app_name = "carrinho"

urlpatterns = [
    path("carrinho/", views.pagina_carrinho, name="pagina"),
    path("carrinho/adicionar/", views.adicionar, name="adicionar"),
    path("carrinho/atualizar/", views.atualizar, name="atualizar"),
    path("carrinho/limpar/", views.limpar, name="limpar"),
    path("carrinho/remover/", views.remover, name="remover"),
    path("carrinho/cupom/", views.aplicar_cupom, name="cupom"),
    path("api/frete/", views.api_frete, name="api_frete"),
]
