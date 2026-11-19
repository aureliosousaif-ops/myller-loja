"""Formulários de autenticação e cadastro."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User


class EstiloBootstrapMixin:
    """Aplica classes Bootstrap 5 aos widgets dos formulários."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, (forms.CheckboxInput,)):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class RegistroForm(EstiloBootstrapMixin, UserCreationForm):
    first_name = forms.CharField(
        label="Nome", max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Seu nome"}),
    )
    last_name = forms.CharField(
        label="Sobrenome", max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Seu sobrenome"}),
    )
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={"placeholder": "voce@email.com"}),
    )
    telefone = forms.CharField(
        label="Telefone", max_length=20, required=False,
        widget=forms.TextInput(attrs={"placeholder": "(11) 99999-9999"}),
    )
    aceite_termos = forms.BooleanField(
        required=True,
        label="Li e aceito os Termos de Uso e a Política de Privacidade",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "username", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = ""
        self.fields["password1"].label = "Senha"
        self.fields["password2"].label = "Confirmar senha"
        self.fields["password1"].widget.attrs["placeholder"] = "Mínimo de 8 caracteres"
        self.fields["password2"].widget.attrs["placeholder"] = "Repita a senha"
        self.fields["username"].widget.attrs["placeholder"] = "nome de usuário"

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Já existe uma conta com este e-mail.")
        return email

    def clean(self):
        cleaned = super().clean()
        senha1 = cleaned.get("password1")
        senha2 = cleaned.get("password2")
        if senha1 and senha2 and senha1 != senha2:
            self.add_error("password2", "As senhas não coincidem.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"].lower()
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user


class FormLogin(EstiloBootstrapMixin, AuthenticationForm):
    """Login com estilo Bootstrap."""

    username = forms.CharField(
        label="E-mail ou usuário",
        widget=forms.TextInput(attrs={"placeholder": "voce@email.com", "autofocus": True}),
    )
    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={"placeholder": "••••••••"}),
    )

    def clean_username(self):
        """Permite entrar com o e-mail cadastrado (mapeia para o username)."""
        valor = (self.cleaned_data.get("username") or "").strip()
        if valor and "@" in valor:
            usuario = User.objects.filter(email__iexact=valor).first()
            if usuario:
                return usuario.username
        return valor
