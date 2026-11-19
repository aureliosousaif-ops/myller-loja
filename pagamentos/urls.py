from django.urls import path

from pagamentos import views

app_name = "pagamentos"

urlpatterns = [
    path("webhooks/mercadopago/", views.webhook_mercadopago, name="webhook_mercadopago"),
    path("webhooks/stripe/", views.webhook_stripe, name="webhook_stripe"),
]
