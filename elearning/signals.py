from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.contrib.sites.models import Site
from django.conf import settings
import logging

from .models import InscripcionCurso

logger = logging.getLogger(__name__)


def _absolute_site_url(path: str) -> str:
    site = Site.objects.get_current()
    domain = (site.domain or "").strip()
    path = path if path.startswith("/") else f"/{path}"
    if domain.startswith("http://") or domain.startswith("https://"):
        base = domain.rstrip("/")
    else:
        scheme = "http" if getattr(settings, "DEBUG", False) else "https"
        base = f"{scheme}://{domain}".rstrip("/")
    return f"{base}{path}"


@receiver(post_save, sender=InscripcionCurso)
def notificar_inscripcion_curso(sender, instance, created, **kwargs):
    if not (created and instance.activo):
        return
    estudiante = instance.estudiante
    curso = instance.curso
    institucion = curso.institucion

    email_destino = None
    if estudiante.usuario and estudiante.usuario.email:
        email_destino = estudiante.usuario.email

    if not email_destino:
        return

    try:
        path = reverse("elearning:aula_virtual", args=[curso.id])
        url_curso = _absolute_site_url(path)
    except Exception:
        url_curso = "#"

    asunto = f"Acceso a oferta e-learning: {curso.nombre}"
    html_content = (
        f"<p>Hola {estudiante.usuario.first_name},</p>"
        f"<p>Has sido matriculado en la oferta <strong>{curso.nombre}</strong>.</p>"
        f"<p><a href='{url_curso}'>Ir al aula virtual</a></p>"
        "<p>¡Muchos éxitos!</p>"
    )

    try:
        from admisiones.utils import enviar_correo_dinamico
        enviar_correo_dinamico(
            institucion=institucion,
            asunto=asunto,
            destinatarios=[email_destino],
            html_content=html_content,
        )
    except Exception as e:
        logger.error("Error enviando correo e-learning: %s", e)
