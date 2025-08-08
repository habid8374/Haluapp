# gestion_academica/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.conf import settings # Para usar settings.AUTH_USER_MODEL
import datetime
from datetime import date
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
import calendar

    
class InstitucionEducativa(models.Model):
    nombre = models.CharField(max_length=255)
    direccion = models.TextField(blank=True)
    email_contacto = models.EmailField(blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    sitio_web = models.URLField(blank=True)

    def __str__(self):
        return self.nombre   

class Grado(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre del Grado")
    nivel = models.CharField(max_length=50, blank=True, null=True, verbose_name="Nivel Educativo (Ej: Primaria, Secundaria)")
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.nombre
    
    class Meta:
        verbose_name = "Grado"
        verbose_name_plural = "Grados"
        ordering = ['nombre']

class Estudiante(models.Model):
    usuario = models.OneToOneField('Usuario', on_delete=models.CASCADE, primary_key=True, limit_choices_to={'rol': 'estudiante'}, verbose_name="Cuenta de Usuario")
    documento_identidad = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Documento de Identidad")
    codigo_estudiante = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Código de Estudiante")
    fecha_nacimiento = models.DateField(null=True, blank=True, verbose_name="Fecha de Nacimiento")
    direccion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Dirección")
    grado_actual = models.ForeignKey('Grado', on_delete=models.SET_NULL, null=True, blank=True, related_name='estudiantes_actuales', verbose_name="Grado Actual")
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    valor_matricula = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    valor_mensualidad = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    def __str__(self):
        nombre_completo = self.usuario.get_full_name()
        return nombre_completo if nombre_completo else self.usuario.username
    
    class Meta:
        verbose_name = "Estudiante"
        verbose_name_plural = "Estudiantes"

class Docente(models.Model):
    usuario = models.OneToOneField('Usuario', on_delete=models.CASCADE, primary_key=True, limit_choices_to={'rol': 'docente'}, verbose_name="Cuenta de Usuario")
    codigo_docente = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Código de Docente")
    especialidad = models.CharField(max_length=100, blank=True, null=True, verbose_name="Especialidad Principal")
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        nombre_completo = self.usuario.get_full_name()
        return nombre_completo if nombre_completo else self.usuario.username

    class Meta:
        verbose_name = "Docente"
        verbose_name_plural = "Docentes"

class Familiar(models.Model):
    usuario = models.OneToOneField('Usuario', on_delete=models.CASCADE, primary_key=True, limit_choices_to={'rol': 'familiar'}, verbose_name="Cuenta de Usuario (Login)")
    parentesco = models.CharField(max_length=50, verbose_name="Parentesco con el Estudiante")
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono de Contacto")
    estudiantes_asociados = models.ManyToManyField('Estudiante', related_name='familiares', verbose_name="Estudiante(s) Asociado(s)")
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    # Campos nuevos
    email = models.EmailField(null=True, blank=True, verbose_name="Correo del Acudiente")
    fecha_pago = models.DateField(default=date.today)

    def __str__(self):
        if hasattr(self, 'usuario') and self.usuario:
            nombre_usuario = self.usuario.get_full_name()
            return nombre_usuario if nombre_usuario else self.usuario.username
        return f"Familiar ID: {self.pk}"

    class Meta:
        verbose_name = "Familiar"
        verbose_name_plural = "Familiares"

class Materia(models.Model):
    nombre_materia = models.CharField(max_length=100, unique=True, verbose_name="Nombre de la Materia")
    codigo_materia = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Código de Materia")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.nombre_materia

    class Meta:
        verbose_name = "Materia"
        verbose_name_plural = "Materias"
        ordering = ['nombre_materia']

class PeriodoAcademico(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Periodo")
    fecha_inicio = models.DateField(verbose_name="Fecha de Inicio")
    fecha_fin = models.DateField(verbose_name="Fecha de Fin")
    año_escolar = models.PositiveIntegerField(verbose_name="Año Escolar", default=datetime.date.today().year)
    activo = models.BooleanField(default=False, verbose_name="¿Es el periodo activo actual?")
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.nombre} ({self.año_escolar})"

    class Meta:
        verbose_name = "Periodo Académico"
        verbose_name_plural = "Periodos Académicos"
        ordering = ['-año_escolar', '-fecha_inicio']
        unique_together = ('nombre', 'año_escolar')

class Curso(models.Model):
    materia = models.ForeignKey('Materia', on_delete=models.PROTECT, related_name="cursos", verbose_name="Materia")
    grado = models.ForeignKey('Grado', on_delete=models.PROTECT, related_name="cursos", verbose_name="Grado")
    periodo_academico = models.ForeignKey('PeriodoAcademico', on_delete=models.CASCADE, related_name="cursos", verbose_name="Periodo Académico")
    docentes_asignados = models.ManyToManyField(
        'Docente',
        related_name="cursos_impartidos",
        blank=True,
        verbose_name="Docentes Asignados"
    )
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.materia.nombre_materia} - {self.grado.nombre} ({self.periodo_academico.nombre})"

    class Meta:
        verbose_name = "Curso"
        verbose_name_plural = "Cursos"
        unique_together = ('materia', 'grado', 'periodo_academico')
        ordering = ['periodo_academico', 'grado', 'materia']

class DirectorCurso(models.Model):
    docente = models.ForeignKey('Docente', on_delete=models.CASCADE, related_name="direcciones_grado", verbose_name="Docente Director")
    grado = models.ForeignKey('Grado', on_delete=models.CASCADE, related_name="directores_grado", verbose_name="Grado Dirigido")
    periodo_academico = models.ForeignKey('PeriodoAcademico', on_delete=models.CASCADE, related_name="directores_grado_periodo", verbose_name="Periodo Académico")
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        nombre_docente = self.docente.usuario.get_full_name() or self.docente.usuario.username
        return f"Dir. {nombre_docente} - {self.grado.nombre} ({self.periodo_academico.nombre})"

    class Meta:
        verbose_name = "Director de Curso"
        verbose_name_plural = "Directores de Curso"
        unique_together = ('grado', 'periodo_academico')
        ordering = ['periodo_academico', 'grado']

class EsquemaCalificacion(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre del Esquema")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción (Opcional)")
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Esquema de Calificación"
        verbose_name_plural = "Esquemas de Calificación"
        ordering = ['nombre']

class TipoActividad(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre del Tipo de Actividad")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción (Opcional)")
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Tipo de Actividad"
        verbose_name_plural = "Tipos de Actividad"
        ordering = ['nombre']

class ActividadCalificable(models.Model):
    curso = models.ForeignKey('Curso', on_delete=models.CASCADE, related_name='actividades_calificables', verbose_name="Curso")
    tipo_actividad = models.ForeignKey('TipoActividad', on_delete=models.PROTECT, verbose_name="Tipo de Actividad")
    titulo = models.CharField(max_length=200, verbose_name="Título de la Actividad")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción Detallada")
    fecha_publicacion = models.DateField(verbose_name="Fecha de Publicación/Asignación", default=datetime.date.today)
    fecha_entrega_limite = models.DateField(null=True, blank=True, verbose_name="Fecha Límite de Entrega (Opcional)")
    porcentaje_en_periodo = models.DecimalField(
        max_digits=5, decimal_places=2,
        verbose_name="Porcentaje en la Nota del Periodo (%)",
        help_text="Valor entre 0.01 y 100.00. Ej: 20 para 20%",
        null=True, blank=True
    )
    material_adjunto = models.FileField(
        upload_to='actividades_materiales/',
        blank=True,
        null=True,
        verbose_name="Material Adjunto (Opcional)"
    )
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        porcentaje_str = f"{self.porcentaje_en_periodo}%" if self.porcentaje_en_periodo is not None else "N/P"
        return f"{self.titulo} ({self.curso}) - {porcentaje_str}"

    class Meta:
        verbose_name = "Actividad Calificable"
        verbose_name_plural = "Actividades Calificables"
        ordering = ['curso', '-fecha_publicacion', 'titulo']

class Calificacion(models.Model):
    estudiante = models.ForeignKey('Estudiante', on_delete=models.CASCADE, related_name='calificaciones', verbose_name="Estudiante")
    actividad_calificable = models.ForeignKey('ActividadCalificable', on_delete=models.CASCADE, related_name='calificaciones_recibidas', verbose_name="Actividad Calificable")
    valor_numerico = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Valor Numérico")
    valor_cualitativo = models.CharField(max_length=50, blank=True, null=True, verbose_name="Valor Cualitativo")
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro")
    registrada_por = models.ForeignKey('Docente', on_delete=models.SET_NULL, null=True, blank=True, related_name='calificaciones_registradas', verbose_name="Registrada por")
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        unique_together = ('estudiante', 'actividad_calificable')
        verbose_name = "Calificación"
        verbose_name_plural = "Calificaciones"
        ordering = ['actividad_calificable__curso', 'estudiante__usuario__last_name', 'actividad_calificable__fecha_publicacion']

    def __str__(self):
        valor = self.valor_numerico if self.valor_numerico is not None else self.valor_cualitativo
        return f"Cal: {self.estudiante.usuario.username} en {self.actividad_calificable.titulo}: {valor or 'Pendiente'}"

class PlanCurricular(models.Model):
    nombre = models.CharField(max_length=255, verbose_name="Nombre del Plan Curricular")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción Detallada (Opcional)")
    documento_adjunto = models.FileField(upload_to='planes_curriculares/', blank=True, null=True, verbose_name="Documento Adjunto del Plan (PDF, Word, etc.)")
    grado_asociado = models.ForeignKey('Grado', on_delete=models.SET_NULL, null=True, blank=True, related_name='planes_curriculares_grado', verbose_name="Grado Asociado (Opcional)")
    materia_asociada = models.ForeignKey('Materia', on_delete=models.SET_NULL, null=True, blank=True, related_name='planes_curriculares_materia', verbose_name="Materia Asociada (Opcional)")
    periodo_academico_asociado = models.ForeignKey('PeriodoAcademico', on_delete=models.SET_NULL, null=True, blank=True, related_name='planes_curriculares_periodo', verbose_name="Periodo Académico Asociado (Opcional)")
    fecha_publicacion = models.DateField(verbose_name="Fecha de Publicación/Vigencia", default=datetime.date.today)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='planes_curriculares_creados', verbose_name="Creado por")
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Plan Curricular"
        verbose_name_plural = "Planes Curriculares"
        ordering = ['-fecha_publicacion', 'nombre']

class Deber(models.Model):
    curso = models.ForeignKey('Curso', on_delete=models.CASCADE, related_name='deberes', verbose_name="Curso al que pertenece el deber")
    titulo = models.CharField(max_length=255, verbose_name="Título del Deber")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción / Instrucciones")
    fecha_asignacion = models.DateField(verbose_name="Fecha de Asignación", default=datetime.date.today)
    fecha_entrega = models.DateField(verbose_name="Fecha Límite de Entrega")
    material_adjunto = models.FileField(upload_to='deberes_materiales/', blank=True, null=True, verbose_name="Material de Apoyo Adjunto (Opcional)")
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
         return f"{self.titulo} ({self.curso})"

    class Meta:
        verbose_name = "Deber / Tarea"
        verbose_name_plural = "Deberes / Tareas"
        ordering = ['curso', '-fecha_entrega', 'titulo']

class EntregaDeber(models.Model):
    deber = models.ForeignKey('Deber', on_delete=models.CASCADE, related_name='entregas', verbose_name="Deber")
    estudiante = models.ForeignKey('Estudiante', on_delete=models.CASCADE, related_name='entregas_deberes', verbose_name="Estudiante")
    fecha_entrega_real = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Entrega Real")
    archivo_adjunto_estudiante = models.FileField(upload_to='entregas_deberes_estudiantes/', blank=True, null=True, verbose_name="Archivo Adjunto del Estudiante")
    comentarios_estudiante = models.TextField(blank=True, null=True, verbose_name="Comentarios del Estudiante (Opcional)")
    calificacion_obtenida = models.CharField(max_length=20, blank=True, null=True, verbose_name="Calificación Obtenida")
    comentarios_docente = models.TextField(blank=True, null=True, verbose_name="Comentarios del Docente")
    fecha_calificacion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Calificación")
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        unique_together = ('deber', 'estudiante')
        verbose_name = "Entrega de Deber"
        verbose_name_plural = "Entregas de Deberes"
        ordering = ['deber', 'estudiante']

    def __str__(self):
         return f"Entrega de '{self.deber.titulo}' por {self.estudiante.usuario.username}"

class MencionReconocimiento(models.Model):
    estudiante = models.ForeignKey('Estudiante', on_delete=models.CASCADE, related_name='menciones_reconocimientos', verbose_name="Estudiante")
    curso = models.ForeignKey('Curso', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Curso (Opcional)")
    periodo = models.ForeignKey('PeriodoAcademico', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Periodo Académico (Opcional)")
    tipo = models.CharField(max_length=150, verbose_name="Tipo de Mención/Reconocimiento")
    descripcion = models.TextField(verbose_name="Descripción Detallada del Reconocimiento")
    fecha_otorgamiento = models.DateField(verbose_name="Fecha de Otorgamiento", default=datetime.date.today)
    otorgado_por = models.ForeignKey('Docente', on_delete=models.SET_NULL, null=True, blank=True, related_name='menciones_otorgadas', verbose_name="Otorgado/Registrado por (Docente)")
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        otorgante = f" (Otorgado por: {self.otorgado_por})" if self.otorgado_por else ""
        return f"{self.tipo} a {self.estudiante.usuario.get_full_name() or self.estudiante.usuario.username} el {self.fecha_otorgamiento}{otorgante}"

    class Meta:
        verbose_name = "Mención o Reconocimiento"
        verbose_name_plural = "Menciones y Reconocimientos"
        ordering = ['-fecha_otorgamiento', 'estudiante']

class ArchivoPlanAcademico(models.Model):
    nombre_archivo_descriptivo = models.CharField(max_length=255, verbose_name="Nombre Descriptivo del Archivo", default="[Nombre no especificado]")
    archivo = models.FileField(upload_to='planes_academicos_materiales/', verbose_name="Archivo")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción (Opcional)")
    tipo_documento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Tipo de Documento (Ej: Plan de Estudio, Guía, Presentación)")
    curso_asociado = models.ForeignKey('Curso', on_delete=models.SET_NULL, null=True, blank=True, related_name='archivos_material_apoyo_curso', verbose_name="Curso Asociado (Opcional)")
    materia_asociada = models.ForeignKey('Materia', on_delete=models.SET_NULL, null=True, blank=True, related_name='archivos_material_apoyo_materia', verbose_name="Materia Asociada (Opcional)")
    subido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Subido por") # Usar settings.AUTH_USER_MODEL
    fecha_subida = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Subida")
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.nombre_archivo_descriptivo

    class Meta:
        verbose_name = "Archivo de Plan Académico o Material"
        verbose_name_plural = "Archivos de Planes Académicos y Materiales"
        ordering = ['-fecha_subida', 'nombre_archivo_descriptivo']

class ConfiguracionInstitucion(models.Model):
    nombre_institucion = models.CharField(max_length=255, default="Nombre de Mi Institución")
    lema_institucion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Lema o Eslogan")
    direccion = models.TextField(blank=True, null=True, verbose_name="Dirección")
    telefono_contacto = models.CharField(max_length=50, blank=True, null=True, verbose_name="Teléfono(s) de Contacto")
    email_contacto = models.EmailField(blank=True, null=True, verbose_name="Email de Contacto")
    sitio_web = models.URLField(blank=True, null=True, verbose_name="Sitio Web")
    logo = models.ImageField(upload_to='logos_institucion/', blank=True, null=True, verbose_name="Logo de la Institución")
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.nombre_institucion

    class Meta:
        verbose_name = "Configuración de la Institución"
        verbose_name_plural = "Configuración de la Institución"

    def save(self, *args, **kwargs):
        if not self.pk and ConfiguracionInstitucion.objects.exists():
            raise ValidationError('Solo puede existir una configuración de la institución. Edite la existente.')
        super().save(*args, **kwargs)

# --- MODELOS PARA GESTIÓN DE PAGOS ---

class TipoConceptoPago(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre del Tipo de Concepto")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción Adicional")
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Tipo de Concepto de Pago"
        verbose_name_plural = "Tipos de Conceptos de Pago"
        ordering = ['nombre']

class ConceptoPago(models.Model):
    tipo_concepto = models.ForeignKey('TipoConceptoPago', on_delete=models.PROTECT, verbose_name="Tipo de Concepto")
    nombre_concepto = models.CharField(max_length=200, verbose_name="Nombre Específico del Concepto")
    descripcion_detallada = models.TextField(blank=True, null=True, verbose_name="Descripción Detallada")
    monto_estandar = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto Estándar del Concepto")
    periodo_academico_aplicable = models.ForeignKey(
        'PeriodoAcademico', 
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='conceptos_pago',
        verbose_name="Periodo Académico Aplicable (Opcional)"
    )
    fecha_vencimiento_general = models.DateField(null=True, blank=True, verbose_name="Fecha de Vencimiento General (Opcional)")
    automatico = models.BooleanField(default=False, verbose_name="¿Generar automáticamente al registrar estudiante?")
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.nombre_concepto} (${self.monto_estandar:.2f})"

    class Meta:
        permissions = [
            ("ver_cuentas_por_cobrar", "Puede ver el módulo de cuentas por cobrar"),
        ]
        verbose_name = "Concepto de Pago"
        verbose_name_plural = "Conceptos de Pago"
        ordering = ['periodo_academico_aplicable', 'nombre_concepto']

class CuentaPorCobrarEstudiante(models.Model):
    ESTADOS_CUENTA = [
        ('PENDIENTE', 'Pendiente'),
        ('PAGADO_PARCIAL', 'Pagado Parcialmente'),
        ('PAGADO', 'Pagado Completamente'),
        ('VENCIDO', 'Vencido'),
        ('ANULADO', 'Anulado'),
    ]
    estudiante = models.ForeignKey('Estudiante', on_delete=models.CASCADE, related_name='cuentas_por_cobrar', verbose_name="Estudiante")
    concepto_pago = models.ForeignKey('ConceptoPago', on_delete=models.PROTECT, related_name='instancias_cobro', verbose_name="Concepto de Pago")
    monto_asignado = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto Asignado al Estudiante", default=0.00)
    monto_pagado = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Monto Pagado")
    fecha_vencimiento_especifica = models.DateField(verbose_name="Fecha de Vencimiento para este Estudiante")
    estado = models.CharField(max_length=20, choices=ESTADOS_CUENTA, default='PENDIENTE', verbose_name="Estado de la Cuenta")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación de la Cuenta")
    ultima_modificacion = models.DateTimeField(auto_now=True, verbose_name="Última Modificación")
    observaciones_internas = models.TextField(blank=True, null=True, verbose_name="Observaciones Internas (Admin)")
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    @property
    def saldo_pendiente(self):
        return (self.monto_asignado or 0) - (self.monto_pagado or 0)

    def save(self, *args, **kwargs):
        current_monto_asignado = self.monto_asignado if self.monto_asignado is not None else 0
        current_monto_pagado = self.monto_pagado if self.monto_pagado is not None else 0

        if current_monto_pagado >= current_monto_asignado and current_monto_asignado > 0:
            self.estado = 'PAGADO'
        elif current_monto_pagado > 0 and current_monto_pagado < current_monto_asignado:
            self.estado = 'PAGADO_PARCIAL'
        elif self.estado not in ['PAGADO', 'PAGADO_PARCIAL', 'ANULADO'] and \
             self.fecha_vencimiento_especifica and \
             self.fecha_vencimiento_especifica < timezone.now().date():
            self.estado = 'VENCIDO'
        elif self.estado not in ['ANULADO', 'VENCIDO', 'PAGADO', 'PAGADO_PARCIAL']:
             self.estado = 'PENDIENTE'
        super().save(*args, **kwargs)

    def __str__(self):
        saldo = self.saldo_pendiente
        return f"Cuenta de {self.estudiante} por {self.concepto_pago.nombre_concepto} - Saldo: ${saldo:.2f} ({self.estado})"

    class Meta:
        verbose_name = "Cuenta por Cobrar a Estudiante"
        verbose_name_plural = "Cuentas por Cobrar a Estudiantes"
        ordering = ['estudiante', 'fecha_vencimiento_especifica']
        unique_together = ('estudiante', 'concepto_pago')

class PagoRegistrado(models.Model):
    METODOS_PAGO = [
        ('EFECTIVO', 'Efectivo'),
        ('TRANSFERENCIA', 'Transferencia Bancaria'),
        ('TARJETA_DEBITO', 'Tarjeta de Débito'),
        ('TARJETA_CREDITO', 'Tarjeta de Crédito'),
        ('PSE', 'PSE (Pagos Seguros en Línea)'),
        ('OTRO', 'Otro'),
    ]

    cuenta = models.ForeignKey('CuentaPorCobrarEstudiante', on_delete=models.CASCADE, related_name='pagos', verbose_name="Cuenta Asociada")
    estudiante = models.ForeignKey('Estudiante', on_delete=models.PROTECT, related_name='pagos_realizados', verbose_name="Estudiante que Paga")
    fecha_pago = models.DateField(verbose_name="Fecha del Pago", default=datetime.date.today)
    valor_pagado = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Pagado")
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, verbose_name="Método de Pago")
    referencia_pago = models.CharField(max_length=100, blank=True, null=True, verbose_name="Referencia del Pago")
    observacion = models.TextField(blank=True, null=True)  # ← Agregado aquí
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pagos_registrados_por_usuario',
        verbose_name="Registrado por (Admin)"
    )
    fecha_registro_sistema = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro en Sistema")
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f'Pago de {self.valor_pagado} para cuenta #{self.cuenta.id}'

    class Meta:
        permissions = [
            ("puede_editar_pago", "Puede editar pagos registrados"),
            ("puede_eliminar_pago", "Puede eliminar pagos registrados"),
        ] 

# --- NUEVO MODELO PARA NOTICIAS Y ANUNCIOS ---
class Noticia(models.Model):
    titulo = models.CharField(max_length=200, verbose_name="Título de la Noticia/Anuncio")
    contenido = models.TextField(verbose_name="Contenido Completo")
    fecha_publicacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Publicación")
    publicado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL,
        null=True, 
        blank=True,
        related_name='noticias_publicadas',
        verbose_name="Publicado por"
    )
    imagen_destacada = models.ImageField(
        upload_to='noticias_imagenes/', 
        blank=True, 
        null=True, 
        verbose_name="Imagen Destacada (Opcional)"
    )
    institucion = models.ForeignKey('InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.titulo

    class Meta:
        verbose_name = "Noticia o Anuncio"
        verbose_name_plural = "Noticias y Anuncios"
        ordering = ['-fecha_publicacion']

@receiver(post_save, sender=Estudiante)
def crear_cuentas_automaticas(sender, instance, created, **kwargs):
    """
    CORREGIDO: Crea las cuentas de cobro usando los valores del perfil del estudiante,
    que a su vez vienen del Nivel de Escolaridad.
    """
    if not created:
        return

    # 'instance' aquí es el objeto Estudiante que se acaba de crear
    estudiante = instance
    
    # Verificamos que el estudiante tenga un nivel de escolaridad para buscar los conceptos
    if not (estudiante.grado_actual and estudiante.grado_actual.nivel_escolaridad):
        print(f"ADVERTENCIA: El estudiante {estudiante} no tiene un nivel de escolaridad asignado. No se generaron pensiones.")
        return

    # Buscamos conceptos automáticos para el nivel del estudiante
    conceptos = ConceptoPago.objects.filter(
        automatico=True,
        nivel_escolaridad=estudiante.grado_actual.nivel_escolaridad
    )

    año_actual = date.today().year
    # La lista de meses a generar
    meses_a_generar = [
        ("Matrícula", 2),
        ("Mensualidad", 2), ("Mensualidad", 3), ("Mensualidad", 4),
        ("Mensualidad", 5), ("Mensualidad", 6), ("Mensualidad", 7),
        ("Mensualidad", 8), ("Mensualidad", 9), ("Mensualidad", 10),
        ("Mensualidad", 11),
    ]

    for nombre_concepto, mes in meses_a_generar:
        # Buscamos el concepto específico (ej. "Matrícula" o "Mensualidad")
        concepto = conceptos.filter(nombre_concepto__icontains=nombre_concepto).first()
        
        if concepto:
            # --- INICIO DE LA LÓGICA CORREGIDA ---
            monto_a_usar = 0
            if "Matrícula" in concepto.nombre_concepto:
                monto_a_usar = estudiante.valor_matricula
            elif "Mensualidad" in concepto.nombre_concepto or "Pensión" in concepto.nombre_concepto:
                monto_a_usar = estudiante.valor_mensualidad
            # --- FIN DE LA LÓGICA CORREGIDA ---

            # Solo creamos la cuenta si el monto es mayor a cero
            if monto_a_usar > 0:
                fecha_venc = date(año_actual, mes, 10)  # Vence el 10 de cada mes
                CuentaPorCobrarEstudiante.objects.create(
                    estudiante=estudiante,
                    concepto_pago=concepto,
                    monto_asignado=monto_a_usar, # Usamos el valor correcto
                    fecha_vencimiento_especifica=fecha_venc,
                    institucion=estudiante.institucion # Asignamos la institución
                )                      

