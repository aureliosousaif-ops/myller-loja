"""ASGI config for myller project."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myller.settings")

application = get_asgi_application()
