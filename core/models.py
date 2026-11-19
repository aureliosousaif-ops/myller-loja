"""Modelos do núcleo: configurações da loja e newsletter."""
from urllib.parse import quote

from django.db import models
from django.utils.text import slugify

# -----------------------------------------------------------------contatos
# Contatos oficiais da MYLLER (usados como padrão e fallback nos templates).
# Podem ser sobrescritos pelo administrador no painel de configurações.
INSTAGRAM_OFICIAL = "https://www.instagram.com/myller_my/"
WHATSAPP_OFICIAL = "6391073145"  # +55 63 9107-3145 (só dígitos, com DDI)
TELEFONE_OFICIAL = "(63) 9107-3145"
MENSAGEM_WHATSAPP = (
    "Olá! Vim pelo site da MYLLER e gostaria de conhecer os produtos."
)


class ConfiguracaoLoja(models.Model):
    """Configurações gerais da loja (registro único configurado via painel)."""

    nome_loja = models.CharField("Nome da loja", max_length=120, default="MYLLER")
    logo = models.ImageField("Logo", upload_to="loja/logo/", blank=True)
    favicon = models.ImageField("Favicon", upload_to="loja/favicon/", blank=True)

    # Banner principal
    banner_imagem = models.ImageField("Banner principal", upload_to="loja/banner/", blank=True)
    banner_titulo = models.CharField("Título do banner", max_length=160, default="MYLLER")
    banner_subtitulo = models.CharField(
        "Subtítulo do banner", max_length=200,
        default="Essência, estilo e tecnologia em cada detalhe.",
    )
    banner_texto = models.TextField("Texto do banner", blank=True)
    banner_botao_texto = models.CharField("Texto do botão", max_length=60, default="Comprar agora")
    banner_botao_link = models.CharField("Link do botão", max_length=200, default="/produtos/")

    # Textos institucionais da homepage
    frase_apresentacao = models.TextField(
        "Frase de apresentação",
        default="A MYLLER nasce para quem veste tecnologia como estilo de vida. "
                "Peças premium, design sofisticado e conforto em cada coleção.",
    )
    titulo_categorias = models.CharField("Título: categorias", max_length=120, default="Categorias em destaque")
    titulo_mais_vendidos = models.CharField("Título: mais vendidos", max_length=120, default="Mais vendidos")
    titulo_novidades = models.CharField("Título: novidades", max_length=120, default="Novidades")
    titulo_promocoes = models.CharField("Título: promoções", max_length=120, default="Promoções")

    # Newsletter
    newsletter_titulo = models.CharField("Título da newsletter", max_length=160,
                                         default="Entre para o universo MYLLER")
    newsletter_texto = models.CharField("Texto da newsletter", max_length=240,
                                        default="Receba novidades, lançamentos e ofertas exclusivas em primeira mão.")

    # Contato e redes sociais
    # Sem e-mail público por padrão: o campo só é exibido quando preenchido
    # com um endereço real (configurado pelo proprietário no painel).
    email_contato = models.EmailField("E-mail de contato", blank=True, default="")
    telefone_contato = models.CharField("Telefone", max_length=40, blank=True)
    whatsapp = models.CharField("WhatsApp (só números)", max_length=20, blank=True)
    horario_atendimento = models.CharField("Horário de atendimento", max_length=120, blank=True,
                                           default="Segunda a sexta, das 9h às 18h")
    cnpj = models.CharField("CNPJ", max_length=20, blank=True)
    endereco_loja = models.CharField("Endereço da loja", max_length=240, blank=True)

    instagram = models.URLField("Instagram", blank=True)
    facebook = models.URLField("Facebook", blank=True)
    tiktok = models.URLField("TikTok", blank=True)
    youtube = models.URLField("YouTube", blank=True)

    # Dados de entrega / frete (fallback da tabela de frete)
    frete_valor_base = models.DecimalField("Frete base (R$)", max_digits=8, decimal_places=2, default=19.90)
    frete_prazo_dias = models.PositiveIntegerField("Prazo de entrega (dias úteis)", default=7)
    frete_gratis_acima = models.DecimalField(
        "Frete grátis para pedidos acima de (R$)", max_digits=8, decimal_places=2, default=399.00
    )
    frete_por_kg = models.DecimalField("Valor por quilo adicional (R$)", max_digits=8, decimal_places=2, default=4.50)
    prazo_estimado_observacao = models.CharField(
        "Observação de prazo", max_length=200,
        default="Prazos estimados, variáveis conforme região e transportadora.",
    )

    # SEO
    meta_description = models.CharField("Meta description", max_length=160, blank=True)

    atualizado_em = models.DateTimeField(auto_now=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Configuração da loja"
        verbose_name_plural = "Configurações da loja"

    def __str__(self):
        return self.nome_loja

    @classmethod
    def carregar(cls):
        """Retorna o registro de configuração, criando o padrão se necessário."""
        obj, criado = cls.objects.get_or_create(pk=1)
        if criado:
            # Relê do banco para garantir tipos corretos (Decimal, não float).
            obj.refresh_from_db()
        return obj

    @property
    def whatsapp_link(self):
        """Link direto do WhatsApp com mensagem inicial pré-preenchida."""
        numero = "".join(ch for ch in (self.whatsapp or WHATSAPP_OFICIAL) if ch.isdigit())
        if not numero:
            numero = WHATSAPP_OFICIAL
        if not numero.startswith("55"):
            numero = f"55{numero}"
        return f"https://wa.me/{numero}?text={quote(MENSAGEM_WHATSAPP, safe='')}"

    @property
    def whatsapp_formatado(self):
        """Número exibido para o visitante: (63) 9107-3145."""
        numero = "".join(ch for ch in (self.whatsapp or WHATSAPP_OFICIAL) if ch.isdigit())
        if numero.startswith("55") and len(numero) >= 12:
            numero = numero[2:]
        if len(numero) == 11:
            return f"({numero[:2]}) {numero[2:7]}-{numero[7:]}"
        if len(numero) == 10:
            return f"({numero[:2]}) {numero[2:6]}-{numero[6:]}"
        return numero or TELEFONE_OFICIAL

    @property
    def instagram_url(self):
        """Instagram oficial da loja (fallback para o perfil oficial MYLLER)."""
        return self.instagram or INSTAGRAM_OFICIAL


class NewsletterInscrito(models.Model):
    """Assinantes da newsletter."""

    email = models.EmailField("E-mail", unique=True)
    nome = models.CharField("Nome", max_length=120, blank=True)
    ativo = models.BooleanField("Ativo", default=True)
    origem = models.CharField("Origem", max_length=60, default="site")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Inscrito na newsletter"
        verbose_name_plural = "Inscritos na newsletter"
        ordering = ["-criado_em"]

    def __str__(self):
        return self.email


class PaginaInstitucional(models.Model):
    """Páginas estáticas editáveis (Sobre, Trocas e Devoluções, Privacidade...)."""

    titulo = models.CharField("Título", max_length=160)
    slug = models.SlugField("Slug", unique=True, max_length=180)
    conteudo = models.TextField("Conteúdo")
    ativa = models.BooleanField("Ativa", default=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Página institucional"
        verbose_name_plural = "Páginas institucionais"
        ordering = ["titulo"]

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.titulo)
        super().save(*args, **kwargs)
