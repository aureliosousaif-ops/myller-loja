"""Formulários do painel administrativo."""
from django import forms

from categorias.models import Categoria
from core.models import ConfiguracaoLoja
from pedidos.models import CupomDesconto
from produtos.models import Produto, Variacao
from usuarios.forms import EstiloBootstrapMixin


class ProdutoForm(EstiloBootstrapMixin, forms.ModelForm):
    class Meta:
        model = Produto
        fields = [
            "nome", "categoria", "resumo", "descricao", "preco",
            "preco_promocional", "sku", "status", "destaque_home",
            "eh_novidade", "demonstracao", "peso_kg",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 6}),
            "resumo": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Rótulo vazio em português (o padrão do Django 6 ainda não traduz
        # essa string para pt_BR).
        self.fields["categoria"].empty_label = "— Selecione a categoria —"

    def clean_preco(self):
        preco = self.cleaned_data["preco"]
        if preco <= 0:
            raise forms.ValidationError("O preço deve ser maior que zero.")
        return preco

    def clean(self):
        cleaned = super().clean()
        promocional = cleaned.get("preco_promocional")
        preco = cleaned.get("preco")
        if promocional is not None and preco and promocional >= preco:
            raise forms.ValidationError(
                "O preço promocional deve ser menor que o preço normal."
            )
        return cleaned


class UploadMultiploInput(forms.ClearableFileInput):
    """Widget que aceita seleção múltipla de arquivos."""

    allow_multiple_selected = True


class ProdutoImagemForm(EstiloBootstrapMixin, forms.Form):
    """Upload múltiplo de imagens para a galeria do produto."""

    imagens = forms.ImageField(
        label="Adicionar imagens",
        required=False,
        widget=UploadMultiploInput(attrs={"multiple": True, "class": "form-control"}),
    )
    alt = forms.CharField(
        label="Texto alternativo (opcional)", max_length=200, required=False
    )

    def clean_imagens(self):
        imagem = self.cleaned_data.get("imagens")
        if imagem is None:
            return None
        permitidos = {"image/jpeg", "image/png", "image/webp", "image/gif"}
        if imagem.content_type not in permitidos:
            raise forms.ValidationError("Formato inválido. Use JPG, PNG, WEBP ou GIF.")
        if imagem.size > 8 * 1024 * 1024:
            raise forms.ValidationError("Imagem muito grande (máx. 8 MB).")
        return imagem


class VariacaoForm(EstiloBootstrapMixin, forms.ModelForm):
    class Meta:
        model = Variacao
        fields = ["tamanho", "cor", "sku", "preco_adicional", "estoque", "ativa"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Rótulos vazios em português (padrão do Django 6 sem tradução).
        self.fields["tamanho"].empty_label = "— Selecione —"
        self.fields["cor"].empty_label = "— Selecione —"

    @staticmethod
    def _vazio(valor):
        return valor in (None, "", 0, "0")

    def _linha_efetivamente_vazia(self):
        """True quando a linha extra não foi preenchida em nada."""
        prefixo = self.add_prefix("")
        dados = self.data
        ativa = dados.get(prefixo + "ativa")
        delete = dados.get(prefixo + "DELETE")
        return (
            self._vazio(dados.get(prefixo + "tamanho"))
            and self._vazio(dados.get(prefixo + "cor"))
            and not (dados.get(prefixo + "sku") or "").strip()
            and self._vazio(dados.get(prefixo + "estoque"))
            and self._vazio(dados.get(prefixo + "preco_adicional"))
            and not ativa
            and not delete
        )

    def has_changed(self):
        # Linha extra totalmente em branco não é alteração: o formset a
        # ignora em vez de exigir tamanho/cor/estoque de uma variação
        # que o usuário não quis criar.
        if self.is_bound and self.empty_permitted and self._linha_efetivamente_vazia():
            return False
        return super().has_changed()


VariacaoFormSet = forms.inlineformset_factory(
    Produto, Variacao, form=VariacaoForm,
    extra=1, can_delete=True,
)


class CategoriaForm(EstiloBootstrapMixin, forms.ModelForm):
    class Meta:
        model = Categoria
        fields = [
            "nome", "slug", "descricao", "imagem", "icone", "pai",
            "ordem", "ativa", "mostrar_home", "meta_title", "meta_description",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 3}),
        }


class CupomForm(EstiloBootstrapMixin, forms.ModelForm):
    class Meta:
        model = CupomDesconto
        fields = [
            "codigo", "tipo", "valor", "pedido_minimo", "inicio", "fim",
            "usos_max", "ativo", "descricao",
        ]
        widgets = {
            "inicio": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "fim": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["inicio"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["fim"].input_formats = ["%Y-%m-%dT%H:%M"]


class ConfiguracaoLojaForm(EstiloBootstrapMixin, forms.ModelForm):
    class Meta:
        model = ConfiguracaoLoja
        exclude = ["atualizado_em", "criado_em"]
        widgets = {
            "frase_apresentacao": forms.Textarea(attrs={"rows": 3}),
            "banner_texto": forms.Textarea(attrs={"rows": 3}),
            "newsletter_texto": forms.TextInput(attrs={"rows": 1}),
        }


class PedidoStatusForm(EstiloBootstrapMixin, forms.Form):
    status = forms.ChoiceField(label="Novo status")
    observacao = forms.CharField(
        label="Observação (opcional)", max_length=240, required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ex.: separado para envio"}),
    )

    def __init__(self, *args, **kwargs):
        from pedidos.models import PedidoStatus

        super().__init__(*args, **kwargs)
        # "Pagamento aprovado" só pode vir da confirmação real do gateway
        # (webhook) — o painel não marca pagamento como aprovado.
        self.fields["status"].choices = [
            (valor, rotulo)
            for valor, rotulo in PedidoStatus.choices
            if valor != PedidoStatus.PAGAMENTO_APROVADO
        ]


class EstoqueEntradaForm(EstiloBootstrapMixin, forms.Form):
    tipo = forms.ChoiceField(
        label="Tipo de movimento",
        choices=[("entrada", "Entrada"), ("saida", "Saída")],
        initial="entrada",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    variacao = forms.ModelChoiceField(
        label="Variação do produto", queryset=Variacao.objects.none(),
        empty_label="— Selecione a variação —",
    )
    quantidade = forms.IntegerField(
        label="Quantidade", min_value=1,
        initial=1, widget=forms.NumberInput(attrs={"min": 1}),
    )
    motivo = forms.CharField(label="Motivo", max_length=200, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["variacao"].queryset = Variacao.objects.select_related(
            "produto", "tamanho", "cor"
        ).order_by("produto__nome")
