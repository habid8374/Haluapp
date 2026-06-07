"""Modelos del módulo de Facturación Electrónica (Factus / DIAN).

⚠️ MÓDULO MULTI-INSTITUCIÓN Y OPCIONAL:
  * Cada institución tiene su propia ``ConfiguracionFactus`` (credenciales + estado).
  * El módulo solo opera si ``ConfiguracionFactus.activo == True``. Ese interruptor
    lo controla el PROPIETARIO de la plataforma (tras el pago del adicional del cliente).
  * Sin credenciales / sin activar, NADA del sistema se ve afectado.
"""
from django.db import models
from django.utils import timezone

from utils.encrypted_fields import EncryptedCharField


class ConfiguracionFactus(models.Model):
    """Configuración de Factus por institución (credenciales + estado del módulo)."""

    class Ambiente(models.TextChoices):
        SANDBOX = "SANDBOX", "Pruebas (Sandbox)"
        PRODUCCION = "PRODUCCION", "Producción"

    institucion = models.OneToOneField(
        "finanzas.InstitucionEducativa",
        on_delete=models.CASCADE,
        related_name="config_factus",
        verbose_name="Institución",
    )

    # ── Interruptor del módulo (lo activa el propietario tras el pago) ──
    activo = models.BooleanField(
        default=False,
        verbose_name="Módulo activo",
        help_text="Habilita la facturación electrónica para esta institución. "
        "Lo activa el propietario de la plataforma tras el pago del adicional.",
    )

    ambiente = models.CharField(
        max_length=12,
        choices=Ambiente.choices,
        default=Ambiente.SANDBOX,
        verbose_name="Ambiente",
    )

    # ── Modo B: emisión automática al confirmarse un pago ──
    emision_automatica = models.BooleanField(
        default=False,
        verbose_name="Emisión automática",
        help_text="Si está activo, se emite la factura electrónica automáticamente "
        "al registrarse/confirmarse cada pago (efectivo o Mercado Pago). "
        "Si está apagado, la factura se emite manualmente con el botón.",
    )

    # ── Credenciales Factus (OAuth2 password grant) — encriptadas ──
    client_id = EncryptedCharField(blank=True, null=True, verbose_name="Client ID (Factus)")
    client_secret = EncryptedCharField(blank=True, null=True, verbose_name="Client Secret (Factus)")
    username = EncryptedCharField(blank=True, null=True, verbose_name="Usuario / Email (Factus)")
    password = EncryptedCharField(blank=True, null=True, verbose_name="Contraseña (Factus)")

    # Rangos de numeración autorizados por la DIAN (se obtienen de Factus)
    numbering_range_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID Rango Numeración Factura (DIAN)"
    )
    numbering_range_id_nota_credito = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID Rango Numeración Nota Crédito (DIAN)"
    )
    numbering_range_id_nota_debito = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID Rango Numeración Nota Débito (DIAN)"
    )

    # Contador de consumo (base para facturar el adicional al cliente)
    facturas_emitidas = models.PositiveIntegerField(default=0, verbose_name="Facturas emitidas")

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración Factus"
        verbose_name_plural = "Configuraciones Factus"

    def __str__(self):
        return f"Factus [{self.get_ambiente_display()}] — {self.institucion} ({'ACTIVO' if self.activo else 'inactivo'})"

    @property
    def credenciales_completas(self) -> bool:
        return all([self.client_id, self.client_secret, self.username, self.password])

    @property
    def operativo(self) -> bool:
        """True si el módulo puede emitir facturas (activo + credenciales + rango)."""
        return bool(self.activo and self.credenciales_completas and self.numbering_range_id)


class FacturaElectronica(models.Model):
    """Registro de cada documento electrónico (factura / nota) emitido vía Factus."""

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente de envío"
        VALIDADA = "VALIDADA", "Validada por DIAN"
        RECHAZADA = "RECHAZADA", "Rechazada por DIAN"
        ERROR = "ERROR", "Error de comunicación"

    class Tipo(models.TextChoices):
        FACTURA = "FACTURA", "Factura de Venta"
        NOTA_CREDITO = "NOTA_CREDITO", "Nota Crédito"
        NOTA_DEBITO = "NOTA_DEBITO", "Nota Débito"

    tipo = models.CharField(
        max_length=14, choices=Tipo.choices, default=Tipo.FACTURA, verbose_name="Tipo de documento"
    )
    # Para notas: documento (factura) que corrige/anula
    documento_origen = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="notas", verbose_name="Documento de origen",
    )

    institucion = models.ForeignKey(
        "finanzas.InstitucionEducativa",
        on_delete=models.CASCADE,
        related_name="facturas_electronicas",
    )
    # Vínculos opcionales con el pago / estudiante de origen
    pago = models.ForeignKey(
        "finanzas.PagoRegistrado",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="facturas_electronicas",
    )
    # Para facturación al CAUSAR el cobro (mensual), sin pago aún.
    cuenta = models.ForeignKey(
        "finanzas.CuentaPorCobrarEstudiante",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="facturas_electronicas",
    )
    estudiante = models.ForeignKey(
        "gestion_academica.Estudiante",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="facturas_electronicas",
    )

    ambiente = models.CharField(max_length=12, default=ConfiguracionFactus.Ambiente.SANDBOX)
    reference_code = models.CharField(
        max_length=60, verbose_name="Código de referencia",
        help_text="Identificador idempotente enviado a Factus.",
    )

    estado = models.CharField(
        max_length=12, choices=Estado.choices, default=Estado.PENDIENTE
    )

    # Datos devueltos por Factus / DIAN
    numero = models.CharField(max_length=60, blank=True, verbose_name="Número DIAN")
    cufe = models.CharField(max_length=120, blank=True, verbose_name="CUFE")
    url_pdf = models.URLField(blank=True, verbose_name="URL del PDF")
    url_xml = models.URLField(blank=True, verbose_name="URL del XML")
    qr = models.TextField(blank=True, verbose_name="Contenido QR DIAN")

    # Trazabilidad / auditoría
    json_enviado = models.JSONField(null=True, blank=True)
    json_respuesta = models.JSONField(null=True, blank=True)
    mensaje = models.TextField(blank=True, verbose_name="Mensaje / Error")

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_validacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Factura Electrónica"
        verbose_name_plural = "Facturas Electrónicas"
        ordering = ["-fecha_creacion"]
        constraints = [
            models.UniqueConstraint(
                fields=["institucion", "reference_code"],
                name="factura_electronica_ref_unica_por_institucion",
            )
        ]

    def __str__(self):
        return f"FE {self.reference_code} [{self.estado}] — {self.institucion_id}"

    def marcar_validada(self, *, numero, cufe, url_pdf="", url_xml="", qr="", respuesta=None):
        self.numero = numero or ""
        self.cufe = cufe or ""
        self.url_pdf = url_pdf or ""
        self.url_xml = url_xml or ""
        self.qr = qr or ""
        self.json_respuesta = respuesta
        self.estado = self.Estado.VALIDADA
        self.fecha_validacion = timezone.now()
        self.mensaje = ""
        self.save()
