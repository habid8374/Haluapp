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
