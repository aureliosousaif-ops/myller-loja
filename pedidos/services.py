"""Serviços de pedidos: totais, criação, status e estoque."""
import logging
from decimal import Decimal

from django.db import transaction

logger = logging.getLogger(__name__)


def calcular_totais_pedido(subtotal, codigo_cupom="", frete=Decimal("0.00")):
    """
    Calcula desconto de cupom e total final.

    Retorna dict com subtotal, desconto, frete, total, cupom e cupom_mensagem.
    """
    from pedidos.models import CupomDesconto

    subtotal = Decimal(subtotal)
    frete = Decimal(frete)
    desconto = Decimal("0.00")
    cupom = None
    mensagem = ""

    if codigo_cupom:
        cupom = CupomDesconto.objects.filter(codigo=codigo_cupom.upper(), ativo=True).first()
        if cupom is None:
            mensagem = "Cupom inválido."
        else:
            erro = cupom.validar(subtotal)
            if erro:
                mensagem = erro
            else:
                desconto = cupom.calcular_desconto(subtotal)
                mensagem = ""

    total = subtotal - desconto + frete
    total = max(total, Decimal("0.00"))

    return {
        "subtotal": subtotal,
        "desconto": desconto,
        "frete": frete,
        "total": total,
        "cupom": cupom,
        "cupom_mensagem": mensagem,
    }


def gerar_numero_pedido():
    """Gera número único no formato MYL-AAAA-000123."""
    import itertools

    from pedidos.models import Pedido

    sequencia = itertools.count(Pedido.objects.count() + 1)
    while True:
        candidato = f"MYL-{next(sequencia):06d}"
        if not Pedido.objects.filter(numero=candidato).exists():
            return candidato


@transaction.atomic
def criar_pedido(carrinho, dados, usuario=None, chave_sessao="", itens_snapshot=None):
    """
    Cria o pedido a partir do carrinho, baixa o estoque de forma atômica
    e limpa o carrinho.

    `dados` deve conter: nome, email, telefone, cep, logradouro, numero,
    complemento, bairro, cidade, estado, subtotal, frete, desconto, total,
    metodo_entrega, prazo_entrega (e opcionalmente observacao).

    Retorna (pedido, None) ou (None, mensagem_de_erro).
    """
    from carrinho.models import CarrinhoItem
    from estoque.services import EstoqueInsuficiente, baixar_estoque
    from pedidos.models import HistoricoStatus, Pedido, PedidoItem, PedidoStatus

    if not carrinho or not carrinho.itens.exists():
        return None, "Seu carrinho está vazio."

    itens = list(carrinho.itens.select_related("variacao__produto", "variacao__tamanho", "variacao__cor"))
    for item in itens:
        if item.variacao.estoque < item.quantidade:
            return None, (
                f"Estoque insuficiente para {item.variacao.produto.nome} "
                f"({item.variacao.tamanho}/{item.variacao.cor}). "
                f"Disponível: {item.variacao.estoque}."
            )

    cupom = None
    if carrinho.cupom_codigo:
        from pedidos.models import CupomDesconto

        cupom = CupomDesconto.objects.filter(
            codigo=carrinho.cupom_codigo, ativo=True
        ).first()

    pedido = Pedido.objects.create(
        numero=gerar_numero_pedido(),
        usuario=usuario,
        chave_sessao=chave_sessao,
        nome=dados["nome"],
        email=dados["email"],
        telefone=dados["telefone"],
        cep=dados["cep"],
        logradouro=dados["logradouro"],
        endereco_numero=dados.get("numero", ""),
        complemento=dados.get("complemento", ""),
        bairro=dados["bairro"],
        cidade=dados["cidade"],
        estado=dados["estado"],
        subtotal=dados["subtotal"],
        frete=dados.get("frete", Decimal("0.00")),
        desconto=dados.get("desconto", Decimal("0.00")),
        total=dados["total"],
        cupom=cupom,
        metodo_entrega=dados.get("metodo_entrega", ""),
        prazo_entrega=dados.get("prazo_entrega", ""),
        observacao=dados.get("observacao", ""),
        status=PedidoStatus.AGUARDANDO_PAGAMENTO,
    )

    itens_pedido = [
        PedidoItem(
            pedido=pedido,
            produto=item.variacao.produto,
            variacao=item.variacao,
            nome=item.variacao.produto.nome,
            tamanho_nome=item.variacao.tamanho.nome,
            cor_nome=item.variacao.cor.nome,
            sku=item.variacao.sku or item.variacao.produto.sku,
            preco_unitario=item.preco_unitario,
            quantidade=item.quantidade,
            subtotal=item.total,
        )
        for item in itens
    ]

    try:
        baixar_estoque(pedido, itens_pedido)
    except EstoqueInsuficiente as exc:
        logger.warning("Falha ao baixar estoque para pedido %s: %s", pedido.numero, exc)
        pedido.delete()
        return None, f"Item sem estoque suficiente: {exc.variacao}."

    PedidoItem.objects.bulk_create(itens_pedido)

    if cupom:
        type(cupom).objects.filter(pk=cupom.pk).update(usos=cupom.usos + 1)

    HistoricoStatus.objects.create(
        pedido=pedido,
        status=PedidoStatus.AGUARDANDO_PAGAMENTO,
        observacao="Pedido criado no checkout.",
        usuario=usuario if usuario and usuario.is_authenticated else None,
    )

    # Limpa o carrinho
    CarrinhoItem.objects.filter(pk__in=[i.pk for i in itens]).delete()
    carrinho.cupom_codigo = ""
    carrinho.save(update_fields=["cupom_codigo", "atualizado_em"])

    return pedido, None


def alterar_status_pedido(pedido, novo_status, usuario=None, observacao=""):
    """
    Altera o status do pedido, registrando o histórico e
    devolvendo o estoque automaticamente ao cancelar.
    """
    from estoque.services import repor_estoque
    from pedidos.models import HistoricoStatus, PedidoStatus

    if pedido.status == novo_status:
        return pedido

    status_anterior = pedido.status
    pedido.status = novo_status
    if usuario and usuario.is_authenticated:
        pedido.atualizado_por = usuario
    pedido.save(update_fields=["status", "atualizado_em", "atualizado_por"])

    HistoricoStatus.objects.create(
        pedido=pedido,
        status=novo_status,
        observacao=observacao or f"Status alterado de {status_anterior} para {novo_status}.",
        usuario=usuario if usuario and usuario.is_authenticated else None,
    )

    if novo_status == PedidoStatus.CANCELADO:
        repor_estoque(pedido)
        logger.info("Estoque devolvido para o pedido %s cancelado.", pedido.numero)

    return pedido
