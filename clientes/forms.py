"""Formulários de clientes e endereços."""
from django import forms

from clientes.models import Cliente, Endereco
from usuarios.forms import EstiloBootstrapMixin


class PerfilForm(EstiloBootstrapMixin, forms.ModelForm):
    first_name = forms.CharField(label="Nome", max_length=150)
    last_name = forms.CharField(label="Sobrenome", max_length=150)
    email = forms.EmailField(label="E-mail")

    class Meta:
        model = Cliente
        fields = ["cpf", "telefone", "data_nascimento", "aceita_newsletter"]
        widgets = {
            "data_nascimento": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        usuario = self.instance.usuario
        self.fields["first_name"].initial = usuario.first_name
        self.fields["last_name"].initial = usuario.last_name
        self.fields["email"].initial = usuario.email
        self.fields["data_nascimento"].input_formats = ["%Y-%m-%d"]

    def clean_email(self):
        email = (self.cleaned_data["email"] or "").lower()
        from django.contrib.auth.models import User

        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.usuario_id).exists():
            raise forms.ValidationError("Já existe uma conta com este e-mail.")
        return email

    def save(self, commit=True):
        cliente = super().save(commit=False)
        usuario = cliente.usuario
        usuario.first_name = self.cleaned_data["first_name"]
        usuario.last_name = self.cleaned_data["last_name"]
        usuario.email = self.cleaned_data["email"]
        if commit:
            usuario.save()
            cliente.save()
        return cliente


class EnderecoForm(EstiloBootstrapMixin, forms.ModelForm):
    class Meta:
        model = Endereco
        fields = [
            "apelido", "destinatario", "cep", "logradouro", "numero",
            "complemento", "bairro", "cidade", "estado", "padrao",
        ]
        widgets = {
            "cep": forms.TextInput(attrs={"data-cep": "1", "placeholder": "00000-000"}),
            "logradouro": forms.TextInput(attrs={"placeholder": "Rua, avenida..."}),
            "numero": forms.TextInput(attrs={"placeholder": "123"}),
            "complemento": forms.TextInput(attrs={"placeholder": "Apto, bloco (opcional)"}),
            "cidade": forms.TextInput(attrs={"placeholder": "Sua cidade"}),
        }

    def clean_cep(self):
        cep = self.cleaned_data["cep"].strip()
        digitos = "".join(ch for ch in cep if ch.isdigit())
        if len(digitos) != 8:
            raise forms.ValidationError("Informe um CEP válido com 8 dígitos.")
        return digitos[:5] + "-" + digitos[5:]
