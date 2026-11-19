"""Views do carrinho de compras."""
from decimal import Decimal

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from carrinho import services
from pedidos.frete import calcular_frete
from produtos.models import Variacao


def pagina_carrinho(request):
    """Página do carrinho com totais e cupom."""
    carrinho = services.obter_carrinho(request, criar=False)
    frete_info = {
        "cep": "", "valor": "", "prazo": "", "transportadora": "",
        "mensagem": "", "estimativa": True,
    }
    frete_info.update(request.session.get("frete") or {})
    totais = services.totais_carrinho(
        request, frete=Decimal(str(frete_info.get("valor", "0") or "0"))
    )
    return render(
        request,
        "carrinho/carrinho.html",
        {"carrinho": carrinho, "totais": totais, "frete_info": frete_info},
    )


@require_POST
def adicionar(request):
    """Adiciona um item ao carrinho (tamanho + cor resolvidos em variação)."""
    try:
        variacao_id = int(request.POST.get("variacao_id") or 0)
    except (TypeError, ValueError):
        variacao_id = 0
    try:
        quantidade = int(request.POST.get("quantidade") or 1)
    except (TypeError, ValueError):
        quantidade = 1
    produto_slug = request.POST.get("produto_slug", "")

    if variacao_id <= 0:
        return _responder(request, {"ok": False, "mensagem": "Selecione tamanho e cor."})

    variacao = (
        Variacao.objects.select_related("produto", "tamanho", "cor")
        .filter(pk=variacao_id, ativa=True, produto__status="publicado")
        .first()
    )
    if variacao is None:
        return _responder(request, {"ok": False, "mensagem": "Selecione tamanho e cor."})

    if variacao.estoque <= 0:
        return _responder(
            request,
            {"ok": False, "mensagem": "Este item está esgotado."},
        )

    if quantidade < 1:
        quantidade = 1

    item = services.adicionar_item(request, variacao, quantidade)
    mensagem = f"{variacao.produto.nome} ({variacao.tamanho}/{variacao.cor}) adicionado ao carrinho!"

    if item.quantidade >= variacao.estoque and item.quantidade > 1:
        mensagem = f"Quantidade limitada ao estoque disponível ({variacao.estoque})."

    return _responder(
        request,
        {
            "ok": True,
            "mensagem": mensagem,
            "carrinho_qtd": services.contador_itens_carrinho(request),
            "item_total": str(item.total),
        },
    )


@require_POST
def atualizar(request):
    """Atualiza quantidade de um item (Fetch API ou formulário clássico)."""
    item_id = int(request.POST.get("item_id") or request.GET.get("item_id") or 0)
    acao = request.POST.get("acao", "")

    if acao in ("aumentar", "diminuir"):
        from carrinho.models import CarrinhoItem

        item_atual = CarrinhoItem.objects.filter(pk=item_id).first()
        if item_atual is None:
            return _responder(request, {"ok": False, "mensagem": "Item não encontrado."})
        quantidade = item_atual.quantidade + (1 if acao == "aumentar" else -1)
    else:
        quantidade = int(request.POST.get("quantidade") or 0)

    services.atualizar_quantidade(request, item_id, quantidade)

    totais = services.totais_carrinho(
        request, frete=Decimal(str(request.session.get("frete", {}).get("valor", "0") or "0"))
    )
    itens_totais = {}
    quantidades = {}
    if totais.get("carrinho"):
        for i in totais["carrinho"].itens.all():
            itens_totais[str(i.pk)] = str(i.total)
            quantidades[str(i.pk)] = i.quantidade
    return _responder(
        request,
        {
            "ok": True,
            "carrinho_qtd": services.contador_itens_carrinho(request),
            "subtotal": str(totais["subtotal"]),
            "desconto": str(totais["desconto"]),
            "frete": str(totais["frete"]),
            "total": str(totais["total"]),
            "itens": itens_totais,
            "quantidades": quantidades,
        },
    )


@require_POST
def remover(request):
    item_id = int(request.POST.get("item_id") or 0)
    services.remover_item(request, item_id)
    return _responder(
        request,
        {
            "ok": True,
            "carrinho_qtd": services.contador_itens_carrinho(request),
        },
    )


@require_POST
def limpar(request):
    """Esvazia o carrinho por completo."""
    services.limpar_carrinho(request)
    return _responder(
        request,
        {
            "ok": True,
            "mensagem": "Carrinho esvaziado.",
            "carrinho_qtd": 0,
        },
    )


@require_POST
def aplicar_cupom(request):
    """Aplica/remove cupom de desconto."""
    codigo = request.POST.get("codigo", "")
    ok, mensagem = services.aplicar_cupom(request, codigo)
    if ok:
        messages.success(request, mensagem)
    else:
        messages.error(request, mensagem)
    return redirect(request.META.get("HTTP_REFERER", "carrinho:pagina"))


@require_POST
def api_frete(request):
    """Cálculo de frete via API JSON (chamado pelo front-end com Fetch)."""
    cep = (request.POST.get("cep") or request.GET.get("cep") or "").strip()
    carrinho = services.obter_carrinho(request, criar=False)
    if carrinho is None or not carrinho.itens.exists():
        return JsonResponse({"ok": False, "mensagem": "Carrinho vazio."}, status=400)

    resultado = calcular_frete(carrinho, cep)
    if resultado["origem"] == "invalido":
        return JsonResponse({"ok": False, "mensagem": resultado["mensagem"]}, status=400)

    # Persiste a escolha de frete na sessão para o checkout
    request.session["frete"] = {
        "cep": cep,
        "valor": str(resultado["valor"]),
        "prazo": resultado["prazo"],
        "transportadora": resultado["transportadora"],
        "estimativa": resultado["estimativa"],
        "mensagem": resultado["mensagem"],
    }

    totais = services.totais_carrinho(request, frete=resultado["valor"])
    return JsonResponse(
        {
            "ok": True,
            "valor": str(resultado["valor"]),
            "prazo": resultado["prazo"],
            "transportadora": resultado["transportadora"],
            "estimativa": resultado["estimativa"],
            "mensagem": resultado["mensagem"],
            "total": str(totais["total"]),
            "desconto": str(totais["desconto"]),
        }
    )


def _responder(request, dados):
    """Responde JSON para Fetch API ou redireciona para formulário clássico."""
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.POST.get("ajax"):
        return JsonResponse(dados)
    if dados.get("ok"):
        messages.success(request, dados.get("mensagem", "Atualizado."))
    else:
        messages.error(request, dados.get("mensagem", "Falha na operação."))
    return redirect(request.POST.get("next") or "carrinho:pagina")
