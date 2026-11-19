from django.urls import path

from pedidos import views

app_name = "pedidos"

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("pedido/<str:numero>/", views.pedido_detalhe, name="detalhe"),
    path("pedido/<str:numero>/status/", views.api_status_pedido, name="api_status"),
    path("pedido/<str:numero>/cancelar/", views.cancelar_pedido, name="cancelar"),
]
