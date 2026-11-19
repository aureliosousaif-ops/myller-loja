"""Views do catálogo: listagem, categoria, detalhe, busca e avaliações."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from categorias.models import Categoria
from favoritos.models import Favorito
from produtos.models import Avaliacao, Cor, Produto, Tamanho

ORDENACOES = {
    "preco_asc": "Preço: menor primeiro",
    "preco_desc": "Preço: maior primeiro",
    "novidades": "Novidades",
    "mais_vendidos": "Mais vendidos",
    "populares": "Mais vistos",
}


def _aplicar_filtros(request, queryset):
    """Aplica filtros de categoria, tamanho, cor, faixa de preço e busca."""
    categoria = request.GET.get("categoria")
    if categoria:
        queryset = queryset.filter(categoria__slug=categoria)

    tamanhos = request.GET.getlist("tamanho")
    if tamanhos:
        queryset = queryset.filter(variacoes__tamanho__nome__in=tamanhos)

    cores = request.GET.getlist("cor")
    if cores:
        queryset = queryset.filter(variacoes__cor__nome__in=cores)

    preco_min = request.GET.get("preco_min")
    if preco_min:
        try:
            queryset = queryset.filter(preco__gte=float(preco_min))
        except ValueError:
            pass

    preco_max = request.GET.get("preco_max")
    if preco_max:
        try:
            queryset = queryset.filter(
                Q(preco__lte=float(preco_max)) | Q(preco_promocional__lte=float(preco_max))
            )
        except ValueError:
            pass

    if request.GET.get("promocao"):
        queryset = queryset.filter(preco_promocional__isnull=False)

    if request.GET.get("novidade"):
        queryset = queryset.filter(eh_novidade=True)

    return queryset.distinct()


def _aplicar_ordenacao(request, queryset):
    ordem = request.GET.get("ordem", "")
    if ordem == "preco_asc":
        return queryset.order_by("preco")
    if ordem == "preco_desc":
        return queryset.order_by("-preco")
    if ordem == "novidades":
        return queryset.order_by("-criado_em")
    if ordem == "mais_vendidos":
        return queryset.annotate(
            vendidos=Sum(
                "pedidos__quantidade",
                filter=~Q(pedidos__pedido__status="cancelado"),
            )
        ).order_by("-vendidos", "-criado_em")
    if ordem == "populares":
        return queryset.order_by("-visualizacoes")
    return queryset.order_by("-destaque_home", "-criado_em")


def _contexto_filtros(request):
    return {
        "todos_tamanhos": Tamanho.objects.filter(ativo=True),
        "todas_cores": Cor.objects.filter(ativa=True),
        "ordenacoes": ORDENACOES,
        "tamanhos_selecionados": request.GET.getlist("tamanho"),
        "cores_selecionadas": request.GET.getlist("cor"),
    }


def lista_produtos(request):
    """Catálogo completo com filtros e ordenação."""
    queryset = _aplicar_filtros(request, Produto.objects.filter(status=Produto.Status.PUBLICADO))
    queryset = _aplicar_ordenacao(request, queryset)
    context = {
        "produtos": queryset,
        "titulo": "Todos os produtos",
        "categoria_atual": None,
        **_contexto_filtros(request),
    }
    return render(request, "produtos/lista.html", context)


def categoria_detalhe(request, slug):
    """Produtos de uma categoria (incluindo subcategorias)."""
    categoria = get_object_or_404(Categoria, slug=slug, ativa=True)
    subcategorias = categoria.filhas.filter(ativa=True)
    ids_sub = list(subcategorias.values_list("id", flat=True))

    queryset = Produto.objects.filter(
        status=Produto.Status.PUBLICADO,
        categoria_id__in=[categoria.pk] + ids_sub,
    )
    # Mantém os filtros de tamanho/cor da URL
    request.GET = request.GET.copy()
    request.GET.pop("categoria", None)
    queryset = _aplicar_filtros(request, queryset)
    queryset = _aplicar_ordenacao(request, queryset)

    context = {
        "produtos": queryset,
        "categoria": categoria,
        "subcategorias": subcategorias,
        "titulo": categoria.nome,
        "categoria_atual": categoria,
        **_contexto_filtros(request),
    }
    return render(request, "produtos/lista.html", context)


def detalhe_produto(request, slug):
    """Página individual do produto com galeria, variações e avaliações."""
    produto = get_object_or_404(
        Produto.objects.select_related("categoria").prefetch_related(
            "imagens", "avaliacoes__cliente", "variacoes__tamanho", "variacoes__cor"
        ),
        slug=slug,
        status=Produto.Status.PUBLICADO,
    )

    # Contabiliza visualização (consulta simples, sem gerenciar sessão)
    Produto.objects.filter(pk=produto.pk).update(visualizacoes=produto.visualizacoes + 1)

    relacionados = Produto.objects.filter(
        status=Produto.Status.PUBLICADO, categoria=produto.categoria
    ).exclude(pk=produto.pk)[:4]
    if relacionados.count() < 4:
        extras = Produto.objects.filter(
            status=Produto.Status.PUBLICADO, destaque_home=True
        ).exclude(pk__in=[produto.pk] + [r.pk for r in relacionados])
        relacionados = list(relacionados) + list(extras[: 4 - relacionados.count()])

    # Mapa de variações para o front-end resolver tamanho+cor → id e estoque
    mapa_variacoes = {
        f"{v.tamanho.nome}|{v.cor.nome}": {
            "id": v.pk,
            "estoque": v.estoque,
            "ativo": v.ativa,
            "preco": str(v.preco_unitario),
        }
        for v in produto.variacoes.filter(ativa=True)
    }

    favoritado = False
    if request.user.is_authenticated:
        favoritado = Favorito.objects.filter(
            usuario=request.user, produto=produto
        ).exists()

    avaliacoes = produto.avaliacoes.filter(ativa=True).select_related("cliente")
    nota_media = produto.nota_media

    context = {
        "produto": produto,
        "relacionados": relacionados,
        "mapa_variacoes": mapa_variacoes,
        "favoritado": favoritado,
        "avaliacoes": avaliacoes,
        "nota_media": nota_media,
    }
    return render(request, "produtos/detalhe.html", context)


@login_required
@require_POST
def avaliar(request, slug):
    """Registra uma avaliação do cliente autenticado."""
    produto = get_object_or_404(Produto, slug=slug, status=Produto.Status.PUBLICADO)
    from clientes.models import Cliente

    cliente, _ = Cliente.objects.get_or_create(usuario=request.user)
    nota = request.POST.get("nota")
    comentario = (request.POST.get("comentario") or "").strip()

    try:
        nota = int(nota)
        if nota < 1 or nota > 5:
            raise ValueError
    except (ValueError, TypeError):
        messages.error(request, "Escolha uma nota de 1 a 5 estrelas.")
        return redirect(produto.get_absolute_url() + "#avaliacoes")

    if len(comentario) < 5:
        messages.error(request, "Escreva um comentário com pelo menos 5 caracteres.")
        return redirect(produto.get_absolute_url() + "#avaliacoes")

    avaliacao, criada = Avaliacao.objects.get_or_create(
        produto=produto, cliente=cliente,
        defaults={"nota": nota, "comentario": comentario},
    )
    if not criada:
        avaliacao.nota = nota
        avaliacao.comentario = comentario
        avaliacao.ativa = True
        avaliacao.save()

    messages.success(request, "Avaliação publicada. Obrigado por contribuir!")
    return redirect(produto.get_absolute_url() + "#avaliacoes")


def busca(request):
    """Página de resultados de busca com filtros."""
    termo = (request.GET.get("q") or "").strip()
    queryset = Produto.objects.filter(status=Produto.Status.PUBLICADO)
    if termo:
        queryset = queryset.filter(
            Q(nome__icontains=termo)
            | Q(descricao__icontains=termo)
            | Q(sku__icontains=termo)
            | Q(categoria__nome__icontains=termo)
        )
    queryset = _aplicar_filtros(request, queryset)
    queryset = _aplicar_ordenacao(request, queryset)

    context = {
        "produtos": queryset,
        "termo": termo,
        "titulo": f'Resultados para "{termo}"' if termo else "Busca",
        "categoria_atual": None,
        **_contexto_filtros(request),
    }
    return render(request, "produtos/busca.html", context)


def api_busca(request):
    """Sugestões de busca em tempo real (Fetch API)."""
    termo = (request.GET.get("q") or "").strip()
    if len(termo) < 2:
        return JsonResponse({"ok": True, "resultados": []})

    encontrados = (
        Produto.objects.filter(
            Q(nome__icontains=termo) | Q(categoria__nome__icontains=termo),
            status=Produto.Status.PUBLICADO,
        )
        .select_related("categoria")[:6]
    )
    return JsonResponse(
        {
            "ok": True,
            "resultados": [
                {
                    "nome": p.nome,
                    "url": p.get_absolute_url(),
                    "preco": f"R$ {p.preco_final:.2f}".replace(".", ","),
                    "imagem": p.imagem_principal.url if p.imagem_principal else "",
                    "categoria": p.categoria.nome,
                }
                for p in encontrados
            ],
        }
    )
