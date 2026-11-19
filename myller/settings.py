"""
Configurações do projeto MYLLER.

Todos os valores sensíveis são lidos de variáveis de ambiente (.env).
Nunca deixe credenciais diretamente no código.
"""
from pathlib import Path
import os
import sys

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# Detecta o ambiente da Railway (deploy automático) para ativar as
# proteções de produção por padrão, sem depender de configuração manual.
EM_DEPLOY = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PUBLIC_DOMAIN"))

# ---------------------------------------------------------------- Segurança
# Em produção a chave SECRETA vem de variável de ambiente. Se estiver
# ausente em produção, o projeto falha de forma explícita — não existe
# chave "de fábrica" utilizável fora do desenvolvimento local.
DEBUG = env_bool("DJANGO_DEBUG", not EM_DEPLOY)

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-dev-only-secret-key-change-me"
    elif "test" in sys.argv:
        # A suíte de testes roda com DEBUG=False (padrão do Django).
        SECRET_KEY = "django-insecure-test-secret-key-da-suite"
    else:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY não definido. Gere uma chave com: "
            'python -c "from django.core.management.utils import '
            'get_random_secret_key; print(get_random_secret_key())"'
        )

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")

# Domínio público fornecido automaticamente pela Railway (*.up.railway.app).
# Domínios próprios são adicionados via DJANGO_ALLOWED_HOSTS /
# DJANGO_CSRF_TRUSTED_ORIGINS — nunca usamos ["*"].
_RAILWAY_DOMINIO = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
if _RAILWAY_DOMINIO:
    if _RAILWAY_DOMINIO not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_RAILWAY_DOMINIO)
    _RAILWAY_ORIGEM = f"https://{_RAILWAY_DOMINIO}"
    if _RAILWAY_ORIGEM not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_RAILWAY_ORIGEM)

# ---------------------------------------------------------------- Apps
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Apps MYLLER
    "core",
    "usuarios",
    "clientes",
    "categorias",
    "produtos",
    "estoque",
    "carrinho",
    "favoritos",
    "pedidos",
    "pagamentos",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# WhiteNoise (produção) — opcional, só ativo se instalado.
try:
    import whitenoise  # noqa: F401

    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
    STORAGES_STATIC = {
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
        }
    }
except ImportError:
    STORAGES_STATIC = {}

ROOT_URLCONF = "myller.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.store_context",
                "dashboard.context_processors.painel_notificacoes",
            ],
        },
    },
]

WSGI_APPLICATION = "myller.wsgi.application"

# ---------------------------------------------------------------- Banco de dados
# Produção: PostgreSQL via variáveis de ambiente. Desenvolvimento: SQLite.
_db_name = os.getenv("POSTGRES_DB", "")
if _db_name:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _db_name,
            "USER": os.getenv("POSTGRES_USER", ""),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": int(os.getenv("POSTGRES_CONN_MAX_AGE", "60")),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---------------------------------------------------------------- Senhas
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------- Internacionalização
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------- Arquivos estáticos e mídia
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Em produção o próprio Django serve os arquivos de mídia quando
# SERVE_MEDIA=True (padrão — plano gratuito da Railway não tem disco
# persistente nem S3 configurado). Pendência de evolução: migrar para
# armazenamento S3-compatible. Desative com SERVE_MEDIA=False.
SERVE_MEDIA = env_bool("SERVE_MEDIA", True)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        **STORAGES_STATIC.get("staticfiles", {}),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------- Autenticação
LOGIN_URL = "usuarios:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "core:home"
AUTH_PROFILE_MODULE = "clientes.Cliente"

# ---------------------------------------------------------------- Segurança (produção)
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"

# ---------------------------------------------------------------- E-mail
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
# Vazio por padrão: sem e-mail público fictício. Em produção, defina o
# remetente real via variável de ambiente DEFAULT_FROM_EMAIL.
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "")

# ---------------------------------------------------------------- Pagamentos (camada abstrata)
# none | mercadopago | stripe
PAYMENT_GATEWAY = os.getenv("PAYMENT_GATEWAY", "none").strip().lower()
MERCADOPAGO_ACCESS_TOKEN = os.getenv("MERCADOPAGO_ACCESS_TOKEN", "")
MERCADOPAGO_PUBLIC_KEY = os.getenv("MERCADOPAGO_PUBLIC_KEY", "")
MERCADOPAGO_WEBHOOK_SECRET = os.getenv("MERCADOPAGO_WEBHOOK_SECRET", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# ---------------------------------------------------------------- Frete (integração preparada)
# melhorenvio | correios | tabela (fallback sem credenciais)
FRETE_BACKEND = os.getenv("FRETE_BACKEND", "tabela").strip().lower()
MELHOR_ENVIO_TOKEN = os.getenv("MELHOR_ENVIO_TOKEN", "")
CORREIOS_CONTRATO = os.getenv("CORREIOS_CONTRATO", "")
CORREIOS_SENHA = os.getenv("CORREIOS_SENHA", "")
FRETE_TIMEOUT = int(os.getenv("FRETE_TIMEOUT", "8"))

# ---------------------------------------------------------------- Integrações externas
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000").rstrip("/")
WHATSAPP_NUMERO = os.getenv("WHATSAPP_NUMERO", "")
VIA_CEP_URL = os.getenv("VIA_CEP_URL", "https://viacep.com.br/ws")

# ---------------------------------------------------------------- Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {module} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "pedidos": {"level": "INFO"},
        "pagamentos": {"level": "INFO"},
    },
}
