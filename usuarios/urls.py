from django.urls import path

from usuarios import views

app_name = "usuarios"

urlpatterns = [
    path("entrar/", views.VistaLogin.as_view(), name="login"),
    path("sair/", views.VistaLogout.as_view(), name="logout"),
    path("cadastro/", views.VistaCadastro.as_view(), name="registro"),
    path("senha/redefinir/", views.RecuperarSenha.as_view(), name="recuperar_senha"),
    path(
        "senha/redefinir/enviado/",
        views.RecuperarSenhaEnviado.as_view(),
        name="recuperar_senha_feito",
    ),
    path(
        "senha/redefinir/<uidb64>/<token>/",
        views.RecuperarSenhaConfirmar.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "senha/redefinir/concluido/",
        views.RecuperarSenhaCompleto.as_view(),
        name="recuperar_senha_completo",
    ),
]
