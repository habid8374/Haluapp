from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail, get_connection
from django.conf import settings
from django.urls import reverse
from django.contrib.sites.models import Site
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

    if not (institucion.email_host_user and institucion.email_host_password):
        logger.warning(
            "notificar_inscripcion_curso: SMTP no configurado para %s; no se envía correo.",
            institucion,
        )
        return

    try:
        path = reverse("elearning:aula_virtual", args=[curso.id])
        url_curso = _absolute_site_url(path)
    except Exception:
        url_curso = "#"

    asunto = f"Acceso a oferta e-learning: {curso.nombre}"
    mensaje = (
        f"Hola {estudiante.usuario.first_name},\n\n"
        f"Has sido matriculado en la oferta «{curso.nombre}».\n\n"
        f"Enlace al aula: {url_curso}\n\n"
        "¡Muchos éxitos!"
    )

    connection = get_connection(
        host=institucion.email_host or "smtp.gmail.com",
        port=institucion.email_port or 587,
        username=institucion.email_host_user,
        password=institucion.email_host_password,
        use_tls=institucion.email_use_tls,
    )
    from_email = f"{institucion.nombre} <{institucion.email_host_user}>"

    try:
        send_mail(
            asunto,
            mensaje,
            from_email,
            [email_destino],
            connection=connection,
            fail_silently=False,
        )
    except Exception as e:
        logger.error("Error enviando correo e-learning: %s", e)
