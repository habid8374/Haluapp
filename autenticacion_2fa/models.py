from django.db import models
from django.conf import settings
import pyotp
import qrcode
import io
import base64


class DispositivoTOTP(models.Model):
    """Un dispositivo TOTP (Google Authenticator, Authy, etc.) por usuario."""
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='dispositivo_totp',
    )
    secret = models.CharField(max_length=64)
    confirmado = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Dispositivo TOTP'
        verbose_name_plural = 'Dispositivos TOTP'

    def __str__(self):
        estado = 'activo' if self.confirmado else 'pendiente'
        return f'TOTP {self.usuario} ({estado})'

    @classmethod
    def crear_para(cls, usuario):
        secret = pyotp.random_base32()
        disp, _ = cls.objects.get_or_create(usuario=usuario, defaults={'secret': secret})
        if disp.confirmado:
            return disp
        disp.secret = secret
        disp.save()
        return disp

    def verificar(self, codigo):
        totp = pyotp.TOTP(self.secret)
        return totp.verify(codigo, valid_window=1)

    def uri_provision(self, nombre_app='HALU'):
        totp = pyotp.TOTP(self.secret)
        return totp.provisioning_uri(
            name=self.usuario.email,
            issuer_name=nombre_app,
        )

    def qr_base64(self):
        uri = self.uri_provision()
        img = qrcode.make(uri)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue()).decode()
