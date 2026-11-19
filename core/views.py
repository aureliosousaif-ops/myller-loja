"""Views do núcleo: homepage, páginas institucionais, newsletter e erros."""
from django.contrib import messages
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from categorias.models import Categoria
from core.models import ConfiguracaoLoja, NewsletterInscrito, PaginaInstitucional
from produtos.models import Produto


def home(request):
    """Homepage com destaques da loja."""
    categorias_home = Categoria.objects.filter(
        ativa=True, mostrar_home=True, pai__isnull=True
    )[:8]

    mais_vendidos = list(
        Produto.objects.filter(status=Produto.Status.PUBLICADO)
        .annotate(
            vendidos=Sum(
                "pedidos__quantidade",
                filter=~Q(pedidos__pedido__status="cancelado"),
            )
        )
        .order_by("-vendidos", "-visualizacoes")[:8]
    )
    # Preenche com destaques caso ainda não haja vendas registradas.
    if len(mais_vendidos) < 8:
        extras = Produto.objects.filter(
            status=Produto.Status.PUBLICADO, destaque_home=True
        ).exclude(pk__in=[p.pk for p in mais_vendidos])
        mais_vendidos = list(mais_vendidos) + list(extras[: 8 - len(mais_vendidos)])

    novidades = Produto.objects.filter(
        status=Produto.Status.PUBLICADO, eh_novidade=True
    )[:8]

    promocoes = Produto.objects.filter(
        status=Produto.Status.PUBLICADO,
        preco_promocional__isnull=False,
    ).exclude(preco_promocional=None)[:8]

    # "Escolhas da MYLLER" — curadoria editorial da marca
    escolhas = list(
        Produto.objects.filter(status=Produto.Status.PUBLICADO, destaque_home=True)
        .exclude(pk__in=[p.pk for p in novidades])[:8]
    )
    if len(escolhas) < 8:
        extras = Produto.objects.filter(status=Produto.Status.PUBLICADO).exclude(
            pk__in=[p.pk for p in novidades] + [p.pk for p in escolhas]
        )[: 8 - len(escolhas)]
        escolhas += list(extras)

    # Grade do Instagram da marca (produtos reais da vitrine)
    instagram = list(
        Produto.objects.filter(status=Produto.Status.PUBLICADO).order_by(
            "-atualizado_em", "-pk"
        )[:8]
    )

    context = {
        "categorias_home": categorias_home,
        "mais_vendidos": mais_vendidos,
        "novidades": novidades,
        "promocoes": promocoes,
        "escolhas": escolhas,
        "instagram": instagram,
        "beneficios": _beneficios(),
    }
    return render(request, "core/home.html", context)


def _beneficios():
    return [
        {"icone": "bi-truck", "titulo": "Entrega para todo o Brasil",
         "texto": "Frete calculado no checkout e rastreio do pedido na sua conta."},
        {"icone": "bi-shield-check", "titulo": "Compra 100% segura",
         "texto": "Pagamento por PIX ou cartão via gateway reconhecido, dados protegidos."},
        {"icone": "bi-arrow-repeat", "titulo": "Trocas descomplicadas",
         "texto": "Política de troca e devolução clara em até 7 dias após o recebimento."},
        {"icone": "bi-headset", "titulo": "Atendimento próximo",
         "texto": "Fale com a MYLLER pelo WhatsApp e acompanhe tudo pelo seu painel."},
    ]


def pagina_institucional(request, slug):
    pagina = get_object_or_404(PaginaInstitucional, slug=slug, ativa=True)
    return render(request, "core/pagina.html", {"pagina": pagina})


def newsletter_view(request):
    """Inscrição na newsletter (POST)."""
    if request.method != "POST":
        return redirect("core:home")
    email = (request.POST.get("email") or "").strip().lower()
    nome = (request.POST.get("nome") or "").strip()
    if not email:
        messages.error(request, "Informe um e-mail válido.")
        return redirect(request.META.get("HTTP_REFERER", "core:home"))
    inscrito, criado = NewsletterInscrito.objects.get_or_create(
        email=email, defaults={"nome": nome}
    )
    if not criado and not inscrito.ativo:
        inscrito.ativo = True
        inscrito.save(update_fields=["ativo"])
    if criado:
        messages.success(request, "Inscrição realizada! Bem-vindo ao universo MYLLER.")
    else:
        messages.info(request, "Este e-mail já estava inscrito.")
    return redirect(request.META.get("HTTP_REFERER", "core:home"))


def api_cep(request, cep):
    """Busca endereço via ViaCEP (API pública, sem credenciais)."""
    from core.services import buscar_cep

    digitos = "".join(ch for ch in cep if ch.isdigit())
    if len(digitos) != 8:
        return JsonResponse({"ok": False, "erro": "CEP inválido."}, status=400)
    dados = buscar_cep(digitos)
    if dados is None:
        return JsonResponse({"ok": False, "erro": "CEP não encontrado."}, status=404)
    return JsonResponse({"ok": True, "endereco": dados})


def pagina_nao_encontrada(request, exception=None):
    return render(request, "core/404.html", status=404)


def erro_interno(request):
    return render(request, "core/500.html", status=500)
