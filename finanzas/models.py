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
    nota_minima_aprobacion = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('3.0'), verbose_name="Nota Mínima para Aprobar", help_text="La nota que un estudiante debe alcanzar o superar para aprobar (ej: 3.0, 3.5).")
    escala_valorativa_texto = models.CharField(max_length=255, blank=True, default="Sup = Superior, Alt = Alto, Bas = Básico, Baj = Bajo", verbose_name="Texto de la Escala Valorativa")
    google_calendar_embed_code = models.TextField(blank=True, null=True, verbose_name="Código para insertar Google Calendar")
    mp_public_key_test = models.CharField(max_length=255, blank=True, null=True, verbose_name="Public Key de Prueba (Mercado Pago)")
    mp_access_token_test = models.CharField(max_length=255, blank=True, null=True, verbose_name="Access Token de Prueba (Mercado Pago)")
    mp_public_key_prod = models.CharField(max_length=255, blank=True, null=True, verbose_name="Public Key de Producción (Mercado Pago)")
    mp_access_token_prod = models.CharField(max_length=255, blank=True, null=True, verbose_name="Access Token de Producción (Mercado Pago)")
    mp_modo_produccion = models.BooleanField(default=False, verbose_name="¿Activar modo producción para Mercado Pago?", help_text="Si está desmarcado, se usarán las credenciales de prueba.")
    email_host_user = models.EmailField(max_length=255, blank=True, null=True, verbose_name="Correo para Envío de Notificaciones (SMTP User)", help_text="Ej: notificaciones@micolegio.com")
    email_host_password = models.CharField(max_length=255, blank=True, null=True, verbose_name="Contraseña de Aplicación (SMTP Password)", help_text="¡IMPORTANTE! Usa una contraseña de aplicación generada, no tu contraseña principal.")
    email_host = models.CharField(max_length=255, blank=True, null=True, verbose_name="Servidor SMTP", default="smtp.gmail.com")
    email_port = models.PositiveIntegerField(blank=True, null=True, verbose_name="Puerto SMTP", default=587)
    email_use_tls = models.BooleanField(default=True, verbose_name="¿Usar TLS?")
    activa = models.BooleanField(
        default=True,
        verbose_name="Institución Activa",
        help_text="Desmarca esta casilla para bloquear el acceso de todos los usuarios de esta institución (excepto super-admins)."
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

    class Meta:
        verbose_name = "Institución Educativa"
        verbose_name_plural = "Instituciones Educativas"
        permissions = [("can_manage_institutions", "Puede gestionar instituciones educativas")]

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
            return self.pagos.aggregate(total_pagado=Sum('valor_pagado'))['total_pagado'] or Decimal('0.00')
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

    

    def save(self, *args, **kwargs):
        if not self.institucion_id and self.cuenta:
            self.institucion = self.cuenta.institucion

        if not self.pk:  # Solo al crear
            self.numero_documento = ConsecutivoDocumento.obtener_siguiente(
                self.institucion.pk, 'recibo_pago'
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