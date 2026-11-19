"""Views de checkout, detalhe do pedido e cancelamento."""
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from carrinho.services import obter_carrinho, totais_carrinho
from clientes.forms import EnderecoForm
from clientes.models import Cliente
from pagamentos.gateways import GatewayError, gateway_atual_info, obter_gateway
from pedidos.frete import calcular_frete
from pedidos.models import Pedido, PedidoStatus
from pedidos.services import alterar_status_pedido, criar_pedido
from usuarios.forms import EstiloBootstrapMixin


class CheckoutForm(EstiloBootstrapMixin, forms.Form):
    """Identificação e endereço de entrega no checkout."""

    nome = forms.CharField(
        label="Nome completo", max_length=160,
        widget=forms.TextInput(attrs={"placeholder": "Seu nome completo"}),
    )
    email = forms.EmailField(
        label="E-mail", widget=forms.EmailInput(attrs={"placeholder": "voce@email.com"})
    )
    telefone = forms.CharField(
        label="Telefone", max_length=20,
        widget=forms.TextInput(attrs={"placeholder": "(11) 99999-9999"}),
    )
    cep = forms.CharField(
        label="CEP", max_length=9,
        widget=forms.TextInput(attrs={"placeholder": "00000-000", "data-cep": "1"}),
    )
    logradouro = forms.CharField(label="Endereço", max_length=200)
    numero = forms.CharField(label="Número", max_length=20)
    complemento = forms.CharField(
        label="Complemento", max_length=120, required=False,
        widget=forms.TextInput(attrs={"placeholder": "Opcional"}),
    )
    bairro = forms.CharField(label="Bairro", max_length=100)
    cidade = forms.CharField(label="Cidade", max_length=100)
    estado = forms.CharField(label="Estado (UF)", max_length=2)
    observacao = forms.CharField(
        label="Observação para a entrega", max_length=300, required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Opcional"}),
    )

    def clean_cep(self):
        digitos = "".join(ch for ch in self.cleaned_data["cep"] if ch.isdigit())
        if len(digitos) != 8:
            raise forms.ValidationError("Informe um CEP válido com 8 dígitos.")
        return digitos[:5] + "-" + digitos[5:]

    def clean_estado(self):
        return (self.cleaned_data["estado"] or "").upper()[:2]

    def clean(self):
        cleaned = super().clean()
        obrigatorios = ["nome", "email", "telefone", "logradouro", "numero", "bairro", "cidade", "estado"]
        if all(cleaned.get(c) for c in obrigatorios) and not cleaned.get("cep"):
            self.add_error("cep", "Informe o CEP.")
        return cleaned


def _frete_info(request):
    """Dados de frete da sessão sempre com as chaves esperadas pelos templates."""
    dados = {
        "cep": "",
        "valor": "",
        "prazo": "",
        "transportadora": "",
        "mensagem": "",
        "estimativa": True,
    }
    dados.update(request.session.get("frete") or {})
    return dados


def checkout(request):
    """Página de checkout: identificação, endereço, frete, cupom e pagamento."""
    carrinho = obter_carrinho(request, criar=False)
    if carrinho is None or not carrinho.itens.exists():
        messages.info(request, "Seu carrinho está vazio.")
        return redirect("carrinho:pagina")

    # Dados pré-preenchidos
    dados_iniciais = {}
    cliente = None
    if request.user.is_authenticated:
        cliente = Cliente.objects.filter(usuario=request.user).first()
        if cliente:
            dados_iniciais.update(
                {
                    "nome": cliente.nome_exibicao,
                    "email": request.user.email,
                    "telefone": cliente.telefone,
                }
            )
            endereco = cliente.endereco_padrao()
            if endereco:
                dados_iniciais.update(
                    {
                        "cep": endereco.cep,
                        "logradouro": endereco.logradouro,
                        "numero": endereco.numero,
                        "complemento": endereco.complemento,
                        "bairro": endereco.bairro,
                        "cidade": endereco.cidade,
                        "estado": endereco.estado,
                    }
                )

    frete_info = _frete_info(request)
    form = CheckoutForm(initial=dados_iniciais) if request.method == "GET" else None

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            return _finalizar(request, carrinho, form, cliente)

    totais = totais_carrinho(
        request, frete=Decimal(str(frete_info.get("valor", "0") or "0"))
    )

    context = {
        "form": form,
        "carrinho": carrinho,
        "totais": totais,
        "frete_info": frete_info,
        "gateway": gateway_atual_info(),
        "endereco_form": EnderecoForm,
    }
    return render(request, "pedidos/checkout.html", context)


def _finalizar(request, carrinho, form, cliente):
    """Cria o pedido e inicia o pagamento real no gateway configurado."""
    frete_info = _frete_info(request)
    totais = totais_carrinho(
        request, frete=Decimal(str(frete_info.get("valor", "0") or "0"))
    )
    if totais["cupom_mensagem"]:
        messages.warning(request, totais["cupom_mensagem"])
        return render(
            request,
            "pedidos/checkout.html",
            {
                "form": form,
                "carrinho": carrinho,
                "totais": totais,
                "frete_info": frete_info,
                "gateway": gateway_atual_info(),
            },
        )

    dados = form.cleaned_data
    dados.update(
        {
            "subtotal": totais["subtotal"],
            "desconto": totais["desconto"],
            "frete": totais["frete"],
            "total": totais["total"],
            "metodo_entrega": frete_info.get("transportadora", "Entrega estimada"),
            "prazo_entrega": frete_info.get("prazo", ""),
        }
    )

    with transaction.atomic():
        pedido, erro = criar_pedido(
            carrinho=carrinho,
            dados=dados,
            usuario=request.user if request.user.is_authenticated else None,
            chave_sessao=request.session.session_key or "",
        )
    if erro:
        messages.error(request, erro)
        return redirect("carrinho:pagina")

    # Registra o vínculo do cliente (para compradores logados)
    if cliente is None and request.user.is_authenticated:
        cliente, _ = Cliente.objects.get_or_create(usuario=request.user)
    if cliente:
        pedido.cliente = cliente
        pedido.save(update_fields=["cliente"])

    # Inicia a cobrança real no gateway
    gateway = obter_gateway()
    try:
        resultado = gateway.iniciar_pagamento(pedido, request)
    except GatewayError as exc:
        messages.warning(request, str(exc))
        resultado = {"ok": False, "mensagem": str(exc)}

    if resultado.get("ok") and resultado.get("link"):
        request.session.pop("frete", None)
        return redirect(resultado["link"])

    request.session.pop("frete", None)
    return render(
        request,
        "pedidos/confirmacao.html",
        {
            "pedido": pedido,
            "mensagem_gateway": resultado.get("mensagem", ""),
            "gateway": gateway_atual_info(),
        },
    )


def _pertence_ao_usuario(request, pedido):
    if request.user.is_authenticated and pedido.usuario_id == request.user.id:
        return True
    if (
        not pedido.usuario_id
        and request.session.session_key
        and pedido.chave_sessao == request.session.session_key
    ):
        return True
    return request.user.is_staff


def pedido_detalhe(request, numero):
    """Detalhe do pedido com acompanhamento de status."""
    pedido = get_object_or_404(
        Pedido.objects.select_related("cupom").prefetch_related(
            "itens", "historico", "pagamentos"
        ),
        numero=numero,
    )
    if not _pertence_ao_usuario(request, pedido):
        messages.error(request, "Você não tem permissão para ver este pedido.")
        return redirect("core:home")
    return render(
        request,
        "pedidos/detalhe.html",
        {"pedido": pedido, "gateway": gateway_atual_info()},
    )


def api_status_pedido(request, numero):
    """Polling do status do pedido (somente leitura — a aprovação vem do webhook)."""
    pedido = get_object_or_404(Pedido, numero=numero)
    if not _pertence_ao_usuario(request, pedido):
        return JsonResponse({"ok": False}, status=403)
    ultimo_pagamento = pedido.pagamentos.order_by("-criado_em").first()
    return JsonResponse(
        {
            "ok": True,
            "status": pedido.status,
            "status_display": pedido.get_status_display(),
            "pagamento_status": ultimo_pagamento.status if ultimo_pagamento else None,
        }
    )


@login_required
def cancelar_pedido(request, numero):
    pedido = get_object_or_404(Pedido, numero=numero, usuario=request.user)
    if request.method == "POST":
        if not pedido.pode_ser_cancelado:
            messages.error(request, "Este pedido não pode mais ser cancelado.")
        else:
            alterar_status_pedido(
                pedido, PedidoStatus.CANCELADO,
                usuario=request.user, observacao="Cancelado pelo cliente.",
            )
            messages.info(request, f"Pedido {pedido.numero} cancelado.")
    return redirect("pedidos:detalhe", numero=numero)
