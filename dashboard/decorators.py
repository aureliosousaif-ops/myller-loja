"""Decorator de proteção do painel administrativo."""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from urllib.parse import quote

# Grupos autorizados a acessar o painel além de staff/superusuário.
# O acesso é verificado no servidor — ocultar botões nunca é segurança.
GRUPOS_PAINEL = ("proprietarios", "administradores")


def usuario_painel(user):
    """Retorna True se o usuário pode acessar o painel do proprietário."""
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return user.groups.filter(name__in=GRUPOS_PAINEL).exists()


def painel_requerido(view_func):
    """Exige usuário autorizado (staff, superusuário ou grupo do painel)."""

    @wraps(view_func)
    def _wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Entre com uma conta de administrador.")
            destino = request.get_full_path() or reverse("dashboard:home")
            return redirect(
                f"{reverse('usuarios:login')}?next={quote(destino)}"
            )
        if not usuario_painel(request.user):
            messages.error(request, "Acesso restrito à equipe da MYLLER.")
            return redirect("core:home")
        return view_func(request, *args, **kwargs)

    return _wrapper
