from django.db import models
from django.conf import settings


class RegistroAuditoria(models.Model):
    ACCIONES = [
        ('CREAR', 'Crear'),
        ('EDITAR', 'Editar'),
        ('ELIMINAR', 'Eliminar'),
    ]

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa',
        on_delete=models.CASCADE,
        verbose_name="Institución",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        verbose_name="Usuario",
    )
    accion = models.CharField(max_length=10, choices=ACCIONES, verbose_name="Acción")
    modelo = models.CharField(max_length=60, verbose_name="Modelo")  # 'Calificacion', 'PagoRegistrado', etc.
    objeto_id = models.PositiveIntegerField(verbose_name="ID del objeto")
    descripcion = models.TextField(verbose_name="Descripción")  # resumen legible
    valor_anterior = models.JSONField(null=True, blank=True, verbose_name="Valor anterior")
    valor_nuevo = models.JSONField(null=True, blank=True, verbose_name="Valor nuevo")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Dirección IP")
    fecha = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")

    class Meta:
        ordering = ['-fecha']
        verbose_name = "Registro de Auditoría"
        verbose_name_plural = "Registros de Auditoría"
        indexes = [
            models.Index(fields=['institucion', 'fecha'], name='auditoria_r_institu_idx'),
            models.Index(fields=['modelo', 'objeto_id'], name='auditoria_r_modelo_idx'),
        ]

    def __str__(self):
        return f"[{self.accion}] {self.modelo} #{self.objeto_id} — {self.fecha:%Y-%m-%d %H:%M}"


class RegistroSesion(models.Model):
    """Bitácora de inicios/cierres de sesión y acciones de seguridad.

    Captura quién se conectó, desde qué IP, con qué dispositivo y a qué hora,
    para que el panel superadmin pueda mostrar usuarios conectados e historial,
    y dejar constancia de cierres remotos y restablecimientos de contraseña de
    emergencia.
    """
    EVENTOS = [
        ('LOGIN', 'Inicio de sesión'),
        ('LOGOUT', 'Cierre de sesión'),
        ('CIERRE_REMOTO', 'Cierre remoto por administrador'),
        ('RESET_EMERGENCIA', 'Restablecimiento de contraseña (emergencia)'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='registros_sesion',
        verbose_name="Usuario",
    )
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Institución",
    )
    tipo_evento = models.CharField(
        max_length=20, choices=EVENTOS, default='LOGIN', verbose_name="Tipo de evento",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Dirección IP")
    user_agent = models.TextField(blank=True, default='', verbose_name="Dispositivo / navegador")
    session_key = models.CharField(
        max_length=40, blank=True, default='', db_index=True, verbose_name="Clave de sesión",
    )
    # Para acciones de seguridad (cierre remoto / reset): qué superadmin la ejecutó.
    ejecutado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='acciones_sesion_ejecutadas',
        verbose_name="Ejecutado por",
    )
    fecha = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")

    class Meta:
        ordering = ['-fecha']
        verbose_name = "Registro de Sesión"
        verbose_name_plural = "Registros de Sesión"
        indexes = [
            models.Index(fields=['usuario', 'fecha'], name='auditoria_s_usuario_idx'),
            models.Index(fields=['tipo_evento', 'fecha'], name='auditoria_s_evento_idx'),
            models.Index(fields=['institucion', 'fecha'], name='auditoria_s_institu_idx'),
        ]

    def __str__(self):
        return f"[{self.tipo_evento}] {self.usuario_id} — {self.fecha:%Y-%m-%d %H:%M}"
