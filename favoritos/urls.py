from django.urls import path

from favoritos import views

app_name = "favoritos"

urlpatterns = [
    path("favoritos/", views.pagina_favoritos, name="lista"),
    path("minha-conta/favoritos/", views.pagina_favoritos, name="lista"),
    path("api/favoritos/alternar/", views.alternar, name="alternar"),
]
