# finanzas/models.py
from django.db import models
from gestion_academica.models import NivelEscolaridad
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum
from django.utils import timezone
import datetime
from datetime import date
import calendar
from decimal import Decimal
from .managers import CuentaPorCobrarEstudianteManager
from django.db import transaction
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import timedelta
from django.apps import apps
from utils.encrypted_fields import EncryptedCharField




# Lista de nombres de meses en español (como constante global, fuera de cualquier función)
NOMBRES_MESES_ESPANOL = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
    7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
}

ESTADOS_CUENTA = [
    ('PENDIENTE', 'Pendiente'),
    ('PAGADO_PARCIAL', 'Pagado Parcialmente'),
    ('PAGADO', 'Pagado Completamente'),
    ('VENCIDO', 'Vencido'),
    ('ANULADO', 'Anulado'),
]

class InstitucionEducativa(models.Model):
    
    nombre = models.CharField(max_length=100, verbose_name="Nombre de la Institución Educativa")
    nit = models.CharField(max_length=20, unique=True, verbose_name="NIT")
    direccion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Dirección")
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")
    correo_electronico = models.EmailField(blank=True, null=True, verbose_name="Correo Electrónico de Contacto")
    logo = models.ImageField(upload_to='logos/', blank=True, null=True, verbose_name="Logo")
    texto_aprobacion = models.CharField(max_length=255, blank=True, default="Aprobado por Secretaria de Educación Departamental", verbose_name="Texto de Aprobación")
    texto_resolucion = models.TextField(blank=True, default="Resolución Ampliación Nivel Básica Primaria\nN°3161 del 18 de octubre de 2022", verbose_name="Texto de Resolución(es)")
    codigo_dane = models.CharField(max_length=50, blank=True, verbose_name="Código de Identificación DANE")
    ciudad_departamento = models.CharField(max_length=150, blank=True, default="Sabanalarga - Atlántico", verbose_name="Ciudad y Departamento")
    nombre_rectora = models.CharField(max_length=150, blank=True, verbose_name="Nombre Completo del Rector(a)")
    firma_rectora = models.ImageField(upload_to='firmas/', blank=True, null=True, verbose_name="Firma del Rector(a) (Imagen)")
    eslogan = models.CharField(max_length=255, blank=True, null=True, verbose_name="Eslogan (Opcional)")
    cuenta_bancaria = models.CharField(max_length=255, blank=True, null=True, verbose_name="Información Cuenta Bancaria", help_text="Ej: Ahorros Bancolombia 123-456789-00")
    pagos_digitales = models.CharField(max_length=255, blank=True, null=True, verbose_name="Información Nequi/Daviplata", help_text="Ej: Nequi 300-123-4567")
    TIPO_INSTITUCION_CHOICES = [
        ('privado', 'Privado'),
        ('publico', 'Público'),
    ]
    tipo_institucion = models.CharField(
        max_length=10,
        choices=TIPO_INSTITUCION_CHOICES,
        default='privado',
        verbose_name="Tipo de Institución",
        help_text="Privado: cobra mensualidades. Público: financiado por el Estado, sin cobros a estudiantes.",
    )
    IDIOMA_CHOICES = [
        ('en', 'Inglés'),
        ('fr', 'Francés'),
        ('pt', 'Portugués'),
        ('de', 'Alemán'),
        ('zh', 'Mandarín'),
    ]
    es_bilingue = models.BooleanField(
        default=False,
        verbose_name="Institución Bilingüe / Multiidioma",
        help_text="Activa campos de segundo idioma en materias y mallas curriculares.",
    )
    idioma_secundario = models.CharField(
        max_length=5,
        choices=IDIOMA_CHOICES,
        blank=True,
        default='en',
        verbose_name="Idioma Secundario de Instrucción",
        help_text="Idioma en que se dictan las materias bilingües (por defecto inglés).",
    )
    nota_minima_aprobacion = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('3.0'), verbose_name="Nota Mínima para Aprobar", help_text="La nota que un estudiante debe alcanzar o superar para aprobar (ej: 3.0, 3.5).")
    escala_valorativa_texto = models.CharField(max_length=255, blank=True, default="Sup = Superior, Alt = Alto, Bas = Básico, Baj = Bajo", verbose_name="Texto de la Escala Valorativa")
    google_calendar_embed_code = models.TextField(blank=True, null=True, verbose_name="Código para insertar Google Calendar")
    mp_public_key_test = models.CharField(max_length=255, blank=True, null=True, verbose_name="Public Key de Prueba (Mercado Pago)")
    mp_access_token_test = EncryptedCharField(blank=True, null=True, verbose_name="Access Token de Prueba (Mercado Pago)")
    mp_public_key_prod = models.CharField(max_length=255, blank=True, null=True, verbose_name="Public Key de Producción (Mercado Pago)")
    mp_access_token_prod = EncryptedCharField(blank=True, null=True, verbose_name="Access Token de Producción (Mercado Pago)")
    mp_modo_produccion = models.BooleanField(default=False, verbose_name="¿Activar modo producción para Mercado Pago?", help_text="Si está desmarcado, se usarán las credenciales de prueba.")
    mp_webhook_secret = models.CharField(
        max_length=255,
        blank=False,
        default="",
        verbose_name="Secret de firma Webhooks (Mercado Pago)",
        help_text="Secret generado en Mercado Pago > Tu integración > Webhooks (obligatorio para validar notificaciones).",
    )
    google_api_key = EncryptedCharField(
        blank=False,
        default="",
        verbose_name="Google API Key (Gemini)",
        help_text="Clave de la API de Google AI / Gemini para esta institución (obligatoria para funciones de IA).",
    )
    email_host_user = models.EmailField(max_length=255, blank=True, null=True, verbose_name="Correo para Envío de Notificaciones (SMTP User)", help_text="Ej: notificaciones@micolegio.com")
    email_host_password = EncryptedCharField(blank=True, null=True, verbose_name="Contraseña de Aplicación (SMTP Password)", help_text="¡IMPORTANTE! Usa una contraseña de aplicación generada, no tu contraseña principal.")
    email_host = models.CharField(max_length=255, blank=True, null=True, verbose_name="Servidor SMTP", default="smtp.gmail.com")
    email_port = models.PositiveIntegerField(blank=True, null=True, verbose_name="Puerto SMTP", default=587)
    email_use_tls = models.BooleanField(default=True, verbose_name="¿Usar TLS?")
    activa = models.BooleanField(
        default=True,
        verbose_name="Institución Activa",
        help_text="Desmarca esta casilla para bloquear el acceso de todos los usuarios de esta institución (excepto super-admins)."
    )

    # ---- Política de bloqueo del portal del estudiante por mora (Fase C) ----
    bloquear_portal_por_mora = models.BooleanField(
        default=True,
        verbose_name="¿Bloquear portal del estudiante si tiene mensualidades vencidas?",
        help_text=(
            "Si está activo, los estudiantes con cuentas vencidas no podrán "
            "acceder a deberes, actividades, calificaciones, lecciones, ni "
            "boletín. Solo verán su estado de cartera con CTA para pagar."
        ),
    )
    dias_gracia_mora = models.PositiveIntegerField(
        default=0,
        verbose_name="Días de gracia para mora",
        help_text=(
            "Días de margen tras el vencimiento antes de bloquear el portal. "
            "Ej: 3 → no se bloquea hasta 3 días después del vencimiento. "
            "Solo aplica si 'bloquear_portal_por_mora' está activo."
        ),
    )
    tarifa_mensual_plataforma = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name="Tarifa Mensual de la Plataforma ($)",
        help_text="El valor que esta institución paga mensualmente por usar HALU."
    )
    comision_por_transaccion_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name="Comisión por Transacción (%)",
        help_text="Porcentaje de comisión a cobrar sobre cada pago procesado por la pasarela. Ej: 1.5 para 1.5%"
    )
    
    # ✅ CAMBIA la referencia a 'Aspirante' para que sea un texto
    aspirante = models.ForeignKey(
        'admisiones.Aspirante', # <-- Así, como texto
        on_delete=models.CASCADE, 
        related_name='cuentas_por_cobrar_estudiante', # Nombre de relación único
        null=True, blank=True
    )
    
    def __str__(self):
        return self.nombre

    def clean(self):
        super().clean()
        errs = {}
        if not (self.google_api_key or "").strip():
            errs["google_api_key"] = "La API key de Google AI / Gemini es obligatoria para esta institución."
        if not (self.mp_webhook_secret or "").strip():
            errs["mp_webhook_secret"] = "El secret de firma de webhooks de Mercado Pago es obligatorio."
        if errs:
            raise ValidationError(errs)

    class Meta:
        verbose_name = "Institución Educativa"
        verbose_name_plural = "Instituciones Educativas"
        permissions = [
            ("can_manage_institutions", "Puede gestionar instituciones educativas"),
            (
                "acceso_modulo_finanzas",
                "Puede acceder al módulo de finanzas (panel, reportes y exportaciones)",
            ),
        ]

class CuentaContable(models.Model):
    class TipoCuenta(models.TextChoices):
        INGRESO = 'INGRESO', 'Ingreso'
        GASTO = 'GASTO', 'Gasto'
        ACTIVO = 'ACTIVO', 'Activo'
        PASIVO = 'PASIVO', 'Pasivo'
        PATRIMONIO = 'PATRIMONIO', 'Patrimonio'

    codigo = models.CharField(max_length=20, unique=True, verbose_name="Código PUC")
    nombre = models.CharField(max_length=200, verbose_name="Nombre de la Cuenta")
    tipo = models.CharField(max_length=20, choices=TipoCuenta.choices, verbose_name="Tipo de Cuenta")
    institucion = models.ForeignKey(
        'InstitucionEducativa', 
        on_delete=models.CASCADE,
        verbose_name="Institución"
    )

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    class Meta:
        verbose_name = "Cuenta Contable (PUC)"
        verbose_name_plural = "Cuentas Contables (PUC)"
        unique_together = ('codigo', 'institucion')
        ordering = ['codigo']         



# --- MODELOS PARA GESTIÓN DE PAGOS ---

class TipoConceptoPago(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Tipo de Concepto")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción Adicional")    
    institucion = models.ForeignKey(InstitucionEducativa, on_delete=models.CASCADE, verbose_name="Institución")

    def __str__(self):
        return f"{self.nombre} ({self.institucion.nombre})"

    class Meta:
        verbose_name = "Tipo de Concepto de Pago"
        verbose_name_plural = "Tipos de Conceptos de Pago"
        ordering = ['nombre']
        # CAMBIO 2: La unicidad ahora es por nombre + institución
        unique_together = ('nombre', 'institucion')


class ConceptoPago(models.Model):
    tipo_concepto = models.ForeignKey(TipoConceptoPago, on_delete=models.PROTECT, verbose_name="Tipo de Concepto")
    nombre_concepto = models.CharField(max_length=200, verbose_name="Nombre Específico del Concepto")
    descripcion_detallada = models.TextField(blank=True, null=True, verbose_name="Descripción Detallada")
    valor = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Estándar del Concepto")
    periodo_academico_aplicable = models.ForeignKey(
        'gestion_academica.PeriodoAcademico',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='conceptos_pago', verbose_name="Periodo Académico Aplicable (Opcional)"
    )
    fecha_vencimiento_general = models.DateField(null=True, blank=True, verbose_name="Fecha de Vencimiento General (Opcional)")
    automatico = models.BooleanField(default=False, verbose_name="¿Generar automáticamente al registrar estudiante?")
    
    es_pago_inscripcion = models.BooleanField(
        default=False, 
        verbose_name="¿Es el concepto de pago de Inscripción?",
        help_text="Marcar solo para el único concepto que se usará para cobrar la inscripción/postulación."
    )

    permite_mora = models.BooleanField(
        default=False, 
        verbose_name="¿Permite generar mora?",
        help_text="Marcar si este concepto debe generar intereses si se vence."
    )
    porcentaje_mora_mensual = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        verbose_name="Porcentaje de Mora Mensual (%)",
        help_text="Ej: 2.5 para 2.5%. Solo aplica si se marca 'Permite generar mora'."
    )

    cuenta_contable = models.ForeignKey(
        CuentaContable, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        limit_choices_to={'tipo': 'INGRESO'}, # Solo permite seleccionar cuentas de tipo Ingreso
        verbose_name="Cuenta Contable (PUC)"
    )
    
    
    es_pago_matricula = models.BooleanField(
        default=False,
        verbose_name="¿Es el concepto de pago de Matrícula?",
        help_text="Marcar solo para el único concepto que se usará para cobrar la matrícula oficial."
    )

    es_pago_pension = models.BooleanField(
        default=False,
        verbose_name="¿Es un concepto de pago de Pensión / Mensualidad?",
        help_text=(
            "Marca todas las mensualidades del año lectivo (Feb–Nov). "
            "Las cuentas por cobrar mensuales se crean automáticamente "
            "tomando los conceptos con este flag y filtrados por Nivel."
        ),
    )

    es_solicitable_por_egresado = models.BooleanField(
        default=False,
        verbose_name="¿Es solicitable desde el Portal de Egresados?",
        help_text="Marcar si este concepto debe aparecer en la lista de documentos que un egresado puede solicitar y pagar."
    )
    nivel_escolaridad = models.ForeignKey(
        NivelEscolaridad,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Nivel de Escolaridad (si aplica)",
        help_text="Asigna esto si el valor es solo para un nivel (ej: Matrícula Primaria)."
    )
    

    institucion = models.ForeignKey(InstitucionEducativa, on_delete=models.CASCADE, verbose_name="Institución")

    def clean(self):
        # Validación para asegurar que el porcentaje se ingrese si se permite mora
        if self.permite_mora and not self.porcentaje_mora_mensual:
            raise ValidationError({'porcentaje_mora_mensual': 'Debe especificar un porcentaje si el concepto permite mora.'})


    class Meta:
        permissions = []
        verbose_name = "Concepto de Pago"
        verbose_name_plural = "Conceptos de Pago"
        ordering = ['periodo_academico_aplicable', 'nombre_concepto']
        unique_together = ('nombre_concepto', 'tipo_concepto', 'institucion',)

    def __str__(self):
        return f"{self.nombre_concepto} (${self.valor:.2f})"
    
ESTADOS_CUENTA = [
        ('PENDIENTE', 'Pendiente'),
        ('PAGADO_PARCIAL', 'Pagado Parcialmente'),
        ('PAGADO', 'Pagado Completamente'),
        ('VENCIDO', 'Vencido'),
        ('ANULADO', 'Anulado'), 
    ]    

def default_fecha_vencimiento():
    return timezone.now().date() + timedelta(days=15)    


class CuentaPorCobrarEstudiante(models.Model):
    estudiante = models.ForeignKey(
        'gestion_academica.Estudiante', 
        on_delete=models.CASCADE, 
        related_name='cuentas_por_cobrar', # Apodo único
        null=True, blank=True
    )
    concepto_pago = models.ForeignKey(ConceptoPago, on_delete=models.PROTECT, related_name='instancias_cobro', verbose_name="Concepto de Pago")
    monto_asignado = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto Asignado al Estudiante", default=Decimal('0.00'))
    fecha_vencimiento_especifica = models.DateField(verbose_name="Fecha de Vencimiento para este Estudiante")
    estado = models.CharField(max_length=20, choices=ESTADOS_CUENTA, default='PENDIENTE', verbose_name="Estado de la Cuenta")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación de la Cuenta")
    ultima_modificacion = models.DateTimeField(auto_now=True, verbose_name="Última Modificación")
    observaciones_internas = models.TextField(blank=True, null=True, verbose_name="Observaciones Internas (Admin)")
    institucion = models.ForeignKey(InstitucionEducativa, on_delete=models.CASCADE, editable=False)
    mercadopago_preference_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="ID de Preferencia (Mercado Pago)")
    referencia_pago_externo = models.CharField(max_length=255, blank=True, null=True, verbose_name="Referencia de Pago Externo")
    numero_documento = models.PositiveIntegerField(null=True, blank=True, editable=False, verbose_name="Número de Factura")
    año = models.PositiveIntegerField(null=True, blank=True, verbose_name="Año del Cobro")
    mes = models.PositiveIntegerField(null=True, blank=True, verbose_name="Mes del Cobro (2-11)")
    aspirante = models.ForeignKey(
        'admisiones.Aspirante', 
        on_delete=models.CASCADE, 
        related_name='cuentas_por_cobrar_aspirante', # Apodo único
        null=True, blank=True
    )
    
    
    objects = CuentaPorCobrarEstudianteManager()

    @property
    def monto_pagado_actual(self):
        if self.pk:
            # Excluimos pagos ANULADOS (p. ej. revertidos por una Nota Crédito):
            # no cuentan en el saldo, pero quedan en el historial.
            return self.pagos.filter(anulado=False).aggregate(
                total_pagado=Sum('valor_pagado')
            )['total_pagado'] or Decimal('0.00')
        return Decimal('0.00')

    @property
    def saldo_pendiente(self):
        return (self.monto_asignado if self.monto_asignado is not None else Decimal('0.00')) - self.monto_pagado_actual

    # --- INICIO DE LA CORRECCIÓN ---
    # Añade esta nueva propiedad aquí
    @property
    def esta_vencida(self):
        """
        Devuelve True si la cuenta no está pagada y su fecha de vencimiento ya pasó.
        Esta propiedad se calcula en tiempo real y no depende del estado guardado en la BD.
        """
        if self.estado == 'PAGADO':
            return False
        return self.fecha_vencimiento_especifica < timezone.now().date()
    # --- FIN DE LA CORRECCIÓN --- 

    # --- ✅ MÉTODO SAVE CORREGIDO Y UNIFICADO ---
    def save(self, *args, **kwargs):
        # 1. Asigna la institución (lógica de la primera definición)
        if not self.institucion_id and self.estudiante:
            self.institucion = self.estudiante.institucion

        # 2. Asigna el número de factura si es un objeto nuevo
        if not self.pk:
            if self.institucion: # Asegurarse de que la institución esté definida
                self.numero_documento = ConsecutivoDocumento.obtener_siguiente(self.institucion.pk, 'factura_venta')

        # 3. Asigna el año y mes a partir de la fecha de vencimiento
        if self.fecha_vencimiento_especifica:
            if not self.año:
                self.año = self.fecha_vencimiento_especifica.year
            if not self.mes:
                self.mes = self.fecha_vencimiento_especifica.month
        
        # 4. Actualiza el estado basado en el saldo
        # Esta lógica se ejecutará antes de guardar, asegurando que el estado sea correcto.
        self._update_estado_based_on_saldo()

        # 5. Llama a super().save() UNA SOLA VEZ al final
        super().save(*args, **kwargs)

    def _update_estado_based_on_saldo(self):
        # Esta función no cambia, está bien
        if self.estado != 'ANULADO':
            saldo = self.saldo_pendiente
            if saldo <= Decimal('0.00') and self.monto_asignado > Decimal('0.00'):
                self.estado = 'PAGADO'
            elif self.monto_pagado_actual > Decimal('0.00') and saldo > Decimal('0.00'):
                self.estado = 'PAGADO_PARCIAL'
            elif self.fecha_vencimiento_especifica and self.fecha_vencimiento_especifica < timezone.localdate() and saldo > Decimal('0.00'):
                self.estado = 'VENCIDO'
            else:
                self.estado = 'PENDIENTE'

    def __str__(self):
        return f"Cuenta ID: {self.pk} por {self.concepto_pago.nombre_concepto} - Saldo: ${self.saldo_pendiente:.2f}"

    class Meta:
        # El Meta no cambia, está bien
        unique_together = [['estudiante', 'concepto_pago', 'año', 'mes']]
        verbose_name = "Cuenta por Cobrar a Estudiante"
        verbose_name_plural = "Cuentas por Cobrar a Estudiantes"
        ordering = ['-fecha_vencimiento_especifica']
        permissions = [("ver_cuentas_por_cobrar", "Puede ver el listado de cuentas por cobrar")]

        


class PagoRegistrado(models.Model):
    METODOS_PAGO = [
        ('EFECTIVO', 'Efectivo'),
        ('TRANSFERENCIA', 'Transferencia Bancaria'),
        ('TARJETA_DEBITO', 'Tarjeta de Débito'),
        ('TARJETA_CREDITO', 'Tarjeta de Crédito'),
        ('PSE', 'PSE (Pagos Seguros en Línea)'),
        ('MERCADO_PAGO', 'Mercado Pago'),  # Opción añadida
        ('OTRO', 'Otro'),
    ]

    cuenta = models.ForeignKey(CuentaPorCobrarEstudiante, on_delete=models.CASCADE, related_name='pagos', verbose_name="Cuenta Asociada")
    estudiante = models.ForeignKey('gestion_academica.Estudiante', on_delete=models.PROTECT, related_name='pagos_realizados', verbose_name="Estudiante que Paga")
    fecha_pago = models.DateField(verbose_name="Fecha del Pago", default=timezone.now)
    valor_pagado = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Pagado")
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, verbose_name="Método de Pago")
    referencia_transaccion = models.CharField(max_length=100, blank=True, null=True, verbose_name="Referencia de la Transacción")
    observacion = models.TextField(blank=True, null=True, verbose_name="Observación del Pago")
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='pagos_registrados_por_usuario', verbose_name="Registrado por (Admin)")
    fecha_registro_sistema = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro en Sistema")
    institucion = models.ForeignKey(InstitucionEducativa, on_delete=models.CASCADE, editable=False)
    numero_documento = models.PositiveIntegerField(
        null=True, blank=True, editable=False,
        verbose_name="Número de Recibo"
    )
    # Anulación contable (p. ej. al emitir una Nota Crédito de anulación).
    # No se borra el pago: se marca anulado y deja de contar en el saldo.
    anulado = models.BooleanField(default=False, verbose_name="Anulado")
    anulado_en = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de anulación")
    anulado_motivo = models.CharField(max_length=255, blank=True, verbose_name="Motivo de anulación")

    def save(self, *args, **kwargs):
        if not self.institucion_id and self.cuenta:
            self.institucion = self.cuenta.institucion

        if not self.pk:  # Solo al crear
            # El número de recibo (consecutivo) se genera ÚNICAMENTE para pagos
            # en EFECTIVO: son los que se registran manualmente y necesitan un
            # número de recibo formal para imprimir. Los demás métodos
            # (transferencia, tarjeta, PSE, Mercado Pago) ya traen su propia
            # referencia de transacción y NO consumen el consecutivo de efectivo.
            if self.metodo_pago == 'EFECTIVO':
                self.numero_documento = ConsecutivoDocumento.obtener_siguiente(
                    self.institucion.pk, 'recibo_efectivo'
                )

        super().save(*args, **kwargs)

    def __str__(self):
        return f'Pago de ${self.valor_pagado:.2f} para cuenta #{self.cuenta.id} por Estudiante ID: {self.estudiante.pk}'

    class Meta:
        verbose_name = "Pago Registrado"
        verbose_name_plural = "Pagos Registrados"
        ordering = ['-fecha_registro_sistema']
        permissions = [
            ("puede_editar_pago", "Puede editar pagos registrados"),
            ("puede_eliminar_pago", "Puede eliminar pagos registrados"),
        ]


@receiver([post_save, post_delete], sender=PagoRegistrado)
def actualizar_estado_de_cuenta_asociada(sender, instance, **kwargs):
    """
    Cada vez que un pago se crea, edita o elimina, esta señal se asegura
    de que el estado de la 'CuentaPorCobrarEstudiante' padre se actualice.
    """
    # Usamos try-except para evitar errores si la cuenta se borra en cascada
    try:
        cuenta_a_actualizar = instance.cuenta
        cuenta_a_actualizar.save()  # Esto llamará al método save() y a _update_estado_based_on_saldo()
    except CuentaPorCobrarEstudiante.DoesNotExist:
        pass # La cuenta ya no existe, no hay nada que hacer.

class TipoGasto(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Tipo de Gasto")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción Adicional")
    institucion = models.ForeignKey(InstitucionEducativa, on_delete=models.CASCADE, verbose_name="Institución")

    def __str__(self):
        return f"{self.nombre} ({self.institucion.nombre})"

    class Meta:
        verbose_name = "Tipo de Gasto"
        verbose_name_plural = "Tipos de Gastos"
        ordering = ['nombre']
        unique_together = ('nombre', 'institucion')


class CategoriaGasto(models.Model):
    # --- CAMPO AÑADIDO ---
    tipo_gasto = models.ForeignKey(
        TipoGasto, 
        on_delete=models.PROTECT, 
        related_name='categorias',
        verbose_name="Tipo de Gasto al que Pertenece"
    )
    # --- FIN DEL CAMPO AÑADIDO ---
    
    nombre = models.CharField(max_length=100, verbose_name="Nombre de la Categoría")
    institucion = models.ForeignKey(InstitucionEducativa, on_delete=models.CASCADE)

    cuenta_contable = models.ForeignKey(
        CuentaContable, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        limit_choices_to={'tipo': 'GASTO'}, 
        verbose_name="Cuenta Contable (PUC)"
    )

    def __str__(self):
        return f"{self.tipo_gasto.nombre} > {self.nombre}"

    class Meta:
        verbose_name = "Categoría de Gasto"
        verbose_name_plural = "Categorías de Gastos"
        # La unicidad ahora debería ser dentro de un tipo de gasto
        unique_together = ('nombre', 'tipo_gasto', 'institucion')


class Proveedor(models.Model):
    nombre = models.CharField(max_length=200, verbose_name="Nombre o Razón Social")
    nit_o_cedula = models.CharField(max_length=20, blank=True, null=True, verbose_name="NIT o Cédula")
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True, verbose_name="Correo Electrónico")
    institucion = models.ForeignKey(InstitucionEducativa, on_delete=models.CASCADE)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"


class Gasto(models.Model):
    descripcion = models.CharField(max_length=255, verbose_name="Descripción del Gasto")
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_gasto = models.DateField(default=timezone.now, verbose_name="Fecha del Gasto")
    categoria = models.ForeignKey(CategoriaGasto, on_delete=models.PROTECT, verbose_name="Categoría")
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)
    comprobante = models.FileField(upload_to='comprobantes_gastos/', blank=True, null=True, verbose_name="Comprobante (Factura/Recibo)")
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    institucion = models.ForeignKey(InstitucionEducativa, on_delete=models.CASCADE, editable=False)
    numero_documento = models.PositiveIntegerField(
        null=True, blank=True, editable=False,
        verbose_name="Número de Comprobante"
    )

    def __str__(self):
        return f"{self.descripcion} - ${self.monto}"

    def save(self, *args, **kwargs):
        if not self.pk: # Solo al crear
            self.numero_documento = ConsecutivoDocumento.obtener_siguiente(self.institucion.pk, 'comprobante_egreso')
        super().save(*args, **kwargs)    

    class Meta:
        verbose_name = "Gasto"
        verbose_name_plural = "Gastos"
        ordering = ['-fecha_gasto']

class GastoListView(LoginRequiredMixin, ListView):
    model = Gasto
    template_name = 'finanzas/listado_gastos.html'  # Asegúrate de que la plantilla exista
    context_object_name = 'gastos'

    def get_queryset(self):
        return Gasto.objects.filter(institucion=self.request.user.institucion_asociada)        

class Descuento(models.Model):
    class TipoDescuento(models.TextChoices):
        PORCENTAJE = 'PORCENTAJE', 'Porcentaje (%)'
        VALOR_FIJO = 'VALOR_FIJO', 'Valor Fijo ($)'

    nombre = models.CharField(max_length=150, verbose_name="Nombre del Descuento o Beca")
    tipo = models.CharField(max_length=20, choices=TipoDescuento.choices, default=TipoDescuento.PORCENTAJE)
    valor = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="El porcentaje (ej: 10.00 para 10%) o el valor fijo en pesos."
    )
    # A qué conceptos de pago se puede aplicar este descuento (ej: solo a pensiones)
    conceptos_aplicables = models.ManyToManyField('ConceptoPago', blank=True)
    activo = models.BooleanField(default=True)
    institucion = models.ForeignKey(InstitucionEducativa, on_delete=models.CASCADE)

    def __str__(self):
        if self.tipo == self.TipoDescuento.PORCENTAJE:
            return f"{self.nombre} ({self.valor}%)"
        return f"{self.nombre} (${self.valor})"

    class Meta:
        verbose_name = "Descuento o Beca"
        verbose_name_plural = "Descuentos y Becas"

class ConsecutivoDocumento(models.Model):
    institucion = models.ForeignKey(InstitucionEducativa, on_delete=models.CASCADE)
    tipo_documento = models.CharField(max_length=50, verbose_name="Tipo de Documento")
    siguiente_numero = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('institucion', 'tipo_documento')

    @classmethod
    def obtener_siguiente(cls, institucion_id, tipo):
        # Usamos select_for_update para bloquear la fila y evitar que dos procesos obtengan el mismo número
        with transaction.atomic():
            consecutivo, created = cls.objects.select_for_update().get_or_create(
                institucion_id=institucion_id,
                tipo_documento=tipo,
                defaults={'siguiente_numero': 1}
            )
            numero_actual = consecutivo.siguiente_numero
            consecutivo.siguiente_numero += 1
            consecutivo.save()
            return numero_actual     

class ItemCuenta(models.Model):
    cuenta = models.ForeignKey('CuentaPorCobrarEstudiante', on_delete=models.CASCADE, related_name='items')
    descripcion = models.CharField(max_length=255, verbose_name="Descripción")
    valor = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor")

    def __str__(self):
        return f"{self.descripcion}: ${self.valor}"

    class Meta:
        verbose_name = "Ítem de Cuenta"
        verbose_name_plural = "Ítems de Cuenta"


class AuditoriaExportacionContable(models.Model):
    """
    Registro de cada exportación contable generada (trazabilidad para auditoría interna).
    """

    institucion = models.ForeignKey(
        InstitucionEducativa,
        on_delete=models.CASCADE,
        related_name="auditorias_exportacion_contable",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exportaciones_contables_generadas",
    )
    creado = models.DateTimeField(auto_now_add=True)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    tipo_transaccion = models.CharField(max_length=24)
    formato = models.CharField(max_length=8)
    periodo_academico = models.ForeignKey(
        "gestion_academica.PeriodoAcademico",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    registros = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-creado"]
        verbose_name = "Auditoría de exportación contable"
        verbose_name_plural = "Auditorías de exportación contable"

    def __str__(self):
        return f"{self.institucion} {self.fecha_inicio}–{self.fecha_fin} ({self.creado:%Y-%m-%d %H:%M})"


# ============================================================================
# AUDITORÍA Y SEGURIDAD DE INTEGRACIÓN MERCADO PAGO (Fase 3)
# ============================================================================
# Plataforma multi-tenant: cada InstitucionEducativa tiene credenciales propias
# de Mercado Pago (test/prod + webhook secret). Estos modelos permiten:
#   1. Garantizar idempotencia ante reintentos de notificaciones (MP suele
#      reenviar el mismo evento varias veces).
#   2. Auditar cada llamada al SDK (latencia, errores, intentos, tenant).
#   3. Investigar disputas: para cada `data_id` del webhook tenemos el evento
#      original, la firma, el resultado HTTP devuelto y el pago resultante.

class WebhookEventoMercadoPago(models.Model):
    """Cada notificación POST entrante de Mercado Pago queda registrada.

    Aislamiento SaaS: ``unique_together(institucion, data_id, payload_hash)``
    garantiza que el mismo evento no se procese dos veces dentro de una
    institución, pero el mismo data_id en otra institución (caso real cuando
    dos tenants comparten infraestructura de pruebas) sí se permite.
    """

    institucion = models.ForeignKey(
        InstitucionEducativa,
        on_delete=models.CASCADE,
        related_name="webhooks_mercadopago",
        verbose_name="Institución",
    )
    data_id = models.CharField(
        max_length=64,
        verbose_name="data.id de Mercado Pago",
        help_text="ID del recurso (payment/merchant_order) notificado.",
    )
    tipo = models.CharField(
        max_length=32, blank=True,
        verbose_name="type",
        help_text="Campo `type` del payload (payment, merchant_order, etc.).",
    )
    payload_hash = models.CharField(
        max_length=64,
        verbose_name="SHA-256 del payload",
        help_text="Hash del body bruto: detecta reenvíos exactos del proveedor.",
    )
    x_request_id = models.CharField(max_length=128, blank=True)
    x_signature = models.CharField(max_length=255, blank=True)
    firma_valida = models.BooleanField(default=False)

    payload_resumen = models.JSONField(
        default=dict, blank=True,
        verbose_name="Resumen del payload",
        help_text="Subset auditable del payload (sin datos sensibles).",
    )
    estado_http_devuelto = models.PositiveSmallIntegerField(default=0)
    procesado_ok = models.BooleanField(default=False)
    error_mensaje = models.TextField(blank=True)

    pago_registrado = models.ForeignKey(
        "PagoRegistrado",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="webhook_eventos",
    )
    cuenta = models.ForeignKey(
        "CuentaPorCobrarEstudiante",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="webhook_eventos",
    )

    fecha_recepcion = models.DateTimeField(auto_now_add=True)
    fecha_procesamiento = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Evento webhook Mercado Pago"
        verbose_name_plural = "Eventos webhook Mercado Pago"
        ordering = ["-fecha_recepcion"]
        constraints = [
            models.UniqueConstraint(
                fields=["institucion", "data_id", "payload_hash"],
                name="webhook_mp_unico_por_inst_dataid_hash",
            ),
        ]
        indexes = [
            models.Index(fields=["institucion", "-fecha_recepcion"]),
            models.Index(fields=["data_id"]),
            models.Index(fields=["procesado_ok"]),
        ]

    def __str__(self):
        return (
            f"WebhookMP inst={self.institucion_id} data_id={self.data_id} "
            f"http={self.estado_http_devuelto}"
        )


class LlamadaMercadoPago(models.Model):
    """Auditoría de cada llamada outbound al SDK de Mercado Pago.

    Permite responder preguntas como:
      - ¿Cuántos timeouts tuvimos esta semana en `payment.get`?
      - ¿Cuál fue la latencia p95 al crear preferencias para la institución X?
      - ¿Qué error devolvió MP cuando un usuario reportó "no pude pagar"?
    """

    class Accion(models.TextChoices):
        PREFERENCE_CREATE = "preference.create", "Crear preferencia"
        PAYMENT_GET = "payment.get", "Consultar pago"
        PAYMENT_SEARCH = "payment.search", "Buscar pagos"
        OTRO = "otro", "Otro"

    institucion = models.ForeignKey(
        InstitucionEducativa,
        on_delete=models.CASCADE,
        related_name="llamadas_mercadopago",
    )
    accion = models.CharField(
        max_length=32, choices=Accion.choices,
        verbose_name="Acción",
    )
    external_reference = models.CharField(max_length=128, blank=True)
    monto = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
    )
    cuenta = models.ForeignKey(
        "CuentaPorCobrarEstudiante",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="llamadas_mercadopago",
    )
    intento = models.PositiveSmallIntegerField(default=1)
    latencia_ms = models.PositiveIntegerField(default=0)
    estado_http = models.PositiveSmallIntegerField(default=0)
    exito = models.BooleanField(default=False)
    error_mensaje = models.TextField(blank=True)

    request_resumen = models.JSONField(default=dict, blank=True)
    response_resumen = models.JSONField(default=dict, blank=True)

    modo_produccion = models.BooleanField(default=False)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Llamada Mercado Pago"
        verbose_name_plural = "Llamadas Mercado Pago"
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["institucion", "-fecha"]),
            models.Index(fields=["accion", "exito"]),
            models.Index(fields=["external_reference"]),
        ]

    def __str__(self):
        return (
            f"MP {self.accion} inst={self.institucion_id} "
            f"http={self.estado_http} exito={self.exito} ({self.latencia_ms}ms)"
        )


# ---------------------------------------------------------------------------
# Health-check del super-admin (dashboard de mantenimiento)
# ---------------------------------------------------------------------------

class EjecucionHealthCheck(models.Model):
    """Registro auditado de cada ejecución del health-check desde el dashboard.

    El comando CLI (`manage.py verificar_admisiones_health`) NO crea registros
    aquí; solo lo hacen las ejecuciones que el super-admin dispara desde el
    dashboard de mantenimiento (vía Celery + WebSocket).
    """

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        EJECUTANDO = "EJECUTANDO", "Ejecutando"
        OK = "OK", "OK"
        WARN = "WARN", "Con advertencias"
        ERROR = "ERROR", "Con errores"
        FALLIDO = "FALLIDO", "Fallido (excepción interna)"

    iniciado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ejecuciones_healthcheck",
        verbose_name="Iniciado por",
    )
    institucion_filtro = models.ForeignKey(
        "InstitucionEducativa",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ejecuciones_healthcheck",
        verbose_name="Filtro de institución",
        help_text="Si se especifica, el check se restringe a esta institución.",
    )
    iniciado_at = models.DateTimeField(auto_now_add=True, verbose_name="Iniciado en")
    terminado_at = models.DateTimeField(null=True, blank=True, verbose_name="Terminado en")
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.PENDIENTE,
    )
    task_id = models.CharField(
        max_length=255, blank=True, default="",
        help_text="ID de la tarea Celery asociada.",
    )
    errores_count = models.PositiveIntegerField(default=0)
    warnings_count = models.PositiveIntegerField(default=0)
    pasos_completados = models.PositiveSmallIntegerField(default=0)
    eventos = models.JSONField(
        default=list, blank=True,
        help_text="Lista de eventos generados por el health-check (cada uno con nivel/mensaje/paso).",
    )
    error_excepcion = models.TextField(
        blank=True,
        help_text="Si la tarea falló por excepción interna, traceback resumido.",
    )

    class Meta:
        verbose_name = "Ejecución de Health-Check"
        verbose_name_plural = "Ejecuciones de Health-Check"
        ordering = ["-iniciado_at"]
        indexes = [
            models.Index(fields=["-iniciado_at"]),
            models.Index(fields=["estado"]),
        ]

    def __str__(self):
        return f"HealthCheck #{self.pk} {self.estado} ({self.iniciado_at:%Y-%m-%d %H:%M})"

    @property
    def duracion_segundos(self):
        if not self.terminado_at:
            return None
        return int((self.terminado_at - self.iniciado_at).total_seconds())

    @property
    def en_curso(self):
        return self.estado in (self.Estado.PENDIENTE, self.Estado.EJECUTANDO)