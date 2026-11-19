from django.urls import path

from clientes import views

app_name = "clientes"

urlpatterns = [
    path("conta/", views.perfil, name="perfil"),
    path("conta/dados/", views.editar_perfil, name="editar_perfil"),
    path("conta/enderecos/", views.enderecos, name="enderecos"),
    path("conta/enderecos/novo/", views.endereco_novo, name="endereco_novo"),
    path("conta/enderecos/<int:pk>/editar/", views.endereco_editar, name="endereco_editar"),
    path("conta/enderecos/<int:pk>/excluir/", views.endereco_excluir, name="endereco_excluir"),
    path("conta/enderecos/<int:pk>/padrao/", views.endereco_padrao, name="endereco_padrao"),
    path("conta/pedidos/", views.meus_pedidos, name="meus_pedidos"),
    path("conta/senha/", views.AlterarSenhaView.as_view(), name="alterar_senha"),
    # Aliases canônicos da área do cliente (/minha-conta/...)
    path("minha-conta/", views.perfil, name="perfil"),
    path("minha-conta/perfil/", views.editar_perfil, name="editar_perfil"),
    path("minha-conta/enderecos/", views.enderecos, name="enderecos"),
    path("minha-conta/pedidos/", views.meus_pedidos, name="meus_pedidos"),
    path("minha-conta/senha/", views.AlterarSenhaView.as_view(), name="alterar_senha"),
]
