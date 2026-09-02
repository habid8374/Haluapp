# gestion_academica/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.core.validators import MinValueValidator, MaxValueValidator
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


# ── Choices reutilizables en varios modelos ─────────────────────────────────
TIPO_DOCUMENTO_CHOICES = [
    ('TI', _('Tarjeta de Identidad')),
    ('CC', _('Cédula de Ciudadanía')),
    ('RC', _('Registro Civil')),
    ('PA', _('Pasaporte')),
    ('CE', _('Cédula de Extranjería')),
    # Población migrante (exigidos por el SIMAT / circulares de auditoría)
    ('NES', _('NES — Número establecido por la Secretaría')),
    ('PEP', _('PEP — Permiso Especial de Permanencia')),
    ('VISA', _('Visa')),
    ('TMF', _('TMF — Tarjeta de Movilidad Fronteriza')),
    ('OT', _('Otro')),
]

GRUPO_SANGUINEO_CHOICES = [
    ('A+', _('A+')), ('A-', _('A-')),
    ('B+', _('B+')), ('B-', _('B-')),
    ('AB+', _('AB+')), ('AB-', _('AB-')),
    ('O+', _('O+')), ('O-', _('O-')),
]
# ────────────────────────────────────────────────────────────────────────────

# NO DEBE HABER NINGUNA IMPORTACIÓN DIRECTA DE finanzas.models AQUÍ
# from finanzas.models import InstitucionEducativa # ESTA LÍNEA DEBE HABER SIDO ELIMINADA POR COMPLETO

class Usuario(AbstractUser):
    ROLES = (
        ('administrador', 'Administrador'), # Rol para admin de una institución
        # Podrías tener un 'superadmin' que no necesite institución
        ('coordinador', 'Coordinador(a)'),
        ('rector', 'Rector(a) / Directivo'),
        ('secretaria', 'Secretaría'),
        ('tesoreria', 'Tesorería / Financiera'),
        ('psicologo', 'Psicoorientador(a)'),
        ('docente', 'Docente'),
        ('estudiante', 'Estudiante'),
        ('familiar', 'Familiar'),
    )
    rol = models.CharField(max_length=20, choices=ROLES, default='estudiante', verbose_name=_("Rol de Usuario"))

    IDIOMAS_INTERFAZ = (
        ('es', 'Español'),
        ('en', 'English'),
        ('fr', 'Français'),
        ('de', 'Deutsch'),
    )
    idioma_preferido = models.CharField(
        max_length=5, choices=IDIOMAS_INTERFAZ, default='es',
        verbose_name=_("Idioma de la Plataforma"),
        help_text="En qué idioma ve esta persona la interfaz. Solo aplica en instituciones bilingües.",
    )
    
    # --- CAMBIO: Se quita null=True, blank=True ---
    # Esto fuerza a que cada usuario se asigne a una institución al crearse.
    # Es más seguro para la lógica de tu aplicación.
    institucion_asociada = models.ForeignKey(
        'finanzas.InstitucionEducativa',
        on_delete=models.PROTECT, # Usar PROTECT para evitar borrar una institución si tiene usuarios
        null=True, blank=True, # Mantenemos nulo por ahora para el superadmin, pero sé consciente de esto
        related_name='usuarios', # 'usuarios' es un nombre más corto y común
        verbose_name=_("Institución Asociada")
    )
    google_calendar_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("ID del Calendario de Google Sincronizado")
    )
    foto_perfil = models.ImageField(
        upload_to='fotos_perfil/',
        null=True,
        blank=True,
        verbose_name=_("Foto de Perfil")
    )
    # Preferencias de accesibilidad (Ola 1): tamaño de texto, alto contraste,
    # fuente legible, espaciado, reducir animaciones, lectura fácil. Se guardan
    # como JSON para poder crecer sin migraciones y siguen al usuario entre
    # dispositivos. No son datos sensibles (son ajustes de interfaz).
    preferencias_accesibilidad = models.JSONField(
        default=dict, blank=True,
        verbose_name=_("Preferencias de accesibilidad"),
    )

    # ---- Aceptación de la Política de Tratamiento de Datos Personales ----
    # Se completa exclusivamente desde la vista de aceptación (nunca editable
    # a mano) para que quede como evidencia verificable — ver
    # gestion_academica.legal y proyecto_colegio.middleware.PoliticaDatosMiddleware.
    acepto_tratamiento_datos = models.BooleanField(
        default=False,
        verbose_name=_("Aceptó la Política de Tratamiento de Datos"),
    )
    fecha_aceptacion_tratamiento_datos = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_("Fecha de aceptación"),
    )
    version_politica_aceptada = models.CharField(
        max_length=20, blank=True, default="",
        verbose_name=_("Versión de la política aceptada"),
    )
    hash_politica_aceptada = models.CharField(
        max_length=64, blank=True, default="",
        verbose_name=_("Huella (SHA-256) del texto aceptado"),
        help_text="Identifica de forma única el contenido exacto que el usuario aceptó, para poder demostrarlo aunque la política cambie después.",
    )
    ip_aceptacion_politica = models.GenericIPAddressField(
        null=True, blank=True,
        verbose_name=_("IP registrada al aceptar"),
    )
    user_agent_aceptacion_politica = models.TextField(
        blank=True, default="",
        verbose_name=_("Navegador/dispositivo registrado al aceptar"),
    )


    def get_full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username

    class Meta:
        verbose_name = _("Usuario")
        verbose_name_plural = _("Usuarios")
        permissions = [
            ("acceso_modulo_academico", "Puede acceder al módulo académico"),
            ("puede_realizar_registro_inicial", "Puede realizar el registro inicial del sistema"),
        ]

    # El __str__ estaba fuera de la clase en tu código
    def __str__(self):
        return self.username

class NivelEscolaridad(models.Model):
    nombre = models.CharField(max_length=100, verbose_name=_("Nombre del Nivel"))
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, related_name='niveles_escolares')
    valor_inscripcion_estandar = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name=_("Valor Estándar de Inscripción")
    )
    valor_matricula_estandar = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_pension_estandar = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    orden = models.PositiveIntegerField(
        default=0, 
        help_text="Orden de aparición (ej: 1 para Preescolar, 2 para Primaria)"
    )

    class Meta:
        verbose_name = _("Nivel de Escolaridad")
        verbose_name_plural = _("Niveles de Escolaridad")
        unique_together = ('nombre', 'institucion')
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.institucion.nombre})"        

class Grado(models.Model):
    nombre = models.CharField(max_length=100, verbose_name=_("Nombre del Grado"))
    
    # ✅ Se añade la relación al Nivel de Escolaridad
    nivel_escolaridad = models.ForeignKey(
        'NivelEscolaridad', # Se usa como string para evitar errores de importación
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='grados'
    )
    
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name=_("Institución"))
    
    siguiente_grado = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_("Grado Siguiente (Promoción)")
    )
    orden = models.PositiveIntegerField(
        null=True, blank=True, 
        verbose_name=_("Orden Numérico"),
        help_text="Ej: 1 para Primero, 2 para Segundo, etc."
    )
    
    class TipoEvaluacion(models.TextChoices):
        CUANTITATIVO = 'CUANTITATIVO', _('Cuantitativo (Notas Numéricas)')
        CUALITATIVO = 'CUALITATIVO', _('Cualitativo (Logros y Descriptivo)')

    tipo_evaluacion = models.CharField(
        max_length=20, choices=TipoEvaluacion.choices, default=TipoEvaluacion.CUANTITATIVO,
        verbose_name=_("Tipo de Evaluación Predominante")
    )

    # ID de grado OFICIAL del SIMAT (MEN). Cada institución mapea su grado al
    # código nacional para el reporte de matrícula (grado_id del archivo plano).
    SIMAT_GRADO_CHOICES = [
        ('-3', _('Primera Infancia (-3)')),
        ('-2', _('Pre-Jardín (-2)')),
        ('-1', _('Jardín / Kínder (-1)')),
        ('0', _('Transición / Grado 0')),
        ('1', _('Primero')), ('2', _('Segundo')), ('3', _('Tercero')),
        ('4', _('Cuarto')), ('5', _('Quinto')), ('6', _('Sexto')),
        ('7', _('Séptimo')), ('8', _('Octavo')), ('9', _('Noveno')),
        ('10', _('Décimo')), ('11', _('Once')),
        ('12', _('Doce (Normal Superior)')), ('13', _('Trece (Normal Superior)')),
        ('21', _('CLEI 1 (adultos)')), ('22', _('CLEI 2 (adultos)')),
        ('23', _('CLEI 3 (adultos)')), ('24', _('CLEI 4 (adultos)')),
        ('25', _('CLEI 5 (adultos)')),
    ]
    simat_grado_id = models.CharField(
        _("ID de grado SIMAT (MEN)"), max_length=3, blank=True,
        choices=SIMAT_GRADO_CHOICES,
        help_text=_("Código oficial del grado en el SIMAT, para el reporte de matrícula."),
    )

    class Meta:
        verbose_name = _("Grado")
        verbose_name_plural = _("Grados")
        ordering = ['institucion', 'orden']
        unique_together = ('nombre', 'institucion',)

    def __str__(self):
        return f"{self.nombre} ({self.institucion.nombre})"


class Grupo(models.Model):
    """Grupo/sección de estudiantes dentro de un grado (columna GRUPO del SIMAT).

    Un grado puede dividirse en varias secciones (01, 02, "A", "B"...). El SIMAT
    identifica cada estudiante por sede + jornada + grado + grupo. Para colegios
    que no manejan secciones, existe un único grupo "01" por grado (autocreado).

    Institución-scoped: cada grupo pertenece a un colegio.
    """
    JORNADA_CHOICES = [
        ('MANANA', _("Mañana")),
        ('TARDE', _("Tarde")),
        ('NOCHE', _("Noche")),
        ('UNICA', _("Única")),
        ('COMPLETA', _("Completa")),
        ('FIN_DE_SEMANA', _("Fin de semana")),
    ]
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='grupos', verbose_name=_("Institución"),
    )
    grado = models.ForeignKey(
        'Grado', on_delete=models.CASCADE, related_name='grupos',
        verbose_name=_("Grado"),
    )
    sede = models.ForeignKey(
        'simat.Sede', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='grupos', verbose_name=_("Sede"),
    )
    jornada = models.CharField(
        _("Jornada"), max_length=15, choices=JORNADA_CHOICES, blank=True,
    )
    nombre = models.CharField(
        _("Nombre del grupo"), max_length=20,
        help_text=_("Código o letra de la sección, ej. 01, 02, A, B."),
    )
    activo = models.BooleanField(_("Activo"), default=True)

    class Meta:
        verbose_name = _("Grupo")
        verbose_name_plural = _("Grupos")
        ordering = ['grado__orden', 'nombre']
        constraints = [
            models.UniqueConstraint(
                fields=['institucion', 'grado', 'jornada', 'nombre'],
                name='uniq_grupo_institucion_grado_jornada_nombre',
            ),
        ]

    def __str__(self):
        etiqueta = f"{self.grado.nombre} · {self.nombre}"
        if self.jornada:
            etiqueta += f" ({self.get_jornada_display()})"
        return etiqueta


class PerfilAccesibilidad(models.Model):
    """Perfil de accesibilidad del estudiante (Ola 2 — inclusión operativa).

    Convierte los ajustes razonables del PIAR en una configuración que la
    plataforma APLICA automáticamente para ese estudiante: tamaño de texto,
    alto contraste, fuente legible, espaciado, lectura por voz, tiempo extra en
    evaluaciones, etc. El estudiante no tiene que configurar nada; hereda su
    perfil y puede ajustar por encima con el panel de accesibilidad.

    Acceso restringido (coordinación/orientación) por tratarse de apoyos ligados
    a la condición del estudiante. Institución-scoped.
    """
    FONT_CHOICES = [
        ('normal', _("Normal")),
        ('lg', _("Grande")),
        ('xl', _("Muy grande")),
    ]
    estudiante = models.OneToOneField(
        'Estudiante', on_delete=models.CASCADE, related_name='perfil_accesibilidad',
        verbose_name=_("Estudiante"),
    )
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='perfiles_accesibilidad', verbose_name=_("Institución"),
    )
    activo = models.BooleanField(_("Perfil activo"), default=True)
    font = models.CharField(_("Tamaño de texto"), max_length=10, choices=FONT_CHOICES, default='normal')
    contrast = models.BooleanField(_("Alto contraste"), default=False)
    dyslexia = models.BooleanField(_("Fuente legible"), default=False)
    spacing = models.BooleanField(_("Más espaciado"), default=False)
    reduce_motion = models.BooleanField(_("Reducir animaciones"), default=False)
    easy_read = models.BooleanField(_("Lectura fácil"), default=False)
    tts_default = models.BooleanField(_("Lectura por voz destacada"), default=False)
    tiempo_extra_pct = models.PositiveIntegerField(
        _("Tiempo extra en evaluaciones (%)"), default=0,
        help_text=_("Porcentaje adicional de tiempo en cuestionarios con temporizador (ej. 25, 50)."),
    )
    enunciado_simplificado = models.BooleanField(
        _("Enunciados simplificados"), default=False,
        help_text=_("Prepara la simplificación de enunciados con IA (se aplicará progresivamente)."),
    )
    notas = models.TextField(_("Notas del apoyo"), blank=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Perfil de accesibilidad")
        verbose_name_plural = _("Perfiles de accesibilidad")

    def __str__(self):
        return f"Accesibilidad de {self.estudiante}"

    def como_prefs(self):
        """Ajustes visuales en el formato que entiende el panel de accesibilidad
        (base para el estudiante; sus propios ajustes se aplican por encima)."""
        if not self.activo:
            return {}
        return {
            'font': self.font,
            'contrast': self.contrast,
            'dyslexia': self.dyslexia,
            'spacing': self.spacing,
            'reduce_motion': self.reduce_motion,
            'easy_read': self.easy_read,
        }

    @staticmethod
    def sugerencias_por_condicion(condicion):
        """Sugerencias iniciales de apoyos según la condición del PIAR.
        Es un punto de partida editable, no una imposición."""
        c = (condicion or '').upper()
        base = {
            'font': 'normal', 'contrast': False, 'dyslexia': False, 'spacing': False,
            'reduce_motion': False, 'easy_read': False, 'tts_default': False,
            'tiempo_extra_pct': 0,
        }
        if c == 'VIS':
            base.update(font='xl', contrast=True, tts_default=True, tiempo_extra_pct=25)
        elif c == 'AUD':
            base.update(easy_read=True)
        elif c == 'MOT':
            base.update(spacing=True, reduce_motion=True, tiempo_extra_pct=50)
        elif c in ('COG', 'APR'):
            base.update(dyslexia=True, spacing=True, easy_read=True, tts_default=True, font='lg', tiempo_extra_pct=50)
        elif c == 'CON':
            base.update(easy_read=True, reduce_motion=True, tiempo_extra_pct=25)
        elif c == 'MUL':
            base.update(font='xl', contrast=True, spacing=True, easy_read=True, tts_default=True, tiempo_extra_pct=50)
        return base

class DimensionDesarrollo(models.Model):
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100, verbose_name=_("Nombre de la Dimensión"))
    descripcion = models.TextField(blank=True, null=True)
    orden = models.PositiveIntegerField(default=0, help_text="Orden de aparición en los reportes")

    # --- INICIO DE LA MODIFICACIÓN ---
    # Añadimos una relación ManyToMany para que puedas asignar
    # múltiples materias a esta dimensión.
    materias = models.ManyToManyField(
        'Materia',
        blank=True,
        related_name='dimensiones', # Nombre para la relación inversa
        verbose_name=_("Materias Incluidas en esta Dimensión")
    )
    # --- FIN DE LA MODIFICACIÓN ---

    class Meta:
        verbose_name = _("Dimensión de Desarrollo (Preescolar)")
        verbose_name_plural = _("Dimensiones de Desarrollo (Preescolar)")
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
        verbose_name=_("Dimensión de Desarrollo")
    )
    materia = models.ForeignKey(
        'Materia',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='logros_preescolar',
        verbose_name=_("Materia Asociada (opcional)")
    )
    periodo = models.ForeignKey(
        'PeriodoAcademico', 
        on_delete=models.CASCADE, 
        related_name='logros_preescolar',
        verbose_name=_("Periodo Académico")
    )
    descripcion = models.TextField(verbose_name=_("Descripción del Logro"))
    orden = models.PositiveIntegerField(default=0, help_text="Orden de aparición dentro de la materia.")
    grado = models.ForeignKey('Grado', on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Grado"), related_name='logros_preescolar')
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)

    class Meta:
        verbose_name = _("Logro de Preescolar")
        verbose_name_plural = _("Logros de Preescolar")
        ordering = ['dimension__orden', 'materia__nombre_materia', 'orden']

    def __str__(self):
        materia_str = self.materia.nombre_materia if self.materia_id else "Sin materia"
        return f"{self.descripcion[:50]}... ({materia_str})"


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
        verbose_name = _("Evaluación de Logro (Preescolar)")
        verbose_name_plural = _("Evaluaciones de Logros (Preescolar)")
        # Aseguramos que un estudiante solo pueda tener una evaluación por logro
        unique_together = ('estudiante', 'logro')

    def __str__(self):
        return f"Evaluación de {self.estudiante} para el logro {self.logro_id}"

class EscalaCualitativa(models.Model):
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, related_name='escala_cualitativa')
    nombre_escala = models.CharField(max_length=50, verbose_name=_("Nombre del Desempeño (Ej: Logro Alcanzado)"))
    abreviatura = models.CharField(max_length=10, verbose_name=_("Abreviatura (Ej: LA, LP, LPE)"))
    descripcion = models.TextField(blank=True, null=True, help_text="Descripción de lo que significa este nivel para los padres.")
    orden = models.PositiveIntegerField(default=0, help_text="Orden en que aparecerán las casillas (ej: 1 para LA, 2 para LP, etc.)")
    
    es_reprobatoria = models.BooleanField(
        default=False,
        verbose_name=_("¿Este nivel se considera reprobatorio?"),
        help_text="Marcar solo para el nivel más bajo (ej: 'Bajo', 'Insuficiente')."
    )

    class Meta:
        verbose_name = _("Escala Cualitativa (Preescolar)")
        verbose_name_plural = _("Escalas Cualitativas (Preescolar)")
        ordering = ['institucion', 'orden']
        unique_together = ('institucion', 'nombre_escala')

    def __str__(self):
        return f"{self.nombre_escala} ({self.abreviatura})"                   

class Estudiante(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, primary_key=True, limit_choices_to={'rol': 'estudiante'}, verbose_name=_("Cuenta de Usuario"))
    documento_identidad = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Documento de Identidad"))
    codigo_estudiante = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Código de Estudiante"))
    fecha_nacimiento = models.DateField(null=True, blank=True, verbose_name=_("Fecha de Nacimiento"))
    direccion = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Dirección"))
    grado_actual = models.ForeignKey(Grado, on_delete=models.SET_NULL, null=True, blank=True, related_name='estudiantes_actuales', verbose_name=_("Grado Actual"))
    grupo = models.ForeignKey('Grupo', on_delete=models.SET_NULL, null=True, blank=True, related_name='estudiantes', verbose_name=_("Grupo/Sección"))
    enfasis = models.ForeignKey(
        'Enfasis', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='estudiantes', verbose_name=_("Énfasis / Taller"),
        help_text=_("Solo aplica en instituciones con modalidad técnica (ej. media técnica)."),
    )
    # Acudiente titular para facturación electrónica (el adquiriente de la factura).
    acudiente_responsable = models.ForeignKey(
        'gestion_academica.Familiar', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='estudiantes_responsable', verbose_name=_("Acudiente responsable (facturación)"),
    )
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', 
        on_delete=models.CASCADE, 
        verbose_name=_("Institución"),
        related_name="estudiantes" # Apodo único
    )
    SEXO_CHOICES = [('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro')]
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES, blank=True, null=True, verbose_name=_("Sexo"))
    colegio_procedencia = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Colegio de Procedencia"))
    municipio_ciudad = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Municipio/Ciudad"))
    departamento = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Departamento"))

    # ── Campos del Observador del Estudiante ────────────────────────────────
    tipo_documento = models.CharField(
        max_length=5, choices=TIPO_DOCUMENTO_CHOICES,
        blank=True, null=True, verbose_name=_("Tipo de Documento")
    )
    lugar_nacimiento = models.CharField(
        max_length=150, blank=True, null=True, verbose_name=_("Lugar de Nacimiento")
    )
    grupo_sanguineo = models.CharField(
        max_length=3, choices=GRUPO_SANGUINEO_CHOICES,
        blank=True, null=True, verbose_name=_("Grupo Sanguíneo")
    )
    eps = models.CharField(
        max_length=100, blank=True, null=True, verbose_name=_("EPS / Entidad de Salud")
    )
    discapacidad = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name=_("Discapacidad (si aplica)"),
        help_text="Dejar en blanco si no aplica."
    )
    # ────────────────────────────────────────────────────────────────────────

    valor_matricula = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name=_("Valor Estándar de Matrícula"))
    valor_mensualidad = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name=_("Valor Estándar de Mensualidad"))

    descuentos = models.ManyToManyField(
        'finanzas.Descuento',
        blank=True,
        verbose_name=_("Descuentos o Becas Aplicadas")
    )

    activo = models.BooleanField(
        default=True,
        verbose_name=_("Estudiante Activo"),
        help_text="Desmarca esta casilla si el estudiante se ha retirado o ya no está activo en la institución."
    )

    # ── Bloqueo manual de acceso (ej. por no pago, gestionado por Secretaría) ──
    # El estudiante puede iniciar sesión, pero se le limita el portal (no ve
    # notas, deberes, simulacros…). Independiente del módulo financiero.
    acceso_bloqueado = models.BooleanField(
        default=False,
        verbose_name=_("Acceso bloqueado"),
        help_text="Si está activo, el estudiante ve una pantalla de acceso suspendido en vez del portal.",
    )
    motivo_bloqueo = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name=_("Motivo del bloqueo"),
    )
    fecha_bloqueo = models.DateTimeField(
        null=True, blank=True, verbose_name=_("Fecha de bloqueo"),
    )
    bloqueado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='estudiantes_bloqueados',
        verbose_name=_("Bloqueado por"),
    )

    class Meta:
        verbose_name = _("Estudiante")
        verbose_name_plural = _("Estudiantes")
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
        indexes = [
            # Consulta caliente: estudiantes activos por institución (dashboards,
            # KPIs, listados). Muy frecuente a escala de cientos/miles de alumnos.
            models.Index(fields=['institucion', 'activo'], name='estudiante_inst_activo_idx'),
        ]

    def __str__(self):
        nombre_completo = self.usuario.get_full_name()
        return nombre_completo if nombre_completo else self.usuario.username
    
    qr_identifier = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name=_("Identificador Único para QR"))

    # Sede a la que pertenece el estudiante (Opción A: atributo, no jerarquía).
    # Para colegios de una sola sede se resuelve a la Sede Principal por defecto.
    sede = models.ForeignKey(
        'simat.Sede', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='estudiantes', verbose_name=_("Sede"),
    )

    # ------------------------------------------------------------------
    # Estado financiero (usado por el bloqueo del portal — Fase C)
    # ------------------------------------------------------------------

    @property
    def cuentas_vencidas_qs(self):
        """QuerySet de cuentas vencidas (no pagadas y con vencimiento pasado).

        Tener en cuenta que ``estado`` puede actualizarse al guardar la cuenta
        (ver ``CuentaPorCobrarEstudiante._update_estado_based_on_saldo``), así
        que también filtramos por ``fecha_vencimiento_especifica < hoy`` para
        capturar cuentas que aún no han pasado por save().
        """
        from django.utils import timezone
        from finanzas.models import CuentaPorCobrarEstudiante
        hoy = timezone.localdate()
        return (
            CuentaPorCobrarEstudiante.objects
            .filter(estudiante=self)
            .exclude(estado__in=["PAGADO", "ANULADO"])
            .filter(fecha_vencimiento_especifica__lt=hoy)
        )

    @property
    def dias_de_atraso_max(self):
        """Días de atraso de la cuenta vencida más antigua (0 si no hay)."""
        from django.utils import timezone
        primera = (
            self.cuentas_vencidas_qs
            .order_by("fecha_vencimiento_especifica")
            .values_list("fecha_vencimiento_especifica", flat=True)
            .first()
        )
        if not primera:
            return 0
        return (timezone.localdate() - primera).days

    def esta_al_dia(self) -> bool:
        """Devuelve True si el estudiante NO tiene cuentas vencidas.

        Considera el toggle de la institución ``bloquear_portal_por_mora``:
        si está apagado, **siempre** devuelve True (la institución decidió no
        bloquear por mora, p. ej. en periodo de gracia generalizado).

        Considera ``dias_gracia_mora`` de la institución: una cuenta vencida
        hace N días o menos NO se considera causal de bloqueo.
        """
        institucion = self.institucion
        if institucion is None:
            return True
        if not getattr(institucion, "bloquear_portal_por_mora", True):
            return True

        gracia = int(getattr(institucion, "dias_gracia_mora", 0) or 0)
        if gracia <= 0:
            return not self.cuentas_vencidas_qs.exists()
        return self.dias_de_atraso_max <= gracia


# ── Choices SIMAT/SIMPADE (el VALOR guardado = el código oficial del MEN, para
#    exportar el reporte plano sin tablas de conversión) ──────────────────────
SIMAT_SISBEN_CHOICES = [
    ('1', 'Grupo 1'), ('2', 'Grupo 2'), ('3', 'Grupo 3'),
    ('4', 'Grupo 4'), ('5', 'Grupo 5'), ('6', 'Grupo 6'), ('NO APLICA', 'No aplica'),
]
SIMAT_CARACTER_CHOICES = [('1', 'Académico'), ('2', 'Técnico'), ('0', 'No aplica')]
SIMAT_ESPECIALIDAD_CHOICES = [
    ('05', 'Académico'), ('06', 'Industrial'), ('08', 'Comercial'),
    ('09', 'Pedagógico'), ('10', 'Agropecuario'), ('11', 'Promoción social'),
    ('07', 'Otro'), ('00', 'No aplica'),
]
SIMAT_METODOLOGIA_CHOICES = [
    ('1', 'Educación tradicional'), ('2', 'Escuela nueva'), ('3', 'Post primaria'),
    ('4', 'Telesecundaria'), ('5', 'SER'), ('8', 'Etnoeducación'),
    ('9', 'Aceleración del aprendizaje'), ('10', 'Jóvenes en extraedad y adultos'),
    ('11', 'Preescolar escolarizado'), ('12', 'Preescolar no/semi escolarizado'),
    ('39', 'Secundaria activa'), ('43', 'Escuela nueva activa'), ('51', 'Otra'),
]
SIMAT_SITUACION_VA_CHOICES = [
    ('0', 'No estudió el año anterior'), ('1', 'Aprobó'), ('2', 'Reprobó'),
    ('4', 'Pendiente de logros'), ('6', 'Viene de otra IE'),
    ('7', 'Ingresa por primera vez'), ('8', 'No culminó estudios'),
]
SIMAT_CONDICION_VA_CHOICES = [('3', 'Desertó'), ('5', 'Trasladado a otra IE'), ('9', 'No aplica')]
SIMAT_RECURSO_CHOICES = [
    ('1', 'SGP'), ('2', 'FNR'), ('3', 'Recursos adicionales MEN'),
    ('4', 'Otros recursos de la Nación'), ('5', 'Recursos propios de la SE'),
]
SIMAT_INTERNADO_CHOICES = [('1', 'Internado'), ('2', 'Semi-internado'), ('3', 'Ninguno')]
SIMAT_VALORACION_CHOICES = [('1', 'Superior'), ('2', 'Alto'), ('3', 'Básico'), ('4', 'Bajo')]
SIMAT_SN_CHOICES = [('S', 'Sí'), ('N', 'No')]
SIMAT_SINO_CHOICES = [('SI', 'Sí'), ('NO', 'No')]


class CaracterizacionEstudiante(models.Model):
    """Caracterización socioeconómica y poblacional del estudiante.

    Agrupa los datos exigidos por SIMAT (Anexo 6A) y útiles para SIMPADE y PIAR,
    sin engordar el modelo Estudiante. Todos los campos son opcionales: la
    migración es aditiva y se completa progresivamente. Se crea de forma perezosa
    (get_or_create) cuando se abre el formulario de edición del estudiante.

    NOTA: las etiquetas son legibles para el operador; el mapeo al código exacto
    que espera SIMAT se hará en el generador del archivo de cargue (Fase 3).
    """

    class ZonaResidencia(models.TextChoices):
        URBANA = 'URBANA', _('Urbana')
        RURAL = 'RURAL', _('Rural')

    class RegimenSalud(models.TextChoices):
        CONTRIBUTIVO = 'CONTRIBUTIVO', _('Contributivo')
        SUBSIDIADO = 'SUBSIDIADO', _('Subsidiado')
        ESPECIAL = 'ESPECIAL', _('Especial / Excepción')
        NO_AFILIADO = 'NO_AFILIADO', _('No afiliado / Vinculado')

    class Discapacidad(models.TextChoices):
        NINGUNA = 'NINGUNA', _('Ninguna')
        FISICA = 'FISICA', _('Física (movilidad)')
        INTELECTUAL = 'INTELECTUAL', _('Intelectual / cognitiva')
        PSICOSOCIAL = 'PSICOSOCIAL', _('Psicosocial (mental)')
        VISUAL_BAJA = 'VISUAL_BAJA', _('Visual — baja visión')
        VISUAL_CEGUERA = 'VISUAL_CEGUERA', _('Visual — ceguera')
        AUDITIVA_HIPOACUSIA = 'AUDITIVA_HIPOACUSIA', _('Auditiva — hipoacusia')
        AUDITIVA_SORDA = 'AUDITIVA_SORDA', _('Auditiva — sordera')
        SORDOCEGUERA = 'SORDOCEGUERA', _('Sordoceguera')
        MULTIPLE = 'MULTIPLE', _('Múltiple')
        SISTEMICA = 'SISTEMICA', _('Sistémica')
        VOZ_Y_HABLA = 'VOZ_Y_HABLA', _('De la voz y el habla')
        TEA = 'TEA', _('Trastorno del espectro autista')
        OTRA = 'OTRA', _('Otra')

    class CapacidadExcepcional(models.TextChoices):
        NINGUNA = 'NINGUNA', _('Ninguna')
        GLOBAL = 'GLOBAL', _('Capacidad excepcional global')
        TALENTO_CIENTIFICO = 'TALENTO_CIENTIFICO', _('Talento científico/tecnológico')
        TALENTO_ARTISTICO = 'TALENTO_ARTISTICO', _('Talento artístico')
        TALENTO_DEPORTIVO = 'TALENTO_DEPORTIVO', _('Talento deportivo')
        OTRA = 'OTRA', _('Otra')

    class GrupoEtnico(models.TextChoices):
        NINGUNO = 'NINGUNO', _('Ninguno')
        INDIGENA = 'INDIGENA', _('Indígena')
        AFROCOLOMBIANO = 'AFROCOLOMBIANO', _('Afrocolombiano / negro')
        RAIZAL = 'RAIZAL', _('Raizal (San Andrés)')
        PALENQUERO = 'PALENQUERO', _('Palenquero (San Basilio)')
        ROM = 'ROM', _('ROM (gitano)')

    class Estrato(models.TextChoices):
        E0 = '0', _('Sin estrato')
        E1 = '1', _('Estrato 1')
        E2 = '2', _('Estrato 2')
        E3 = '3', _('Estrato 3')
        E4 = '4', _('Estrato 4')
        E5 = '5', _('Estrato 5')
        E6 = '6', _('Estrato 6')

    class TipoPoblacionVictima(models.TextChoices):
        DESPLAZADO = 'DESPLAZADO', _('Desplazado')
        VICTIMA_MINAS = 'VICTIMA_MINAS', _('Víctima de minas antipersona')
        DESVINCULADO = 'DESVINCULADO', _('Desvinculado de grupos armados')
        HIJO_DESMOVILIZADO = 'HIJO_DESMOVILIZADO', _('Hijo de adulto desmovilizado')
        OTRA = 'OTRA', _('Otra')

    estudiante = models.OneToOneField(
        Estudiante, on_delete=models.CASCADE, primary_key=True,
        related_name='caracterizacion', verbose_name=_("Estudiante"),
    )
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        verbose_name=_("Institución"), related_name='caracterizaciones_estudiante',
    )

    # ── Identidad / ubicación ──────────────────────────────────────────────
    pais_origen = models.CharField(
        max_length=100, blank=True, null=True, verbose_name=_("País de origen"),
        help_text="Para estudiantes migrantes (ej: Venezuela). Dejar en blanco si es Colombia.",
    )
    zona_residencia = models.CharField(
        max_length=10, choices=ZonaResidencia.choices, blank=True, null=True,
        verbose_name=_("Zona de residencia"),
    )
    municipio_divipola = models.CharField(
        max_length=8, blank=True, null=True, verbose_name=_("Código DIVIPOLA municipio"),
        help_text="Código DANE del municipio de residencia (se completará con la tabla DIVIPOLA).",
    )
    departamento_divipola = models.CharField(
        max_length=5, blank=True, null=True, verbose_name=_("Código DIVIPOLA departamento"),
    )

    # ── Salud ──────────────────────────────────────────────────────────────
    regimen_salud = models.CharField(
        max_length=15, choices=RegimenSalud.choices, blank=True, null=True,
        verbose_name=_("Régimen de salud"),
    )
    discapacidad_categoria = models.CharField(
        max_length=25, choices=Discapacidad.choices, blank=True, null=True,
        verbose_name=_("Categoría de discapacidad (MEN)"),
    )
    capacidad_excepcional = models.CharField(
        max_length=25, choices=CapacidadExcepcional.choices, blank=True, null=True,
        verbose_name=_("Capacidad / talento excepcional"),
    )

    # ── Socioeconómico ─────────────────────────────────────────────────────
    grupo_etnico = models.CharField(
        max_length=20, choices=GrupoEtnico.choices, blank=True, null=True,
        verbose_name=_("Grupo étnico"),
    )
    estrato = models.CharField(
        max_length=1, choices=Estrato.choices, blank=True, null=True,
        verbose_name=_("Estrato socioeconómico"),
    )
    sisben_grupo = models.CharField(
        max_length=10, blank=True, null=True, verbose_name=_("Grupo SISBÉN"),
        help_text="Clasificación SISBÉN IV (ej: A1, B2, C3).",
    )
    sisben_puntaje = models.DecimalField(
        max_digits=6, decimal_places=2, blank=True, null=True,
        verbose_name=_("Puntaje SISBÉN"),
    )

    # ── Condiciones especiales ─────────────────────────────────────────────
    victima_conflicto = models.BooleanField(
        default=False, verbose_name=_("¿Víctima del conflicto armado?"),
    )
    tipo_poblacion_victima = models.CharField(
        max_length=20, choices=TipoPoblacionVictima.choices, blank=True, null=True,
        verbose_name=_("Tipo de población víctima"),
    )
    srpa = models.BooleanField(
        default=False,
        verbose_name=_("¿Sistema de Responsabilidad Penal Adolescente (SRPA)?"),
    )
    apoyo_academico_especial = models.BooleanField(
        default=False, verbose_name=_("¿Requiere apoyo académico especial?"),
    )

    # ════════════════════════════════════════════════════════════════════════
    #  SIMAT (espejo del Aspirante) — captura de matrícula para el MEN.
    #  Aditivo y opcional. Las FK apuntan a los catálogos (app simat) → el
    #  usuario SELECCIONA, no escribe.
    # ════════════════════════════════════════════════════════════════════════
    SIMAT_JORNADA_CHOICES = [
        ('MANANA', 'Mañana'), ('TARDE', 'Tarde'), ('NOCHE', 'Noche'),
        ('UNICA', 'Única'), ('COMPLETA', 'Completa'), ('FIN_DE_SEMANA', 'Fin de semana'),
    ]
    primer_nombre = models.CharField(max_length=60, blank=True, verbose_name=_("Primer nombre"))
    segundo_nombre = models.CharField(max_length=60, blank=True, verbose_name=_("Segundo nombre"))
    primer_apellido = models.CharField(max_length=60, blank=True, verbose_name=_("Primer apellido"))
    segundo_apellido = models.CharField(max_length=60, blank=True, verbose_name=_("Segundo apellido"))
    lugar_expedicion_departamento = models.ForeignKey('simat.Departamento', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name=_("Expedición documento · Departamento"))
    lugar_expedicion_municipio = models.ForeignKey('simat.Municipio', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name=_("Expedición documento · Municipio"))
    nacionalidad = models.CharField(max_length=60, blank=True, verbose_name=_("Nacionalidad"))
    pais_nacimiento = models.CharField(max_length=60, blank=True, verbose_name=_("País de nacimiento"))
    departamento_nacimiento = models.ForeignKey('simat.Departamento', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name=_("Nacimiento · Departamento"))
    municipio_nacimiento = models.ForeignKey('simat.Municipio', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name=_("Nacimiento · Municipio"))
    departamento_residencia = models.ForeignKey('simat.Departamento', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name=_("Residencia · Departamento"))
    municipio_residencia = models.ForeignKey('simat.Municipio', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name=_("Residencia · Municipio"))
    barrio = models.CharField(max_length=150, blank=True, verbose_name=_("Barrio"))
    campesino = models.BooleanField(default=False, verbose_name=_("¿Población campesina?"))
    etnia_simat = models.ForeignKey('simat.Etnia', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name=_("Etnia (código SIMAT)"))
    resguardo = models.ForeignKey('simat.Resguardo', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name=_("Resguardo indígena"))
    eps_simat = models.ForeignKey('simat.EPS', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name=_("EPS (código SIMAT)"))
    sede = models.ForeignKey('simat.Sede', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name=_("Sede"))
    jornada = models.CharField(max_length=15, choices=SIMAT_JORNADA_CHOICES, blank=True, verbose_name=_("Jornada"))
    grupo = models.CharField(max_length=20, blank=True, verbose_name=_("Grupo/Curso"))
    modelo_educativo = models.CharField(max_length=60, blank=True, verbose_name=_("Modelo/Metodología educativa"))
    fuente_recursos = models.CharField(max_length=60, blank=True, verbose_name=_("Fuente de recursos"))
    internado = models.CharField(max_length=20, blank=True, verbose_name=_("Internado"))
    matricula_contratada = models.BooleanField(default=False, verbose_name=_("¿Matrícula contratada?"))
    repitente = models.BooleanField(default=False, verbose_name=_("¿Repitente?"))
    situacion_academica_anterior = models.CharField(max_length=60, blank=True, verbose_name=_("Situación académica año anterior"))
    simat_per_id = models.CharField(max_length=20, blank=True, verbose_name=_("SIMAT · PER_ID"))
    simat_nui = models.CharField(max_length=30, blank=True, verbose_name=_("SIMAT · NUI"))

    # ── SIMAT/SIMPADE — campos codificados adicionales (reporte plano) ──
    sisben_simat = models.CharField(_("SISBÉN (grupo SIMAT)"), max_length=10, blank=True, choices=SIMAT_SISBEN_CHOICES)
    caracter = models.CharField(_("Carácter"), max_length=2, blank=True, choices=SIMAT_CARACTER_CHOICES)
    especialidad = models.CharField(_("Especialidad (media)"), max_length=2, blank=True, choices=SIMAT_ESPECIALIDAD_CHOICES)
    metodologia = models.CharField(_("Metodología/Modelo educativo"), max_length=2, blank=True, choices=SIMAT_METODOLOGIA_CHOICES)
    situacion_va = models.CharField(_("Situación académica año anterior"), max_length=1, blank=True, choices=SIMAT_SITUACION_VA_CHOICES)
    condicion_va = models.CharField(_("Condición del alumno año anterior"), max_length=1, blank=True, choices=SIMAT_CONDICION_VA_CHOICES)
    fuente_recurso = models.CharField(_("Fuente de recursos"), max_length=1, blank=True, choices=SIMAT_RECURSO_CHOICES)
    tipo_internado = models.CharField(_("Internado"), max_length=1, blank=True, choices=SIMAT_INTERNADO_CHOICES)
    valoracion_p1 = models.CharField(_("Valoración período 1"), max_length=1, blank=True, choices=SIMAT_VALORACION_CHOICES)
    valoracion_p2 = models.CharField(_("Valoración período 2"), max_length=1, blank=True, choices=SIMAT_VALORACION_CHOICES)
    subsidiado = models.CharField(_("¿Subsidiado?"), max_length=2, blank=True, choices=SIMAT_SINO_CHOICES)
    es_nuevo = models.CharField(_("¿Nuevo en la institución?"), max_length=2, blank=True, choices=SIMAT_SINO_CHOICES)
    proviene_sector_privado = models.CharField(_("¿Proviene del sector privado?"), max_length=2, blank=True, choices=SIMAT_SINO_CHOICES)
    proviene_otro_municipio = models.CharField(_("¿Proviene de otro municipio?"), max_length=2, blank=True, choices=SIMAT_SINO_CHOICES)
    madre_cabeza_familia = models.CharField(_("¿Madre cabeza de familia?"), max_length=1, blank=True, choices=SIMAT_SN_CHOICES)
    hijo_madre_cabeza_familia = models.CharField(_("¿Hijo de madre cabeza de familia?"), max_length=1, blank=True, choices=SIMAT_SN_CHOICES)
    beneficiario_veterano = models.CharField(_("¿Beneficiario veterano fuerza pública?"), max_length=1, blank=True, choices=SIMAT_SN_CHOICES)
    beneficiario_heroe = models.CharField(_("¿Beneficiario héroe de la nación?"), max_length=1, blank=True, choices=SIMAT_SN_CHOICES)
    numero_convenio = models.CharField(_("Número de convenio"), max_length=30, blank=True)
    institucion_bienestar = models.CharField(_("Institución de bienestar (ICBF)"), max_length=120, blank=True)
    expulsor_departamento = models.ForeignKey('simat.Departamento', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name=_("Depto. expulsor (víctima)"))
    expulsor_municipio = models.ForeignKey('simat.Municipio', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name=_("Municipio expulsor (víctima)"))

    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Caracterización de estudiante")
        verbose_name_plural = _("Caracterizaciones de estudiantes")

    def __str__(self):
        return f"Caracterización de {self.estudiante}"

    def aplicar_nombres_desde(self, usuario):
        """Deriva primer/segundo nombre y apellido del nombre del usuario, para
        no duplicar la captura (el nombre se ingresa una sola vez en el usuario).
        SIMAT los exige separados; aquí se calculan automáticamente."""
        pn = ((usuario.first_name if usuario else '') or '').split()
        self.primer_nombre = (pn[0] if pn else '')[:60]
        self.segundo_nombre = (' '.join(pn[1:]))[:60]
        pa = ((usuario.last_name if usuario else '') or '').split()
        self.primer_apellido = (pa[0] if pa else '')[:60]
        self.segundo_apellido = (' '.join(pa[1:]))[:60]


class Docente(models.Model):
    class ModalidadLiquidacion(models.TextChoices):
        POR_HORA = 'POR_HORA', _('Por horas laboradas')
        SALARIO_FIJO = 'SALARIO_FIJO', _('Salario fijo (planta / directivo)')

    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, primary_key=True, limit_choices_to={'rol': 'docente'}, verbose_name=_("Cuenta de Usuario"))
    documento_identidad = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Documento de Identidad"))
    codigo_docente = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Código de Docente"))
    especialidad = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Especialidad Principal"))
    fecha_nacimiento = models.DateField(null=True, blank=True, verbose_name=_("Fecha de Nacimiento"))
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name=_("Institución"))
    firma_docente = models.ImageField(upload_to='firmas/', blank=True, null=True, verbose_name=_("Firma del Docente (Imagen)")) 
    qr_identifier = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    dashboard_layout = models.JSONField(null=True, blank=True, verbose_name=_("Diseño del Dashboard"))
    modalidad_liquidacion = models.CharField(
        max_length=20,
        choices=ModalidadLiquidacion.choices,
        default=ModalidadLiquidacion.SALARIO_FIJO,
        verbose_name=_("Modalidad de liquidación"),
        help_text="Por horas: útil para liquidar con marcas entrada/salida. Salario fijo: control de asistencia sin cálculo automático de horas pagadas.",
    )
    valor_hora_docencia = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Valor hora (referencia)"),
        help_text="Opcional. Referencia para docentes por hora; no reemplaza la nómina legal.",
    )

    class Meta:
        verbose_name = _("Docente")
        verbose_name_plural = _("Docentes")
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
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, primary_key=True, limit_choices_to={'rol': 'familiar'}, verbose_name=_("Cuenta de Usuario (Login)"))
    parentesco = models.CharField(max_length=50, verbose_name=_("Parentesco con el Estudiante"))
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Teléfono de Contacto"))
    documento_identidad = models.CharField(
        max_length=20, blank=True, null=True, verbose_name=_("Número de Documento")
    )
    tipo_documento = models.CharField(
        max_length=5, choices=TIPO_DOCUMENTO_CHOICES,
        blank=True, null=True, verbose_name=_("Tipo de Documento")
    )
    ocupacion = models.CharField(
        max_length=150, blank=True, null=True, verbose_name=_("Ocupación")
    )
    lugar_trabajo = models.CharField(
        max_length=200, blank=True, null=True, verbose_name=_("Lugar de Trabajo / Empresa")
    )
    direccion = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_("Dirección de Residencia")
    )
    estudiantes_asociados = models.ManyToManyField(Estudiante, related_name='familiares', verbose_name=_("Estudiante(s) Asociado(s)"))
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name=_("Institución"))

    class Meta:
        verbose_name = _("Familiar")
        verbose_name_plural = _("Familiares")
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
    nombre = models.CharField(max_length=100, verbose_name=_("Nombre del Área"))
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)
    orden = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Orden de aparición"),
        help_text="Define el orden en que se muestran las áreas en pantallas y reportes (menor = primero)."
    )

    materias = models.ManyToManyField(
        'Materia',
        blank=True, # Un área puede no tener materias asignadas todavía
        verbose_name=_("Materias Pertenecientes")
    )

    class Meta:
        verbose_name = _("Área Académica")
        verbose_name_plural = _("Áreas Académicas")
        unique_together = ('nombre', 'institucion',)
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre


class Enfasis(models.Model):
    """Énfasis / taller técnico (modalidad de colegio técnico-industrial,
    ej. Electricidad, Ebanistería, Mecánica). Catálogo propio de cada
    institución — un colegio sin modalidad técnica simplemente no tiene
    registros aquí y nunca ve esta funcionalidad."""
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='enfasis_tecnicos', verbose_name=_("Institución"),
    )
    nombre = models.CharField(max_length=100, verbose_name=_("Énfasis / Taller"))
    activo = models.BooleanField(default=True, verbose_name=_("Activo"))

    class Meta:
        verbose_name = _("Énfasis / Taller")
        verbose_name_plural = _("Énfasis / Talleres")
        unique_together = ('institucion', 'nombre')
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Materia(models.Model):
    IDIOMA_INSTRUCCION_CHOICES = [
        ('es', _('Español')),
        ('en', _('Inglés')),
        ('fr', _('Francés')),
        ('pt', _('Portugués')),
        ('de', _('Alemán')),
        ('zh', _('Mandarín')),
    ]

    nombre_materia = models.CharField(max_length=100, verbose_name=_("Nombre de la Materia"))
    nombre_idioma_secundario = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name=_("Nombre en Idioma Secundario"),
        help_text="Ej: 'Mathematics', 'Natural Sciences'. Solo visible en colegios bilingües.",
    )
    # --- CAMBIO 1: Se quita unique=True de aquí ---
    codigo_materia = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Código de Materia"))

    descripcion = models.TextField(blank=True, null=True, verbose_name=_("Descripción"))

    # --- CAMBIO 2: Se quita null=True, blank=True ---
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name=_("Institución"))

    # Nivel de escolaridad al que pertenece esta materia (Preescolar/Primaria/
    # Secundaria/Media). Permite que exista "Matemáticas" de Primaria y otra de
    # Secundaria como materias distintas (distinto nivel de complejidad).
    # Nullable (como Grado.nivel_escolaridad) por compatibilidad con datos
    # previos; el formulario sí lo exige al crear materias nuevas.
    nivel_escolaridad = models.ForeignKey(
        'NivelEscolaridad',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='materias',
        verbose_name=_("Nivel de Escolaridad"),
    )

    intensidad_horaria_semanal = models.PositiveIntegerField(default=0, verbose_name=_("Intensidad Horaria Semanal (Ihs)"))
    idioma_instruccion = models.CharField(
        max_length=5,
        choices=IDIOMA_INSTRUCCION_CHOICES,
        default='es',
        verbose_name=_("Idioma de Instrucción"),
        help_text="Idioma en que se dicta esta materia.",
    )

    class Meta:
        verbose_name = _("Materia")
        verbose_name_plural = _("Materias")
        ordering = ['nombre_materia']
        # La unicidad del NOMBRE ahora incluye el nivel: puede haber
        # "Matemáticas" en Primaria y otra en Secundaria. El código sigue
        # siendo único por institución.
        unique_together = [
            ('nombre_materia', 'nivel_escolaridad', 'institucion'),
            ('codigo_materia', 'institucion'),
        ]

    def __str__(self):
        # Se muestra el nivel para distinguir materias del mismo nombre en
        # niveles distintos (ej. "Matemáticas (Primaria)").
        if self.nivel_escolaridad_id:
            return f"{self.nombre_materia} ({self.nivel_escolaridad.nombre})"
        return self.nombre_materia
    
class DescriptorLogro(models.Model):
    descripcion = models.TextField(verbose_name=_("Descripción del Logro/Descriptor"))
    materia = models.ForeignKey('Materia', on_delete=models.CASCADE, related_name='descriptores')
    periodo_academico = models.ForeignKey('PeriodoAcademico', on_delete=models.CASCADE, related_name='descriptores')
    
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Creado por")
    )

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', 
        on_delete=models.CASCADE,
        editable=False,
        verbose_name=_("Institución")
    )

    dimension = models.ForeignKey(
        DimensionDesarrollo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logros'
    )

    grado = models.ForeignKey(
        'Grado',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Grado"),
        related_name='descriptores_logro'
    )

    class Meta:
        verbose_name = _("Descriptor de Logro")
        verbose_name_plural = _("Descriptores de Logros")

    def __str__(self):
        return f"{self.materia.nombre_materia} - {self.descripcion[:50]}..."

    def save(self, *args, **kwargs):
        # Esta lógica asegura que la institución se asigne automáticamente desde la materia
        if not self.institucion_id and self.materia:
            self.institucion = self.materia.institucion
        super().save(*args, **kwargs)

class PeriodoAcademico(models.Model):
    nombre = models.CharField(max_length=100, verbose_name=_("Nombre del Periodo"))
    fecha_inicio = models.DateField(verbose_name=_("Fecha de Inicio"))
    fecha_fin = models.DateField(verbose_name=_("Fecha de Fin"))
    año_escolar = models.PositiveIntegerField(verbose_name=_("Año Escolar"), default=datetime.date.today().year)
    activo = models.BooleanField(default=False, verbose_name=_("¿Es el periodo activo actual?"))
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name=_("Institución"))
    notas_cerradas = models.BooleanField(default=False, verbose_name=_("Notas cerradas"))
    fecha_cierre_notas = models.DateTimeField(null=True, blank=True, verbose_name=_("Fecha de cierre de notas"))
    boletines_publicados = models.BooleanField(
        default=False,
        verbose_name=_("Boletines publicados"),
        help_text="Controla si estudiantes y acudientes ya pueden ver/descargar el boletín de este periodo. Independiente del cierre de notas.",
    )
    fecha_publicacion_boletines = models.DateTimeField(null=True, blank=True, verbose_name=_("Fecha de publicación de boletines"))

    class Meta:
        verbose_name = _("Periodo Académico")
        verbose_name_plural = _("Periodos Académicos")
        ordering = ['-año_escolar', '-fecha_inicio']
        unique_together = ('nombre', 'año_escolar', 'institucion',)

    def __str__(self):
        return f"{self.nombre} ({self.año_escolar})"

class Curso(models.Model):
    materia = models.ForeignKey(Materia, on_delete=models.PROTECT, related_name="cursos", verbose_name=_("Materia"))
    grado = models.ForeignKey(Grado, on_delete=models.PROTECT, related_name="cursos", verbose_name=_("Grado"))
    periodo_academico = models.ForeignKey(PeriodoAcademico, on_delete=models.CASCADE, related_name="cursos", verbose_name=_("Periodo Académico"))
    docentes_asignados = models.ManyToManyField(
        'Docente',
        related_name="cursos_impartidos",
        blank=True,
        verbose_name=_("Docentes Asignados")
    )
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name=_("Institución"))
    aula = models.ForeignKey('gestion_academica.Aula', null=True, blank=True, on_delete=models.SET_NULL)
    enfasis = models.ForeignKey(
        'Enfasis', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cursos', verbose_name=_("Énfasis / Taller"),
        help_text=_("Vacío = aplica a todo el grado (comportamiento normal). "
                     "Con un énfasis = solo ven y califican este curso los "
                     "estudiantes con ese mismo énfasis (talleres técnicos)."),
    )

    class Meta:
        verbose_name = _("Curso")
        verbose_name_plural = _("Cursos")
        unique_together = ('materia', 'grado', 'periodo_academico', 'institucion',) 
        ordering = ['periodo_academico', 'grado', 'materia']

    def __str__(self):
        return f"{self.materia.nombre_materia} - {self.grado.nombre} ({self.periodo_academico.nombre})"

class DirectorCurso(models.Model):
    docente = models.ForeignKey(Docente, on_delete=models.CASCADE, related_name="direcciones_grado", verbose_name=_("Docente Director"))
    grado = models.ForeignKey(Grado, on_delete=models.CASCADE, related_name="directores_grado", verbose_name=_("Grado Dirigido"))
    periodo_academico = models.ForeignKey(PeriodoAcademico, on_delete=models.CASCADE, related_name="directores_grado_periodo", verbose_name=_("Periodo Académico"))
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name=_("Institución"))

    class Meta:
        verbose_name = _("Director de Curso")
        verbose_name_plural = _("Directores de Curso")
        unique_together = ('grado', 'periodo_academico', 'institucion',) 
        ordering = ['periodo_academico', 'grado']

    def __str__(self):
        nombre_docente = self.docente.usuario.get_full_name() or self.docente.usuario.username
        return f"Dir. {nombre_docente} - {self.grado.nombre} ({self.periodo_academico.nombre})"

class TipoActividad(models.Model):
    nombre = models.CharField(max_length=100, verbose_name=_("Nombre del Tipo de Actividad"))
    descripcion = models.TextField(blank=True, null=True, verbose_name=_("Descripción (Opcional)"))
    
    # --- CAMBIO: Se quita null=True, blank=True ---
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name=_("Institución"))

    # ▼▼▼ AÑADE ESTE CAMPO ▼▼▼
    porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Porcentaje de la Categoría (%)"),
        help_text="El peso que esta categoría tiene en la nota final del periodo. Ej: 30.00 para 30%"
    )

    orden = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Orden de Aparición"),
        help_text="Un número más bajo aparecerá primero (ej: 1 para Exámenes, 2 para Tareas)."
    )
    # ▲▲▲ FIN DEL CAMPO AÑADIDO ▲▲▲ 

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Creado por")
    )
    # ▲▲▲ FIN DEL CAMPO AÑADIDO ▲▲

    class Meta:
        verbose_name = _("Tipo de Actividad")
        verbose_name_plural = _("Tipos de Actividad")
        ordering = ['nombre']
        unique_together = ('nombre', 'institucion',)

    def __str__(self):
        return self.nombre

class ActividadCalificable(models.Model):
    curso = models.ForeignKey('Curso', on_delete=models.CASCADE, related_name='actividades_calificables', verbose_name=_("Curso"))
    tipo_actividad = models.ForeignKey('TipoActividad', on_delete=models.PROTECT, verbose_name=_("Tipo de Actividad"))
    titulo = models.CharField(max_length=200, verbose_name=_("Título de la Actividad"))
    descripcion = models.TextField(blank=True, null=True, verbose_name=_("Descripción Detallada"))
    material_adjunto = models.FileField(
        upload_to='actividades_materiales/',
        blank=True,
        null=True,
        verbose_name=_("Material Adjunto (Opcional)")
    )
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name=_("Institución"))

    # --- INICIO: CAMPOS DE CONFIGURACIÓN (AQUÍ ES DONDE DEBEN ESTAR) ---
    fecha_publicacion = models.DateField(verbose_name=_("Fecha de Publicación/Asignación"), default=datetime.date.today)
    fecha_entrega_limite = models.DateField(null=True, blank=True, verbose_name=_("Fecha Límite de Entrega (Opcional)"))
    
    duracion_minutos = models.PositiveIntegerField(
        null=True, blank=True, 
        verbose_name=_("Duración en Minutos"),
        help_text="Dejar en blanco si no hay límite de tiempo."
    )
    numero_intentos_permitidos = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
        verbose_name=_("Número de Intentos Permitidos"),
        help_text=(
            "Veces que el estudiante puede iniciar la actividad (cada sesión cuenta). "
            "Por defecto 5, adecuado para etapa escolar; máximo 20 para evaluaciones especiales."
        ),
    )
    # --- FIN DE CAMPOS DE CONFIGURACIÓN ---

    class Meta:
        verbose_name = _("Actividad Calificable")
        verbose_name_plural = _("Actividades Calificables")
        ordering = ['curso', '-fecha_publicacion', 'titulo']

    def __str__(self):
        return f"{self.titulo} ({self.curso})"

class Calificacion(models.Model):
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='calificaciones', verbose_name=_("Estudiante"))
    actividad_calificable = models.ForeignKey(ActividadCalificable, on_delete=models.CASCADE, related_name='calificaciones_recibidas', verbose_name=_("Actividad Calificable"))
    valor_numerico = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=_("Valor Numérico"))
    valor_cualitativo = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("Valor Cualitativo"))
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name=_("Fecha de Registro"))
    registrada_por = models.ForeignKey(Docente, on_delete=models.SET_NULL, null=True, blank=True, related_name='calificaciones_registradas', verbose_name=_("Registrada por"))
    observaciones = models.TextField(blank=True, null=True, verbose_name=_("Observaciones"))
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name=_("Institución"))

    class Meta:
        unique_together = ('estudiante', 'actividad_calificable', 'institucion',) 
        verbose_name = _("Calificación")
        verbose_name_plural = _("Calificaciones")
        ordering = ['actividad_calificable__curso', 'estudiante__usuario__last_name', 'actividad_calificable__fecha_publicacion']
        permissions = [
            ("ver_mis_calificaciones", "Puede ver sus propias calificaciones"), 
            ("puede_calificar_estudiantes", "Puede calificar estudiantes en actividades"), 
        ]

    def __str__(self):
        valor = self.valor_numerico if self.valor_numerico is not None else self.valor_cualitativo
        return f"Cal: {self.estudiante.usuario.username} en {self.actividad_calificable.titulo}: {valor or 'Pendiente'}"

class PlanCurricular(models.Model):
    nombre = models.CharField(max_length=255, verbose_name=_("Nombre del Plan Curricular"))
    descripcion = models.TextField(blank=True, null=True, verbose_name=_("Descripción Detallada (Opcional)"))
    documento_adjunto = models.FileField(upload_to='planes_curriculares/', blank=True, null=True, verbose_name=_("Documento Adjunto del Plan (PDF, Word, etc.)"))
    grado_asociado = models.ForeignKey(Grado, on_delete=models.SET_NULL, null=True, blank=True, related_name='planes_curriculares_grado', verbose_name=_("Grado Asociado (Opcional)"))
    materia_asociada = models.ForeignKey(Materia, on_delete=models.SET_NULL, null=True, blank=True, related_name='planes_curriculares_materia', verbose_name=_("Materia Asociada (Opcional)"))
    periodo_academico_asociado = models.ForeignKey(PeriodoAcademico, on_delete=models.SET_NULL, null=True, blank=True, related_name='planes_curriculares_periodo', verbose_name=_("Periodo Académico Asociado (Opcional)"))
    fecha_publicacion = models.DateField(verbose_name=_("Fecha de Publicación/Vigencia"), default=datetime.date.today)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='planes_curriculares_creados', verbose_name=_("Creado por"))
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name=_("Institución"))

    class Meta:
        verbose_name = _("Plan Curricular")
        verbose_name_plural = _("Planes Curriculares")
        ordering = ['-fecha_publicacion', 'nombre']
        unique_together = ('nombre', 'institucion',) 

    def __str__(self):
        return self.nombre

class Deber(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='deberes', verbose_name=_("Curso al que pertenece el deber"))
    titulo = models.CharField(max_length=255, verbose_name=_("Título del Deber"))
    descripcion = models.TextField(blank=True, null=True, verbose_name=_("Descripción / Instrucciones"))
    # Accesibilidad (lectura fácil): versión simplificada con IA de la descripción.
    # Se calcula una vez y se cachea para reutilizarla con todos los estudiantes.
    descripcion_simple = models.TextField(
        blank=True, default='',
        verbose_name=_("Descripción en lectura fácil (IA)"),
        help_text=_("Versión simplificada de las instrucciones, generada con IA para apoyo a la lectura."),
    )
    fecha_asignacion = models.DateField(verbose_name=_("Fecha de Asignación"), default=datetime.date.today)
    fecha_entrega = models.DateField(verbose_name=_("Fecha Límite de Entrega"))
    material_adjunto = models.FileField(upload_to='deberes_materiales/', blank=True, null=True, verbose_name=_("Material de Apoyo Adjunto (Opcional)"))
    # Accesibilidad auditiva: el docente puede adjuntar una explicación en audio.
    # La transcripción (subtítulo) se genera con IA y se cachea para reutilizarla
    # con todos los estudiantes (apoyo para sordos y para lectura acompañada).
    audio = models.FileField(
        upload_to='deberes_audio/%Y/%m/', blank=True, null=True,
        verbose_name=_("Audio de apoyo (explicación hablada, opcional)"),
        help_text=_("Explicación en voz para el deber. Se puede transcribir con IA como subtítulo."),
    )
    audio_transcripcion = models.TextField(
        blank=True, default='',
        verbose_name=_("Transcripción del audio (IA)"),
        help_text=_("Subtítulo del audio para estudiantes sordos o con dificultad auditiva."),
    )
    # Categoría de evaluación (Saber Ser, Saber Hacer, …). Determina el
    # porcentaje con el que la nota del deber pondera en el boletín. Nullable
    # por compatibilidad con deberes antiguos; el formulario lo exige.
    tipo_actividad = models.ForeignKey(
        'TipoActividad', on_delete=models.PROTECT, null=True, blank=True,
        related_name='deberes', verbose_name=_("Categoría de la actividad"),
    )
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name=_("Institución"))

    class Meta:
        verbose_name = _("Deber / Tarea")
        verbose_name_plural = _("Deberes / Tareas")
        ordering = ['curso', '-fecha_entrega', 'titulo']
        unique_together = ('curso', 'titulo', 'institucion',) 

    def __str__(self):
        return f"{self.titulo} ({self.curso})"

class EntregaDeber(models.Model):
    deber = models.ForeignKey(Deber, on_delete=models.CASCADE, related_name='entregas', verbose_name=_("Deber"))
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='entregas_deberes', verbose_name=_("Estudiante"))
    fecha_entrega_real = models.DateTimeField(auto_now_add=True, verbose_name=_("Fecha de Entrega Real"))
    archivo_adjunto_estudiante = models.FileField(upload_to='entregas_deberes_estudiantes/', blank=True, null=True, verbose_name=_("Archivo Adjunto del Estudiante"))
    comentarios_estudiante = models.TextField(blank=True, null=True, verbose_name=_("Comentarios del Estudiante (Opcional)"))
    calificacion_obtenida = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Calificación Obtenida"))
    comentarios_docente = models.TextField(blank=True, null=True, verbose_name=_("Comentarios del Docente"))
    fecha_calificacion = models.DateTimeField(null=True, blank=True, verbose_name=_("Fecha de Calificación"))
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name=_("Institución"))
    porcentaje_similitud = models.PositiveIntegerField(
        null=True, blank=True, 
        verbose_name=_("Porcentaje de Similitud (%)")
    )
    alerta_plagio = models.BooleanField(
        default=False, 
        verbose_name=_("Alerta de Posible Plagio")
    )

    class Meta:
        unique_together = ('deber', 'estudiante', 'institucion',) 
        verbose_name = _("Entrega de Deber")
        verbose_name_plural = _("Entregas de Deberes")
        ordering = ['deber', 'estudiante']
        permissions = [
            ("puede_realizar_entrega_deber", "Puede realizar entregas de deberes"), 
        ]

    def __str__(self):
        return f"Entrega de '{self.deber.titulo}' por {self.estudiante.usuario.username}"

class MencionReconocimiento(models.Model):
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='menciones_reconocimientos', verbose_name=_("Estudiante"))
    curso = models.ForeignKey(Curso, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Curso (Opcional)"))
    periodo = models.ForeignKey(PeriodoAcademico, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Periodo Académico (Opcional)"))
    tipo = models.CharField(max_length=150, verbose_name=_("Tipo de Mención/Reconocimiento"))
    descripcion = models.TextField(verbose_name=_("Descripción Detallada del Reconocimiento"))
    fecha_otorgamiento = models.DateField(verbose_name=_("Fecha de Otorgamiento"), default=datetime.date.today)
    otorgado_por = models.ForeignKey(Docente, on_delete=models.SET_NULL, null=True, blank=True, related_name='menciones_otorgadas', verbose_name=_("Otorgado/Registrado por (Docente)"))
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name=_("Institución"))

    class Meta:
        verbose_name = _("Mención o Reconocimiento")
        verbose_name_plural = _("Menciones y Reconocimientos")
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
    nombre_archivo_descriptivo = models.CharField(max_length=255, verbose_name=_("Nombre Descriptivo del Archivo"), default="[Nombre no especificado]")
    archivo = models.FileField(upload_to='planes_academicos_materiales/', verbose_name=_("Archivo"))
    descripcion = models.TextField(blank=True, null=True, verbose_name=_("Descripción (Opcional)"))
    tipo_documento = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Tipo de Documento (Ej: Plan de Estudio, Guía, Presentación)"))
    curso_asociado = models.ForeignKey(Curso, on_delete=models.SET_NULL, null=True, blank=True, related_name='archivos_material_apoyo_curso', verbose_name=_("Curso Asociado (Opcional)"))
    materia_asociada = models.ForeignKey(Materia, on_delete=models.SET_NULL, null=True, blank=True, related_name='archivos_material_apoyo_materia', verbose_name=_("Materia Asociada (Opcional)"))
    subido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Subido por"))
    fecha_subida = models.DateTimeField(auto_now_add=True, verbose_name=_("Fecha de Subida"))
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name=_("Institución"))
    palabras_clave = models.CharField(
        max_length=255, 
        blank=True,
        verbose_name=_("Palabras Clave (temas)"),
        help_text="Separa los temas con comas. Ej: fracciones, suma, resta, decimales"
    )
    temas_relacionados = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Temas Relevantes"),
        help_text="Añade temas específicos separados por comas (ej: 'Suma de fracciones', 'Teorema de Pitágoras', 'Análisis de personajes')."
    )

    class Meta:
        verbose_name = _("Archivo de Plan Académico o Material")
        verbose_name_plural = _("Archivos de Planes Académicos y Materiales")
        ordering = ['-fecha_subida', 'nombre_archivo_descriptivo']
        unique_together = ('nombre_archivo_descriptivo', 'curso_asociado', 'materia_asociada', 'institucion',) 

    def __str__(self):
        return self.nombre_archivo_descriptivo

class ConfiguracionInstitucion(models.Model):
    institucion_principal = models.OneToOneField(
        'finanzas.InstitucionEducativa', 
        on_delete=models.CASCADE, 
        primary_key=True, 
        verbose_name=_("Institución Principal") 
    ) 
    nombre_institucion = models.CharField(max_length=255, default="Nombre de Mi Institución", verbose_name=_("Nombre de la Institución (Opcional, si difiere de la principal)"))
    lema_institucion = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Lema o Eslogan (Opcional)"))
    direccion = models.TextField(blank=True, null=True, verbose_name=_("Dirección (Opcional)"))
    telefono_contacto = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("Teléfono(s) de Contacto (Opcional)"))
    email_contacto = models.EmailField(blank=True, null=True, verbose_name=_("Email de Contacto (Opcional)"))
    sitio_web = models.URLField(blank=True, null=True, verbose_name=_("Sitio Web (Opcional)"))
    logo = models.ImageField(upload_to='logos_institucion_gestion_academica/', blank=True, null=True, verbose_name=_("Logo de la Institución (Opcional, si difiere del principal)"))

    class Meta:
        verbose_name = _("Configuración de la Institución (Adicional)") 
        verbose_name_plural = _("Configuraciones de la Institución (Adicionales)")

    def __str__(self):
        return f"Configuración para {self.institucion_principal.nombre}"

class Noticia(models.Model):
    TIPO_URGENTE = 'URGENTE'
    TIPO_EVENTO = 'EVENTO'
    TIPO_INFORMATIVO = 'INFORMATIVO'
    TIPO_CHOICES = [
        (TIPO_URGENTE, 'Urgente (pagos, fechas límite, acceso)'),
        (TIPO_EVENTO, 'Evento (celebraciones, actividades)'),
        (TIPO_INFORMATIVO, 'Informativo (sin banner)'),
    ]

    AUDIENCIA_TODOS = 'TODOS'
    AUDIENCIA_DOCENTES = 'DOCENTES'
    AUDIENCIA_ESTUDIANTES = 'ESTUDIANTES'
    AUDIENCIA_FAMILIAS = 'FAMILIAS'
    AUDIENCIA_CHOICES = [
        (AUDIENCIA_TODOS, 'Todos (docentes + estudiantes + familias)'),
        (AUDIENCIA_DOCENTES, 'Solo docentes'),
        (AUDIENCIA_ESTUDIANTES, 'Solo estudiantes'),
        (AUDIENCIA_FAMILIAS, 'Solo familias / acudientes'),
    ]

    titulo = models.CharField(max_length=200, verbose_name=_("Título de la Noticia/Anuncio"))
    contenido = models.TextField(verbose_name=_("Contenido Completo"))
    fecha_publicacion = models.DateTimeField(auto_now_add=True, verbose_name=_("Fecha de Publicación"))
    publicado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='noticias_publicadas',
        verbose_name=_("Publicado por")
    )
    imagen_destacada = models.ImageField(
        upload_to='noticias_imagenes/',
        blank=True,
        null=True,
        verbose_name=_("Imagen Destacada (Opcional)")
    )
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name=_("Institución"))

    tipo = models.CharField(
        max_length=15,
        choices=TIPO_CHOICES,
        default=TIPO_INFORMATIVO,
        verbose_name=_("Tipo")
    )
    mostrar_banner = models.BooleanField(
        default=False,
        verbose_name=_("Mostrar como banner flotante"),
        help_text="Activa esto para que aparezca como banner en la esquina inferior izquierda."
    )
    fecha_expiracion_banner = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Fecha de expiración del banner"),
        help_text="El banner se oculta automáticamente después de esta fecha. Dejar vacío para que no expire."
    )
    audiencia = models.CharField(
        max_length=15,
        choices=AUDIENCIA_CHOICES,
        default=AUDIENCIA_TODOS,
        verbose_name=_("Audiencia del banner")
    )
    banner_revision = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Revisión del banner"),
        help_text="Se incrementa automáticamente al reactivar el banner, forzando que reaparezca para todos los usuarios."
    )

    class Meta:
        verbose_name = _("Noticia o Anuncio")
        verbose_name_plural = _("Noticias y Anuncios")
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
    # Fecha calendario (sin hora) para consultas por día: filtrar por fecha_solo
    # usa índice; filtrar por fecha__date obliga a convertir fila por fila.
    fecha_solo = models.DateField(null=True, blank=True, editable=False, db_index=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PRESENTE')
    curso = models.ForeignKey(Curso, on_delete=models.SET_NULL, null=True, blank=True)
    aula = models.ForeignKey('gestion_academica.Aula', on_delete=models.SET_NULL, null=True, blank=True)  # ✅ Nuevo
    registrado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('estudiante', 'fecha', 'curso')
        indexes = [
            # KPIs de asistencia diaria por institución (dashboards y reportes).
            models.Index(fields=['institucion', 'fecha_solo', 'estado'], name='asistencia_inst_fecha_idx'),
        ]

    def save(self, *args, **kwargs):
        if self.fecha:
            self.fecha_solo = localtime(self.fecha).date()
        if self.curso and self.curso.aula and not self.aula:
            self.aula = self.curso.aula  # ✅ Autocompleta aula desde el curso
        super().save(*args, **kwargs)


def ruta_documento_justificacion_inasistencia(instance, filename):
    """Ej: soportes_inasistencia/45-ana-gomez/incapacidad.pdf — evita colisiones de nombres."""
    nombre_limpio = "".join(
        c for c in instance.estudiante.usuario.get_full_name().lower() if c.isalnum() or c in (' ', '_')
    ).rstrip()
    return f"soportes_inasistencia/{instance.estudiante_id}-{nombre_limpio}/{filename}"


class JustificacionInasistencia(models.Model):
    """
    Justificación (médica u otro motivo) que un estudiante sube desde su
    portal para uno o varios días en los que el sistema ya marcó — o
    marcará — inasistencias/tardanzas suyas. Docentes de los cursos
    involucrados y coordinación revisan y aprueban/rechazan; al aprobar,
    los RegistroAsistencia relacionados pasan a estado 'JUSTIFICADO'.
    """

    class Motivo(models.TextChoices):
        MEDICA = 'MEDICA', _('Incapacidad médica')
        FAMILIAR = 'FAMILIAR', _('Motivo familiar')
        OTRO = 'OTRO', _('Otro motivo')

    class EstadoRevision(models.TextChoices):
        PENDIENTE = 'PENDIENTE', _('Pendiente de revisión')
        APROBADA = 'APROBADA', _('Aprobada')
        RECHAZADA = 'RECHAZADA', _('Rechazada')

    estudiante = models.ForeignKey(
        Estudiante, on_delete=models.CASCADE, related_name='justificaciones_inasistencia'
    )
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, editable=False)
    fecha_inicio = models.DateField(verbose_name=_("Desde"))
    fecha_fin = models.DateField(verbose_name=_("Hasta"))
    motivo = models.CharField(max_length=10, choices=Motivo.choices, verbose_name=_("Motivo"))
    descripcion = models.TextField(blank=True, verbose_name=_("Descripción"))
    documento_soporte = models.FileField(
        upload_to=ruta_documento_justificacion_inasistencia, null=True, blank=True,
        verbose_name=_("Soporte (incapacidad, certificado, etc.)"),
    )
    estado_revision = models.CharField(
        max_length=10, choices=EstadoRevision.choices, default=EstadoRevision.PENDIENTE
    )
    revisado_por = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    fecha_revision = models.DateTimeField(null=True, blank=True)
    observaciones_revision = models.TextField(blank=True, verbose_name=_("Observaciones de quien revisa"))
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Justificación de Inasistencia")
        verbose_name_plural = _("Justificaciones de Inasistencia")
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.estudiante} — {self.fecha_inicio} a {self.fecha_fin} ({self.get_estado_revision_display()})"

    def registros_relacionados(self):
        """RegistroAsistencia del estudiante en el rango cuyo estado amerita justificación.
        Se resuelve dinámicamente (no se guarda snapshot) para no perder inasistencias
        que el docente registre después de que el estudiante ya haya enviado la justificación."""
        return RegistroAsistencia.objects.filter(
            estudiante=self.estudiante,
            fecha_solo__gte=self.fecha_inicio,
            fecha_solo__lte=self.fecha_fin,
            estado__in=['AUSENTE', 'TARDANZA'],
        )


class EnlaceVideollamada(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='enlaces_videollamada')
    titulo = models.CharField(max_length=200, verbose_name=_("Título del Enlace"))
    url = models.URLField(max_length=500, verbose_name=_("URL de la Videollamada (Meet, Zoom, etc.)"))
    descripcion = models.TextField(blank=True, help_text="Instrucciones o descripción breve.")
    
    # --- CAMPO AÑADIDO ---
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', 
        on_delete=models.CASCADE,
        editable=False
    )

    class Meta:
        verbose_name = _("Enlace de Videollamada")
        verbose_name_plural = _("Enlaces de Videollamada")
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
    tipo = models.CharField(max_length=4, choices=TIPO_AULA, default='AULA', verbose_name=_("Tipo de Aula"))
    capacidad = models.PositiveIntegerField(default=0, help_text="Número máximo de estudiantes")
    ubicacion = models.CharField(max_length=255, blank=True, help_text="Ej: Edificio A, Segundo Piso")
    recursos = models.TextField(blank=True, help_text="Ej: Proyector, Pizarra Inteligente, 20 Computadores")
    
    # Este campo es la clave para la arquitectura multi-institución.
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)

    class Meta:
        verbose_name = _("Aula o Salón de Clases")
        verbose_name_plural = _("Aulas y Salones de Clases")
        
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
    dia_semana = models.IntegerField(choices=DIA_SEMANA_CHOICES, verbose_name=_("Día de la Semana"))
    hora_inicio = models.TimeField(verbose_name=_("Hora de Inicio"))
    hora_fin = models.TimeField(verbose_name=_("Hora de Fin"))
    aula = models.ForeignKey('gestion_academica.Aula', on_delete=models.SET_NULL, null=True, blank=True, related_name='horarios')
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)
    google_event_id = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("ID del Evento en Google Calendar"))

    class Meta:
        verbose_name = _("Bloque de Horario")
        verbose_name_plural = _("Bloques de Horario")
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
        ('opcion_multiple', _('Opción Múltiple')),
        ('verdadero_falso', _('Verdadero o Falso')),
        ('respuesta_abierta', _('Respuesta Abierta')),
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
        verbose_name=_("Duración para esta pregunta (minutos)"),
        help_text="Dejar en blanco si esta pregunta no tiene un límite de tiempo específico."
    )
    numero_intentos_permitidos = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Intentos permitidos para esta pregunta"),
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
        verbose_name = _("Pregunta de Actividad")
        verbose_name_plural = _("Preguntas de Actividades")

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
    texto_respuesta = models.TextField(blank=True, null=True, verbose_name=_("Respuesta de Texto"))
    
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
    inicio = models.DateTimeField(auto_now_add=True, verbose_name=_("Inicio del Intento"))
    fin = models.DateTimeField(null=True, blank=True, verbose_name=_("Fin del Intento"))
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
        verbose_name = _("Intento de Actividad")
        verbose_name_plural = _("Intentos de Actividades")
        constraints = [
            models.UniqueConstraint(
                fields=['estudiante', 'actividad'],
                condition=Q(estado='en_progreso'),
                name='ga_intentoactividad_uniq_en_progreso',
            ),
        ]

class ObservacionBoletin(models.Model):
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='observaciones_boletin')
    periodo = models.ForeignKey(PeriodoAcademico, on_delete=models.CASCADE, related_name='observaciones_recibidas')
    observacion = models.TextField(verbose_name=_("Observación para el Boletín"))
    # Accesibilidad (lectura fácil): versión simplificada con IA de la observación.
    observacion_simple = models.TextField(
        blank=True, default='',
        verbose_name=_("Observación en lectura fácil (IA)"),
        help_text=_("Versión simplificada de la observación, generada con IA para apoyo a la lectura."),
    )
    creado_por = models.ForeignKey('Docente', on_delete=models.SET_NULL, null=True)
    ultima_modificacion = models.DateTimeField(auto_now=True)
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE,)

    class Meta:
        unique_together = ('estudiante', 'periodo') # Solo una observación por estudiante y periodo 

class EscalaValorativa(models.Model):
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, related_name='escala_valorativa')
    nombre_desempeno = models.CharField(max_length=50, verbose_name=_("Nombre del Desempeño (Ej: Superior, Alto)"))
    abreviatura = models.CharField(max_length=10, verbose_name=_("Abreviatura (Ej: Sup, Alt)"))
    nota_minima = models.DecimalField(max_digits=3, decimal_places=2, verbose_name=_("Nota Mínima para este Desempeño"))
    nota_maxima = models.DecimalField(max_digits=3, decimal_places=2, verbose_name=_("Nota Máxima para este Desempeño"))
    orden = models.PositiveIntegerField(default=0, help_text="Orden para mostrar en la leyenda (ej. 1 para Superior, 2 para Alto, etc.)")

    class Meta:
        ordering = ['-nota_maxima'] # Ordenamos de la nota más alta a la más baja
        unique_together = ('institucion', 'nombre_desempeno')
        verbose_name = _("Escala Valorativa")
        verbose_name_plural = _("Escalas Valorativas")

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
    fecha_hora = models.DateTimeField(default=timezone.now, verbose_name=_("Fecha y Hora"))
    tipo = models.CharField(max_length=20, choices=TIPO_ANOTACION, verbose_name=_("Tipo de Anotación"))
    descripcion = models.TextField(verbose_name=_("Descripción de la Anotación"))
    
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
        verbose_name=_("Curso Relacionado (Opcional)")
    )
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE,)

    
    class Sentiment(models.TextChoices):
        POSITIVO = 'POSITIVO', _('Positivo')
        NEUTRO = 'NEUTRO', _('Neutro')
        NEGATIVO = 'NEGATIVO', _('Negativo')

    sentimiento_detectado = models.CharField(
        max_length=10, 
        choices=Sentiment.choices, 
        null=True, blank=True, 
        verbose_name=_("Sentimiento Detectado por IA")
    )
    requiere_revision = models.BooleanField(
        default=False, 
        verbose_name=_("¿Requiere Revisión Urgente?"),
        help_text="Marcado automáticamente por la IA si detecta riesgo (bullying, tristeza, etc.)"
    )
    analisis_ia = models.TextField(
        blank=True, null=True, 
        verbose_name=_("Análisis y Sugerencias de la IA"),
        help_text="Resumen generado por la IA para el coordinador."
    )

    # --- NUEVOS CAMPOS PARA LA RUTA DE ATENCIÓN ---
    TIPO_SITUACION_CHOICES = [
        ('TIPO I', _('Situación Tipo I')),
        ('TIPO II', _('Situación Tipo II')),
        ('TIPO III', _('Situación Tipo III')),
        ('NINGUNO', _('Ninguno')),
    ]
    tipo_situacion_ia = models.CharField(
        max_length=10, 
        choices=TIPO_SITUACION_CHOICES,
        blank=True, null=True,
        verbose_name=_("Clasificación de Convivencia (IA)")
    )
    acciones_protocolo_ia = models.TextField(
        blank=True, null=True,
        verbose_name=_("Protocolo Sugerido por IA")
    )
    
    class Meta:
        verbose_name = _("Anotación en Observador")
        verbose_name_plural = _("Anotaciones en Observador")
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
        ALTO = 'ALTO', _('Alto')
        MEDIO = 'MEDIO', _('Medio')
        BAJO = 'BAJO', _('Bajo')

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
    mensaje = models.CharField(max_length=255, verbose_name=_("Mensaje de la Notificación"))
    enlace = models.URLField(blank=True, null=True, help_text="URL a la que llevará la notificación al hacer clic.")
    consejo_ia = models.TextField(blank=True, null=True, verbose_name=_("Consejo Generado por IA"))
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE,)
    
    # Estados de la notificación
    leido = models.BooleanField(default=False, verbose_name=_("¿Leído?"))
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_leido = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = _("Notificación")
        verbose_name_plural = _("Notificaciones")

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
    dia_semana = models.IntegerField(choices=DIA_SEMANA_CHOICES, verbose_name=_("Día de la semana"))
    hora_inicio = models.TimeField(verbose_name=_("Hora de inicio de disponibilidad"))
    hora_fin = models.TimeField(verbose_name=_("Hora de fin de disponibilidad"))
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)

    class Meta:
        verbose_name = _("Disponibilidad de Docente")
        verbose_name_plural = _("Disponibilidades de Docentes")
        unique_together = ('docente', 'dia_semana', 'hora_inicio')

    def __str__(self):
        return f"{self.docente} - {self.get_dia_semana_display()} de {self.hora_inicio.strftime('%H:%M')} a {self.hora_fin.strftime('%H:%M')}"


class CitaReunion(models.Model):
    """
    Representa una cita específica reservada por un familiar.
    """
    class EstadoCita(models.TextChoices):
        PENDIENTE = 'PENDIENTE', _('Pendiente')
        CONFIRMADA = 'CONFIRMADA', _('Confirmada')
        CANCELADA = 'CANCELADA', _('Cancelada')
        REALIZADA = 'REALIZADA', _('Realizada')

    docente = models.ForeignKey(Docente, on_delete=models.CASCADE, related_name='citas')
    familiar = models.ForeignKey(Familiar, on_delete=models.CASCADE, related_name='citas')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='citas_reuniones')
    
    fecha_hora_inicio = models.DateTimeField(verbose_name=_("Fecha y hora de la cita"))
    duracion_minutos = models.PositiveIntegerField(default=15, verbose_name=_("Duración (minutos)"))
    
    asunto = models.CharField(max_length=255, verbose_name=_("Asunto principal de la reunión"))
    enlace_virtual = models.URLField(blank=True, null=True, verbose_name=_("Enlace de la videollamada (si aplica)"))
    
    estado = models.CharField(max_length=15, choices=EstadoCita.choices, default=EstadoCita.PENDIENTE)
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE,)
    

    observaciones_docente = models.TextField(
        blank=True, null=True, 
        verbose_name=_("Observaciones de la Reunión"),
        help_text="Notas privadas del docente sobre lo discutido en la reunión."
    )
    acuerdos_compromisos = models.TextField(
        blank=True, null=True, 
        verbose_name=_("Acuerdos y Compromisos"),
        help_text="Resumen de los acuerdos a los que se llegaron. Será visible para el familiar."
    )
    
    class Meta:
        verbose_name = _("Cita de Reunión")
        verbose_name_plural = _("Citas de Reuniones")
        ordering = ['fecha_hora_inicio']
        constraints = [
            # Solo las citas activas (no canceladas) bloquean el horario — una
            # cita cancelada libera de nuevo ese mismo horario para otro familiar.
            models.UniqueConstraint(
                fields=['docente', 'fecha_hora_inicio'],
                condition=~models.Q(estado='CANCELADA'),
                name='unique_cita_activa_por_docente_horario',
            )
        ]

    def __str__(self):
        return f"Cita de {self.familiar} con {self.docente} el {self.fecha_hora_inicio.strftime('%d/%m/%Y %H:%M')}"


class DisponibilidadOrientador(models.Model):
    """
    Bloque de tiempo RECURRENTE en el que el/la orientador(a) escolar
    (psicoorientador, rol='psicologo') está disponible para atender a las
    familias. Es el espejo de DisponibilidadDocente, pero ligado a un Usuario
    y NO a un Docente: así el flujo de citas del docente queda 100% intacto.
    """
    DIA_SEMANA_CHOICES = [
        (0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'),
        (3, 'Jueves'), (4, 'Viernes'),
    ]

    orientador = models.ForeignKey(
        Usuario, on_delete=models.CASCADE,
        related_name='disponibilidades_orientacion',
        limit_choices_to={'rol': 'psicologo'},
    )
    dia_semana = models.IntegerField(choices=DIA_SEMANA_CHOICES, verbose_name=_("Día de la semana"))
    hora_inicio = models.TimeField(verbose_name=_("Hora de inicio de disponibilidad"))
    hora_fin = models.TimeField(verbose_name=_("Hora de fin de disponibilidad"))
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)

    class Meta:
        verbose_name = _("Disponibilidad de Orientador")
        verbose_name_plural = _("Disponibilidades de Orientadores")
        unique_together = ('orientador', 'dia_semana', 'hora_inicio')

    def __str__(self):
        return f"{self.orientador.get_full_name()} - {self.get_dia_semana_display()} de {self.hora_inicio.strftime('%H:%M')} a {self.hora_fin.strftime('%H:%M')}"


class CitaOrientacion(models.Model):
    """
    Cita entre una familia y el/la orientador(a) escolar. Es bidireccional:
    puede ser solicitada por la familia (origen=FAMILIA) desde el portal, o
    citada por el propio orientador (origen=ORIENTADOR) cuando lo considera
    pertinente. Espejo de CitaReunion, ligado a Usuario (rol='psicologo').
    """
    class EstadoCita(models.TextChoices):
        PENDIENTE = 'PENDIENTE', _('Pendiente')
        CONFIRMADA = 'CONFIRMADA', _('Confirmada')
        REAGENDANDO = 'REAGENDANDO', _('En reprogramación')
        CANCELADA = 'CANCELADA', _('Cancelada')
        REALIZADA = 'REALIZADA', _('Realizada')

    class Origen(models.TextChoices):
        FAMILIA = 'FAMILIA', _('Solicitada por la familia')
        ORIENTADOR = 'ORIENTADOR', _('Citada por el orientador')

    class Parte(models.TextChoices):
        FAMILIA = 'FAMILIA', _('Familia')
        ORIENTADOR = 'ORIENTADOR', _('Orientador(a)')

    orientador = models.ForeignKey(
        Usuario, on_delete=models.CASCADE,
        related_name='citas_orientacion',
        limit_choices_to={'rol': 'psicologo'},
    )
    familiar = models.ForeignKey(Familiar, on_delete=models.CASCADE, related_name='citas_orientacion')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='citas_orientacion')

    fecha_hora_inicio = models.DateTimeField(verbose_name=_("Fecha y hora de la cita"))
    duracion_minutos = models.PositiveIntegerField(default=30, verbose_name=_("Duración (minutos)"))

    asunto = models.CharField(max_length=255, verbose_name=_("Asunto principal de la reunión"))
    enlace_virtual = models.URLField(blank=True, null=True, verbose_name=_("Enlace de la videollamada (si aplica)"))

    estado = models.CharField(max_length=15, choices=EstadoCita.choices, default=EstadoCita.PENDIENTE)
    origen = models.CharField(max_length=12, choices=Origen.choices, default=Origen.FAMILIA)
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)

    observaciones_orientador = models.TextField(
        blank=True, null=True,
        verbose_name=_("Observaciones de la Reunión"),
        help_text="Notas privadas del orientador sobre lo discutido en la reunión.",
    )
    acuerdos_compromisos = models.TextField(
        blank=True, null=True,
        verbose_name=_("Acuerdos y Compromisos"),
        help_text="Resumen de los acuerdos a los que se llegaron. Será visible para la familia.",
    )
    motivo_cancelacion = models.TextField(
        blank=True, null=True,
        verbose_name=_("Motivo de cancelación"),
        help_text="Razón indicada por quien canceló la cita (familia u orientador).",
    )
    # ── Reprogramación (negociación de horario) ──────────────────────────
    # Cuando una de las partes propone un nuevo horario, se guarda aquí a la
    # espera de que la OTRA parte lo acepte o contraproponga. Al aceptar, el
    # valor pasa a fecha_hora_inicio y estos campos se limpian.
    fecha_propuesta = models.DateTimeField(
        blank=True, null=True,
        verbose_name=_("Nuevo horario propuesto"),
    )
    propuesta_por = models.CharField(
        max_length=12, choices=Parte.choices, blank=True, null=True,
        verbose_name=_("Propuesta hecha por"),
    )
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Cita de Orientación")
        verbose_name_plural = _("Citas de Orientación")
        ordering = ['fecha_hora_inicio']
        constraints = [
            # Solo las citas activas (no canceladas) bloquean el horario.
            models.UniqueConstraint(
                fields=['orientador', 'fecha_hora_inicio'],
                condition=~models.Q(estado='CANCELADA'),
                name='unique_cita_orientacion_activa',
            )
        ]

    def __str__(self):
        return f"Cita de {self.familiar} con {self.orientador.get_full_name()} el {self.fecha_hora_inicio.strftime('%d/%m/%Y %H:%M')}"


class SeguimientoOrientacion(models.Model):
    """
    Registro de seguimiento psicosocial que hace el/la orientador(a) escolar
    por estudiante. CONFIDENCIAL (Ley 1581/2012 habeas data): solo accede el
    orientador y la rectoría. Se acumula en la carpeta del estudiante y queda
    disponible para inspección y vigilancia (Decreto 1075/2015). Marco de la
    orientación: Resolución 3842/2022, Decreto 1421/2017 (PIAR), Ley 1620/2013.
    """
    class Motivo(models.TextChoices):
        EMOCIONAL = 'EMOCIONAL', _('Acompañamiento emocional')
        CONVIVENCIA = 'CONVIVENCIA', _('Convivencia / comportamiento')
        FAMILIAR = 'FAMILIAR', _('Situación familiar')
        ACADEMICO = 'ACADEMICO', _('Dificultad académica')
        RIESGO = 'RIESGO', _('Riesgo psicosocial')
        REMISION = 'REMISION', _('Remisión a entidad externa')
        PIAR = 'PIAR', _('Seguimiento PIAR / inclusión')
        ORIENTACION_VOCACIONAL = 'VOCACIONAL', _('Orientación vocacional')
        OTRO = 'OTRO', _('Otro')

    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, related_name='seguimientos_orientacion')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='seguimientos_orientacion')
    orientador = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='seguimientos_orientacion_registrados',
        limit_choices_to={'rol': 'psicologo'},
    )
    fecha = models.DateTimeField(default=timezone.now, verbose_name=_("Fecha de la atención"))
    motivo = models.CharField(max_length=20, choices=Motivo.choices, default=Motivo.EMOCIONAL, verbose_name=_("Motivo de la atención"))
    descripcion = models.TextField(verbose_name=_("Relato / observaciones (confidencial)"))
    acuerdos = models.TextField(blank=True, null=True, verbose_name=_("Acuerdos y recomendaciones"))
    remision = models.TextField(blank=True, null=True, verbose_name=_("Remisión / entidad externa"), help_text="Si se remitió a EPS, ICBF, comisaría u otra entidad.")
    requiere_seguimiento = models.BooleanField(default=False, verbose_name=_("Requiere seguimiento"))
    proxima_cita = models.DateField(null=True, blank=True, verbose_name=_("Próxima cita / seguimiento"))
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Seguimiento de Orientación")
        verbose_name_plural = _("Seguimientos de Orientación")
        ordering = ['-fecha']

    def __str__(self):
        return f"Seguimiento {self.get_motivo_display()} — {self.estudiante} ({self.fecha:%d/%m/%Y})"


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
        verbose_name = _("Voto")
        verbose_name_plural = _("Votos")
        # Un votante solo puede votar una vez por elección.
        unique_together = ('eleccion', 'votante')

    def __str__(self):
        return f"{self.votante} votó por {self.candidato}"

        
        
class RegistroAsistenciaDocente(models.Model):
    class Estado(models.TextChoices):
        PRESENTE = 'PRESENTE', _('Presente')
        AUSENTE = 'AUSENTE', _('Ausente')
        JUSTIFICADO = 'JUSTIFICADO', _('Justificado')

    docente = models.ForeignKey(Docente, on_delete=models.CASCADE, related_name='asistencias')
    dia = models.DateField(verbose_name=_("Día de la jornada"), db_index=True)
    hora_entrada = models.DateTimeField(null=True, blank=True, verbose_name=_("Marca de entrada"))
    hora_salida = models.DateTimeField(null=True, blank=True, verbose_name=_("Marca de salida"))
    fecha = models.DateTimeField(auto_now=True, verbose_name=_("Última actualización"))
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PRESENTE)
    registrado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)

    class Meta:
        verbose_name = _("Registro de Asistencia de Docente")
        verbose_name_plural = _("Asistencias de Docentes")
        ordering = ['-dia', '-hora_entrada']
        unique_together = [('docente', 'dia')]

    def __str__(self):
        return f"{self.docente} — {self.dia}"

    @property
    def horas_en_institucion(self):
        """Horas entre entrada y salida (solo informativo)."""
        if not (self.hora_entrada and self.hora_salida):
            return None
        delta = self.hora_salida - self.hora_entrada
        if delta.total_seconds() <= 0:
            return None
        return round(delta.total_seconds() / 3600.0, 2)

class Egresado(models.Model):
    estudiante = models.OneToOneField(
        Estudiante, 
        on_delete=models.PROTECT, 
        related_name='perfil_egresado',
        verbose_name=_("Perfil de Estudiante Original")
    )
    año_graduacion = models.PositiveIntegerField(verbose_name=_("Año de Graduación"))
    fecha_egreso = models.DateField(verbose_name=_("Fecha de Egreso"))
    estado = models.CharField(max_length=50, default="Activo", verbose_name=_("Estado del Egresado"))

    class Meta:
        verbose_name = _("Egresado")
        verbose_name_plural = _("Egresados")
        ordering = ['-año_graduacion', 'estudiante__usuario__last_name']

    def __str__(self):
        return f"Egresado: {self.estudiante.usuario.get_full_name()} ({self.año_graduacion})"


class ArchivoHistorico(models.Model):
    class TipoDocumento(models.TextChoices):
        CERTIFICADO_NOTAS = 'CERT_NOTAS', _('Certificado de Notas')
        BOLETIN_FINAL = 'BOL_FINAL', _('Boletín Final')
        DIPLOMA_BACHILLER = 'DIPLOMA', _('Copia de Diploma')
        PAZ_Y_SALVO = 'PAZ_SALVO', _('Paz y Salvo Financiero')
        CONSTANCIA_ESTUDIOS = 'CONST_ESTUDIOS', _('Constancia de Estudios')

    egresado = models.ForeignKey(Egresado, on_delete=models.CASCADE, related_name='archivos')
    tipo_documento = models.CharField(max_length=50, choices=TipoDocumento.choices, verbose_name=_("Tipo de Documento"))
    año_academico = models.PositiveIntegerField(verbose_name=_("Año Académico del Reporte"))
    archivo_pdf = models.FileField(upload_to='archivos_historicos/', verbose_name=_("Archivo PDF Generado"))
    fecha_generacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Archivo Histórico")
        verbose_name_plural = _("Archivos Históricos")
        ordering = ['-año_academico', 'tipo_documento']

    def __str__(self):
        return f"{self.get_tipo_documento_display()} de {self.egresado} ({self.año_academico})"

class SolicitudDocumento(models.Model):
    class EstadoSolicitud(models.TextChoices):
        PENDIENTE_PAGO = 'PENDIENTE_PAGO', _('Pendiente de Pago')
        EN_PROCESO = 'EN_PROCESO', _('Pagado, en Proceso')
        LISTO_DESCARGA = 'LISTO_DESCARGA', _('Listo para Descargar')
        COMPLETADO = 'COMPLETADO', _('Completado')
        CANCELADO = 'CANCELADO', _('Cancelado')

    egresado = models.ForeignKey(Egresado, on_delete=models.CASCADE, related_name='solicitudes')
    tipo_documento_solicitado = models.CharField(max_length=100, verbose_name=_("Documento Solicitado"))
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
        BAJA = 'BAJA', _('Baja')
        MEDIA = 'MEDIA', _('Media')
        ALTA = 'ALTA', _('Alta')
        URGENTE = 'URGENTE', _('Urgente')

    class Estado(models.TextChoices):
        ABIERTO = 'ABIERTO', _('Abierto')
        EN_PROGRESO = 'EN_PROGRESO', _('En Progreso')
        RESUELTO = 'RESUELTO', _('Resuelto')
        CERRADO = 'CERRADO', _('Cerrado')

    ticket_id = models.CharField(max_length=20, unique=True, editable=False, verbose_name=_("ID del Ticket"))
    titulo = models.CharField(max_length=255, verbose_name=_("Asunto del Ticket"))
    descripcion = models.TextField(verbose_name=_("Descripción Detallada del Problema"))
    
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
        verbose_name = _("Ticket de Soporte")
        verbose_name_plural = _("Tickets de Soporte")
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
        verbose_name = _("Respuesta de Ticket")
        verbose_name_plural = _("Respuestas de Tickets")
        ordering = ['fecha_creacion']        

class PlaneacionClase(models.Model):
    """
    Representa una unidad de planeación completa para un curso,
    generada por un docente con la ayuda de la IA.
    VERSIÓN ACTUALIZADA CON ESTADOS DE GENERACIÓN.
    """
    class Metodologia(models.TextChoices):
        PROYECTOS = 'PROYECTOS', _('Aprendizaje Basado en Proyectos (ABP)')
        PROBLEMAS = 'PROBLEMAS', _('Aprendizaje Basado en Problemas (ABP)')
        INVERTIDA = 'INVERTIDA', _('Aula Invertida')
        TRADICIONAL = 'TRADICIONAL', _('Clase Magistral / Tradicional')
        COLABORATIVO = 'COLABORATIVO', _('Aprendizaje Colaborativo')
        GAMIFICACION = 'GAMIFICACION', _('Gamificación')

    class EstadoGeneracion(models.TextChoices):
        PENDIENTE = 'PENDIENTE', _('Pendiente de Generación')
        GENERANDO = 'GENERANDO', _('Generando Contenido con IA')
        COMPLETADO = 'COMPLETADO', _('Completado Exitosamente')
        FALLIDO = 'FALLIDO', _('Falló la Generación')

    # --- Campos existentes ---
    titulo = models.CharField(max_length=255, verbose_name=_("Título de la Unidad o Tema"))
    curso = models.ForeignKey('Curso', on_delete=models.CASCADE, related_name='planeaciones')
    docente = models.ForeignKey('Docente', on_delete=models.CASCADE, related_name='planeaciones')
    metodologia = models.CharField(max_length=20, choices=Metodologia.choices, verbose_name=_("Metodología Principal"))
    duracion_clases = models.PositiveIntegerField(default=1, verbose_name=_("Número de Clases de Duración"))
    objetivos_aprendizaje = models.TextField(blank=True, null=True, verbose_name=_("Objetivos de Aprendizaje"))
    recursos_necesarios = models.TextField(blank=True, null=True, verbose_name=_("Recursos Necesarios"))
    criterios_evaluacion = models.TextField(blank=True, null=True, verbose_name=_("Criterios de Evaluación"))
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    ultima_actualizacion = models.DateTimeField(auto_now=True)
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, editable=False)

    # ▼▼▼ CAMPOS NUEVOS AÑADIDOS ▼▼▼
    estado_generacion = models.CharField(
        max_length=20,
        choices=EstadoGeneracion.choices,
        default=EstadoGeneracion.PENDIENTE,
        verbose_name=_("Estado de Generación IA")
    )
    error_generacion = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Mensaje de Error (si falló)")
    )
    # ▲▲▲ FIN DE LOS CAMPOS AÑADIDOS ▲▲▲

    def save(self, *args, **kwargs):
        if not self.institucion_id and self.curso:
            self.institucion = self.curso.institucion
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Planeación: {self.titulo} para {self.curso}"

    class Meta:
        verbose_name = _("Planeación de Clase")
        verbose_name_plural = _("Planeaciones de Clases")
        ordering = ['-fecha_creacion']


class DetalleClase(models.Model):
    """
    Representa una de las clases individuales dentro de una PlaneacionClase.
    """
    planeacion = models.ForeignKey(PlaneacionClase, on_delete=models.CASCADE, related_name='detalles_clase')
    numero_clase = models.PositiveIntegerField(verbose_name=_("Número de Clase"))
    
    # Campos que serán llenados por la IA
    tema_clase = models.CharField(max_length=255, verbose_name=_("Tema de la Clase"))
    actividades_inicio = models.TextField(verbose_name=_("Actividades de Inicio"))
    actividades_desarrollo = models.TextField(verbose_name=_("Actividades de Desarrollo"))
    actividades_cierre = models.TextField(verbose_name=_("Actividades de Cierre"))

    def __str__(self):
        return f"Clase {self.numero_clase}: {self.tema_clase}"

    class Meta:
        verbose_name = _("Detalle de Clase")
        verbose_name_plural = _("Detalles de Clases")
        ordering = ['numero_clase']
        unique_together = ('planeacion', 'numero_clase')        

       
     
class AnalisisComportamientoIA(models.Model):
    """
    Guarda el resumen y los patrones detectados por la IA al analizar el
    historial completo de un estudiante en el observador.
    """
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='analisis_comportamiento')
    resumen_ia = models.TextField(verbose_name=_("Análisis y Resumen de la IA"))
    patrones_detectados = models.JSONField(null=True, blank=True, verbose_name=_("Patrones Estructurados"))
    fecha_analisis = models.DateTimeField(auto_now_add=True, verbose_name=_("Fecha del Análisis"))
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)

    def __str__(self):
        return f"Análisis para {self.estudiante} - {self.fecha_analisis.strftime('%Y-%m-%d')}"

    class Meta:
        verbose_name = _("Análisis de Comportamiento (IA)")
        verbose_name_plural = _("Análisis de Comportamiento (IA)")
        ordering = ['-fecha_analisis']


# ======================================================================= #
#  HALU SENTINEL — Ruta de Atención Integral (Resolución 1620 / Ley 1620)  #
# ======================================================================= #

class CasoConvivencia(models.Model):
    """
    Expediente formal de una situación de convivencia escolar.
    Se crea automáticamente cuando la IA clasifica una AnotacionObservador
    como Tipo II o Tipo III, o manualmente por un coordinador.

    Ciclo de vida: ABIERTO → EN_SEGUIMIENTO → CERRADO / ARCHIVADO
    Plazos legales (Res. 1620 / Dec. 1965 Art. 42):
      - Tipo I  : resolución inmediata por el docente
      - Tipo II : Comité de Convivencia debe responder en 5 días hábiles
      - Tipo III: reporte a autoridades en máx. 2 horas hábiles
    """

    class TipoSituacion(models.TextChoices):
        TIPO_I   = 'TIPO I',   _('Tipo I — Conflicto menor')
        TIPO_II  = 'TIPO II',  _('Tipo II — Daño moderado')
        TIPO_III = 'TIPO III', _('Tipo III — Daño grave / delito')

    class Estado(models.TextChoices):
        ABIERTO        = 'ABIERTO',        _('Abierto')
        EN_SEGUIMIENTO = 'EN_SEGUIMIENTO', _('En seguimiento')
        VENCIDO        = 'VENCIDO',        _('Vencido — plazo superado')
        CERRADO        = 'CERRADO',        _('Cerrado')
        ARCHIVADO      = 'ARCHIVADO',      _('Archivado')

    class RolInvolucrado(models.TextChoices):
        VICTIMA   = 'VICTIMA',   _('Víctima')
        AGRESOR   = 'AGRESOR',   _('Agresor/a')
        TESTIGO   = 'TESTIGO',   _('Testigo')
        OTRO      = 'OTRO',      _('Otro involucrado')

    # ── Identificación ─────────────────────────────────────────────────
    radicado = models.CharField(
        max_length=20, unique=True, editable=False,
        verbose_name=_('Número de radicado'),
        help_text='Generado automáticamente: CONV-AAAA-NNNN',
    )
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='casos_convivencia',
    )

    # ── Clasificación ───────────────────────────────────────────────────
    tipo_situacion = models.CharField(
        max_length=10, choices=TipoSituacion.choices,
        verbose_name=_('Tipo de situación (Res. 1620)'),
    )
    estado = models.CharField(
        max_length=15, choices=Estado.choices,
        default=Estado.ABIERTO, verbose_name=_('Estado del caso'),
    )

    # ── Origen ─────────────────────────────────────────────────────────
    anotacion_origen = models.OneToOneField(
        AnotacionObservador, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='caso_convivencia',
        verbose_name=_('Anotación que originó el caso'),
    )
    descripcion_detalle = models.TextField(
        verbose_name=_('Descripción detallada del hecho'),
        help_text='Completar o ampliar la descripción inicial.',
    )

    # ── Actores ─────────────────────────────────────────────────────────
    # Los involucrados se registran a través de InvolucradoCaso (intermedia)
    # para poder asignarles un rol (víctima, agresor, testigo).

    # ── Responsable y plazos ────────────────────────────────────────────
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='casos_convivencia_asignados',
        verbose_name=_('Coordinador responsable'),
    )
    fecha_apertura  = models.DateTimeField(auto_now_add=True)
    fecha_limite    = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_('Fecha límite legal de respuesta'),
    )
    fecha_cierre    = models.DateTimeField(null=True, blank=True)

    # ── Campos adicionales ──────────────────────────────────────────────
    protocolo_ia = models.TextField(
        blank=True, verbose_name=_('Protocolo sugerido por IA'),
    )
    resolucion_final = models.TextField(
        blank=True, verbose_name=_('Resolución y compromisos finales'),
        help_text='Completar al cerrar el caso.',
    )

    class Meta:
        verbose_name = _('Caso de Convivencia')
        verbose_name_plural = _('Casos de Convivencia')
        ordering = ['-fecha_apertura']
        permissions = [
            ('puede_gestionar_casos', 'Puede gestionar casos de convivencia (Sentinel)'),
        ]

    def __str__(self):
        return f'{self.radicado} — {self.tipo_situacion} ({self.estado})'

    def save(self, *args, **kwargs):
        if not self.radicado:
            self.radicado = self._generar_radicado()
        super().save(*args, **kwargs)

    @staticmethod
    def _generar_radicado():
        from django.utils import timezone as tz
        año = tz.now().year
        ultimo = (
            CasoConvivencia.objects
            .filter(radicado__startswith=f'CONV-{año}-')
            .order_by('-radicado')
            .first()
        )
        if ultimo:
            try:
                n = int(ultimo.radicado.split('-')[-1]) + 1
            except ValueError:
                n = 1
        else:
            n = 1
        return f'CONV-{año}-{n:04d}'

    def esta_vencido(self):
        from django.utils import timezone as tz
        if self.fecha_limite and self.estado not in (
            self.Estado.CERRADO, self.Estado.ARCHIVADO
        ):
            return tz.now() > self.fecha_limite
        return False

    def dias_restantes(self):
        from django.utils import timezone as tz
        if not self.fecha_limite:
            return None
        delta = self.fecha_limite - tz.now()
        return int(delta.total_seconds() / 3600 / 24)


class InvolucradoCaso(models.Model):
    """Tabla intermedia que vincula estudiantes a un caso con su rol."""
    caso      = models.ForeignKey(CasoConvivencia, on_delete=models.CASCADE, related_name='involucrados')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='casos_involucrado')
    rol        = models.CharField(max_length=10, choices=CasoConvivencia.RolInvolucrado.choices)

    class Meta:
        unique_together = ('caso', 'estudiante')
        verbose_name = _('Involucrado en caso')
        verbose_name_plural = _('Involucrados en caso')

    def __str__(self):
        return f'{self.estudiante} → {self.rol} en {self.caso.radicado}'


class AccionCaso(models.Model):
    """
    Cada acción documentada sobre un CasoConvivencia:
    reuniones, notificaciones a padres, reportes a autoridades,
    acuerdos, seguimientos y el cierre formal.
    """

    class TipoAccion(models.TextChoices):
        NOTIFICACION_PADRE   = 'NOTIFICACION_PADRE',   _('Notificación a padre/tutor')
        REUNION_COMITE       = 'REUNION_COMITE',       _('Reunión de Comité de Convivencia')
        REPORTE_AUTORIDAD    = 'REPORTE_AUTORIDAD',    _('Reporte a autoridad externa (ICBF / Policía)')
        ACUERDO_COMPROMISO   = 'ACUERDO_COMPROMISO',   _('Acuerdo y compromisos firmados')
        SEGUIMIENTO          = 'SEGUIMIENTO',          _('Seguimiento periódico')
        MEDIACION            = 'MEDIACION',            _('Proceso de mediación escolar')
        REMISION_PROFESIONAL = 'REMISION_PROFESIONAL', _('Remisión a profesional externo')
        CIERRE               = 'CIERRE',               _('Cierre formal del caso')
        OTRO                 = 'OTRO',                 _('Otra acción')

    caso          = models.ForeignKey(CasoConvivencia, on_delete=models.CASCADE, related_name='acciones')
    tipo_accion   = models.CharField(max_length=25, choices=TipoAccion.choices, verbose_name=_('Tipo de acción'))
    descripcion   = models.TextField(verbose_name=_('Descripción de lo actuado'))
    ejecutado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='acciones_caso',
        verbose_name=_('Ejecutado por'),
    )
    fecha         = models.DateTimeField(auto_now_add=True)
    evidencia     = models.FileField(
        upload_to='sentinel/evidencias/%Y/%m/',
        null=True, blank=True,
        verbose_name=_('Evidencia / documento adjunto'),
    )

    class Meta:
        verbose_name = _('Acción sobre caso')
        verbose_name_plural = _('Acciones sobre casos')
        ordering = ['fecha']

    def __str__(self):
        return f'[{self.caso.radicado}] {self.get_tipo_accion_display()} — {self.fecha.strftime("%d/%m/%Y")}'


# ══════════════════════════════════════════════════════════════════════════════
#  MÓDULO: MALLA CURRICULAR + PLAN SEMANAL DOCENTE
# ══════════════════════════════════════════════════════════════════════════════

_MESES_CHOICES = [
    (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
    (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
    (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre'),
]


class MallaCurricular(models.Model):
    """
    Hoja de ruta curricular por materia + grado + año lectivo.
    Creada por el coordinador o jefe de área; consultada por los docentes
    como referencia para sus planes semanales.
    """
    materia = models.ForeignKey(
        'Materia', on_delete=models.CASCADE,
        related_name='mallas_curriculares', verbose_name=_("Materia"),
    )
    grado = models.ForeignKey(
        'Grado', on_delete=models.CASCADE,
        related_name='mallas_curriculares', verbose_name=_("Grado"),
    )
    año_lectivo = models.PositiveIntegerField(
        verbose_name=_("Año Lectivo"), default=datetime.date.today().year,
    )
    descripcion_general = models.TextField(
        blank=True, null=True, verbose_name=_("Propósitos Generales / Descripción"),
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='mallas_creadas',
    )
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        verbose_name=_("Institución"),
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Malla Curricular")
        verbose_name_plural = _("Mallas Curriculares")
        unique_together = ('materia', 'grado', 'año_lectivo', 'institucion')
        ordering = ['grado__orden', 'materia__nombre_materia']

    def __str__(self):
        return f"Malla · {self.materia} · {self.grado} · {self.año_lectivo}"

    def total_items(self):
        return self.items.count()


class ItemMalla(models.Model):
    """
    Un eje temático dentro de la malla curricular, organizado por período.
    Sigue la estructura oficial colombiana: EBC, DBA, competencias,
    logros, indicadores de desempeño por nivel (Bajo/Básico/Alto/Superior).
    """
    malla = models.ForeignKey(
        MallaCurricular, on_delete=models.CASCADE, related_name='items',
    )
    periodo = models.PositiveSmallIntegerField(
        verbose_name=_("Período"),
        choices=[(1, '1° Período'), (2, '2° Período'), (3, '3° Período'), (4, '4° Período')],
    )
    eje_tematico = models.CharField(
        max_length=255, verbose_name=_("Eje Temático / Contenido"), default='',
    )
    # Referentes nacionales
    ebc = models.TextField(
        blank=True, null=True,
        verbose_name=_("Estándares Básicos de Competencias (EBC)"),
    )
    dba = models.TextField(
        blank=True, null=True,
        verbose_name=_("Derechos Básicos de Aprendizaje (DBA)"),
    )
    evidencias_dba = models.TextField(
        blank=True, null=True,
        verbose_name=_("Evidencias de Aprendizaje del DBA"),
        help_text="Las 3-5 acciones observables del DBA que evidencian su logro. Sirven de base para los indicadores de desempeño.",
    )
    # Competencias y logro
    competencias = models.TextField(
        blank=True, null=True, verbose_name=_("Competencias"),
    )
    logro = models.TextField(
        verbose_name=_("Logro del Período"), default='',
    )
    # Indicadores de desempeño por nivel
    indicador_bajo = models.TextField(
        blank=True, null=True, verbose_name=_("Indicador — Desempeño Bajo (1.0–2.9)"),
    )
    indicador_basico = models.TextField(
        blank=True, null=True, verbose_name=_("Indicador — Desempeño Básico (3.0–3.9)"),
    )
    indicador_alto = models.TextField(
        blank=True, null=True, verbose_name=_("Indicador — Desempeño Alto (4.0–4.5)"),
    )
    indicador_superior = models.TextField(
        blank=True, null=True, verbose_name=_("Indicador — Desempeño Superior (4.6–5.0)"),
    )
    # Planeación pedagógica
    metodologia = models.TextField(
        blank=True, null=True, verbose_name=_("Metodología / Estrategias Pedagógicas"),
    )
    recursos = models.TextField(
        blank=True, null=True, verbose_name=_("Recursos"),
    )
    evaluacion = models.TextField(
        blank=True, null=True, verbose_name=_("Criterios de Evaluación"),
    )
    tiempo_semanas = models.PositiveSmallIntegerField(
        default=10, verbose_name=_("Duración (semanas del período)"),
    )
    # --- Campos bilingües (Nivel 3) ---
    # Solo se llenan cuando la institución tiene es_bilingue=True.
    # El sufijo _L2 indica "segundo idioma" (language 2).
    eje_tematico_L2 = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name=_("Eje Temático (Idioma Secundario)"),
    )
    logro_L2 = models.TextField(
        blank=True, default='',
        verbose_name=_("Logro del Período (Idioma Secundario)"),
    )
    competencias_L2 = models.TextField(
        blank=True, null=True,
        verbose_name=_("Competencias (Idioma Secundario)"),
    )
    indicador_bajo_L2 = models.TextField(
        blank=True, null=True,
        verbose_name=_("Indicador Bajo (Idioma Secundario)"),
    )
    indicador_basico_L2 = models.TextField(
        blank=True, null=True,
        verbose_name=_("Indicador Básico (Idioma Secundario)"),
    )
    indicador_alto_L2 = models.TextField(
        blank=True, null=True,
        verbose_name=_("Indicador Alto (Idioma Secundario)"),
    )
    indicador_superior_L2 = models.TextField(
        blank=True, null=True,
        verbose_name=_("Indicador Superior (Idioma Secundario)"),
    )
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _("Ítem de Malla")
        verbose_name_plural = _("Ítems de Malla")
        ordering = ['periodo', 'orden']

    def __str__(self):
        return f"P{self.periodo} · {self.eje_tematico}"


class PlanSemanal(models.Model):
    """
    Plan semanal de un docente para un curso.
    Flujo de estados: BORRADOR → ENVIADO → APROBADO / CON_OBSERVACIONES
    """
    class Estado(models.TextChoices):
        BORRADOR          = 'BORRADOR',          _('Borrador')
        ENVIADO           = 'ENVIADO',           _('Enviado al Coordinador')
        APROBADO          = 'APROBADO',          _('Aprobado')
        CON_OBSERVACIONES = 'CON_OBSERVACIONES', _('Con Observaciones')

    docente = models.ForeignKey(
        'Docente', on_delete=models.CASCADE, related_name='planes_semanales',
    )
    curso = models.ForeignKey(
        'Curso', on_delete=models.CASCADE, related_name='planes_semanales',
    )
    semana_inicio = models.DateField(verbose_name=_("Inicio de Semana (Lunes)"))
    semana_fin    = models.DateField(verbose_name=_("Fin de Semana (Viernes)"))
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.BORRADOR,
    )
    observaciones_coordinador = models.TextField(
        blank=True, null=True, verbose_name=_("Observaciones del Coordinador"),
    )
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='planes_revisados',
    )
    fecha_envio    = models.DateTimeField(null=True, blank=True)
    fecha_revision = models.DateTimeField(null=True, blank=True)
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
    )

    class Meta:
        verbose_name = _("Plan Semanal")
        verbose_name_plural = _("Planes Semanales")
        unique_together = ('docente', 'curso', 'semana_inicio')
        ordering = ['-semana_inicio']

    def __str__(self):
        return f"{self.docente} · {self.curso} · {self.semana_inicio}"


class ItemPlanSemanal(models.Model):
    """
    Una clase/sesión dentro del plan semanal.
    Opcionalmente enlazada a un ítem de malla curricular.
    Puede convertirse en Deber o ActividadCalificable con un clic.
    """
    plan = models.ForeignKey(
        PlanSemanal, on_delete=models.CASCADE, related_name='items',
    )
    fecha       = models.DateField(verbose_name=_("Fecha de la Clase"))
    titulo      = models.CharField(max_length=255, verbose_name=_("Tema / Título"))
    descripcion = models.TextField(blank=True, null=True, verbose_name=_("Descripción / Actividades"))
    item_malla  = models.ForeignKey(
        ItemMalla, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='items_plan', verbose_name=_("Ítem de Malla Vinculado"),
    )
    # Conversiones (se llenan al convertir)
    deber = models.OneToOneField(
        'Deber', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='item_plan_origen',
    )
    actividad = models.OneToOneField(
        'ActividadCalificable', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='item_plan_origen',
    )
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _("Ítem de Plan Semanal")
        verbose_name_plural = _("Ítems de Plan Semanal")
        ordering = ['fecha', 'orden']

    def __str__(self):
        return f"{self.fecha} – {self.titulo}"


# ══════════════════════════════════════════════════════════════════════════════
#  MÓDULO: CORTE PREVENTIVO
#  Informes académicos intermedios de alerta temprana (Decreto 1290/2009)
# ══════════════════════════════════════════════════════════════════════════════

class ConfiguracionCortePreventivo(models.Model):
    """Configuración global del módulo de cortes preventivos por institución."""

    institucion = models.OneToOneField(
        'finanzas.InstitucionEducativa',
        on_delete=models.CASCADE,
        related_name='config_corte_preventivo',
        verbose_name=_("Institución"),
    )
    umbral_riesgo_bajo = models.DecimalField(
        max_digits=4, decimal_places=2, default=2.90,
        verbose_name=_("Umbral Riesgo Alto (nota por debajo de...)"),
        help_text="Estudiantes con promedio menor a este valor se marcan en RIESGO ALTO. Ej: 2.9",
    )
    umbral_riesgo_medio = models.DecimalField(
        max_digits=4, decimal_places=2, default=3.40,
        verbose_name=_("Umbral Riesgo Medio (nota por debajo de...)"),
        help_text="Estudiantes entre el umbral alto y este valor se marcan en RIESGO MEDIO. Ej: 3.4",
    )
    porcentaje_inasistencia_alerta = models.PositiveIntegerField(
        default=20,
        verbose_name=_("% Inasistencia que genera alerta"),
        help_text="Si el porcentaje de clases perdidas supera este valor, se activa alerta de asistencia. Ej: 20 = 20%",
    )
    mostrar_promedio_parcial = models.BooleanField(default=True, verbose_name=_("Mostrar promedio parcial en el reporte"))
    mostrar_asistencia = models.BooleanField(default=True, verbose_name=_("Incluir asistencia en el reporte"))
    mostrar_observaciones_docente = models.BooleanField(default=True, verbose_name=_("Incluir observaciones de docentes"))
    firma_rector_en_reporte = models.BooleanField(default=True, verbose_name=_("Incluir firma del rector en el PDF"))
    permitir_descarga_familiar = models.BooleanField(
        default=False,
        verbose_name=_("Permitir que familias descarguen el reporte desde el portal"),
    )
    texto_pie_pagina = models.TextField(
        blank=True,
        default="Este informe es de carácter preventivo y no constituye el boletín oficial de calificaciones.",
        verbose_name=_("Texto del pie de página del reporte PDF"),
    )

    class Meta:
        verbose_name = _("Configuración de Corte Preventivo")
        verbose_name_plural = _("Configuraciones de Corte Preventivo")

    def __str__(self):
        return f"Config. Corte Preventivo — {self.institucion}"


class CortePreventivo(models.Model):
    """Evento de corte: encabezado del reporte para un grado y período."""

    ESTADO_CHOICES = [
        ('BORRADOR',   _('Borrador')),
        ('CALCULANDO', _('Calculando...')),
        ('PUBLICADO',  _('Publicado')),
        ('ARCHIVADO',  _('Archivado')),
    ]

    institucion      = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name=_("Institución"))
    periodo_academico = models.ForeignKey('PeriodoAcademico', on_delete=models.CASCADE, related_name='cortes_preventivos', verbose_name=_("Período Académico"))
    grado            = models.ForeignKey('Grado', on_delete=models.CASCADE, related_name='cortes_preventivos', verbose_name=_("Grado"))
    fecha_corte      = models.DateField(verbose_name=_("Fecha de Corte"), help_text="Fecha hasta la cual se toman en cuenta las actividades y calificaciones")
    nombre_corte     = models.CharField(max_length=150, verbose_name=_("Nombre del Corte"), help_text="Ej: Corte 1 – Mayo 2025")
    estado           = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='BORRADOR', verbose_name=_("Estado"))
    generado_por     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Generado por"))
    fecha_generacion = models.DateTimeField(auto_now_add=True, verbose_name=_("Fecha de Creación"))
    fecha_publicacion = models.DateTimeField(null=True, blank=True, verbose_name=_("Fecha de Publicación"))
    observacion_general = models.TextField(blank=True, verbose_name=_("Observación General del Coordinador"), help_text="Mensaje del coordinador para todos los estudiantes del grado")
    total_estudiantes_evaluados = models.PositiveIntegerField(default=0, verbose_name=_("Total Estudiantes Evaluados"))
    total_en_riesgo  = models.PositiveIntegerField(default=0, verbose_name=_("Total en Riesgo"))

    class Meta:
        verbose_name = _("Corte Preventivo")
        verbose_name_plural = _("Cortes Preventivos")
        unique_together = ('institucion', 'periodo_academico', 'grado', 'fecha_corte')
        ordering = ['-fecha_corte', 'grado__nombre']

    def __str__(self):
        return f"{self.nombre_corte} — {self.grado} ({self.periodo_academico})"


class ResultadoCorteEstudiante(models.Model):
    """Resultado individual de cada estudiante dentro de un corte."""

    NIVEL_CHOICES = [
        ('SUPERIOR', _('Superior')),
        ('ALTO',     _('Alto')),
        ('BASICO',   _('Básico')),
        ('BAJO',     _('Bajo')),
        ('SIN_DATOS',_('Sin datos')),
    ]
    RIESGO_CHOICES = [
        ('ALTO',       _('Riesgo Alto')),
        ('MEDIO',      _('Riesgo Medio')),
        ('BAJO',       _('Riesgo Bajo')),
        ('SIN_RIESGO', _('Sin Riesgo')),
    ]

    corte       = models.ForeignKey(CortePreventivo, on_delete=models.CASCADE, related_name='resultados', verbose_name=_("Corte"))
    estudiante  = models.ForeignKey('Estudiante', on_delete=models.CASCADE, related_name='resultados_corte', verbose_name=_("Estudiante"))
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name=_("Institución"))

    promedio_general         = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, verbose_name=_("Promedio General"))
    nivel_desempeno_general  = models.CharField(max_length=10, choices=NIVEL_CHOICES, default='SIN_DATOS', verbose_name=_("Nivel de Desempeño"))
    nivel_riesgo             = models.CharField(max_length=10, choices=RIESGO_CHOICES, default='SIN_RIESGO', verbose_name=_("Nivel de Riesgo"))
    porcentaje_asistencia    = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name=_("% Asistencia"))
    total_actividades_registradas = models.PositiveIntegerField(default=0, verbose_name=_("Total Actividades Registradas"))
    total_actividades_calificadas = models.PositiveIntegerField(default=0, verbose_name=_("Total Actividades Calificadas"))
    materias_en_riesgo_count = models.PositiveIntegerField(default=0, verbose_name=_("Materias en Riesgo"))
    observacion_director_curso = models.TextField(blank=True, verbose_name=_("Observación del Director de Curso"))
    requiere_citacion_padres = models.BooleanField(default=False, verbose_name=_("Requiere Citación de Padres"))
    notificacion_enviada     = models.BooleanField(default=False, verbose_name=_("Notificación Enviada"))
    fecha_notificacion       = models.DateTimeField(null=True, blank=True, verbose_name=_("Fecha de Notificación"))

    class Meta:
        verbose_name = _("Resultado de Estudiante")
        verbose_name_plural = _("Resultados de Estudiantes")
        unique_together = ('corte', 'estudiante', 'institucion')
        ordering = ['estudiante__usuario__last_name', 'estudiante__usuario__first_name']

    def __str__(self):
        return f"{self.estudiante} — {self.corte.nombre_corte} [{self.nivel_riesgo}]"


class DetalleMateriaCortePrev(models.Model):
    """Resultado por materia de un estudiante dentro del corte."""

    NIVEL_CHOICES = [
        ('SUPERIOR', _('Superior')),
        ('ALTO',     _('Alto')),
        ('BASICO',   _('Básico')),
        ('BAJO',     _('Bajo')),
        ('SIN_DATOS',_('Sin datos')),
    ]

    resultado_estudiante  = models.ForeignKey(ResultadoCorteEstudiante, on_delete=models.CASCADE, related_name='detalles_materias', verbose_name=_("Resultado del Estudiante"))
    curso                 = models.ForeignKey('Curso', on_delete=models.CASCADE, verbose_name=_("Curso"))
    institucion           = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, verbose_name=_("Institución"))
    promedio_materia      = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, verbose_name=_("Promedio en la Materia"))
    nivel_desempeno       = models.CharField(max_length=10, choices=NIVEL_CHOICES, default='SIN_DATOS', verbose_name=_("Nivel de Desempeño"))
    en_riesgo             = models.BooleanField(default=False, verbose_name=_("¿En riesgo?"))
    actividades_registradas = models.PositiveIntegerField(default=0, verbose_name=_("Actividades Registradas"))
    actividades_calificadas = models.PositiveIntegerField(default=0, verbose_name=_("Actividades Calificadas"))
    actividades_pendientes  = models.PositiveIntegerField(default=0, verbose_name=_("Actividades Pendientes de Nota"))
    observacion_docente   = models.TextField(blank=True, verbose_name=_("Observación del Docente"))

    class Meta:
        verbose_name = _("Detalle por Materia")
        verbose_name_plural = _("Detalles por Materia")
        unique_together = ('resultado_estudiante', 'curso', 'institucion')
        ordering = ['curso__materia__nombre_materia']

    def __str__(self):
        return f"{self.curso.materia.nombre_materia} — {self.resultado_estudiante.estudiante}"

# ─────────────────────────────────────────────────────────────────────────────
# DBA PREDEFINIDOS — Biblioteca oficial MEN (global, sin institución)
# ─────────────────────────────────────────────────────────────────────────────

class DBAPredefinido(models.Model):
    """
    Catálogo global de DBA oficiales publicados por el MEN de Colombia.
    No pertenece a ninguna institución — es compartido por toda la plataforma.
    Solo 5 áreas tienen DBA oficiales: Lenguaje, Matemáticas, Ciencias Naturales,
    Ciencias Sociales e Inglés (documentos V.2, 2016).
    """
    AREA_CHOICES = [
        ('matematicas',       _('Matemáticas')),
        ('lenguaje',          _('Lenguaje')),
        ('ciencias_naturales',_('Ciencias Naturales')),
        ('ciencias_sociales', _('Ciencias Sociales')),
        ('ingles',            _('Inglés')),
    ]
    GRADO_CHOICES = [
        ('transicion', _('Transición')),
        ('1',  _('Grado 1°')),
        ('2',  _('Grado 2°')),
        ('3',  _('Grado 3°')),
        ('4',  _('Grado 4°')),
        ('5',  _('Grado 5°')),
        ('6',  _('Grado 6°')),
        ('7',  _('Grado 7°')),
        ('8',  _('Grado 8°')),
        ('9',  _('Grado 9°')),
        ('10', _('Grado 10°')),
        ('11', _('Grado 11°')),
    ]

    area        = models.CharField(max_length=30, choices=AREA_CHOICES, verbose_name=_("Área"))
    grado       = models.CharField(max_length=15, choices=GRADO_CHOICES, verbose_name=_("Grado"))
    numero      = models.PositiveSmallIntegerField(verbose_name=_("N° DBA"))
    enunciado   = models.TextField(verbose_name=_("Enunciado del DBA"))
    evidencias  = models.TextField(blank=True, verbose_name=_("Evidencias de Aprendizaje"))
    version_men = models.CharField(max_length=10, default='V.2', verbose_name=_("Versión MEN"))

    class Meta:
        verbose_name        = _("DBA Predefinido (MEN)")
        verbose_name_plural = _("DBA Predefinidos (MEN)")
        ordering            = ['area', 'grado', 'numero']
        unique_together     = [('area', 'grado', 'numero')]

    def __str__(self):
        return f"DBA N.°{self.numero} — {self.get_area_display()} {self.get_grado_display()}"


class EventoInstitucional(models.Model):
    """
    Evento externo/institucional (festivo local, jornada pedagógica, acto
    cultural, etc.) creado a mano por coordinación — a diferencia de los
    cumpleaños, que NUNCA se guardan aquí: se calculan al vuelo desde
    Estudiante.fecha_nacimiento / Docente.fecha_nacimiento para no duplicar
    datos que ya existen en la plataforma.
    """
    class Categoria(models.TextChoices):
        CULTURAL = 'CULTURAL', _('Cultural / Cívico')
        ACADEMICO = 'ACADEMICO', _('Académico')
        INSTITUCIONAL = 'INSTITUCIONAL', _('Institucional')
        OTRO = 'OTRO', _('Otro')

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='eventos_institucionales', verbose_name=_("Institución"),
    )
    titulo = models.CharField(max_length=150, verbose_name=_("Título del evento"))
    descripcion = models.TextField(blank=True, default='', verbose_name=_("Descripción"))
    categoria = models.CharField(max_length=20, choices=Categoria.choices, default=Categoria.INSTITUCIONAL)
    fecha = models.DateField(verbose_name=_("Fecha (de este año)"))
    recurrente_anual = models.BooleanField(
        default=False,
        verbose_name=_("¿Se repite cada año?"),
        help_text="Actívalo para festivos o celebraciones que caen en la misma fecha todos los años (ej. Amor y Amistad, fiestas patronales).",
    )
    dias_aviso_previo = models.PositiveSmallIntegerField(
        default=3, verbose_name=_("Días de aviso previo"),
        help_text="Con cuántos días de anticipación se notifica a los destinatarios.",
    )

    # A quién avisar — checkboxes simples, pensado para coordinación no técnica.
    para_docentes = models.BooleanField(default=True, verbose_name=_("Avisar a docentes"))
    para_estudiantes = models.BooleanField(default=True, verbose_name=_("Avisar a estudiantes"))
    para_familiares = models.BooleanField(default=True, verbose_name=_("Avisar a familiares"))
    para_coordinadores = models.BooleanField(default=True, verbose_name=_("Avisar a coordinadores/administrador"))

    activo = models.BooleanField(default=True, verbose_name=_("¿Activo?"))
    ultima_alerta_fecha = models.DateField(
        null=True, blank=True,
        verbose_name=_("Fecha de la última ocurrencia ya avisada"),
        help_text="La usa el sistema para no enviar la misma alerta dos veces — no editar a mano.",
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='eventos_institucionales_creados',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha']
        verbose_name = _("Evento Institucional")
        verbose_name_plural = _("Eventos Institucionales")

    def __str__(self):
        return f"{self.titulo} ({self.fecha:%d/%m})"

    def proxima_ocurrencia(self, desde=None):
        """Fecha de la próxima vez que cae este evento. Para eventos no
        recurrentes, es simplemente `fecha`. Para recurrentes, recalcula
        el mes/día sobre el año actual (o el siguiente, si ya pasó)."""
        hoy = desde or timezone.localdate()
        if not self.recurrente_anual:
            return self.fecha
        try:
            candidata = self.fecha.replace(year=hoy.year)
        except ValueError:
            candidata = self.fecha.replace(year=hoy.year, day=28)  # 29-feb en año no bisiesto
        if candidata < hoy:
            try:
                candidata = candidata.replace(year=hoy.year + 1)
            except ValueError:
                candidata = candidata.replace(year=hoy.year + 1, day=28)
        return candidata


# ══════════════════════════════════════════════════════════════════════════════
#  MÓDULO: HALU STEAM — Proyectos e Insignias (Fase 2)
#  Aprendizaje Basado en Proyectos (ABP) + microcredenciales verificables.
#  Un ProyectoSTEAM se enlaza 1 a 1 a una ActividadCalificable existente, así
#  que se califica desde el Libro de Notas de siempre (ya filtrado por
#  énfasis) — no hay una pantalla de calificación paralela.
# ══════════════════════════════════════════════════════════════════════════════

class ProyectoSTEAM(models.Model):
    class Estado(models.TextChoices):
        PLANEACION = 'PLANEACION', _('En planeación')
        EN_CURSO = 'EN_CURSO', _('En curso')
        ENTREGADO = 'ENTREGADO', _('Entregado')
        EVALUADO = 'EVALUADO', _('Evaluado')

    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, related_name='proyectos_steam', verbose_name=_("Institución"))
    curso = models.ForeignKey('Curso', on_delete=models.CASCADE, related_name='proyectos_steam', verbose_name=_("Curso"))
    actividad_calificable = models.OneToOneField(
        'ActividadCalificable', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='proyecto_steam', verbose_name=_("Actividad calificable enlazada"),
    )
    titulo = models.CharField(max_length=200, verbose_name=_("Título del proyecto"))
    reto = models.TextField(blank=True, verbose_name=_("Reto / pregunta guía"), help_text=_("¿Qué problema real intenta resolver este proyecto?"))
    fecha_inicio = models.DateField(null=True, blank=True, verbose_name=_("Fecha de inicio"))
    fecha_entrega = models.DateField(null=True, blank=True, verbose_name=_("Fecha de entrega"))
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PLANEACION, verbose_name=_("Estado"))
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='proyectos_steam_creados', verbose_name=_("Creado por"))
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Proyecto STEAM")
        verbose_name_plural = _("Proyectos STEAM")
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.titulo} ({self.curso})"

    @property
    def porcentaje_hitos_completados(self):
        total = self.hitos.count()
        if not total:
            return 0
        return round(self.hitos.filter(completado=True).count() * 100 / total)


class HitoProyecto(models.Model):
    proyecto = models.ForeignKey(ProyectoSTEAM, on_delete=models.CASCADE, related_name='hitos', verbose_name=_("Proyecto"))
    titulo = models.CharField(max_length=200, verbose_name=_("Hito"))
    fecha_limite = models.DateField(null=True, blank=True, verbose_name=_("Fecha límite"))
    completado = models.BooleanField(default=False, verbose_name=_("Completado"))
    orden = models.PositiveIntegerField(default=0, verbose_name=_("Orden"))

    class Meta:
        verbose_name = _("Hito de Proyecto")
        verbose_name_plural = _("Hitos de Proyecto")
        ordering = ['orden', 'fecha_limite']

    def __str__(self):
        return self.titulo


class ParticipanteProyecto(models.Model):
    proyecto = models.ForeignKey(ProyectoSTEAM, on_delete=models.CASCADE, related_name='participantes', verbose_name=_("Proyecto"))
    estudiante = models.ForeignKey('Estudiante', on_delete=models.CASCADE, related_name='proyectos_steam_participados', verbose_name=_("Estudiante"))
    rol = models.CharField(max_length=100, blank=True, verbose_name=_("Rol en el equipo"), help_text=_("Ej: Líder, Diseñador, Documentador."))

    class Meta:
        verbose_name = _("Participante de Proyecto")
        verbose_name_plural = _("Participantes de Proyecto")
        unique_together = ('proyecto', 'estudiante')
        ordering = ['estudiante__usuario__last_name']

    def __str__(self):
        return f"{self.estudiante} — {self.rol or 'Participante'}"


class EvidenciaProyecto(models.Model):
    proyecto = models.ForeignKey(ProyectoSTEAM, on_delete=models.CASCADE, related_name='evidencias', verbose_name=_("Proyecto"))
    titulo = models.CharField(max_length=200, verbose_name=_("Título de la evidencia"))
    url = models.URLField(verbose_name=_("Enlace (foto, video o documento)"), help_text=_("Solo URLs http:// o https://"))
    subido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='evidencias_steam_subidas', verbose_name=_("Subido por"))
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Evidencia de Proyecto")
        verbose_name_plural = _("Evidencias de Proyecto")
        ordering = ['-creado_en']

    def __str__(self):
        return self.titulo


class Insignia(models.Model):
    """Catálogo de microcredenciales STEAM por institución (ej. 'Programó su
    primer robot'). Mismo patrón que Enfasis: catálogo por institución; se
    otorga a estudiantes vía InsigniaObtenida."""
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, related_name='insignias', verbose_name=_("Institución"))
    nombre = models.CharField(max_length=100, verbose_name=_("Nombre de la insignia"))
    descripcion = models.TextField(blank=True, verbose_name=_("Criterio para obtenerla"))
    icono = models.CharField(max_length=40, default='bi-award-fill', verbose_name=_("Ícono"), help_text=_("Clase de Bootstrap Icons, ej. 'bi-award-fill'."))
    color = models.CharField(max_length=7, default='#7c3aed', verbose_name=_("Color"), help_text=_("Color hexadecimal, ej. #7c3aed."))
    activo = models.BooleanField(default=True, verbose_name=_("Activa"))

    class Meta:
        verbose_name = _("Insignia")
        verbose_name_plural = _("Insignias")
        unique_together = ('institucion', 'nombre')
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class InsigniaObtenida(models.Model):
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, related_name='insignias_otorgadas', verbose_name=_("Institución"))
    insignia = models.ForeignKey(Insignia, on_delete=models.CASCADE, related_name='otorgadas', verbose_name=_("Insignia"))
    estudiante = models.ForeignKey('Estudiante', on_delete=models.CASCADE, related_name='insignias_obtenidas', verbose_name=_("Estudiante"))
    proyecto = models.ForeignKey(ProyectoSTEAM, on_delete=models.SET_NULL, null=True, blank=True, related_name='insignias_otorgadas', verbose_name=_("Proyecto de origen (opcional)"))
    otorgada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='insignias_steam_otorgadas', verbose_name=_("Otorgada por"))
    nota = models.CharField(max_length=255, blank=True, verbose_name=_("Comentario (opcional)"))
    fecha_obtenida = models.DateTimeField(auto_now_add=True, verbose_name=_("Fecha obtenida"))

    class Meta:
        verbose_name = _("Insignia Obtenida")
        verbose_name_plural = _("Insignias Obtenidas")
        ordering = ['-fecha_obtenida']

    def __str__(self):
        return f"{self.insignia} → {self.estudiante}"
