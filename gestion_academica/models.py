# gestion_academica/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.conf import settings 
import datetime
from datetime import date
from django.utils import timezone
from django.utils.timezone import localtime
import calendar 
from decimal import Decimal 
import uuid
from django.utils.text import slugify



# NO DEBE HABER NINGUNA IMPORTACIÓN DIRECTA DE finanzas.models AQUÍ
# from finanzas.models import InstitucionEducativa # ESTA LÍNEA DEBE HABER SIDO ELIMINADA POR COMPLETO

class Usuario(AbstractUser):
    ROLES = (
        ('administrador', 'Administrador'), # Rol para admin de una institución
        # Podrías tener un 'superadmin' que no necesite institución
        ('coordinador', 'Coordinador(a)'),
        ('docente', 'Docente'),
        ('estudiante', 'Estudiante'),
        ('familiar', 'Familiar'),
    )
    rol = models.CharField(max_length=20, choices=ROLES, default='estudiante', verbose_name="Rol de Usuario")
    
    # --- CAMBIO: Se quita null=True, blank=True ---
    # Esto fuerza a que cada usuario se asigne a una institución al crearse.
    # Es más seguro para la lógica de tu aplicación.
    institucion_asociada = models.ForeignKey(
        'finanzas.InstitucionEducativa',
        on_delete=models.PROTECT, # Usar PROTECT para evitar borrar una institución si tiene usuarios
        null=True, blank=True, # Mantenemos nulo por ahora para el superadmin, pero sé consciente de esto
        related_name='usuarios', # 'usuarios' es un nombre más corto y común
        verbose_name="Institución Asociada"
    )
    # ▼▼▼ AÑADE ESTE CAMPO AL FINAL DEL MODELO ▼▼▼
    google_calendar_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="ID del Calendario de Google Sincronizado"
    )
    # ▲▲▲ FIN DEL CAMPO AÑADIDO ▲▲▲

    
    def get_full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        permissions = [
            ("acceso_modulo_academico", "Puede acceder al módulo académico"),
            ("puede_realizar_registro_inicial", "Puede realizar el registro inicial del sistema"),
        ]

    # El __str__ estaba fuera de la clase en tu código
    def __str__(self):
        return self.username

class NivelEscolaridad(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Nivel")
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, related_name='niveles_escolares')
    valor_inscripcion_estandar = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name="Valor Estándar de Inscripción"
    )
    valor_matricula_estandar = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_pension_estandar = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    orden = models.PositiveIntegerField(
        default=0, 
        help_text="Orden de aparición (ej: 1 para Preescolar, 2 para Primaria)"
    )

    class Meta:
        verbose_name = "Nivel de Escolaridad"
        verbose_name_plural = "Niveles de Escolaridad"
        unique_together = ('nombre', 'institucion')
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.institucion.nombre})"        

class Grado(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Grado")
    
    # ✅ Se añade la relación al Nivel de Escolaridad
    nivel_escolaridad = models.ForeignKey(
        'NivelEscolaridad', # Se usa como string para evitar errores de importación
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='grados'
    )
    
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name="Institución")
    
    siguiente_grado = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Grado Siguiente (Promoción)"
    )
    orden = models.PositiveIntegerField(
        null=True, blank=True, 
        verbose_name="Orden Numérico",
        help_text="Ej: 1 para Primero, 2 para Segundo, etc."
    )
    
    class TipoEvaluacion(models.TextChoices):
        CUANTITATIVO = 'CUANTITATIVO', 'Cuantitativo (Notas Numéricas)'
        CUALITATIVO = 'CUALITATIVO', 'Cualitativo (Logros y Descriptivo)'

    tipo_evaluacion = models.CharField(
        max_length=20, choices=TipoEvaluacion.choices, default=TipoEvaluacion.CUANTITATIVO,
        verbose_name="Tipo de Evaluación Predominante"
    )

    class Meta:
        verbose_name = "Grado"
        verbose_name_plural = "Grados"
        ordering = ['institucion', 'orden']
        unique_together = ('nombre', 'institucion',)

    def __str__(self):
        return f"{self.nombre} ({self.institucion.nombre})"

class Logro(models.Model):
    # --- ✅ INICIO DE LA CORRECCIÓN ---
    # Se usan strings para referenciar los modelos y evitar errores de importación.
    materia = models.ForeignKey('Materia', on_delete=models.CASCADE, related_name='logros')
    periodo = models.ForeignKey('PeriodoAcademico', on_delete=models.CASCADE, related_name='logros')
    # --- FIN DE LA CORRECCIÓN ---
    
    descripcion = models.TextField(verbose_name="Descripción del Logro")
    orden = models.PositiveIntegerField(default=0, help_text="Orden en que aparecerá en el boletín")
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Logro de Aprendizaje (Preescolar)"
        verbose_name_plural = "Logros de Aprendizaje (Preescolar)"
        ordering = ['materia', 'orden']

    def __str__(self):
        return f"{self.materia.nombre_materia} - {self.descripcion[:40]}..."

class DimensionDesarrollo(models.Model):
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100, verbose_name="Nombre de la Dimensión")
    descripcion = models.TextField(blank=True, null=True)
    orden = models.PositiveIntegerField(default=0, help_text="Orden de aparición en los reportes")

    # --- INICIO DE LA MODIFICACIÓN ---
    # Añadimos una relación ManyToMany para que puedas asignar
    # múltiples materias a esta dimensión.
    materias = models.ManyToManyField(
        'Materia',
        blank=True,
        related_name='dimensiones', # Nombre para la relación inversa
        verbose_name="Materias Incluidas en esta Dimensión"
    )
    # --- FIN DE LA MODIFICACIÓN ---

    class Meta:
        verbose_name = "Dimensión de Desarrollo (Preescolar)"
        verbose_name_plural = "Dimensiones de Desarrollo (Preescolar)"
        ordering = ['orden', 'nombre']
        unique_together = ('institucion', 'nombre')

    def __str__(self):
        return self.nombre

class LogroPreescolar(models.Model):
    """
    Modelo dedicado EXCLUSIVAMENTE para los logros evaluables del nivel Preescolar.
    Es independiente de DescriptorLogro.
    """
    dimension = models.ForeignKey(
        'DimensionDesarrollo', 
        on_delete=models.CASCADE, 
        related_name='logros_preescolar',
        verbose_name="Dimensión de Desarrollo"
    )
    materia = models.ForeignKey(
        'Materia', 
        on_delete=models.CASCADE, 
        related_name='logros_preescolar',
        verbose_name="Materia Asociada"
    )
    periodo = models.ForeignKey(
        'PeriodoAcademico', 
        on_delete=models.CASCADE, 
        related_name='logros_preescolar',
        verbose_name="Periodo Académico"
    )
    descripcion = models.TextField(verbose_name="Descripción del Logro")
    orden = models.PositiveIntegerField(default=0, help_text="Orden de aparición dentro de la materia.")
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Logro de Preescolar"
        verbose_name_plural = "Logros de Preescolar"
        ordering = ['dimension__orden', 'materia__nombre_materia', 'orden']

    def __str__(self):
        return f"{self.descripcion[:50]}... ({self.materia.nombre_materia})"


class EvaluacionLogroPreescolar(models.Model):
    """
    Guarda la evaluación cualitativa de un estudiante para un LogroPreescolar específico.
    """
    estudiante = models.ForeignKey('Estudiante', on_delete=models.CASCADE, related_name='evaluaciones_logros_preescolar') # related_name corregido para ser único
    
    # --- INICIO DE LA CORRECCIÓN 1 ---
    # Apuntamos al nuevo modelo que creamos.
    logro = models.ForeignKey('LogroPreescolar', on_delete=models.CASCADE, related_name='evaluaciones')
    # --- FIN DE LA CORRECCIÓN 1 ---

    # --- INICIO DE LA CORRECCIÓN 2 ---
    # Eliminamos el campo CharField duplicado y nos quedamos solo con la ForeignKey.
    estado = models.ForeignKey('EscalaCualitativa', on_delete=models.SET_NULL, null=True, blank=True)
    # --- FIN DE LA CORRECCIÓN 2 ---
    
    registrado_por = models.ForeignKey('Docente', on_delete=models.SET_NULL, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Evaluación de Logro (Preescolar)"
        verbose_name_plural = "Evaluaciones de Logros (Preescolar)"
        # Aseguramos que un estudiante solo pueda tener una evaluación por logro
        unique_together = ('estudiante', 'logro')

    def __str__(self):
        return f"Evaluación de {self.estudiante} para el logro {self.logro_id}"

class EscalaCualitativa(models.Model):
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, related_name='escala_cualitativa')
    nombre_escala = models.CharField(max_length=50, verbose_name="Nombre del Desempeño (Ej: Logro Alcanzado)")
    abreviatura = models.CharField(max_length=10, verbose_name="Abreviatura (Ej: LA, LP, LPE)")
    descripcion = models.TextField(blank=True, null=True, help_text="Descripción de lo que significa este nivel para los padres.")
    orden = models.PositiveIntegerField(default=0, help_text="Orden en que aparecerán las casillas (ej: 1 para LA, 2 para LP, etc.)")
    
    es_reprobatoria = models.BooleanField(
        default=False,
        verbose_name="¿Este nivel se considera reprobatorio?",
        help_text="Marcar solo para el nivel más bajo (ej: 'Bajo', 'Insuficiente')."
    )

    class Meta:
        verbose_name = "Escala Cualitativa (Preescolar)"
        verbose_name_plural = "Escalas Cualitativas (Preescolar)"
        ordering = ['institucion', 'orden']
        unique_together = ('institucion', 'nombre_escala')

    def __str__(self):
        return f"{self.nombre_escala} ({self.abreviatura})"                   

class Estudiante(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, primary_key=True, limit_choices_to={'rol': 'estudiante'}, verbose_name="Cuenta de Usuario")
    documento_identidad = models.CharField(max_length=20, blank=True, null=True, verbose_name="Documento de Identidad")
    codigo_estudiante = models.CharField(max_length=20, blank=True, null=True, verbose_name="Código de Estudiante")
    fecha_nacimiento = models.DateField(null=True, blank=True, verbose_name="Fecha de Nacimiento")
    direccion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Dirección")
    grado_actual = models.ForeignKey(Grado, on_delete=models.SET_NULL, null=True, blank=True, related_name='estudiantes_actuales', verbose_name="Grado Actual")
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', 
        on_delete=models.CASCADE, 
        verbose_name="Institución",
        related_name="estudiantes" # Apodo único
    )
    SEXO_CHOICES = [('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro')]
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES, blank=True, null=True, verbose_name="Sexo")
    colegio_procedencia = models.CharField(max_length=255, blank=True, null=True, verbose_name="Colegio de Procedencia")
    municipio_ciudad = models.CharField(max_length=100, blank=True, null=True, verbose_name="Municipio/Ciudad")
    departamento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Departamento")

    valor_matricula = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Valor Estándar de Matrícula")
    valor_mensualidad = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Valor Estándar de Mensualidad")

    descuentos = models.ManyToManyField(
        'finanzas.Descuento',
        blank=True,
        verbose_name="Descuentos o Becas Aplicadas"
    )

    activo = models.BooleanField(
        default=True,
        verbose_name="Estudiante Activo",
        help_text="Desmarca esta casilla si el estudiante se ha retirado o ya no está activo en la institución."
    )

    class Meta:
        verbose_name = "Estudiante"
        verbose_name_plural = "Estudiantes"
        permissions = [
            ("ver_mis_calificaciones", "Puede ver sus propias calificaciones"),
            ("ver_mis_deberes", "Puede ver sus propios deberes"),
            ("puede_realizar_entrega_deber", "Puede realizar entregas de deberes"),
            ("ver_mi_boletin", "Puede ver su boletín de calificaciones"),
            ("exportar_boletin_pdf", "Puede exportar su boletín en PDF"),
        ]
        unique_together = [
            ('institucion', 'documento_identidad'),
            ('institucion', 'codigo_estudiante'),
        ]

    def __str__(self):
        nombre_completo = self.usuario.get_full_name()
        return nombre_completo if nombre_completo else self.usuario.username
    
    qr_identifier = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="Identificador Único para QR")
    
    
class Docente(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, primary_key=True, limit_choices_to={'rol': 'docente'}, verbose_name="Cuenta de Usuario")
    documento_identidad = models.CharField(max_length=20, blank=True, null=True, verbose_name="Documento de Identidad")
    codigo_docente = models.CharField(max_length=20, blank=True, null=True, verbose_name="Código de Docente") 
    especialidad = models.CharField(max_length=100, blank=True, null=True, verbose_name="Especialidad Principal")
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name="Institución")
    firma_docente = models.ImageField(upload_to='firmas/', blank=True, null=True, verbose_name="Firma del Docente (Imagen)") 
    qr_identifier = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    dashboard_layout = models.JSONField(null=True, blank=True, verbose_name="Diseño del Dashboard")

    class Meta:
        verbose_name = "Docente"
        verbose_name_plural = "Docentes"
        permissions = [
            ("acceso_libro_notas_docente", "Puede acceder al libro de notas como docente"),
            ("puede_calificar_estudiantes", "Puede calificar estudiantes en actividades"),
        ]

        unique_together = [
            ('institucion', 'documento_identidad'),
            ('institucion', 'codigo_docente'),
        ]

    def __str__(self):
        nombre_completo = self.usuario.get_full_name()
        return nombre_completo if nombre_completo else self.usuario.username

class Familiar(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, primary_key=True, limit_choices_to={'rol': 'familiar'}, verbose_name="Cuenta de Usuario (Login)")
    parentesco = models.CharField(max_length=50, verbose_name="Parentesco con el Estudiante")
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono de Contacto")
    estudiantes_asociados = models.ManyToManyField(Estudiante, related_name='familiares', verbose_name="Estudiante(s) Asociado(s)")
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name="Institución")

    class Meta:
        verbose_name = "Familiar"
        verbose_name_plural = "Familiares"
        permissions = [
            ("acceso_portal_familiar", "Puede acceder al portal de familiares"),
            ("ver_calificaciones_estudiante_familiar", "Puede ver calificaciones de sus estudiantes"),
            ("ver_boletin_estudiante_familiar", "Puede ver el boletín de sus estudiantes"),
            ("ver_deberes_estudiante_familiar", "Puede ver deberes de sus estudiantes"),
        ]

    def __str__(self):
        if hasattr(self, 'usuario') and self.usuario:
            nombre_usuario = self.usuario.get_full_name()
            return nombre_usuario if nombre_usuario else self.usuario.username
        return f"Familiar ID: {self.pk}"
    
class AreaAcademica(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Área")
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)

    # --- CAMBIO IMPORTANTE: AÑADIMOS ESTE CAMPO ---
    # Creamos la relación muchos a muchos aquí.
    materias = models.ManyToManyField(
        'Materia', 
        blank=True, # Un área puede no tener materias asignadas todavía
        verbose_name="Materias Pertenecientes"
    )

    class Meta:
        verbose_name = "Área Académica"
        verbose_name_plural = "Áreas Académicas"
        unique_together = ('nombre', 'institucion',)
     
    def __str__(self):
        return self.nombre


class Materia(models.Model):
    nombre_materia = models.CharField(max_length=100, verbose_name="Nombre de la Materia")
    
    # --- CAMBIO 1: Se quita unique=True de aquí ---
    codigo_materia = models.CharField(max_length=20, blank=True, null=True, verbose_name="Código de Materia")
    
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    
    # --- CAMBIO 2: Se quita null=True, blank=True ---
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name="Institución")
    
    intensidad_horaria_semanal = models.PositiveIntegerField(default=0, verbose_name="Intensidad Horaria Semanal (Ihs)")

    class Meta:
        verbose_name = "Materia"
        verbose_name_plural = "Materias"
        ordering = ['nombre_materia']
        # --- CAMBIO 3: Se añade codigo_materia a la validación ---
        unique_together = [
            ('nombre_materia', 'institucion'),
            ('codigo_materia', 'institucion'),
        ]

    def __str__(self):
        # --- CAMBIO 4: Se quita la coma extra ---
        return self.nombre_materia
    
class DescriptorLogro(models.Model):
    descripcion = models.TextField(verbose_name="Descripción del Logro/Descriptor")
    materia = models.ForeignKey('Materia', on_delete=models.CASCADE, related_name='descriptores')
    periodo_academico = models.ForeignKey('PeriodoAcademico', on_delete=models.CASCADE, related_name='descriptores')
    
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Creado por"
    )

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', 
        on_delete=models.CASCADE,
        editable=False,
        verbose_name="Institución"
    )

    dimension = models.ForeignKey(
        DimensionDesarrollo, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='logros'
    )

    class Meta:
        verbose_name = "Descriptor de Logro"
        verbose_name_plural = "Descriptores de Logros"

    def __str__(self):
        return f"{self.materia.nombre_materia} - {self.descripcion[:50]}..."

    def save(self, *args, **kwargs):
        # Esta lógica asegura que la institución se asigne automáticamente desde la materia
        if not self.institucion_id and self.materia:
            self.institucion = self.materia.institucion
        super().save(*args, **kwargs)

class PeriodoAcademico(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Periodo")
    fecha_inicio = models.DateField(verbose_name="Fecha de Inicio")
    fecha_fin = models.DateField(verbose_name="Fecha de Fin")
    año_escolar = models.PositiveIntegerField(verbose_name="Año Escolar", default=datetime.date.today().year)
    activo = models.BooleanField(default=False, verbose_name="¿Es el periodo activo actual?")
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name="Institución")

    class Meta:
        verbose_name = "Periodo Académico"
        verbose_name_plural = "Periodos Académicos"
        ordering = ['-año_escolar', '-fecha_inicio']
        unique_together = ('nombre', 'año_escolar', 'institucion',) 

    def __str__(self):
        return f"{self.nombre} ({self.año_escolar})"

class Curso(models.Model):
    materia = models.ForeignKey(Materia, on_delete=models.PROTECT, related_name="cursos", verbose_name="Materia")
    grado = models.ForeignKey(Grado, on_delete=models.PROTECT, related_name="cursos", verbose_name="Grado")
    periodo_academico = models.ForeignKey(PeriodoAcademico, on_delete=models.CASCADE, related_name="cursos", verbose_name="Periodo Académico")
    docentes_asignados = models.ManyToManyField(
        'Docente',
        related_name="cursos_impartidos",
        blank=True,
        verbose_name="Docentes Asignados"
    )
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name="Institución")
    aula = models.ForeignKey('gestion_academica.Aula', null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = "Curso"
        verbose_name_plural = "Cursos"
        unique_together = ('materia', 'grado', 'periodo_academico', 'institucion',) 
        ordering = ['periodo_academico', 'grado', 'materia']

    def __str__(self):
        return f"{self.materia.nombre_materia} - {self.grado.nombre} ({self.periodo_academico.nombre})"

class DirectorCurso(models.Model):
    docente = models.ForeignKey(Docente, on_delete=models.CASCADE, related_name="direcciones_grado", verbose_name="Docente Director")
    grado = models.ForeignKey(Grado, on_delete=models.CASCADE, related_name="directores_grado", verbose_name="Grado Dirigido")
    periodo_academico = models.ForeignKey(PeriodoAcademico, on_delete=models.CASCADE, related_name="directores_grado_periodo", verbose_name="Periodo Académico")
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name="Institución")

    class Meta:
        verbose_name = "Director de Curso"
        verbose_name_plural = "Directores de Curso"
        unique_together = ('grado', 'periodo_academico', 'institucion',) 
        ordering = ['periodo_academico', 'grado']

    def __str__(self):
        nombre_docente = self.docente.usuario.get_full_name() or self.docente.usuario.username
        return f"Dir. {nombre_docente} - {self.grado.nombre} ({self.periodo_academico.nombre})"

class EsquemaCalificacion(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Esquema")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción (Opcional)")
    
    # --- CAMBIO: Se quita null=True, blank=True ---
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name="Institución")

    class Meta:
        verbose_name = "Esquema de Calificación"
        verbose_name_plural = "Esquemas de Calificación"
        ordering = ['nombre']
        unique_together = ('nombre', 'institucion',)

    def __str__(self):
        return self.nombre

class TipoActividad(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Tipo de Actividad")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción (Opcional)")
    
    # --- CAMBIO: Se quita null=True, blank=True ---
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name="Institución")

    # ▼▼▼ AÑADE ESTE CAMPO ▼▼▼
    porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Porcentaje de la Categoría (%)",
        help_text="El peso que esta categoría tiene en la nota final del periodo. Ej: 30.00 para 30%"
    )

    orden = models.PositiveIntegerField(
        default=0,
        verbose_name="Orden de Aparición",
        help_text="Un número más bajo aparecerá primero (ej: 1 para Exámenes, 2 para Tareas)."
    )
    # ▲▲▲ FIN DEL CAMPO AÑADIDO ▲▲▲ 

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Creado por"
    )
    # ▲▲▲ FIN DEL CAMPO AÑADIDO ▲▲

    class Meta:
        verbose_name = "Tipo de Actividad"
        verbose_name_plural = "Tipos de Actividad"
        ordering = ['nombre']
        unique_together = ('nombre', 'institucion',)

    def __str__(self):
        return self.nombre

class ActividadCalificable(models.Model):
    curso = models.ForeignKey('Curso', on_delete=models.CASCADE, related_name='actividades_calificables', verbose_name="Curso")
    tipo_actividad = models.ForeignKey('TipoActividad', on_delete=models.PROTECT, verbose_name="Tipo de Actividad")
    titulo = models.CharField(max_length=200, verbose_name="Título de la Actividad")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción Detallada")
    material_adjunto = models.FileField(
        upload_to='actividades_materiales/',
        blank=True,
        null=True,
        verbose_name="Material Adjunto (Opcional)"
    )
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name="Institución")

    # --- INICIO: CAMPOS DE CONFIGURACIÓN (AQUÍ ES DONDE DEBEN ESTAR) ---
    fecha_publicacion = models.DateField(verbose_name="Fecha de Publicación/Asignación", default=datetime.date.today)
    fecha_entrega_limite = models.DateField(null=True, blank=True, verbose_name="Fecha Límite de Entrega (Opcional)")
    
    duracion_minutos = models.PositiveIntegerField(
        null=True, blank=True, 
        verbose_name="Duración en Minutos",
        help_text="Dejar en blanco si no hay límite de tiempo."
    )
    numero_intentos_permitidos = models.PositiveIntegerField(
        default=1,
        verbose_name="Número de Intentos Permitidos",
        help_text="¿Cuántas veces puede el estudiante realizar esta actividad?"
    )
    # --- FIN DE CAMPOS DE CONFIGURACIÓN ---

    class Meta:
        verbose_name = "Actividad Calificable"
        verbose_name_plural = "Actividades Calificables"
        ordering = ['curso', '-fecha_publicacion', 'titulo']

    def __str__(self):
        return f"{self.titulo} ({self.curso})"

class Calificacion(models.Model):
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='calificaciones', verbose_name="Estudiante")
    actividad_calificable = models.ForeignKey(ActividadCalificable, on_delete=models.CASCADE, related_name='calificaciones_recibidas', verbose_name="Actividad Calificable")
    valor_numerico = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Valor Numérico")
    valor_cualitativo = models.CharField(max_length=50, blank=True, null=True, verbose_name="Valor Cualitativo")
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro")
    registrada_por = models.ForeignKey(Docente, on_delete=models.SET_NULL, null=True, blank=True, related_name='calificaciones_registradas', verbose_name="Registrada por")
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name="Institución")

    class Meta:
        unique_together = ('estudiante', 'actividad_calificable', 'institucion',) 
        verbose_name = "Calificación"
        verbose_name_plural = "Calificaciones"
        ordering = ['actividad_calificable__curso', 'estudiante__usuario__last_name', 'actividad_calificable__fecha_publicacion']
        permissions = [
            ("ver_mis_calificaciones", "Puede ver sus propias calificaciones"), 
            ("puede_calificar_estudiantes", "Puede calificar estudiantes en actividades"), 
        ]

    def __str__(self):
        valor = self.valor_numerico if self.valor_numerico is not None else self.valor_cualitativo
        return f"Cal: {self.estudiante.usuario.username} en {self.actividad_calificable.titulo}: {valor or 'Pendiente'}"

class PlanCurricular(models.Model):
    nombre = models.CharField(max_length=255, verbose_name="Nombre del Plan Curricular")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción Detallada (Opcional)")
    documento_adjunto = models.FileField(upload_to='planes_curriculares/', blank=True, null=True, verbose_name="Documento Adjunto del Plan (PDF, Word, etc.)")
    grado_asociado = models.ForeignKey(Grado, on_delete=models.SET_NULL, null=True, blank=True, related_name='planes_curriculares_grado', verbose_name="Grado Asociado (Opcional)")
    materia_asociada = models.ForeignKey(Materia, on_delete=models.SET_NULL, null=True, blank=True, related_name='planes_curriculares_materia', verbose_name="Materia Asociada (Opcional)")
    periodo_academico_asociado = models.ForeignKey(PeriodoAcademico, on_delete=models.SET_NULL, null=True, blank=True, related_name='planes_curriculares_periodo', verbose_name="Periodo Académico Asociado (Opcional)")
    fecha_publicacion = models.DateField(verbose_name="Fecha de Publicación/Vigencia", default=datetime.date.today)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='planes_curriculares_creados', verbose_name="Creado por")
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name="Institución")

    class Meta:
        verbose_name = "Plan Curricular"
        verbose_name_plural = "Planes Curriculares"
        ordering = ['-fecha_publicacion', 'nombre']
        unique_together = ('nombre', 'institucion',) 

    def __str__(self):
        return self.nombre

class Deber(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='deberes', verbose_name="Curso al que pertenece el deber")
    titulo = models.CharField(max_length=255, verbose_name="Título del Deber")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción / Instrucciones")
    fecha_asignacion = models.DateField(verbose_name="Fecha de Asignación", default=datetime.date.today)
    fecha_entrega = models.DateField(verbose_name="Fecha Límite de Entrega")
    material_adjunto = models.FileField(upload_to='deberes_materiales/', blank=True, null=True, verbose_name="Material de Apoyo Adjunto (Opcional)")
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name="Institución")

    class Meta:
        verbose_name = "Deber / Tarea"
        verbose_name_plural = "Deberes / Tareas"
        ordering = ['curso', '-fecha_entrega', 'titulo']
        unique_together = ('curso', 'titulo', 'institucion',) 

    def __str__(self):
        return f"{self.titulo} ({self.curso})"

class EntregaDeber(models.Model):
    deber = models.ForeignKey(Deber, on_delete=models.CASCADE, related_name='entregas', verbose_name="Deber")
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='entregas_deberes', verbose_name="Estudiante")
    fecha_entrega_real = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Entrega Real")
    archivo_adjunto_estudiante = models.FileField(upload_to='entregas_deberes_estudiantes/', blank=True, null=True, verbose_name="Archivo Adjunto del Estudiante")
    comentarios_estudiante = models.TextField(blank=True, null=True, verbose_name="Comentarios del Estudiante (Opcional)")
    calificacion_obtenida = models.CharField(max_length=20, blank=True, null=True, verbose_name="Calificación Obtenida")
    comentarios_docente = models.TextField(blank=True, null=True, verbose_name="Comentarios del Docente")
    fecha_calificacion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Calificación")
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name="Institución")
    porcentaje_similitud = models.PositiveIntegerField(
        null=True, blank=True, 
        verbose_name="Porcentaje de Similitud (%)"
    )
    alerta_plagio = models.BooleanField(
        default=False, 
        verbose_name="Alerta de Posible Plagio"
    )

    class Meta:
        unique_together = ('deber', 'estudiante', 'institucion',) 
        verbose_name = "Entrega de Deber"
        verbose_name_plural = "Entregas de Deberes"
        ordering = ['deber', 'estudiante']
        permissions = [
            ("puede_realizar_entrega_deber", "Puede realizar entregas de deberes"), 
        ]

    def __str__(self):
        return f"Entrega de '{self.deber.titulo}' por {self.estudiante.usuario.username}"

class MencionReconocimiento(models.Model):
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='menciones_reconocimientos', verbose_name="Estudiante")
    curso = models.ForeignKey(Curso, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Curso (Opcional)")
    periodo = models.ForeignKey(PeriodoAcademico, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Periodo Académico (Opcional)")
    tipo = models.CharField(max_length=150, verbose_name="Tipo de Mención/Reconocimiento")
    descripcion = models.TextField(verbose_name="Descripción Detallada del Reconocimiento")
    fecha_otorgamiento = models.DateField(verbose_name="Fecha de Otorgamiento", default=datetime.date.today)
    otorgado_por = models.ForeignKey(Docente, on_delete=models.SET_NULL, null=True, blank=True, related_name='menciones_otorgadas', verbose_name="Otorgado/Registrado por (Docente)")
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name="Institución")

    class Meta:
        verbose_name = "Mención o Reconocimiento"
        verbose_name_plural = "Menciones y Reconocimientos"
        ordering = ['-fecha_otorgamiento', 'estudiante']
        unique_together = ('estudiante', 'tipo', 'fecha_otorgamiento', 'institucion',) 
        permissions = [
            ("acceso_portal_familiar", "Puede acceder al portal de familiares"),
            ("ver_calificaciones_estudiante_familiar", "Puede ver calificaciones de sus estudiantes"),
            ("ver_boletin_estudiante_familiar", "Puede ver el boletín de sus estudiantes"),
            ("ver_deberes_estudiante_familiar", "Puede ver deberes de sus estudiantes"),
        ]

    def __str__(self):
        otorgante = f" (Otorgado por: {self.otorgado_por})" if self.otorgado_por else ""
        return f"{self.tipo} a {self.estudiante.usuario.get_full_name() or self.estudiante.usuario.username} el {self.fecha_otorgamiento}{otorgante}"

class ArchivoPlanAcademico(models.Model):
    nombre_archivo_descriptivo = models.CharField(max_length=255, verbose_name="Nombre Descriptivo del Archivo", default="[Nombre no especificado]")
    archivo = models.FileField(upload_to='planes_academicos_materiales/', verbose_name="Archivo")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción (Opcional)")
    tipo_documento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Tipo de Documento (Ej: Plan de Estudio, Guía, Presentación)")
    curso_asociado = models.ForeignKey(Curso, on_delete=models.SET_NULL, null=True, blank=True, related_name='archivos_material_apoyo_curso', verbose_name="Curso Asociado (Opcional)")
    materia_asociada = models.ForeignKey(Materia, on_delete=models.SET_NULL, null=True, blank=True, related_name='archivos_material_apoyo_materia', verbose_name="Materia Asociada (Opcional)")
    subido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Subido por")
    fecha_subida = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Subida")
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name="Institución")
    palabras_clave = models.CharField(
        max_length=255, 
        blank=True,
        verbose_name="Palabras Clave (temas)",
        help_text="Separa los temas con comas. Ej: fracciones, suma, resta, decimales"
    )
    temas_relacionados = models.TextField(
        blank=True,
        null=True,
        verbose_name="Temas Relevantes",
        help_text="Añade temas específicos separados por comas (ej: 'Suma de fracciones', 'Teorema de Pitágoras', 'Análisis de personajes')."
    )

    class Meta:
        verbose_name = "Archivo de Plan Académico o Material"
        verbose_name_plural = "Archivos de Planes Académicos y Materiales"
        ordering = ['-fecha_subida', 'nombre_archivo_descriptivo']
        unique_together = ('nombre_archivo_descriptivo', 'curso_asociado', 'materia_asociada', 'institucion',) 

    def __str__(self):
        return self.nombre_archivo_descriptivo

class ConfiguracionInstitucion(models.Model):
    institucion_principal = models.OneToOneField(
        'finanzas.InstitucionEducativa', 
        on_delete=models.CASCADE, 
        primary_key=True, 
        verbose_name="Institución Principal" 
    ) 
    nombre_institucion = models.CharField(max_length=255, default="Nombre de Mi Institución", verbose_name="Nombre de la Institución (Opcional, si difiere de la principal)")
    lema_institucion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Lema o Eslogan (Opcional)")
    direccion = models.TextField(blank=True, null=True, verbose_name="Dirección (Opcional)")
    telefono_contacto = models.CharField(max_length=50, blank=True, null=True, verbose_name="Teléfono(s) de Contacto (Opcional)")
    email_contacto = models.EmailField(blank=True, null=True, verbose_name="Email de Contacto (Opcional)")
    sitio_web = models.URLField(blank=True, null=True, verbose_name="Sitio Web (Opcional)")
    logo = models.ImageField(upload_to='logos_institucion_gestion_academica/', blank=True, null=True, verbose_name="Logo de la Institución (Opcional, si difiere del principal)")

    class Meta:
        verbose_name = "Configuración de la Institución (Adicional)" 
        verbose_name_plural = "Configuraciones de la Institución (Adicionales)"

    def __str__(self):
        return f"Configuración para {self.institucion_principal.nombre}"

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
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name="Institución")

    class Meta:
        verbose_name = "Noticia o Anuncio"
        verbose_name_plural = "Noticias y Anuncios"
        ordering = ['-fecha_publicacion']
        unique_together = ('titulo', 'fecha_publicacion', 'institucion',) 

    def __str__(self):
        return self.titulo
    
class RegistroAsistencia(models.Model):
    ESTADOS = (
        ('PRESENTE', 'Presente'),
        ('AUSENTE', 'Ausente'),
        ('TARDANZA', 'Tardanza'),
        ('JUSTIFICADO', 'Justificado')
    )

    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='asistencias')
    fecha = models.DateTimeField(default=timezone.now)
    fecha_solo = models.DateField(null=True, blank=True, editable=False)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PRESENTE')
    curso = models.ForeignKey(Curso, on_delete=models.SET_NULL, null=True, blank=True)
    aula = models.ForeignKey('gestion_academica.Aula', on_delete=models.SET_NULL, null=True, blank=True)  # ✅ Nuevo
    registrado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('estudiante', 'fecha', 'curso')

    def save(self, *args, **kwargs):
        if self.fecha:
            self.fecha_solo = localtime(self.fecha).date()
        if self.curso and self.curso.aula and not self.aula:
            self.aula = self.curso.aula  # ✅ Autocompleta aula desde el curso
        super().save(*args, **kwargs)

class EnlaceVideollamada(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='enlaces_videollamada')
    titulo = models.CharField(max_length=200, verbose_name="Título del Enlace")
    url = models.URLField(max_length=500, verbose_name="URL de la Videollamada (Meet, Zoom, etc.)")
    descripcion = models.TextField(blank=True, help_text="Instrucciones o descripción breve.")
    
    # --- CAMPO AÑADIDO ---
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', 
        on_delete=models.CASCADE,
        editable=False
    )

    class Meta:
        verbose_name = "Enlace de Videollamada"
        verbose_name_plural = "Enlaces de Videollamada"
        ordering = ['titulo']

    def __str__(self):
        return f"{self.titulo} - {self.curso}"
        
    def save(self, *args, **kwargs):
        # Lógica para autocompletar la institución
        if not self.institucion_id and self.curso:
            self.institucion = self.curso.institucion
        super().save(*args, **kwargs)

class Aula(models.Model):
    TIPO_AULA = [
        ('AULA', 'Aula Regular'),
        ('LAB', 'Laboratorio'),
        ('AUD', 'Auditorio'),
        ('GYM', 'Gimnasio'),
        ('OTR', 'Otro'),
    ]

    nombre = models.CharField(max_length=100, help_text="Ej: Salón 101, Laboratorio de Química")
    tipo = models.CharField(max_length=4, choices=TIPO_AULA, default='AULA', verbose_name="Tipo de Aula")
    capacidad = models.PositiveIntegerField(default=0, help_text="Número máximo de estudiantes")
    ubicacion = models.CharField(max_length=255, blank=True, help_text="Ej: Edificio A, Segundo Piso")
    recursos = models.TextField(blank=True, help_text="Ej: Proyector, Pizarra Inteligente, 20 Computadores")
    
    # Este campo es la clave para la arquitectura multi-institución.
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Aula o Salón de Clases"
        verbose_name_plural = "Aulas y Salones de Clases"
        
        # ▼▼▼ LA REGLA DE NEGOCIO PARA MULTI-INSTITUCIÓN ▼▼▼
        # Esto asegura que el 'nombre' del aula sea único DENTRO de cada 'institucion'.
        unique_together = ('nombre', 'institucion')

    def __str__(self):
        # Un __str__ más descriptivo ayuda en el panel de administrador.
        return f"{self.nombre} ({self.institucion.nombre})" # Incluir la institución aquí es una buena práctica.


class BloqueHorario(models.Model):
    """
    Representa un bloque de clase específico en el horario semanal.
    VERSIÓN DEFINITIVA: Con validación de conflictos multi-nivel y multi-rol.
    """
    DIA_SEMANA_CHOICES = [
        (0, 'Lunes'),
        (1, 'Martes'),
        (2, 'Miércoles'),
        (3, 'Jueves'),
        (4, 'Viernes'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]

    curso = models.ForeignKey('gestion_academica.Curso', on_delete=models.CASCADE, related_name='horarios')
    dia_semana = models.IntegerField(choices=DIA_SEMANA_CHOICES, verbose_name="Día de la Semana")
    hora_inicio = models.TimeField(verbose_name="Hora de Inicio")
    hora_fin = models.TimeField(verbose_name="Hora de Fin")
    aula = models.ForeignKey('gestion_academica.Aula', on_delete=models.SET_NULL, null=True, blank=True, related_name='horarios')
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)
    google_event_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="ID del Evento en Google Calendar")

    class Meta:
        verbose_name = "Bloque de Horario"
        verbose_name_plural = "Bloques de Horario"
        ordering = ['dia_semana', 'hora_inicio']
        # Se elimina 'unique_together' para permitir una validación más flexible en el método clean.

    def __str__(self):
        return f"{self.curso} - {self.get_dia_semana_display()} de {self.hora_inicio.strftime('%H:%M')} a {self.hora_fin.strftime('%H:%M')}"

    def clean(self):
        # 1. Validación de horas (sin cambios)
        if self.hora_inicio and self.hora_fin and self.hora_fin <= self.hora_inicio:
            raise ValidationError('La hora de fin debe ser posterior a la hora de inicio.')

        # --- 2. NUEVA VALIDACIÓN INTELIGENTE DE CONFLICTOS ---
        # Buscamos todos los bloques que se solapen en el tiempo en la misma institución y día
        conflictos_potenciales = BloqueHorario.objects.filter(
            institucion=self.institucion,
            dia_semana=self.dia_semana,
            hora_inicio__lt=self.hora_fin,
            hora_fin__gt=self.hora_inicio,
        ).exclude(pk=self.pk)

        # a) Conflicto de Aula (solo si los niveles son iguales)
        if self.aula:
            nivel_actual = self.curso.grado.nivel_escolaridad
            conflicto_aula = conflictos_potenciales.filter(
                aula=self.aula,
                curso__grado__nivel_escolaridad=nivel_actual
            ).first()
            if conflicto_aula:
                raise ValidationError(
                    f"Conflicto de Aula: El aula '{self.aula}' ya está ocupada en ese horario "
                    f"por el curso '{conflicto_aula.curso}' del mismo nivel educativo ({nivel_actual.nombre})."
                )

        # b) Conflicto de Grado (un grado no puede tener dos clases a la vez)
        conflicto_grado = conflictos_potenciales.filter(curso__grado=self.curso.grado).first()
        if conflicto_grado:
            raise ValidationError(
                f"Conflicto de Grado: El grado '{self.curso.grado}' ya tiene la clase de "
                f"'{conflicto_grado.curso.materia}' programada a esa hora."
            )

        # c) Conflicto de Docente (un docente no puede tener dos clases a la vez)
        docentes_del_curso = self.curso.docentes_asignados.all()
        if docentes_del_curso.exists():
            conflicto_docente = conflictos_potenciales.filter(curso__docentes_asignados__in=docentes_del_curso).first()
            if conflicto_docente:
                docente_en_conflicto = conflicto_docente.curso.docentes_asignados.filter(pk__in=docentes_del_curso.values_list('pk', flat=True)).first()
                raise ValidationError(
                    f"Conflicto de Docente: El docente '{docente_en_conflicto}' ya tiene la clase de "
                    f"'{conflicto_docente.curso}' programada a esa hora."
                )
            

class LeccionDiaria(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='lecciones')
    fecha = models.DateField(default=timezone.now)
    tema_tratado = models.CharField(max_length=255)
    resumen_clase = models.TextField(help_text="Resumen de lo visto en clase.")
    archivo_adjunto = models.FileField(upload_to='lecciones/', blank=True, null=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE,)

    class Meta:
        ordering = ['-fecha']   

class Pregunta(models.Model):
    TIPO_PREGUNTA_CHOICES = [
        ('opcion_multiple', 'Opción Múltiple'),
        ('verdadero_falso', 'Verdadero o Falso'),
        ('respuesta_abierta', 'Respuesta Abierta'),
    ]
    actividad = models.ForeignKey('ActividadCalificable', on_delete=models.CASCADE, related_name='preguntas')
    enunciado = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_PREGUNTA_CHOICES)
    orden = models.PositiveIntegerField(default=0)

    # --- INICIO DE LA CORRECCIÓN ---
    # Añadimos los campos que el formulario está buscando.
    # Ahora, cada pregunta puede tener su propia configuración.
    
    duracion_minutos = models.PositiveIntegerField(
        null=True, blank=True, 
        verbose_name="Duración para esta pregunta (minutos)",
        help_text="Dejar en blanco si esta pregunta no tiene un límite de tiempo específico."
    )
    numero_intentos_permitidos = models.PositiveIntegerField(
        default=1,
        verbose_name="Intentos permitidos para esta pregunta",
        help_text="¿Cuántas veces puede el estudiante responder esta pregunta específica?"
    )
    
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', 
        on_delete=models.CASCADE,
        editable=False,
        null=True # Permitimos nulo para que el save() lo asigne
    )

    def save(self, *args, **kwargs):
        # Asigna la institución automáticamente desde la actividad padre
        if not self.institucion_id and self.actividad:
            self.institucion = self.actividad.institucion
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['orden']
        verbose_name = "Pregunta de Actividad"
        verbose_name_plural = "Preguntas de Actividades"

    def __str__(self):
        return f"Pregunta: {self.enunciado[:50]}..."

class Opcion(models.Model):
    pregunta = models.ForeignKey('Pregunta', on_delete=models.CASCADE, related_name='opciones')
    texto = models.CharField(max_length=255)
    es_correcta = models.BooleanField(default=False)
    
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', 
        on_delete=models.CASCADE,
        editable=False
    )
    
    def __str__(self):
        return self.texto

    def save(self, *args, **kwargs):
        # ✅ Lógica Corregida: La institución se hereda de la pregunta.
        if not self.institucion_id and self.pregunta:
            self.institucion = self.pregunta.institucion
        super().save(*args, **kwargs)

class RespuestaEstudiante(models.Model):
    estudiante = models.ForeignKey('Estudiante', on_delete=models.CASCADE, related_name='respuestas_actividades')
    pregunta = models.ForeignKey('Pregunta', on_delete=models.CASCADE, related_name='respuestas_recibidas')
    opcion_seleccionada = models.ForeignKey(Opcion, on_delete=models.CASCADE, null=True, blank=True)
    texto_respuesta = models.TextField(blank=True, null=True, verbose_name="Respuesta de Texto")
    
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', 
        on_delete=models.CASCADE,
        editable=False
    )
    

    class Meta:
        # Un estudiante solo puede tener una respuesta por pregunta en una institución.
        unique_together = ('estudiante', 'pregunta', 'institucion')

    def __str__(self):
        return f"Respuesta de {self.estudiante} a {self.pregunta}"
        
    def save(self, *args, **kwargs):
        # ✅ Lógica Corregida: La institución se hereda de la pregunta.
        if not self.institucion_id and self.pregunta:
            self.institucion = self.pregunta.institucion
        super().save(*args, **kwargs)               

class IntentoActividad(models.Model):
    """
    Registra cada intento que un estudiante hace en una actividad calificable.
    """
    ESTADOS = [
        ('en_progreso', 'En Progreso'),
        ('completado', 'Completado'),
        ('tiempo_agotado', 'Tiempo Agotado'),
    ]

    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='intentos')
    actividad = models.ForeignKey(ActividadCalificable, on_delete=models.CASCADE, related_name='intentos')
    inicio = models.DateTimeField(auto_now_add=True, verbose_name="Inicio del Intento")
    fin = models.DateTimeField(null=True, blank=True, verbose_name="Fin del Intento")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='en_progreso')
    puntaje_obtenido = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', 
        on_delete=models.CASCADE,
        editable=False
    )

    def save(self, *args, **kwargs):
        # Asigna la institución automáticamente
        if not self.institucion_id and self.actividad:
            self.institucion = self.actividad.institucion
        super().save(*args, **kwargs)

    class Meta:
        # Un estudiante solo puede tener un intento "en progreso" por actividad a la vez
        unique_together = ('estudiante', 'actividad', 'estado')
        verbose_name = "Intento de Actividad"
        verbose_name_plural = "Intentos de Actividades"

class ObservacionBoletin(models.Model):
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='observaciones_boletin')
    periodo = models.ForeignKey(PeriodoAcademico, on_delete=models.CASCADE, related_name='observaciones_recibidas')
    observacion = models.TextField(verbose_name="Observación para el Boletín")
    creado_por = models.ForeignKey('Docente', on_delete=models.SET_NULL, null=True)
    ultima_modificacion = models.DateTimeField(auto_now=True)
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE,)

    class Meta:
        unique_together = ('estudiante', 'periodo') # Solo una observación por estudiante y periodo 

class EscalaValorativa(models.Model):
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, related_name='escala_valorativa')
    nombre_desempeno = models.CharField(max_length=50, verbose_name="Nombre del Desempeño (Ej: Superior, Alto)")
    abreviatura = models.CharField(max_length=10, verbose_name="Abreviatura (Ej: Sup, Alt)")
    nota_minima = models.DecimalField(max_digits=3, decimal_places=2, verbose_name="Nota Mínima para este Desempeño")
    nota_maxima = models.DecimalField(max_digits=3, decimal_places=2, verbose_name="Nota Máxima para este Desempeño")
    orden = models.PositiveIntegerField(default=0, help_text="Orden para mostrar en la leyenda (ej. 1 para Superior, 2 para Alto, etc.)")

    class Meta:
        ordering = ['-nota_maxima'] # Ordenamos de la nota más alta a la más baja
        unique_together = ('institucion', 'nombre_desempeno')
        verbose_name = "Escala Valorativa"
        verbose_name_plural = "Escalas Valorativas"

    def __str__(self):
        return f"{self.nombre_desempeno} ({self.nota_minima} - {self.nota_maxima})"               

class AnotacionObservador(models.Model):
    TIPO_ANOTACION = [
        ('ACADEMICA', 'Académica'),
        ('CONVIVENCIA', 'Convivencia'),
        ('FELICITACION', 'Felicitación'),
        ('LLAMADO_ATENCION', 'Llamado de Atención'),
        ('OTRO', 'Otro'),
    ]

    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='anotaciones_observador')
    fecha_hora = models.DateTimeField(default=timezone.now, verbose_name="Fecha y Hora")
    tipo = models.CharField(max_length=20, choices=TIPO_ANOTACION, verbose_name="Tipo de Anotación")
    descripcion = models.TextField(verbose_name="Descripción de la Anotación")
    
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='anotaciones_registradas'
    )
    curso = models.ForeignKey(
        Curso, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Curso Relacionado (Opcional)"
    )
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE,)

    
    class Sentiment(models.TextChoices):
        POSITIVO = 'POSITIVO', 'Positivo'
        NEUTRO = 'NEUTRO', 'Neutro'
        NEGATIVO = 'NEGATIVO', 'Negativo'

    sentimiento_detectado = models.CharField(
        max_length=10, 
        choices=Sentiment.choices, 
        null=True, blank=True, 
        verbose_name="Sentimiento Detectado por IA"
    )
    requiere_revision = models.BooleanField(
        default=False, 
        verbose_name="¿Requiere Revisión Urgente?",
        help_text="Marcado automáticamente por la IA si detecta riesgo (bullying, tristeza, etc.)"
    )
    analisis_ia = models.TextField(
        blank=True, null=True, 
        verbose_name="Análisis y Sugerencias de la IA",
        help_text="Resumen generado por la IA para el coordinador."
    )

    # --- NUEVOS CAMPOS PARA LA RUTA DE ATENCIÓN ---
    TIPO_SITUACION_CHOICES = [
        ('TIPO I', 'Situación Tipo I'),
        ('TIPO II', 'Situación Tipo II'),
        ('TIPO III', 'Situación Tipo III'),
        ('NINGUNO', 'Ninguno'),
    ]
    tipo_situacion_ia = models.CharField(
        max_length=10, 
        choices=TIPO_SITUACION_CHOICES,
        blank=True, null=True,
        verbose_name="Clasificación de Convivencia (IA)"
    )
    acciones_protocolo_ia = models.TextField(
        blank=True, null=True,
        verbose_name="Protocolo Sugerido por IA"
    )
    
    class Meta:
        verbose_name = "Anotación en Observador"
        verbose_name_plural = "Anotaciones en Observador"
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"Anotación para {self.estudiante} el {self.fecha_hora.strftime('%d/%m/%Y')}"

# En gestion_academica/models.py

class AnalisisRiesgo(models.Model):
    """
    Representa una ejecución del análisis predictivo. Se ejecuta periódicamente
    (ej. cada semana o quincena) para actualizar las predicciones.
    """
    periodo_academico = models.ForeignKey(PeriodoAcademico, on_delete=models.CASCADE)
    fecha_analisis = models.DateTimeField(auto_now_add=True)
    resumen = models.TextField(blank=True, null=True, help_text="Ej: Se encontraron 25 estudiantes en alto riesgo.")
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE,)

    def __str__(self):
        return f"Análisis del {self.fecha_analisis.strftime('%Y-%m-%d')} para {self.periodo_academico}"

class PrediccionRiesgoEstudiante(models.Model):
    """
    Almacena el resultado del análisis para un estudiante específico en una materia.
    """
    class NivelRiesgo(models.TextChoices):
        ALTO = 'ALTO', 'Alto'
        MEDIO = 'MEDIO', 'Medio'
        BAJO = 'BAJO', 'Bajo'

    analisis = models.ForeignKey(AnalisisRiesgo, on_delete=models.CASCADE, related_name='predicciones')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE)
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, null=True, blank=True)
    
    nivel_riesgo = models.CharField(max_length=5, choices=NivelRiesgo.choices, default=NivelRiesgo.BAJO)
    puntaje_riesgo = models.IntegerField(default=0, help_text="Puntaje calculado por el algoritmo.")
    
    # Este campo es la "magia": explica POR QUÉ el sistema lo marcó.
    factores_influyentes = models.JSONField(default=dict, help_text="Detalles de los factores que elevaron el riesgo.")
    
    fecha_prediccion = models.DateTimeField(auto_now_add=True)
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE,)

    def __str__(self):
        return f"Riesgo {self.nivel_riesgo} para {self.estudiante} en {self.materia}"

class Notificacion(models.Model):
    """
    Representa una notificación interna para un usuario dentro del sistema.
    """
    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='notificaciones'
    )
    mensaje = models.CharField(max_length=255, verbose_name="Mensaje de la Notificación")
    enlace = models.URLField(blank=True, null=True, help_text="URL a la que llevará la notificación al hacer clic.")
    consejo_ia = models.TextField(blank=True, null=True, verbose_name="Consejo Generado por IA")
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE,)
    
    # Estados de la notificación
    leido = models.BooleanField(default=False, verbose_name="¿Leído?")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_leido = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"

    def __str__(self):
        return f"Notificación para {self.destinatario.username}: {self.mensaje[:30]}..."

    def marcar_como_leido(self):
        """Marca la notificación como leída."""
        if not self.leido:
            self.leido = True
            self.fecha_leido = timezone.now()
            self.save(update_fields=['leido', 'fecha_leido'])

class DisponibilidadDocente(models.Model):
    """
    Define un bloque de tiempo RECURRENTE en el que un docente está
    disponible para reuniones. Ej: "Todos los martes de 2 a 4 PM".
    """
    DIA_SEMANA_CHOICES = [
        (0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'), 
        (3, 'Jueves'), (4, 'Viernes')
    ]

    docente = models.ForeignKey(Docente, on_delete=models.CASCADE, related_name='disponibilidades')
    dia_semana = models.IntegerField(choices=DIA_SEMANA_CHOICES, verbose_name="Día de la semana")
    hora_inicio = models.TimeField(verbose_name="Hora de inicio de disponibilidad")
    hora_fin = models.TimeField(verbose_name="Hora de fin de disponibilidad")
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Disponibilidad de Docente"
        verbose_name_plural = "Disponibilidades de Docentes"
        unique_together = ('docente', 'dia_semana', 'hora_inicio')

    def __str__(self):
        return f"{self.docente} - {self.get_dia_semana_display()} de {self.hora_inicio.strftime('%H:%M')} a {self.hora_fin.strftime('%H:%M')}"


class CitaReunion(models.Model):
    """
    Representa una cita específica reservada por un familiar.
    """
    class EstadoCita(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        CONFIRMADA = 'CONFIRMADA', 'Confirmada'
        CANCELADA = 'CANCELADA', 'Cancelada'
        REALIZADA = 'REALIZADA', 'Realizada'

    docente = models.ForeignKey(Docente, on_delete=models.CASCADE, related_name='citas')
    familiar = models.ForeignKey(Familiar, on_delete=models.CASCADE, related_name='citas')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='citas_reuniones')
    
    fecha_hora_inicio = models.DateTimeField(verbose_name="Fecha y hora de la cita")
    duracion_minutos = models.PositiveIntegerField(default=15, verbose_name="Duración (minutos)")
    
    asunto = models.CharField(max_length=255, verbose_name="Asunto principal de la reunión")
    enlace_virtual = models.URLField(blank=True, null=True, verbose_name="Enlace de la videollamada (si aplica)")
    
    estado = models.CharField(max_length=15, choices=EstadoCita.choices, default=EstadoCita.PENDIENTE)
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE,)
    

    observaciones_docente = models.TextField(
        blank=True, null=True, 
        verbose_name="Observaciones de la Reunión",
        help_text="Notas privadas del docente sobre lo discutido en la reunión."
    )
    acuerdos_compromisos = models.TextField(
        blank=True, null=True, 
        verbose_name="Acuerdos y Compromisos",
        help_text="Resumen de los acuerdos a los que se llegaron. Será visible para el familiar."
    )
    
    class Meta:
        verbose_name = "Cita de Reunión"
        verbose_name_plural = "Citas de Reuniones"
        ordering = ['fecha_hora_inicio']
        unique_together = ('docente', 'fecha_hora_inicio')

    def __str__(self):
        return f"Cita de {self.familiar} con {self.docente} el {self.fecha_hora_inicio.strftime('%d/%m/%Y %H:%M')}"          

          

class Eleccion(models.Model):
    nombre = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    cargo = models.CharField(max_length=100)
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)

    def __str__(self):
        return self.nombre

class Candidato(models.Model):
    eleccion = models.ForeignKey(Eleccion, on_delete=models.CASCADE, related_name='candidatos')
    # --- CORRECCIÓN CLAVE ---
    # Vinculamos directamente al Estudiante para evitar inconsistencias de datos.
    estudiante = models.ForeignKey('Estudiante', on_delete=models.CASCADE, related_name='candidaturas')
    # -------------------------
    propuesta = models.TextField()
    foto = models.ImageField(upload_to='candidatos/')
    analisis_ia = models.TextField(blank=True, null=True)
    # La institución se obtiene a través de la elección, no es necesaria aquí.

    def __str__(self):
        return f"{self.estudiante.usuario.get_full_name()} - {self.eleccion.nombre}"

    class Meta:
        # Un estudiante solo puede ser candidato una vez por elección.
        unique_together = ('eleccion', 'estudiante')

class Voto(models.Model):
    eleccion = models.ForeignKey(Eleccion, on_delete=models.CASCADE, related_name='votos')
    votante = models.ForeignKey('Estudiante', on_delete=models.CASCADE, related_name='votos_emitidos')
    candidato = models.ForeignKey(Candidato, on_delete=models.CASCADE, related_name='votos_recibidos')
    fecha_voto = models.DateTimeField(auto_now_add=True)
    # La institución se obtiene a través de la elección.

    class Meta:
        verbose_name = "Voto"
        verbose_name_plural = "Votos"
        # Un votante solo puede votar una vez por elección.
        unique_together = ('eleccion', 'votante')

    def __str__(self):
        return f"{self.votante} votó por {self.candidato}"

        
        
class RegistroAsistenciaDocente(models.Model):
    docente = models.ForeignKey(Docente, on_delete=models.CASCADE, related_name='asistencias')
    fecha = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=[('PRESENTE', 'Presente')], default='PRESENTE')
    registrado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Registro de Asistencia de Docente"
        verbose_name_plural = "Asistencias de Docentes"
        ordering = ['-fecha']

class Egresado(models.Model):
    estudiante = models.OneToOneField(
        Estudiante, 
        on_delete=models.PROTECT, 
        related_name='perfil_egresado',
        verbose_name="Perfil de Estudiante Original"
    )
    año_graduacion = models.PositiveIntegerField(verbose_name="Año de Graduación")
    fecha_egreso = models.DateField(verbose_name="Fecha de Egreso")
    estado = models.CharField(max_length=50, default="Activo", verbose_name="Estado del Egresado")

    class Meta:
        verbose_name = "Egresado"
        verbose_name_plural = "Egresados"
        ordering = ['-año_graduacion', 'estudiante__usuario__last_name']

    def __str__(self):
        return f"Egresado: {self.estudiante.usuario.get_full_name()} ({self.año_graduacion})"


class ArchivoHistorico(models.Model):
    class TipoDocumento(models.TextChoices):
        CERTIFICADO_NOTAS = 'CERT_NOTAS', 'Certificado de Notas'
        BOLETIN_FINAL = 'BOL_FINAL', 'Boletín Final'
        DIPLOMA_BACHILLER = 'DIPLOMA', 'Copia de Diploma'
        PAZ_Y_SALVO = 'PAZ_SALVO', 'Paz y Salvo Financiero'
        CONSTANCIA_ESTUDIOS = 'CONST_ESTUDIOS', 'Constancia de Estudios'

    egresado = models.ForeignKey(Egresado, on_delete=models.CASCADE, related_name='archivos')
    tipo_documento = models.CharField(max_length=50, choices=TipoDocumento.choices, verbose_name="Tipo de Documento")
    año_academico = models.PositiveIntegerField(verbose_name="Año Académico del Reporte")
    archivo_pdf = models.FileField(upload_to='archivos_historicos/', verbose_name="Archivo PDF Generado")
    fecha_generacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Archivo Histórico"
        verbose_name_plural = "Archivos Históricos"
        ordering = ['-año_academico', 'tipo_documento']

    def __str__(self):
        return f"{self.get_tipo_documento_display()} de {self.egresado} ({self.año_academico})"

class SolicitudDocumento(models.Model):
    class EstadoSolicitud(models.TextChoices):
        PENDIENTE_PAGO = 'PENDIENTE_PAGO', 'Pendiente de Pago'
        EN_PROCESO = 'EN_PROCESO', 'Pagado, en Proceso'
        LISTO_DESCARGA = 'LISTO_DESCARGA', 'Listo para Descargar'
        COMPLETADO = 'COMPLETADO', 'Completado'
        CANCELADO = 'CANCELADO', 'Cancelado'

    egresado = models.ForeignKey(Egresado, on_delete=models.CASCADE, related_name='solicitudes')
    tipo_documento_solicitado = models.CharField(max_length=100, verbose_name="Documento Solicitado")
    estado = models.CharField(max_length=50, choices=EstadoSolicitud.choices, default=EstadoSolicitud.PENDIENTE_PAGO)

    # Vinculación con el sistema financiero
    cuenta_por_cobrar = models.OneToOneField(
        'finanzas.CuentaPorCobrarEstudiante', 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='solicitud_documento'
    )

    # El archivo final que el admin subirá
    archivo_generado = models.FileField(upload_to='documentos_solicitados/', null=True, blank=True)

    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Solicitud de {self.tipo_documento_solicitado} para {self.egresado}"        

class TicketSoporte(models.Model):
    """
    Representa un ticket de soporte generado por un usuario.
    """
    class Prioridad(models.TextChoices):
        BAJA = 'BAJA', 'Baja'
        MEDIA = 'MEDIA', 'Media'
        ALTA = 'ALTA', 'Alta'
        URGENTE = 'URGENTE', 'Urgente'

    class Estado(models.TextChoices):
        ABIERTO = 'ABIERTO', 'Abierto'
        EN_PROGRESO = 'EN_PROGRESO', 'En Progreso'
        RESUELTO = 'RESUELTO', 'Resuelto'
        CERRADO = 'CERRADO', 'Cerrado'

    ticket_id = models.CharField(max_length=20, unique=True, editable=False, verbose_name="ID del Ticket")
    titulo = models.CharField(max_length=255, verbose_name="Asunto del Ticket")
    descripcion = models.TextField(verbose_name="Descripción Detallada del Problema")
    
    prioridad = models.CharField(max_length=10, choices=Prioridad.choices, default=Prioridad.MEDIA)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ABIERTO)
    
    usuario_reporta = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tickets_creados")
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, related_name="tickets_soporte")
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    ultima_actualizacion = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Generar un ID de ticket único y consecutivo si es un objeto nuevo
        if not self.pk:
            timestamp = timezone.now().strftime('%Y%m%d')
            last_ticket = TicketSoporte.objects.filter(ticket_id__startswith=f"HALU-{timestamp}").order_by('ticket_id').last()
            if last_ticket:
                last_seq = int(last_ticket.ticket_id.split('-')[-1])
                new_seq = last_seq + 1
            else:
                new_seq = 1
            self.ticket_id = f"HALU-{timestamp}-{new_seq:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.ticket_id}] - {self.titulo}"

    class Meta:
        verbose_name = "Ticket de Soporte"
        verbose_name_plural = "Tickets de Soporte"
        ordering = ['-fecha_creacion']


class RespuestaTicket(models.Model):
    """
    Representa una respuesta o actualización dentro de un ticket de soporte.
    """
    ticket = models.ForeignKey(TicketSoporte, on_delete=models.CASCADE, related_name="respuestas")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    mensaje = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    adjunto = models.FileField(upload_to='soporte_adjuntos/', blank=True, null=True)

    def __str__(self):
        return f"Respuesta de {self.autor} en ticket {self.ticket.ticket_id}"

    class Meta:
        verbose_name = "Respuesta de Ticket"
        verbose_name_plural = "Respuestas de Tickets"
        ordering = ['fecha_creacion']        

class PlaneacionClase(models.Model):
    """
    Representa una unidad de planeación completa para un curso,
    generada por un docente con la ayuda de la IA.
    VERSIÓN ACTUALIZADA CON ESTADOS DE GENERACIÓN.
    """
    class Metodologia(models.TextChoices):
        PROYECTOS = 'PROYECTOS', 'Aprendizaje Basado en Proyectos (ABP)'
        PROBLEMAS = 'PROBLEMAS', 'Aprendizaje Basado en Problemas (ABP)'
        INVERTIDA = 'INVERTIDA', 'Aula Invertida'
        TRADICIONAL = 'TRADICIONAL', 'Clase Magistral / Tradicional'
        COLABORATIVO = 'COLABORATIVO', 'Aprendizaje Colaborativo'
        GAMIFICACION = 'GAMIFICACION', 'Gamificación'

    class EstadoGeneracion(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente de Generación'
        GENERANDO = 'GENERANDO', 'Generando Contenido con IA'
        COMPLETADO = 'COMPLETADO', 'Completado Exitosamente'
        FALLIDO = 'FALLIDO', 'Falló la Generación'

    # --- Campos existentes ---
    titulo = models.CharField(max_length=255, verbose_name="Título de la Unidad o Tema")
    curso = models.ForeignKey('Curso', on_delete=models.CASCADE, related_name='planeaciones')
    docente = models.ForeignKey('Docente', on_delete=models.CASCADE, related_name='planeaciones')
    metodologia = models.CharField(max_length=20, choices=Metodologia.choices, verbose_name="Metodología Principal")
    duracion_clases = models.PositiveIntegerField(default=1, verbose_name="Número de Clases de Duración")
    objetivos_aprendizaje = models.TextField(blank=True, null=True, verbose_name="Objetivos de Aprendizaje")
    recursos_necesarios = models.TextField(blank=True, null=True, verbose_name="Recursos Necesarios")
    criterios_evaluacion = models.TextField(blank=True, null=True, verbose_name="Criterios de Evaluación")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    ultima_actualizacion = models.DateTimeField(auto_now=True)
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, editable=False)

    # ▼▼▼ CAMPOS NUEVOS AÑADIDOS ▼▼▼
    estado_generacion = models.CharField(
        max_length=20,
        choices=EstadoGeneracion.choices,
        default=EstadoGeneracion.PENDIENTE,
        verbose_name="Estado de Generación IA"
    )
    error_generacion = models.TextField(
        blank=True,
        null=True,
        verbose_name="Mensaje de Error (si falló)"
    )
    # ▲▲▲ FIN DE LOS CAMPOS AÑADIDOS ▲▲▲

    def save(self, *args, **kwargs):
        if not self.institucion_id and self.curso:
            self.institucion = self.curso.institucion
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Planeación: {self.titulo} para {self.curso}"

    class Meta:
        verbose_name = "Planeación de Clase"
        verbose_name_plural = "Planeaciones de Clases"
        ordering = ['-fecha_creacion']


class DetalleClase(models.Model):
    """
    Representa una de las clases individuales dentro de una PlaneacionClase.
    """
    planeacion = models.ForeignKey(PlaneacionClase, on_delete=models.CASCADE, related_name='detalles_clase')
    numero_clase = models.PositiveIntegerField(verbose_name="Número de Clase")
    
    # Campos que serán llenados por la IA
    tema_clase = models.CharField(max_length=255, verbose_name="Tema de la Clase")
    actividades_inicio = models.TextField(verbose_name="Actividades de Inicio")
    actividades_desarrollo = models.TextField(verbose_name="Actividades de Desarrollo")
    actividades_cierre = models.TextField(verbose_name="Actividades de Cierre")

    def __str__(self):
        return f"Clase {self.numero_clase}: {self.tema_clase}"

    class Meta:
        verbose_name = "Detalle de Clase"
        verbose_name_plural = "Detalles de Clases"
        ordering = ['numero_clase']
        unique_together = ('planeacion', 'numero_clase')        

       
     
class AnalisisComportamientoIA(models.Model):
    """
    Guarda el resumen y los patrones detectados por la IA al analizar el
    historial completo de un estudiante en el observador.
    """
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='analisis_comportamiento')
    resumen_ia = models.TextField(verbose_name="Análisis y Resumen de la IA")
    patrones_detectados = models.JSONField(null=True, blank=True, verbose_name="Patrones Estructurados")
    fecha_analisis = models.DateTimeField(auto_now_add=True, verbose_name="Fecha del Análisis")
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)

    def __str__(self):
        return f"Análisis para {self.estudiante} - {self.fecha_analisis.strftime('%Y-%m-%d')}"

    class Meta:
        verbose_name = "Análisis de Comportamiento (IA)"
        verbose_name_plural = "Análisis de Comportamiento (IA)"
        ordering = ['-fecha_analisis']     