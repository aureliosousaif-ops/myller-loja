"""Views do painel administrativo MYLLER (independente do Django Admin)."""
import csv
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from categorias.models import Categoria
from clientes.models import Cliente
from core.models import ConfiguracaoLoja, NewsletterInscrito
from dashboard.decorators import painel_requerido
from dashboard.forms import (
    CategoriaForm,
    ConfiguracaoLojaForm,
    CupomForm,
    EstoqueEntradaForm,
    PedidoStatusForm,
    ProdutoForm,
    ProdutoImagemForm,
    VariacaoFormSet,
)
from dashboard.models import RegistroAcao, registrar_acao
from estoque.models import MovimentoEstoque
from estoque.services import EstoqueInsuficiente, registrar_entrada, registrar_saida
from pagamentos.gateways import gateway_atual_info
from pedidos.models import CupomDesconto, Pedido, PedidoStatus
from pedidos.services import alterar_status_pedido
from produtos.models import Produto, Variacao

STATUS_CANCELADO = PedidoStatus.CANCELADO


# ================================================================ Dashboard
@painel_requerido
def home(request):
    """Dashboard com métricas da loja e gráficos."""
    hoje = timezone.now().date()
    primeiro_dia_mes = hoje.replace(day=1)

    total_vendas = Pedido.objects.exclude(status=STATUS_CANCELADO).count()
    faturamento = (
        Pedido.objects.exclude(status=STATUS_CANCELADO).aggregate(t=Sum("total"))["t"] or 0
    )
    faturamento_dia = (
        Pedido.objects.filter(criado_em__date=hoje)
        .exclude(status=STATUS_CANCELADO)
        .aggregate(t=Sum("total"))["t"]
        or 0
    )
    faturamento_mes = (
        Pedido.objects.filter(criado_em__date__gte=primeiro_dia_mes)
        .exclude(status=STATUS_CANCELADO)
        .aggregate(t=Sum("total"))["t"]
        or 0
    )
    total_pedidos = Pedido.objects.count()
    pendentes = Pedido.objects.filter(status=PedidoStatus.AGUARDANDO_PAGAMENTO).count()
    em_andamento = Pedido.objects.filter(
        status__in=[PedidoStatus.EM_PREPARACAO, PedidoStatus.ENVIADO]
    ).count()
    concluidos = Pedido.objects.filter(status=PedidoStatus.ENTREGUE).count()
    total_clientes = User.objects.filter(is_superuser=False, is_staff=False).count()
    total_produtos = Produto.objects.count()
    estoque_baixo = Produto.objects.filter(
        status=Produto.Status.PUBLICADO
    ).annotate(total=Sum("variacoes__estoque")).filter(total__lte=5, total__gt=0).count()

    top_produtos = (
        Produto.objects.annotate(
            vendidos=Sum(
                "pedidos__quantidade",
                filter=~Q(pedidos__pedido__status=STATUS_CANCELADO),
            )
        )
        .exclude(vendidos__isnull=True)
        .order_by("-vendidos")[:6]
    )

    ultimos_pedidos = Pedido.objects.select_related("cliente", "usuario")[:8]

    # Gráfico: vendas diárias (últimos 30 dias)
    inicio30 = hoje - timedelta(days=29)
    diarios = {
        item["dia"]: item
        for item in (
            Pedido.objects.filter(criado_em__date__gte=inicio30)
            .exclude(status=STATUS_CANCELADO)
            .annotate(dia=TruncDate("criado_em"))
            .values("dia")
            .annotate(qtd=Count("id"), total=Sum("total"))
        )
    }
    serie_diaria = []
    for offset in range(30):
        dia = inicio30 + timedelta(days=offset)
        dados = diarios.get(dia, {"qtd": 0, "total": 0})
        serie_diaria.append(
            {
                "label": dia.strftime("%d/%m"),
                "qtd": dados["qtd"] or 0,
                "total": float(dados["total"] or 0),
            }
        )
    max_diario = max([item["qtd"] for item in serie_diaria], default=0) or 1
    for item in serie_diaria:
        item["pct"] = round(item["qtd"] / max_diario * 100, 1)

    # Gráfico: faturamento mensal (últimos 12 meses)
    inicio_mes = hoje.replace(day=1) - timedelta(days=1)
    inicio_mes = inicio_mes.replace(day=1)
    inicio12 = inicio_mes - timedelta(days=365)
    mensal = {
        item["mes"]: item
        for item in (
            Pedido.objects.filter(criado_em__date__gte=inicio12)
            .exclude(status=STATUS_CANCELADO)
            .annotate(mes=TruncMonth("criado_em"))
            .values("mes")
            .annotate(total=Sum("total"), qtd=Count("id"))
        )
    }
    serie_mensal = []
    cursor = inicio12.replace(day=1)
    while cursor <= inicio_mes:
        dados = mensal.get(cursor, {"total": 0, "qtd": 0})
        serie_mensal.append(
            {
                "label": cursor.strftime("%m/%y"),
                "total": float(dados["total"] or 0),
                "qtd": dados["qtd"] or 0,
            }
        )
        cursor = _proximo_mes(cursor)
    max_mensal = max([item["total"] for item in serie_mensal], default=0) or 1
    for item in serie_mensal:
        item["pct"] = round(item["total"] / max_mensal * 100, 1)

    # Gráfico: distribuição dos pedidos por status (histórico completo)
    por_status = {
        item["status"]: item
        for item in Pedido.objects.values("status").annotate(qtd=Count("id"))
    }
    total_status = sum(item["qtd"] for item in por_status.values()) or 1
    serie_status = []
    for valor, rotulo in PedidoStatus.choices:
        dados = por_status.get(valor, {"qtd": 0})
        serie_status.append(
            {
                "valor": valor,
                "rotulo": rotulo,
                "qtd": dados["qtd"],
                "pct": round(dados["qtd"] / total_status * 100, 1),
            }
        )

    context = {
        "kpi": {
            "total_vendas": total_vendas,
            "faturamento": faturamento,
            "faturamento_dia": faturamento_dia,
            "faturamento_mes": faturamento_mes,
            "total_pedidos": total_pedidos,
            "pendentes": pendentes,
            "em_andamento": em_andamento,
            "concluidos": concluidos,
            "total_clientes": total_clientes,
            "total_produtos": total_produtos,
            "estoque_baixo": estoque_baixo,
            "ticket_medio": (faturamento / total_vendas) if total_vendas else 0,
            "produtos_demo": Produto.objects.filter(demonstracao=True).count(),
            "produtos_publicados": Produto.objects.filter(
                status=Produto.Status.PUBLICADO
            ).count(),
            "categorias_ativas": Categoria.objects.filter(ativa=True).count(),
        },
        "top_produtos": top_produtos,
        "ultimos_pedidos": ultimos_pedidos,
        "serie_diaria": serie_diaria,
        "serie_mensal": serie_mensal,
        "serie_status": serie_status,
        "produtos_baixo_estoque": Produto.objects.filter(
            status=Produto.Status.PUBLICADO
        ).annotate(total=Sum("variacoes__estoque")).filter(total__lte=5)[:6],
    }
    return render(request, "dashboard/home.html", context)


def _proximo_mes(data):
    if data.month == 12:
        return data.replace(year=data.year + 1, month=1)
    return data.replace(month=data.month + 1)


# ================================================================ Produtos
@painel_requerido
def produtos_lista(request):
    termo = (request.GET.get("q") or "").strip()
    status_filtro = request.GET.get("status", "")
    categoria_filtro = request.GET.get("categoria", "")
    marcacao = request.GET.get("marcacao", "")
    estoque_filtro = request.GET.get("estoque", "")
    ordenacao = request.GET.get("ordenacao", "-criado_em")

    queryset = Produto.objects.select_related("categoria").annotate(
        total_estoque=Sum("variacoes__estoque")
    )
    if termo:
        queryset = queryset.filter(
            Q(nome__icontains=termo)
            | Q(sku__icontains=termo)
            | Q(descricao__icontains=termo)
            | Q(resumo__icontains=termo)
        )
    if status_filtro in Produto.Status.values:
        queryset = queryset.filter(status=status_filtro)
    if categoria_filtro.isdigit():
        queryset = queryset.filter(categoria_id=categoria_filtro)
    if marcacao == "destaque":
        queryset = queryset.filter(destaque_home=True)
    elif marcacao == "novidade":
        queryset = queryset.filter(eh_novidade=True)
    elif marcacao == "promocao":
        queryset = queryset.filter(preco_promocional__isnull=False)
    if estoque_filtro == "disponivel":
        queryset = queryset.filter(total_estoque__gt=0)
    elif estoque_filtro == "baixo":
        queryset = queryset.filter(total_estoque__lte=5)
    elif estoque_filtro == "esgotado":
        queryset = queryset.filter(
            Q(total_estoque=0) | Q(total_estoque__isnull=True)
        )

    ordenacoes_validas = {
        "-criado_em", "criado_em", "nome", "-nome", "preco", "-preco",
        "-total_estoque", "total_estoque",
    }
    if ordenacao not in ordenacoes_validas:
        ordenacao = "-criado_em"

    context = {
        "produtos": queryset.order_by(ordenacao),
        "termo": termo,
        "status_filtro": status_filtro,
        "categoria_filtro": categoria_filtro,
        "marcacao": marcacao,
        "estoque_filtro": estoque_filtro,
        "ordenacao": ordenacao,
        "status_choices": Produto.Status.choices,
        "categorias": Categoria.objects.order_by("nome"),
    }
    return render(request, "dashboard/produtos.html", context)


def _salvar_imagens(request, produto):
    """Valida e grava as imagens enviadas na galeria do produto."""
    from produtos.models import ProdutoImagem

    arquivos = request.FILES.getlist("imagens")
    alt = (request.POST.get("alt_imagem") or "").strip()
    if not arquivos:
        return 0
    form = ProdutoImagemForm(
        data={"alt": alt}, files={"imagens": arquivos[0]}
    )
    if not form.is_valid():
        for erro in form.errors.get("imagens", []):
            messages.error(request, f"Imagem: {erro}")
        return 0

    ordem = produto.imagens.count()
    salvos = 0
    for arquivo in arquivos:
        # Valida tipo e tamanho de cada arquivo
        if arquivo.content_type not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
            messages.error(request, f"Formato inválido ignorado: {arquivo.name}")
            continue
        if arquivo.size > 8 * 1024 * 1024:
            messages.error(request, f"Arquivo acima de 8 MB ignorado: {arquivo.name}")
            continue
        ProdutoImagem.objects.create(
            produto=produto, imagem=arquivo, alt=alt, ordem=ordem
        )
        ordem += 1
        salvos += 1
    return salvos


@painel_requerido
def produto_form(request, pk=None):
    """Criar ou editar produto com galeria e variações (tamanho/cor/estoque)."""
    produto = get_object_or_404(Produto, pk=pk) if pk else None

    if request.method == "POST":
        form = ProdutoForm(request.POST, instance=produto)
        formset_pre = VariacaoFormSet(request.POST, instance=produto)
        if form.is_valid() and formset_pre.is_valid():
            produto_obj = form.save()
            formset = VariacaoFormSet(request.POST, instance=produto_obj)
            if formset.is_valid():
                formset.save()
                quantidade = _salvar_imagens(request, produto_obj)
                if quantidade:
                    messages.success(
                        request,
                        f"{quantidade} imagem(ns) adicionada(s) à galeria.",
                    )
                registrar_acao(
                    request,
                    acao="Produto editado" if pk else "Produto criado",
                    objeto=f"{produto_obj.nome} (#{produto_obj.pk})",
                    detalhes=f"Preço: R$ {produto_obj.preco}",
                )
                messages.success(
                    request,
                    f"Produto {'atualizado' if pk else 'criado'} com sucesso.",
                )
                return redirect("dashboard:produtos")
        else:
            formset_pre = VariacaoFormSet(request.POST, instance=produto)
        return render(
            request,
            "dashboard/produto_form.html",
            {
                "form": form,
                "formset": formset_pre,
                "produto": produto,
                "modo_edicao": bool(pk),
            },
        )

    form = ProdutoForm(instance=produto)
    formset = VariacaoFormSet(instance=produto)
    return render(
        request,
        "dashboard/produto_form.html",
        {
            "form": form,
            "formset": formset,
            "produto": produto,
            "modo_edicao": bool(pk),
            "imagem_form": ProdutoImagemForm(),
        },
    )


@painel_requerido
@require_POST
def produto_excluir(request, pk):
    produto = get_object_or_404(Produto, pk=pk)
    nome = produto.nome
    produto.delete()
    registrar_acao(
        request, acao="Produto excluído", objeto=f"{nome} (#{pk})"
    )
    messages.info(request, f'Produto "{nome}" excluído.')
    return redirect("dashboard:produtos")


@painel_requerido
@require_POST
def produto_toggle(request, pk):
    produto = get_object_or_404(Produto, pk=pk)
    novo = (
        Produto.Status.RASCUNHO
        if produto.status == Produto.Status.PUBLICADO
        else Produto.Status.PUBLICADO
    )
    Produto.objects.filter(pk=pk).update(status=novo)
    registrar_acao(
        request,
        acao="Produto publicado" if novo == Produto.Status.PUBLICADO else "Produto despublicado",
        objeto=f"{produto.nome} (#{pk})",
    )
    messages.success(
        request,
        f'Produto "{produto.nome}" '
        + ("publicado." if novo == Produto.Status.PUBLICADO else "despublicado."),
    )
    return redirect(request.META.get("HTTP_REFERER", "dashboard:produtos"))


# ================================================================ Pedidos
@painel_requerido
def pedidos_lista(request):
    termo = (request.GET.get("q") or "").strip()
    status_filtro = request.GET.get("status", "")
    data_inicio = request.GET.get("inicio", "")
    data_fim = request.GET.get("fim", "")

    queryset = Pedido.objects.select_related("cliente", "usuario").prefetch_related("itens")

    if termo:
        queryset = queryset.filter(
            Q(numero__icontains=termo)
            | Q(nome__icontains=termo)
            | Q(email__icontains=termo)
        )
    if status_filtro in PedidoStatus.values:
        queryset = queryset.filter(status=status_filtro)
    if data_inicio:
        queryset = queryset.filter(criado_em__date__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(criado_em__date__lte=data_fim)

    context = {
        "pedidos": queryset[:200],
        "termo": termo,
        "status_filtro": status_filtro,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "status_choices": PedidoStatus.choices,
    }
    return render(request, "dashboard/pedidos.html", context)


@painel_requerido
def pedido_detalhe(request, numero):
    pedido = get_object_or_404(
        Pedido.objects.select_related("cupom", "cliente").prefetch_related(
            "itens", "historico", "pagamentos"
        ),
        numero=numero,
    )
    status_form = PedidoStatusForm(initial={"status": pedido.status})
    return render(
        request,
        "dashboard/pedido_detalhe.html",
        {"pedido": pedido, "status_form": status_form},
    )


@painel_requerido
@require_POST
def pedido_atualizar_status(request, numero):
    pedido = get_object_or_404(Pedido, numero=numero)
    if request.POST.get("status") == PedidoStatus.PAGAMENTO_APROVADO:
        messages.error(
            request,
            "Pagamento aprovado só é definido pela confirmação do gateway "
            "de pagamento — não é possível marcar manualmente.",
        )
        return redirect("dashboard:pedido_detalhe", numero=numero)
    form = PedidoStatusForm(request.POST)
    if form.is_valid():
        status_anterior = pedido.get_status_display()
        alterar_status_pedido(
            pedido,
            form.cleaned_data["status"],
            usuario=request.user,
            observacao=form.cleaned_data.get("observacao", ""),
        )
        registrar_acao(
            request,
            acao="Status do pedido alterado",
            objeto=f"Pedido {pedido.numero}",
            detalhes=(
                f"{status_anterior} → "
                f"{pedido.get_status_display()}"
            ),
        )
        messages.success(
            request, f"Pedido {pedido.numero} atualizado para "
                     f'"{form.cleaned_data["status"]}".'
        )
    else:
        messages.error(request, "Status inválido.")
    return redirect("dashboard:pedido_detalhe", numero=numero)


# ================================================================ Clientes
@painel_requerido
def clientes_lista(request):
    termo = (request.GET.get("q") or "").strip()
    queryset = Cliente.objects.select_related("usuario").annotate(
        qtd_pedidos=Count("pedidos", distinct=True),
        gasto=Sum("pedidos__total", filter=~Q(pedidos__status=STATUS_CANCELADO)),
    )
    if termo:
        queryset = queryset.filter(
            Q(usuario__first_name__icontains=termo)
            | Q(usuario__last_name__icontains=termo)
            | Q(usuario__email__icontains=termo)
            | Q(cpf__icontains=termo)
            | Q(telefone__icontains=termo)
        )
    return render(
        request,
        "dashboard/clientes.html",
        {"clientes": queryset.order_by("-criado_em"), "termo": termo},
    )


@painel_requerido
def cliente_detalhe(request, pk):
    cliente = get_object_or_404(
        Cliente.objects.select_related("usuario"), pk=pk
    )
    pedidos = cliente.pedidos.prefetch_related("itens").order_by("-criado_em")
    return render(
        request,
        "dashboard/cliente_detalhe.html",
        {"cliente": cliente, "pedidos": pedidos},
    )


@painel_requerido
@require_POST
def cliente_status(request, pk):
    """Ativa/desativa a conta de um cliente (com registro da ação)."""
    cliente = get_object_or_404(
        Cliente.objects.select_related("usuario"), pk=pk
    )
    usuario = cliente.usuario

    if usuario == request.user:
        messages.error(request, "Você não pode desativar a própria conta aqui.")
        return redirect("dashboard:cliente_detalhe", pk=pk)
    if usuario.is_staff or usuario.is_superuser:
        messages.error(
            request,
            "Contas administrativas não podem ser desativadas por este recurso.",
        )
        return redirect("dashboard:cliente_detalhe", pk=pk)

    usuario.is_active = not usuario.is_active
    usuario.save(update_fields=["is_active"])
    acao = "Conta de cliente reativada" if usuario.is_active else "Conta de cliente desativada"
    registrar_acao(
        request,
        acao=acao,
        objeto=f"{cliente.nome_exibicao} (#{cliente.pk})",
        detalhes=f"E-mail: {usuario.email}",
    )
    messages.success(
        request,
        f"Conta de {cliente.nome_exibicao} "
        + ("reativada." if usuario.is_active else "desativada. O cliente não poderá mais entrar."),
    )
    return redirect("dashboard:cliente_detalhe", pk=pk)


# ================================================================ Categorias
@painel_requerido
def categorias_lista(request):
    return render(
        request,
        "dashboard/categorias.html",
        {"categorias": Categoria.objects.select_related("pai")},
    )


@painel_requerido
def categoria_form(request, pk=None):
    categoria = get_object_or_404(Categoria, pk=pk) if pk else None
    if request.method == "POST":
        form = CategoriaForm(request.POST, request.FILES, instance=categoria)
        if form.is_valid():
            obj = form.save()
            registrar_acao(
                request,
                acao="Categoria editada" if pk else "Categoria criada",
                objeto=f"{obj.nome} (#{obj.pk})",
            )
            messages.success(request, "Categoria salva.")
            return redirect("dashboard:categorias")
    else:
        form = CategoriaForm(instance=categoria)
    return render(
        request,
        "dashboard/formulario_simples.html",
        {"form": form, "titulo": "Editar categoria" if pk else "Nova categoria",
         "acao": "Salvar"},
    )


@painel_requerido
@require_POST
def categoria_excluir(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    if categoria.produtos.exists():
        messages.error(
            request,
            f'A categoria "{categoria.nome}" possui produtos e não pode ser excluída.',
        )
    else:
        nome_categoria = categoria.nome
        categoria.delete()
        registrar_acao(
            request, acao="Categoria excluída", objeto=f"{nome_categoria} (#{pk})"
        )
        messages.info(request, "Categoria excluída.")
    return redirect("dashboard:categorias")


# ================================================================ Cupons
@painel_requerido
def cupons_lista(request):
    return render(
        request,
        "dashboard/cupons.html",
        {"cupons": CupomDesconto.objects.all()},
    )


@painel_requerido
def cupom_form(request, pk=None):
    cupom = get_object_or_404(CupomDesconto, pk=pk) if pk else None
    if request.method == "POST":
        form = CupomForm(request.POST, instance=cupom)
        if form.is_valid():
            obj = form.save()
            registrar_acao(
                request,
                acao="Cupom editado" if pk else "Cupom criado",
                objeto=f"{obj.codigo} (#{obj.pk})",
            )
            messages.success(request, "Cupom salvo.")
            return redirect("dashboard:cupons")
    else:
        form = CupomForm(instance=cupom)
    return render(
        request,
        "dashboard/formulario_simples.html",
        {"form": form, "titulo": "Editar cupom" if pk else "Novo cupom",
         "acao": "Salvar"},
    )


@painel_requerido
@require_POST
def cupom_excluir(request, pk):
    cupom = get_object_or_404(CupomDesconto, pk=pk)
    codigo = cupom.codigo
    cupom.delete()
    registrar_acao(
        request, acao="Cupom excluído", objeto=f"{codigo} (#{pk})"
    )
    messages.info(request, "Cupom excluído.")
    return redirect("dashboard:cupons")


# ================================================================ Estoque
@painel_requerido
def estoque(request):
    baixo = Produto.objects.filter(status=Produto.Status.PUBLICADO).annotate(
        total=Sum("variacoes__estoque")
    ).filter(total__lte=5)

    if request.method == "POST":
        form = EstoqueEntradaForm(request.POST)
        if form.is_valid():
            variacao = form.cleaned_data["variacao"]
            quantidade = form.cleaned_data["quantidade"]
            tipo = form.cleaned_data.get("tipo") or "entrada"
            motivo = form.cleaned_data.get("motivo", "")
            try:
                if tipo == "saida":
                    registrar_saida(
                        variacao,
                        quantidade,
                        motivo=motivo or "Saída manual (painel)",
                        usuario=request.user,
                    )
                else:
                    registrar_entrada(
                        variacao,
                        quantidade,
                        motivo=motivo or "Entrada manual",
                        usuario=request.user,
                    )
            except EstoqueInsuficiente:
                form.add_error(
                    None,
                    f"Estoque insuficiente para saída: "
                    f"{variacao.produto.nome} possui {variacao.estoque} unidade(s).",
                )
            else:
                registrar_acao(
                    request,
                    acao="Estoque: entrada" if tipo == "entrada" else "Estoque: saída",
                    objeto=str(variacao),
                    detalhes=f"Quantidade: {quantidade}",
                )
                messages.success(
                    request,
                    "Entrada de estoque registrada."
                    if tipo == "entrada"
                    else "Saída de estoque registrada.",
                )
                return redirect("dashboard:estoque")
    else:
        form = EstoqueEntradaForm()

    # Filtros do histórico: produto, tipo e período.
    movimentos = MovimentoEstoque.objects.select_related(
        "variacao__produto", "variacao__tamanho", "variacao__cor", "usuario",
        "pedido",
    )
    produto_filtro = request.GET.get("produto", "")
    tipo_filtro = request.GET.get("tipo", "")
    data_inicio = request.GET.get("inicio", "")
    data_fim = request.GET.get("fim", "")
    if produto_filtro.isdigit():
        movimentos = movimentos.filter(variacao__produto_id=produto_filtro)
    if tipo_filtro in MovimentoEstoque.Tipo.values:
        movimentos = movimentos.filter(tipo=tipo_filtro)
    if data_inicio:
        movimentos = movimentos.filter(criado_em__date__gte=data_inicio)
    if data_fim:
        movimentos = movimentos.filter(criado_em__date__lte=data_fim)

    return render(
        request,
        "dashboard/estoque.html",
        {
            "form": form,
            "baixo_estoque": baixo,
            "movimentos": movimentos[:100],
            "produto_filtro": produto_filtro,
            "tipo_filtro": tipo_filtro,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "tipo_choices": MovimentoEstoque.Tipo.choices,
            "produtos_filtro": Produto.objects.filter(
                variacoes__isnull=False
            ).distinct().order_by("nome"),
            "total_movimentos": movimentos.count(),
        },
    )


# ================================================================ Clientes / Newsletter / Config
@painel_requerido
def newsletter_lista(request):
    return render(
        request,
        "dashboard/newsletter.html",
        {"inscritos": NewsletterInscrito.objects.all()[:300]},
    )


@painel_requerido
def configuracoes(request):
    instancia = ConfiguracaoLoja.carregar()
    if request.method == "POST":
        form = ConfiguracaoLojaForm(request.POST, request.FILES, instance=instancia)
        if form.is_valid():
            form.save()
            registrar_acao(
                request,
                acao="Configurações da loja atualizadas",
                objeto=instancia.nome_loja,
            )
            messages.success(request, "Configurações da loja atualizadas.")
            return redirect("dashboard:configuracoes")
    else:
        form = ConfiguracaoLojaForm(instance=instancia)
    return render(
        request,
        "dashboard/configuracoes.html",
        {"form": form, "gateway": gateway_atual_info()},
    )


# ================================================================ Relatórios
@painel_requerido
def relatorios(request):
    """Relatórios de vendas por período, com exportação CSV."""
    hoje = timezone.now().date()
    data_inicio = (request.GET.get("inicio") or "").strip()
    data_fim = (request.GET.get("fim") or "").strip()
    if not data_inicio:
        data_inicio = str(hoje - timedelta(days=29))
    if not data_fim:
        data_fim = str(hoje)

    no_periodo = Pedido.objects.filter(
        criado_em__date__gte=data_inicio, criado_em__date__lte=data_fim
    )
    vendas = no_periodo.exclude(status=STATUS_CANCELADO)
    cancelados = no_periodo.filter(status=STATUS_CANCELADO).count()

    faturamento = vendas.aggregate(t=Sum("total"))["t"] or 0
    qtd_vendas = vendas.count()
    maior_pedido = vendas.order_by("-total").first()

    # Série diária do período (limitada a 120 pontos para o gráfico)
    serie = []
    try:
        inicio_d = datetime.strptime(data_inicio, "%Y-%m-%d").date()
        fim_d = datetime.strptime(data_fim, "%Y-%m-%d").date()
    except ValueError:
        inicio_d, fim_d = hoje - timedelta(days=29), hoje
    if fim_d < inicio_d:
        inicio_d, fim_d = fim_d, inicio_d
    diarios = {
        item["dia"]: item
        for item in vendas.filter(criado_em__date__lte=fim_d)
        .annotate(dia=TruncDate("criado_em"))
        .values("dia")
        .annotate(qtd=Count("id"), total=Sum("total"))
    }
    cursor = inicio_d
    while cursor <= fim_d and len(serie) < 120:
        dados = diarios.get(cursor, {"qtd": 0, "total": 0})
        serie.append(
            {
                "label": cursor.strftime("%d/%m"),
                "qtd": dados["qtd"] or 0,
                "total": float(dados["total"] or 0),
            }
        )
        cursor += timedelta(days=1)
    max_serie = max([item["qtd"] for item in serie], default=0) or 1
    for item in serie:
        item["pct"] = round(item["qtd"] / max_serie * 100, 1)

    # Produtos mais vendidos no período
    top_produtos = (
        Produto.objects.annotate(
            vendidos=Sum(
                "pedidos__quantidade",
                filter=Q(
                    pedidos__pedido__criado_em__date__gte=data_inicio,
                    pedidos__pedido__criado_em__date__lte=data_fim,
                )
                & ~Q(pedidos__pedido__status=STATUS_CANCELADO),
            )
        )
        .exclude(vendidos__isnull=True)
        .order_by("-vendidos")[:10]
    )

    # Distribuição por status no período
    por_status = {
        item["status"]: item
        for item in no_periodo.values("status").annotate(qtd=Count("id"))
    }
    total_status = sum(item["qtd"] for item in por_status.values()) or 1
    serie_status = [
        {
            "valor": valor,
            "rotulo": rotulo,
            "qtd": por_status.get(valor, {"qtd": 0})["qtd"],
            "pct": round(por_status.get(valor, {"qtd": 0})["qtd"] / total_status * 100, 1),
        }
        for valor, rotulo in PedidoStatus.choices
    ]

    # Clientes novos no período
    novos_clientes = User.objects.filter(
        is_superuser=False, is_staff=False,
        date_joined__date__gte=data_inicio, date_joined__date__lte=data_fim,
    ).count()

    # Exportação CSV dos pedidos do período
    if request.GET.get("formato") == "csv":
        return _exportar_pedidos_csv(vendas.select_related("cliente"), data_inicio, data_fim)

    context = {
        "periodo_rotulo": f"{inicio_d.strftime('%d/%m/%Y')} a {fim_d.strftime('%d/%m/%Y')}",
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "kpi": {
            "faturamento": faturamento,
            "qtd_vendas": qtd_vendas,
            "ticket_medio": (faturamento / qtd_vendas) if qtd_vendas else 0,
            "total_pedidos": no_periodo.count(),
            "cancelados": cancelados,
            "novos_clientes": novos_clientes,
            "maior_pedido": maior_pedido.total if maior_pedido else 0,
        },
        "serie": serie,
        "top_produtos": top_produtos,
        "serie_status": serie_status,
        "acoes": RegistroAcao.objects.select_related("usuario")[:25],
    }
    return render(request, "dashboard/relatorios.html", context)


def _exportar_pedidos_csv(pedidos, data_inicio, data_fim):
    """Gera CSV dos pedidos do período (Excel-friendly, com BOM)."""
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = (
        f'attachment; filename="pedidos_{data_inicio}_{data_fim}.csv"'
    )
    resposta.write("\ufeff")
    escritor = csv.writer(resposta, delimiter=";")
    escritor.writerow(
        ["Número", "Data", "Cliente", "E-mail", "Status", "Total (R$)"]
    )
    for pedido in pedidos:
        escritor.writerow(
            [
                pedido.numero,
                pedido.criado_em.strftime("%d/%m/%Y %H:%M"),
                pedido.nome,
                pedido.email,
                pedido.get_status_display(),
                f"{pedido.total:.2f}".replace(".", ","),
            ]
        )
    return resposta
