from django.urls import path

from core import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("newsletter/", views.newsletter_view, name="newsletter"),
    path("api/cep/<str:cep>/", views.api_cep, name="api_cep"),
    path("pagina/<slug:slug>/", views.pagina_institucional, name="pagina"),
]
