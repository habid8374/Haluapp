"""
Backend de correo DEL SISTEMA vía Brevo HTTP API (HTTPS/443).

Se usa SOLO para correos sin contexto de institución (restablecimiento de
contraseña, alertas internas de la plataforma, allauth, etc.), usando una
cuenta Brevo EXCLUSIVA del propietario de la plataforma
(SISTEMA_BREVO_API_KEY / SISTEMA_BREVO_SENDER_EMAIL).

IMPORTANTE — aislamiento de créditos: este backend NUNCA debe usar
BREVO_API_KEY / BREVO_SENDER_EMAIL (esas son el respaldo compartido de
`admisiones.utils.enviar_correo_dinamico` para instituciones sin cuenta Brevo
propia). Mezclar ambos consumiría el plan de Brevo de un colegio con correos
que no son de ese colegio. Cada correo POR institución sigue su propio camino
en enviar_correo_dinamico, con las credenciales de esa institución.

Motivo de usar HTTPS y no SMTP: los puertos SMTP están bloqueados en Railway,
así que el backend SMTP por defecto de Django nunca lograría entregar estos
correos en producción.

Se activa automáticamente cuando SISTEMA_BREVO_API_KEY está configurado (ver
settings.py); si no, Django sigue usando SMTP/consola como antes.
"""
import html
import logging

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class BrevoApiEmailBackend(BaseEmailBackend):
    API_URL = 'https://api.brevo.com/v3/smtp/email'

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        # Deliberadamente SISTEMA_BREVO_* (cuenta propia del sistema), NUNCA
        # BREVO_API_KEY/BREVO_SENDER_EMAIL (esas son el respaldo compartido
        # por institución — ver docstring del módulo).
        api_key = getattr(settings, 'SISTEMA_BREVO_API_KEY', '')
        sender_email = getattr(settings, 'SISTEMA_BREVO_SENDER_EMAIL', '')
        if not api_key or not sender_email:
            if not self.fail_silently:
                raise RuntimeError(
                    "BrevoApiEmailBackend requiere SISTEMA_BREVO_API_KEY y "
                    "SISTEMA_BREVO_SENDER_EMAIL configurados en las variables de entorno "
                    "(cuenta Brevo propia del sistema, distinta de la de cualquier colegio)."
                )
            return 0
        sender_name = getattr(settings, 'SISTEMA_BREVO_SENDER_NAME', 'Halu Plataforma')

        enviados = 0
        for message in email_messages:
            try:
                if self._enviar_uno(message, api_key, sender_email, sender_name):
                    enviados += 1
            except Exception:
                logger.exception(
                    "BrevoApiEmailBackend: fallo enviando a %s", getattr(message, 'to', None)
                )
                if not self.fail_silently:
                    raise
        return enviados

    def _enviar_uno(self, message, api_key, sender_email, sender_name):
        destinatarios = [{'email': e} for e in (message.to or []) if e]
        if not destinatarios:
            return False

        html_content = None
        for content, mimetype in (getattr(message, 'alternatives', None) or []):
            if mimetype == 'text/html':
                html_content = content
                break

        payload = {
            'sender': {'name': sender_name, 'email': sender_email},
            'to': destinatarios,
            'subject': message.subject or '(sin asunto)',
        }
        texto_plano = message.body or ''
        if html_content:
            payload['htmlContent'] = html_content
            if texto_plano:
                payload['textContent'] = texto_plano
        else:
            # Sin versión HTML explícita: Brevo exige htmlContent; usamos el
            # texto plano escapado como HTML mínimo para no perder el mensaje.
            payload['textContent'] = texto_plano
            payload['htmlContent'] = (
                '<pre style="font-family:inherit;white-space:pre-wrap;">'
                + html.escape(texto_plano) + '</pre>'
            )

        cc = [{'email': e} for e in (getattr(message, 'cc', None) or []) if e]
        if cc:
            payload['cc'] = cc
        bcc = [{'email': e} for e in (getattr(message, 'bcc', None) or []) if e]
        if bcc:
            payload['bcc'] = bcc
        reply_to = getattr(message, 'reply_to', None) or []
        if reply_to:
            payload['replyTo'] = {'email': reply_to[0]}

        resp = requests.post(
            self.API_URL,
            headers={'api-key': api_key, 'Content-Type': 'application/json'},
            json=payload,
            timeout=15,
        )
        if resp.status_code != 201:
            raise RuntimeError(f"Brevo API {resp.status_code}: {resp.text[:300]}")
        return True
