"""Modelos do painel administrativo: trilha de auditoria das ações."""
from django.conf import settings
from django.db import models


class RegistroAcao(models.Model):
    """Registro das ações administrativas importantes realizadas no painel.

    Nunca armazena senhas ou dados de autenticação — apenas a descrição
    da ação, o objeto afetado e quem a executou.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acoes_painel",
        verbose_name="Usuário",
    )
    acao = models.CharField("Ação", max_length=80)
    objeto = models.CharField("Objeto afetado", max_length=200, blank=True)
    detalhes = models.TextField("Detalhes", blank=True)
    ip = models.CharField("IP", max_length=45, blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Registro de ação"
        verbose_name_plural = "Registros de ações"
        ordering = ["-criado_em"]

    def __str__(self):
        alvo = f" — {self.objeto}" if self.objeto else ""
        return f"{self.acao}{alvo}"


def _obter_ip(request):
    if request is None:
        return ""
    ip = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if ip:
        return ip.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def registrar_acao(request=None, acao="", objeto="", detalhes=""):
    """Registra uma ação administrativa importante (melhor esforço).

    Nunca levanta exceção: a auditoria não pode derrubar a operação
    principal que motivou o registro.
    """
    try:
        usuario = getattr(request, "user", None) if request is not None else None
        if usuario is not None and not getattr(usuario, "is_authenticated", False):
            usuario = None
        return RegistroAcao.objects.create(
            usuario=usuario,
            acao=acao[:80],
            objeto=objeto[:200],
            detalhes=detalhes,
            ip=_obter_ip(request),
        )
    except Exception:  # noqa: BLE001 — auditoria é melhor esforço
        return None
