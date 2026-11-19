from django.contrib import admin

from pedidos.models import CupomDesconto, HistoricoStatus, Pedido, PedidoItem


class PedidoItemInline(admin.TabularInline):
    model = PedidoItem
    extra = 0
    readonly_fields = [
        "produto", "variacao", "nome", "tamanho_nome", "cor_nome",
        "sku", "preco_unitario", "quantidade", "subtotal",
    ]
    can_delete = False


class HistoricoStatusInline(admin.TabularInline):
    model = HistoricoStatus
    extra = 0
    readonly_fields = ["status", "observacao", "usuario", "criado_em"]
    can_delete = False


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ["numero", "nome", "status", "total", "criado_em"]
    list_filter = ["status", "criado_em"]
    search_fields = ["numero", "nome", "email", "telefone"]
    inlines = [PedidoItemInline, HistoricoStatusInline]
    readonly_fields = [
        "numero", "usuario", "cliente", "subtotal", "frete", "desconto",
        "total", "cupom", "criado_em", "atualizado_em",
    ]


@admin.register(CupomDesconto)
class CupomDescontoAdmin(admin.ModelAdmin):
    list_display = ["codigo", "tipo", "valor", "ativo", "usos", "usos_max", "fim"]
    list_filter = ["ativo", "tipo"]
    search_fields = ["codigo"]
