"""Views de favoritos (lista de desejos)."""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from favoritos.models import Favorito
from produtos.models import Produto


def pagina_favoritos(request):
    """Página de favoritos: lista para logados, aviso para visitantes."""
    favoritos = []
    if request.user.is_authenticated:
        favoritos = (
            Favorito.objects.filter(usuario=request.user)
            .select_related("produto__categoria", "produto")
            .order_by("-criado_em")
        )
    return render(
        request,
        "favoritos/favoritos.html",
        {"favoritos": favoritos, "autenticado": request.user.is_authenticated},
    )


@require_POST
def alternar(request):
    """Adiciona/remove produto dos favoritos (Fetch API)."""
    if not request.user.is_authenticated:
        return JsonResponse(
            {"ok": False, "login_necessario": True,
             "mensagem": "Entre na sua conta para salvar favoritos."},
            status=401,
        )

    produto_id = int(request.POST.get("produto_id") or 0)
    produto = Produto.objects.filter(pk=produto_id, status=Produto.Status.PUBLICADO).first()
    if produto is None:
        return JsonResponse({"ok": False, "mensagem": "Produto não encontrado."}, status=404)

    favorito, criado = Favorito.objects.get_or_create(
        usuario=request.user, produto=produto
    )
    if not criado:
        favorito.delete()
        return JsonResponse(
            {"ok": True, "adicionado": False, "mensagem": "Removido dos favoritos."}
        )
    return JsonResponse(
        {"ok": True, "adicionado": True, "mensagem": "Salvo nos favoritos!"}
    )
