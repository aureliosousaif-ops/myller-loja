from django.urls import path

from dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("painel/", views.home, name="home"),
    # Produtos
    path("painel/produtos/", views.produtos_lista, name="produtos"),
    path("painel/produtos/novo/", views.produto_form, name="produto_novo"),
    path("painel/produtos/<int:pk>/editar/", views.produto_form, name="produto_editar"),
    path("painel/produtos/<int:pk>/excluir/", views.produto_excluir, name="produto_excluir"),
    path("painel/produtos/<int:pk>/publicar/", views.produto_toggle, name="produto_toggle"),
    # Pedidos
    path("painel/pedidos/", views.pedidos_lista, name="pedidos"),
    path("painel/pedidos/<str:numero>/", views.pedido_detalhe, name="pedido_detalhe"),
    path(
        "painel/pedidos/<str:numero>/status/",
        views.pedido_atualizar_status,
        name="pedido_atualizar_status",
    ),
    # Clientes
    path("painel/clientes/", views.clientes_lista, name="clientes"),
    path("painel/clientes/<int:pk>/", views.cliente_detalhe, name="cliente_detalhe"),
    path("painel/clientes/<int:pk>/status/", views.cliente_status, name="cliente_status"),
    # Categorias
    path("painel/categorias/", views.categorias_lista, name="categorias"),
    path("painel/categorias/nova/", views.categoria_form, name="categoria_nova"),
    path("painel/categorias/<int:pk>/editar/", views.categoria_form, name="categoria_editar"),
    path("painel/categorias/<int:pk>/excluir/", views.categoria_excluir, name="categoria_excluir"),
    # Cupons
    path("painel/cupons/", views.cupons_lista, name="cupons"),
    path("painel/cupons/novo/", views.cupom_form, name="cupom_novo"),
    path("painel/cupons/<int:pk>/editar/", views.cupom_form, name="cupom_editar"),
    path("painel/cupons/<int:pk>/excluir/", views.cupom_excluir, name="cupom_excluir"),
    # Estoque / Newsletter / Configurações / Relatórios
    path("painel/estoque/", views.estoque, name="estoque"),
    path("painel/newsletter/", views.newsletter_lista, name="newsletter"),
    path("painel/configuracoes/", views.configuracoes, name="configuracoes"),
    path("painel/relatorios/", views.relatorios, name="relatorios"),
]
