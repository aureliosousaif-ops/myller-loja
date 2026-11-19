"""Context processor: notificações do painel no cabeçalho.

Só executa consultas nas rotas /painel/ — a loja pública não paga o custo.
"""
from django.db.models import Q, Sum
from django.urls import reverse


def painel_notificacoes(request):
    """Indicadores de alerta exibidos no sino do cabeçalho do painel."""
    if not request.path.startswith("/painel/"):
        return {}

    try:
        from pedidos.models import Pedido, PedidoStatus
        from produtos.models import Produto

        pendentes = Pedido.objects.filter(
            status=PedidoStatus.AGUARDANDO_PAGAMENTO
        ).count()
        em_andamento = Pedido.objects.filter(
            status__in=[PedidoStatus.EM_PREPARACAO, PedidoStatus.ENVIADO]
        ).count()
        publicados = Produto.objects.filter(status=Produto.Status.PUBLICADO)
        estoque_baixo = (
            publicados.annotate(total=Sum("variacoes__estoque"))
            .filter(total__lte=5, total__gt=0)
            .count()
        )
        sem_estoque = (
            publicados.annotate(total=Sum("variacoes__estoque"))
            .filter(Q(total__isnull=True) | Q(total=0))
            .count()
        )
    except Exception:  # noqa: BLE001 — notificação nunca derruba a página
        return {}

    itens = [
        {
            "icone": "bi-hourglass-split",
            "texto": f"{pendentes} pedido(s) aguardando pagamento",
            "url": reverse("dashboard:pedidos")
            + f"?status={PedidoStatus.AGUARDANDO_PAGAMENTO}",
            "classe": "alerta-ambar",
        },
        {
            "icone": "bi-arrow-repeat",
            "texto": f"{em_andamento} pedido(s) em andamento",
            "url": reverse("dashboard:pedidos")
            + f"?status={PedidoStatus.EM_PREPARACAO}",
            "classe": "alerta-azul",
        },
        {
            "icone": "bi-exclamation-triangle",
            "texto": f"{estoque_baixo} produto(s) com estoque baixo",
            "url": reverse("dashboard:estoque"),
            "classe": "alerta-ambar",
        },
        {
            "icone": "bi-box-seam",
            "texto": f"{sem_estoque} produto(s) esgotado(s)",
            "url": reverse("dashboard:estoque"),
            "classe": "alerta-vermelho",
        },
    ]
    total = pendentes + estoque_baixo + sem_estoque
    return {"painel_alertas": itens, "painel_alertas_total": total}
