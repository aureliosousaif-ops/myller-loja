"""Views de autenticação: cadastro, login, logout e recuperação de senha."""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.urls import reverse_lazy
from django.views.generic import CreateView

from carrinho.services import mesclar_carrinho_sessao
from clientes.models import Cliente
from usuarios.forms import FormLogin, RegistroForm


class VistaLogin(LoginView):
    template_name = "usuarios/login.html"
    authentication_form = FormLogin
    redirect_authenticated_user = True

    def form_valid(self, form):
        chave_sessao = self.request.session.session_key
        resposta = super().form_valid(form)
        # "Manter sessão iniciada": expira em 2 semanas; sem a opção,
        # a sessão encerra quando o navegador for fechado.
        if self.request.POST.get("lembrar"):
            self.request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        else:
            self.request.session.set_expiry(0)
        # Migra o carrinho da sessão para a conta autenticada.
        mesclar_carrinho_sessao(self.request, chave_sessao)
        return resposta

    def get_success_url(self):
        proximo = self.request.GET.get("next")
        return proximo or super().get_success_url()


class VistaLogout(LogoutView):
    next_page = reverse_lazy("core:home")


class VistaCadastro(CreateView):
    form_class = RegistroForm
    template_name = "usuarios/cadastro.html"
    success_url = reverse_lazy("usuarios:login")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect_home(request)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        from django.urls import reverse

        self.success_url = reverse("clientes:perfil")
        chave_sessao = self.request.session.session_key
        resposta = super().form_valid(form)
        cliente = Cliente.objects.create(usuario=self.object)
        telefone = form.cleaned_data.get("telefone")
        if telefone:
            cliente.telefone = telefone
            cliente.save(update_fields=["telefone"])
        login(self.request, self.object)
        mesclar_carrinho_sessao(self.request, chave_sessao)
        messages.success(
            self.request,
            f"Bem-vindo à MYLLER, {self.object.first_name or self.object.username}!",
        )
        return resposta


def redirect_home(request):
    from django.shortcuts import redirect

    return redirect("core:home")


class RecuperarSenha(PasswordResetView):
    template_name = "usuarios/recuperar_senha.html"
    email_template_name = "usuarios/email/recuperar_senha.txt"
    subject_template_name = "usuarios/email/recuperar_senha_assunto.txt"
    success_url = reverse_lazy("usuarios:recuperar_senha_feito")


class RecuperarSenhaEnviado(PasswordResetDoneView):
    template_name = "usuarios/recuperar_senha_enviado.html"


class RecuperarSenhaConfirmar(PasswordResetConfirmView):
    template_name = "usuarios/recuperar_senha_confirmar.html"
    success_url = reverse_lazy("usuarios:recuperar_senha_completo")


class RecuperarSenhaCompleto(PasswordResetCompleteView):
    template_name = "usuarios/recuperar_senha_completo.html"
