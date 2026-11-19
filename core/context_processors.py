"""Context processor: injeta configurações da loja, menu e contador do carrinho."""
from carrinho.services import contador_itens_carrinho
from core.models import ConfiguracaoLoja


def store_context(request):
    """Dados globais disponíveis em todos os templates."""
    from categorias.models import Categoria

    favoritos_ids = set()
    if request.user.is_authenticated:
        from favoritos.models import Favorito

        favoritos_ids = set(
            Favorito.objects.filter(usuario=request.user).values_list(
                "produto_id", flat=True
            )
        )

    return {
        "loja": ConfiguracaoLoja.carregar(),
        "carrinho_qtd": contador_itens_carrinho(request),
        "categorias_menu": Categoria.objects.filter(
            ativa=True, pai__isnull=True, ordem__lt=500
        ).prefetch_related("filhas")[:7],
        "categorias_todas": Categoria.objects.filter(
            ativa=True, pai__isnull=True, ordem__lt=500
        ).prefetch_related("filhas"),
        "favoritos_ids": favoritos_ids,
    }
