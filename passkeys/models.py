"""
Credenciales WebAuthn (Passkeys) — login biométrico (huella / rostro).

Cada credencial pertenece a un usuario. Guardamos el ID de la credencial y la
llave pública (en base64url), el contador de firmas (protección anti-clonación)
y metadatos. La verificación criptográfica la hace la librería `webauthn`.
"""
from django.conf import settings
from django.db import models


class CredencialWebAuthn(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='credenciales_webauthn', verbose_name="Usuario",
    )
    # ID de la credencial (base64url) — único a nivel global.
    credential_id = models.TextField(unique=True, verbose_name="ID de credencial")
    # Llave pública COSE (base64url).
    public_key = models.TextField(verbose_name="Llave pública")
    # Contador de firmas: debe crecer en cada uso (anti-clonación).
    sign_count = models.BigIntegerField(default=0)
    transports = models.CharField(max_length=255, blank=True, default='')
    nombre_dispositivo = models.CharField(max_length=120, blank=True, default='', verbose_name="Nombre del dispositivo")
    creado_en = models.DateTimeField(auto_now_add=True)
    ultimo_uso = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = "Credencial WebAuthn"
        verbose_name_plural = "Credenciales WebAuthn"

    def __str__(self):
        return f"{self.nombre_dispositivo or 'Dispositivo'} — {self.usuario_id}"
