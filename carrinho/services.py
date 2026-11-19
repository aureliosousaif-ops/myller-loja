"""Serviços do carrinho: criação, adição, totais e fusão de sessão."""
from decimal import Decimal

from django.db.models import Sum

from carrinho.models import Carrinho, CarrinhoItem


def _chave_sessao(request):
    """Retorna a chave de sessão existente, sem forçar a criação de uma nova."""
    return request.session.session_key or ""


def obter_carrinho(request, criar=True):
    """Retorna o carrinho do usuário autenticado ou da sessão atual."""
    if request.user.is_authenticated:
        carrinho, _ = Carrinho.objects.get_or_create(
            usuario=request.user, defaults={"chave_sessao": ""}
        )
        # Um carrinho órfão de sessão pode existir para o mesmo usuário logado depois.
        return carrinho

    chave = _chave_sessao(request)
    if not chave:
        if not criar:
            return None
        request.session.create()
        chave = request.session.session_key
    carrinho = Carrinho.objects.filter(chave_sessao=chave, usuario__isnull=True).first()
    if carrinho is None and criar:
        carrinho = Carrinho.objects.create(chave_sessao=chave)
    return carrinho


def contador_itens_carrinho(request):
    """Total de itens no carrinho sem criar sessões desnecessárias (usado no context processor)."""
    if getattr(request, "_carrinho_qtd_cache", None) is not None:
        return request._carrinho_qtd_cache

    if request.user.is_authenticated:
        total = (
            Carrinho.objects.filter(usuario=request.user)
            .aggregate(total=Sum("itens__quantidade"))["total"]
            or 0
        )
    else:
        chave = _chave_sessao(request)
        if not chave:
            total = 0
        else:
            total = (
                Carrinho.objects.filter(chave_sessao=chave, usuario__isnull=True)
                .aggregate(total=Sum("itens__quantidade"))["total"]
                or 0
            )
    request._carrinho_qtd_cache = total
    return total


def adicionar_item(request, variacao, quantidade=1):
    """Adiciona uma variação ao carrinho, respeitando o limite de estoque."""
    carrinho = obter_carrinho(request)
    item, criado = CarrinhoItem.objects.get_or_create(
        carrinho=carrinho,
        variacao=variacao,
        defaults={
            "preco_unitario": variacao.preco_unitario,
            "quantidade": quantidade,
        },
    )
    if not criado:
        nova = item.quantidade + quantidade
        if nova > variacao.estoque:
            nova = variacao.estoque
        item.quantidade = max(nova, 0)
        item.preco_unitario = variacao.preco_unitario
        item.save()
    else:
        if item.quantidade > variacao.estoque:
            item.quantidade = variacao.estoque
            item.save()
    request._carrinho_qtd_cache = None
    return item


def atualizar_quantidade(request, item_id, quantidade):
    """Atualiza a quantidade de um item (limitada ao estoque)."""
    carrinho = obter_carrinho(request, criar=False)
    if carrinho is None:
        return None
    item = CarrinhoItem.objects.filter(pk=item_id, carrinho=carrinho).select_related("variacao").first()
    if item is None:
        return None
    quantidade = int(quantidade)
    if quantidade <= 0:
        item.delete()
        request._carrinho_qtd_cache = None
        return None
    item.quantidade = min(quantidade, item.variacao.estoque)
    item.preco_unitario = item.variacao.preco_unitario
    item.save()
    request._carrinho_qtd_cache = None
    return item


def remover_item(request, item_id):
    """Remove um item do carrinho."""
    carrinho = obter_carrinho(request, criar=False)
    if carrinho is None:
        return False
    removido = CarrinhoItem.objects.filter(pk=item_id, carrinho=carrinho).delete()
    request._carrinho_qtd_cache = None
    return bool(removido[0])


def limpar_carrinho(request):
    carrinho = obter_carrinho(request, criar=False)
    if carrinho:
        carrinho.itens.all().delete()
        carrinho.cupom_codigo = ""
        carrinho.save(update_fields=["cupom_codigo", "atualizado_em"])
    request._carrinho_qtd_cache = None


def mesclar_carrinho_sessao(request, chave_sessao=None):
    """
    Ao fazer login, migra o carrinho da sessão para o carrinho do usuário,
    somando quantidades duplicadas.

    `chave_sessao` deve ser a chave ANTES do login — o Django troca a chave da
    sessão ao autenticar (cycle_key), por isso ela é informada pelas views.
    """
    if not request.user.is_authenticated:
        return None
    chave = chave_sessao or _chave_sessao(request)
    if not chave:
        return None
    usuario = request.user
    carrinho_sessao = Carrinho.objects.filter(
        chave_sessao=chave, usuario__isnull=True
    ).first()
    if carrinho_sessao is None:
        return None

    carrinho_usuario, _ = Carrinho.objects.get_or_create(usuario=usuario)
    for item in carrinho_sessao.itens.all():
        existente = CarrinhoItem.objects.filter(
            carrinho=carrinho_usuario, variacao=item.variacao
        ).first()
        if existente:
            existente.quantidade = min(
                existente.quantidade + item.quantidade, item.variacao.estoque
            )
            existente.save()
        else:
            item.pk = None
            item.carrinho = carrinho_usuario
            item.save()
    if carrinho_sessao.cupom_codigo and not carrinho_usuario.cupom_codigo:
        carrinho_usuario.cupom_codigo = carrinho_sessao.cupom_codigo
        carrinho_usuario.save()
    carrinho_sessao.delete()
    request._carrinho_qtd_cache = None
    return carrinho_usuario


def aplicar_cupom(request, codigo):
    """Valida e grava o código do cupom no carrinho. Retorna (ok, mensagem)."""
    from pedidos.models import CupomDesconto

    carrinho = obter_carrinho(request)
    codigo = (codigo or "").strip().upper()
    if not codigo:
        carrinho.cupom_codigo = ""
        carrinho.save(update_fields=["cupom_codigo", "atualizado_em"])
        return True, "Cupom removido."

    cupom = CupomDesconto.objects.filter(codigo=codigo, ativo=True).first()
    if cupom is None:
        return False, "Cupom inválido."

    subtotal = carrinho.subtotal
    erro = cupom.validar(subtotal)
    if erro:
        return False, erro

    carrinho.cupom_codigo = cupom.codigo
    carrinho.save(update_fields=["cupom_codigo", "atualizado_em"])
    return True, f"Cupom {cupom.codigo} aplicado com sucesso!"


def totais_carrinho(request, frete=Decimal("0.00")):
    """Calcula subtotal, desconto de cupom, frete e total do carrinho."""
    from pedidos.services import calcular_totais_pedido

    carrinho = obter_carrinho(request, criar=False)
    if carrinho is None or not carrinho.itens.exists():
        return {
            "carrinho": None,
            "subtotal": Decimal("0.00"),
            "desconto": Decimal("0.00"),
            "frete": Decimal("0.00"),
            "total": Decimal("0.00"),
            "cupom": None,
            "cupom_mensagem": "",
        }
    totais = calcular_totais_pedido(
        subtotal=carrinho.subtotal,
        codigo_cupom=carrinho.cupom_codigo,
        frete=frete,
    )
    totais["carrinho"] = carrinho
    return totais
