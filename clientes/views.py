"""Views da área do cliente: perfil, endereços e pedidos."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy

from clientes.forms import EnderecoForm, PerfilForm
from clientes.models import Cliente, Endereco
from pedidos.models import Pedido, PedidoStatus


def _obter_cliente(request):
    cliente, _ = Cliente.objects.get_or_create(usuario=request.user)
    return cliente


@login_required
def perfil(request):
    cliente = _obter_cliente(request)
    pedidos_recentes = (
        cliente.pedidos.order_by("-criado_em")[:5] if cliente else []
    )
    return render(
        request,
        "clientes/perfil.html",
        {"cliente": cliente, "pedidos_recentes": pedidos_recentes},
    )


@login_required
def editar_perfil(request):
    cliente = _obter_cliente(request)
    if request.method == "POST":
        form = PerfilForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, "Dados atualizados com sucesso.")
            return redirect("clientes:perfil")
    else:
        form = PerfilForm(instance=cliente)
    return render(request, "clientes/editar_perfil.html", {"form": form})


# ---------------------------------------------------------------- Endereços
@login_required
def enderecos(request):
    cliente = _obter_cliente(request)
    lista = cliente.enderecos.all()
    return render(request, "clientes/enderecos.html", {"enderecos": lista})


@login_required
def endereco_novo(request):
    cliente = _obter_cliente(request)
    if request.method == "POST":
        form = EnderecoForm(request.POST)
        if form.is_valid():
            endereco = form.save(commit=False)
            endereco.cliente = cliente
            if not cliente.enderecos.exists():
                endereco.padrao = True
            endereco.save()
            messages.success(request, "Endereço cadastrado.")
            return redirect("clientes:enderecos")
    else:
        form = EnderecoForm()
    return render(request, "clientes/endereco_form.html", {"form": form, "titulo": "Novo endereço"})


@login_required
def endereco_editar(request, pk):
    cliente = _obter_cliente(request)
    endereco = get_object_or_404(Endereco, pk=pk, cliente=cliente)
    if request.method == "POST":
        form = EnderecoForm(request.POST, instance=endereco)
        if form.is_valid():
            form.save()
            messages.success(request, "Endereço atualizado.")
            return redirect("clientes:enderecos")
    else:
        form = EnderecoForm(instance=endereco)
    return render(
        request, "clientes/endereco_form.html",
        {"form": form, "titulo": "Editar endereço", "endereco": endereco},
    )


@login_required
def endereco_excluir(request, pk):
    cliente = _obter_cliente(request)
    endereco = get_object_or_404(Endereco, pk=pk, cliente=cliente)
    if request.method == "POST":
        endereco.delete()
        messages.info(request, "Endereço removido.")
    return redirect("clientes:enderecos")


@login_required
def endereco_padrao(request, pk):
    cliente = _obter_cliente(request)
    endereco = get_object_or_404(Endereco, pk=pk, cliente=cliente)
    if request.method == "POST":
        Endereco.objects.filter(cliente=cliente).update(padrao=False)
        endereco.padrao = True
        endereco.save(update_fields=["padrao"])
        messages.success(request, "Endereço padrão atualizado.")
    return redirect("clientes:enderecos")


# ---------------------------------------------------------------- Pedidos
@login_required
def meus_pedidos(request):
    pedidos = (
        Pedido.objects.filter(usuario=request.user)
        .select_related("cupom")
        .prefetch_related("itens")
    )
    return render(request, "clientes/meus_pedidos.html", {"pedidos": pedidos})


class AlterarSenhaView(PasswordChangeView):
    template_name = "clientes/alterar_senha.html"
    success_url = reverse_lazy("clientes:perfil")

    def form_valid(self, form):
        messages.success(self.request, "Senha alterada com sucesso.")
        return super().form_valid(form)
