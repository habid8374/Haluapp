# admisiones/models.py
from django.db import models, transaction
from django.utils import timezone
import uuid
from django.urls import reverse
from gestion_academica.models import (   # Importamos Grado para saber a cuál aspira
    Grado, Usuario, Estudiante,
    TIPO_DOCUMENTO_CHOICES, GRUPO_SANGUINEO_CHOICES,
    CaracterizacionEstudiante,
)
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
import sys
import os
import unicodedata   
import logging




# Obtenemos el modelo de Usuario personalizado
Usuario = get_user_model()

# Las importaciones de envío de correo se quedan en utils.py, no son necesarias aquí.

class Aspirante(models.Model):
    class EstadoAdmision(models.TextChoices):
        INSCRITO = 'INSCRITO', 'Inscrito / Pendiente de Revisión'
        EN_PROCESO = 'EN_PROCESO', 'En Proceso de Admisión'
        ADMITIDO = 'ADMITIDO', 'Admitido'
        APROBADO_MATRICULA = 'APROBADO_MATRICULA', 'Aprobado para Matrícula'
        RECHAZADO = 'RECHAZADO', 'No Admitido'
        MATRICULADO = 'MATRICULADO', 'Matriculado'

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', 
        on_delete=models.CASCADE, 
        verbose_name="Institución a la que aplica",
        related_name="aspirantes" # Apodo único
    )
    nombres = models.CharField(max_length=150, verbose_name="Nombres Completos")
    apellidos = models.CharField(max_length=150, verbose_name="Apellidos Completos")
    numero_documento = models.CharField(max_length=20, verbose_name="Número de Documento")
    fecha_nacimiento = models.DateField(verbose_name="Fecha de Nacimiento", null=True, blank=True)
    email_contacto = models.EmailField(verbose_name="Email de Contacto Principal")
    telefono_contacto = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono de Contacto")
    grado_aspira = models.ForeignKey(Grado, on_delete=models.SET_NULL, null=True, verbose_name="Grado al que Aspira")
    estado = models.CharField(max_length=20, choices=EstadoAdmision.choices, default=EstadoAdmision.INSCRITO)
    requiere_pago_inscripcion = models.BooleanField(default=True)
    colegio_procedencia = models.CharField(max_length=255, blank=True, null=True, verbose_name="Colegio de Procedencia")
    municipio_ciudad = models.CharField(max_length=150, blank=True, null=True, verbose_name="Municipio/Ciudad")
    departamento = models.CharField(max_length=150, blank=True, null=True, verbose_name="Departamento")
    sexo = models.CharField(max_length=1, choices=[('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro')])

    # ── Campos del Observador del Estudiante ────────────────────────────────
    tipo_documento = models.CharField(
        max_length=2, choices=TIPO_DOCUMENTO_CHOICES,
        blank=True, null=True, verbose_name="Tipo de Documento"
    )
    lugar_nacimiento = models.CharField(
        max_length=150, blank=True, null=True, verbose_name="Lugar de Nacimiento"
    )
    grupo_sanguineo = models.CharField(
        max_length=3, choices=GRUPO_SANGUINEO_CHOICES,
        blank=True, null=True, verbose_name="Grupo Sanguíneo"
    )
    eps = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="EPS / Entidad de Salud"
    )
    discapacidad = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name="Discapacidad (si aplica)",
        help_text="Dejar en blanco si no aplica."
    )
    direccion = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="Dirección de Residencia"
    )
    # ────────────────────────────────────────────────────────────────────────

    # ── Caracterización SIMAT/SIMPADE (Fase 2) ──────────────────────────────
    # Se capturan en la admisión y se vuelcan al CaracterizacionEstudiante al
    # crear el estudiante (procesar_inscripcion_completa). Todos opcionales.
    pais_origen = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="País de origen",
        help_text="Para aspirantes migrantes. Dejar en blanco si es Colombia.",
    )
    zona_residencia = models.CharField(
        max_length=10, choices=CaracterizacionEstudiante.ZonaResidencia.choices,
        blank=True, null=True, verbose_name="Zona de residencia",
    )
    regimen_salud = models.CharField(
        max_length=15, choices=CaracterizacionEstudiante.RegimenSalud.choices,
        blank=True, null=True, verbose_name="Régimen de salud",
    )
    discapacidad_categoria = models.CharField(
        max_length=25, choices=CaracterizacionEstudiante.Discapacidad.choices,
        blank=True, null=True, verbose_name="Categoría de discapacidad (MEN)",
    )
    capacidad_excepcional = models.CharField(
        max_length=25, choices=CaracterizacionEstudiante.CapacidadExcepcional.choices,
        blank=True, null=True, verbose_name="Capacidad / talento excepcional",
    )
    grupo_etnico = models.CharField(
        max_length=20, choices=CaracterizacionEstudiante.GrupoEtnico.choices,
        blank=True, null=True, verbose_name="Grupo étnico",
    )
    estrato = models.CharField(
        max_length=1, choices=CaracterizacionEstudiante.Estrato.choices,
        blank=True, null=True, verbose_name="Estrato socioeconómico",
    )
    sisben_grupo = models.CharField(
        max_length=10, blank=True, null=True, verbose_name="Grupo SISBÉN",
        help_text="Clasificación SISBÉN IV (ej: A1, B2, C3).",
    )
    sisben_puntaje = models.DecimalField(
        max_digits=6, decimal_places=2, blank=True, null=True,
        verbose_name="Puntaje SISBÉN",
    )
    victima_conflicto = models.BooleanField(
        default=False, verbose_name="¿Víctima del conflicto armado?",
    )
    tipo_poblacion_victima = models.CharField(
        max_length=20, choices=CaracterizacionEstudiante.TipoPoblacionVictima.choices,
        blank=True, null=True, verbose_name="Tipo de población víctima",
    )
    srpa = models.BooleanField(
        default=False,
        verbose_name="¿Sistema de Responsabilidad Penal Adolescente (SRPA)?",
    )
    apoyo_academico_especial = models.BooleanField(
        default=False, verbose_name="¿Requiere apoyo académico especial?",
    )

    # ════════════════════════════════════════════════════════════════════════
    #  SIMAT / SIMPADE — Fase 1 (captura de matrícula para el MEN).
    #  Campos ADITIVOS y opcionales. Los `nombres`/`apellidos` de arriba se
    #  conservan; aquí se guardan separados como los exige el Anexo 6A.
    #  Las FK apuntan a los catálogos oficiales (app simat) para que el
    #  usuario SELECCIONE (nunca escriba) y no falle la importación.
    # ════════════════════════════════════════════════════════════════════════
    SIMAT_JORNADA_CHOICES = [
        ('MANANA', 'Mañana'), ('TARDE', 'Tarde'), ('NOCHE', 'Noche'),
        ('UNICA', 'Única'), ('COMPLETA', 'Completa'), ('FIN_DE_SEMANA', 'Fin de semana'),
    ]
    # Identificación (nombres/apellidos separados)
    primer_nombre = models.CharField(max_length=60, blank=True, verbose_name="Primer nombre")
    segundo_nombre = models.CharField(max_length=60, blank=True, verbose_name="Segundo nombre")
    primer_apellido = models.CharField(max_length=60, blank=True, verbose_name="Primer apellido")
    segundo_apellido = models.CharField(max_length=60, blank=True, verbose_name="Segundo apellido")
    lugar_expedicion_departamento = models.ForeignKey(
        'simat.Departamento', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="Expedición documento · Departamento")
    lugar_expedicion_municipio = models.ForeignKey(
        'simat.Municipio', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="Expedición documento · Municipio")
    nacionalidad = models.CharField(max_length=60, blank=True, verbose_name="Nacionalidad")
    # Nacimiento (estructurado con código DANE)
    pais_nacimiento = models.CharField(max_length=60, blank=True, verbose_name="País de nacimiento")
    departamento_nacimiento = models.ForeignKey(
        'simat.Departamento', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="Nacimiento · Departamento")
    municipio_nacimiento = models.ForeignKey(
        'simat.Municipio', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="Nacimiento · Municipio")
    # Residencia (estructurada con código DANE)
    departamento_residencia = models.ForeignKey(
        'simat.Departamento', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="Residencia · Departamento")
    municipio_residencia = models.ForeignKey(
        'simat.Municipio', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="Residencia · Municipio")
    barrio = models.CharField(max_length=150, blank=True, verbose_name="Barrio")
    campesino = models.BooleanField(default=False, verbose_name="¿Población campesina?")
    # Caracterización detallada (códigos oficiales SIMAT)
    etnia_simat = models.ForeignKey(
        'simat.Etnia', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="Etnia (código SIMAT)")
    resguardo = models.ForeignKey(
        'simat.Resguardo', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="Resguardo indígena")
    eps_simat = models.ForeignKey(
        'simat.EPS', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="EPS (código SIMAT)")
    # Matrícula
    sede = models.ForeignKey(
        'simat.Sede', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="Sede")
    jornada = models.CharField(max_length=15, choices=SIMAT_JORNADA_CHOICES, blank=True, verbose_name="Jornada")
    grupo = models.CharField(max_length=20, blank=True, verbose_name="Grupo/Curso")
    modelo_educativo = models.CharField(max_length=60, blank=True, verbose_name="Modelo/Metodología educativa")
    fuente_recursos = models.CharField(max_length=60, blank=True, verbose_name="Fuente de recursos")
    internado = models.CharField(max_length=20, blank=True, verbose_name="Internado")
    matricula_contratada = models.BooleanField(default=False, verbose_name="¿Matrícula contratada?")
    repitente = models.BooleanField(default=False, verbose_name="¿Repitente?")
    situacion_academica_anterior = models.CharField(
        max_length=60, blank=True, verbose_name="Situación académica año anterior")
    # Identificadores que devuelve el SIMAT (se llenan al re-importar el reporte)
    simat_per_id = models.CharField(max_length=20, blank=True, verbose_name="SIMAT · PER_ID")
    simat_nui = models.CharField(max_length=30, blank=True, verbose_name="SIMAT · NUI")
    # ────────────────────────────────────────────────────────────────────────

    fecha_inscripcion = models.DateTimeField(auto_now_add=True)
    access_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    usuario = models.OneToOneField(
        Usuario, 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='perfil_aspirante' # Apodo único
    )
    estudiante_creado = models.OneToOneField(
        Estudiante, 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='aspirante_origen' # Apodo único
    )
    
    # Campo para el enlace directo al cobro de inscripción
    cuenta_pago_inscripcion = models.OneToOneField(
        'finanzas.CuentaPorCobrarEstudiante',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='aspirante_inscripcion' # Apodo único
    )

    # Trazabilidad: si el aspirante vino de una importación masiva, queda enlazado
    # al lote para poder auditar, filtrar y descargar reportes posteriores.
    lote_importacion = models.ForeignKey(
        'admisiones.LoteImportacionAspirantes',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='aspirantes_creados',
        verbose_name="Lote de importación de origen",
    )

    class Meta:
        verbose_name = "Aspirante"
        verbose_name_plural = "Aspirantes"
        ordering = ["-fecha_inscripcion"]
        constraints = [
            # SaaS multi-institución: el documento es único DENTRO de cada institución.
            # Se aplica solo cuando hay valor no vacío para no bloquear datos legados.
            models.UniqueConstraint(
                fields=["institucion", "numero_documento"],
                condition=~Q(numero_documento=""),
                name="aspirante_unico_doc_por_institucion",
            ),
        ]
        indexes = [
            models.Index(fields=["institucion", "estado"]),
            models.Index(fields=["institucion", "numero_documento"]),
        ]

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"

    def get_portal_url(self):
        return reverse('admisiones:portal_postulante', kwargs={'token': self.access_token})
        
    @transaction.atomic
    def procesar_inscripcion_completa(self):
        """Crea perfiles (Usuario, Estudiante preliminar) y la cuenta de cobro de inscripción.

        Devuelve ``ResultadoInscripcion(aspirante, cobro_inscripcion)`` para que
        las vistas e importaciones masivas puedan reportar al operador
        problemas de configuración (por ejemplo, si falta el ``ConceptoPago``)
        en lugar de fallar silenciosamente.
        """
        from .utils import (
            crear_cuenta_cobro_inscripcion,
            ResultadoCobroInscripcion,
            ResultadoInscripcion,
        )

        # 1. ¿Ya existe un estudiante con este documento en la institución?
        estudiante_existente = Estudiante.objects.filter(
            institucion=self.institucion,
            documento_identidad=self.numero_documento
        ).first()

        if estudiante_existente:
            estudiante_obj = estudiante_existente
            usuario_obj = estudiante_existente.usuario
        else:
            primer_nombre = self.nombres.split()[0]
            base_username = unicodedata.normalize('NFKD', primer_nombre.lower()).encode('ascii', 'ignore').decode('utf-8')
            username_final = f"{base_username}@halu.com"
            contador = 1
            while Usuario.objects.filter(username=username_final).exists():
                username_final = f"{base_username}{contador}@halu.com"
                contador += 1

            usuario_obj, _ = Usuario.objects.get_or_create(
                username=username_final,
                defaults={
                    'first_name': self.nombres, 'last_name': self.apellidos,
                    'email': self.email_contacto, 'rol': 'aspirante',
                    'institucion_asociada': self.institucion
                }
            )

            estudiante_obj = Estudiante.objects.create(
                usuario=usuario_obj,
                institucion=self.institucion,
                documento_identidad=self.numero_documento,
                tipo_documento=self.tipo_documento or None,
                fecha_nacimiento=self.fecha_nacimiento,
                grado_actual=self.grado_aspira,
                sexo=self.sexo,
                lugar_nacimiento=self.lugar_nacimiento or None,
                grupo_sanguineo=self.grupo_sanguineo or None,
                eps=self.eps or None,
                discapacidad=self.discapacidad or None,
                municipio_ciudad=self.municipio_ciudad or None,
                departamento=self.departamento or None,
                colegio_procedencia=self.colegio_procedencia or None,
                direccion=self.direccion or None,
                activo=False  # El estudiante empieza inactivo
            )

        # 2. Vincula perfiles al aspirante
        self.usuario = usuario_obj
        self.estudiante_creado = estudiante_obj
        self.save(update_fields=['usuario', 'estudiante_creado'])

        # 2.b Vuelca la caracterización SIMAT/SIMPADE capturada en la admisión.
        #     Se hace para ambos casos (estudiante nuevo o existente). Solo
        #     sobrescribe un campo del estudiante si el aspirante trae valor,
        #     para no borrar datos ya cargados manualmente.
        self._sincronizar_caracterizacion(estudiante_obj)

        # 3. Lógica de cobro — solo si el módulo financiero está activo para la
        #    institución (si no, los pagos se manejan por fuera de la plataforma).
        if self.requiere_pago_inscripcion and getattr(self.institucion, 'usa_modulo_financiero', True):
            resultado_cobro = crear_cuenta_cobro_inscripcion(self)
            if resultado_cobro.es_exito:
                self.cuenta_pago_inscripcion = resultado_cobro.cuenta
                self.save(update_fields=['cuenta_pago_inscripcion'])
        else:
            resultado_cobro = ResultadoCobroInscripcion(
                cuenta=None,
                motivo_falla="no_requiere",
                mensaje="El aspirante no requiere pago de inscripción.",
            )

        return ResultadoInscripcion(
            aspirante=self,
            cobro_inscripcion=resultado_cobro,
        )

    def _sincronizar_caracterizacion(self, estudiante):
        """Crea o actualiza el CaracterizacionEstudiante a partir del aspirante.

        Copia los campos planos de caracterización capturados en la admisión.
        Idempotente: solo escribe un campo si el aspirante trae valor, para no
        pisar datos cargados manualmente en el estudiante. No falla la
        inscripción si algo sale mal (la caracterización es complementaria).
        """
        try:
            caracterizacion, _ = CaracterizacionEstudiante.objects.get_or_create(
                estudiante=estudiante,
                defaults={'institucion': estudiante.institucion},
            )
            campos = [
                'pais_origen', 'zona_residencia', 'regimen_salud',
                'discapacidad_categoria', 'capacidad_excepcional', 'grupo_etnico',
                'estrato', 'sisben_grupo', 'sisben_puntaje',
                'tipo_poblacion_victima',
            ]
            actualizados = []
            for campo in campos:
                valor = getattr(self, campo, None)
                if valor not in (None, ''):
                    setattr(caracterizacion, campo, valor)
                    actualizados.append(campo)
            # Los booleanos siempre se reflejan (False es un valor válido).
            for campo in ('victima_conflicto', 'srpa', 'apoyo_academico_especial'):
                setattr(caracterizacion, campo, getattr(self, campo, False))
                actualizados.append(campo)
            caracterizacion.institucion = estudiante.institucion
            caracterizacion.save()
        except Exception:
            logging.getLogger(__name__).exception(
                "No se pudo sincronizar la caracterización del aspirante %s", self.pk
            )

    @transaction.atomic
    def matricular(self):
        """Matricula al aspirante: activa el estudiante, asigna rol, genera cuentas.

        Devuelve una tupla ``(estudiante, ResultadoSincronizacionCuentas)``
        para que la vista que invoca pueda mostrar al admin un mensaje
        accionable si no se pudieron crear las cuentas (p. ej. faltan
        ConceptoPago de pensión configurados para el nivel).

        Backward-compatible: los callers viejos que no leen el resultado
        siguen funcionando porque el primer elemento sigue siendo el
        estudiante.
        """
        import logging
        from finanzas.models import CuentaPorCobrarEstudiante
        from finanzas.managers import ResultadoSincronizacionCuentas

        log = logging.getLogger(__name__)

        estudiante_a_matricular = self.estudiante_creado
        if not estudiante_a_matricular:
            raise Exception("Error: No se encontró un perfil de estudiante para matricular.")

        # 1. Activamos el estudiante y actualizamos su grado
        estudiante_a_matricular.activo = True
        estudiante_a_matricular.grado_actual = self.grado_aspira
        estudiante_a_matricular.save()

        # 2. Actualizamos el rol del usuario
        if estudiante_a_matricular.usuario:
            usuario = estudiante_a_matricular.usuario
            usuario.rol = 'estudiante'
            usuario.save(update_fields=['rol'])

        # 3. Actualizamos el estado del aspirante
        self.estado = self.EstadoAdmision.MATRICULADO
        self.save(update_fields=['estado'])

        # 4. Intentamos crear matrícula + 10 pensiones. Si falla, NO revertimos
        # la matrícula: el alumno sigue activo, pero devolvemos el motivo en
        # el resultado para que la UI lo muestre al admin.
        try:
            resultado_cuentas = (
                CuentaPorCobrarEstudiante.objects
                .sincronizar_cuentas_automaticas(estudiante_a_matricular)
            )
            if resultado_cuentas.es_exito:
                log.info(
                    "Sincronización OK para estudiante %s: %s",
                    estudiante_a_matricular.pk, resultado_cuentas.resumen(),
                )
            else:
                log.warning(
                    "Sincronización con problemas para estudiante %s: %s",
                    estudiante_a_matricular.pk, resultado_cuentas.resumen(),
                )
        except Exception as e:  # noqa: BLE001
            log.error(
                "FALLO SECUNDARIO al sincronizar las pensiones para %s: %s",
                estudiante_a_matricular.pk, e, exc_info=True,
            )
            # Devolvemos un resultado sintético para no romper a los callers
            # que esperan la tupla.
            resultado_cuentas = ResultadoSincronizacionCuentas(
                estudiante=estudiante_a_matricular,
                motivo_falla="error_inesperado",
                mensaje=f"Error inesperado al sincronizar cuentas: {e}",
            )

        return estudiante_a_matricular, resultado_cuentas


class DocumentoRequerido(models.Model):
    """
    Define un tipo de documento que una institución requiere para la admisión.
    Ahora es específico para cada institución.
    """
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', 
        on_delete=models.CASCADE,
        verbose_name="Institución que lo requiere"
    )
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Documento")
    descripcion = models.TextField(blank=True, help_text="Instrucciones para el padre de familia sobre este documento.")
    es_obligatorio = models.BooleanField(default=True)
    grados_aplicables = models.ManyToManyField(
        Grado,
        verbose_name="Grados a los que aplica",
        help_text="Selecciona todos los grados que requieren este documento."
    )
    
    class Meta:
        verbose_name = "Documento Requerido"
        verbose_name_plural = "Documentos Requeridos"
        # Un mismo nombre de documento no puede repetirse en la misma institución
        unique_together = ('institucion', 'nombre')

    def __str__(self):
        return f"{self.nombre} ({self.institucion.nombre})"


def ruta_documento_aspirante(instance, filename):
    """
    Genera una ruta de subida única para los documentos de un aspirante
    para evitar colisiones de nombres.
    Ej: documentos_aspirantes/123-ana-gomez/acta_nacimiento.pdf
    """
    # Limpia el nombre del aspirante para usarlo en la ruta
    nombre_limpio = "".join(c for c in instance.aspirante.nombres.lower() if c.isalnum() or c in (' ', '_')).rstrip()
    return f"documentos_aspirantes/{instance.aspirante.id}-{nombre_limpio}/{filename}"

class DocumentoEntregado(models.Model):
    """
    Representa un archivo específico subido por un aspirante,
    vinculado a un tipo de documento requerido.
    """
    ESTADOS_DOCUMENTO = (
        ('subido', 'Subido por Postulante'),
        ('en_revision', 'En Revisión'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado - Se requiere nueva carga'),
    )
    
    aspirante = models.ForeignKey(Aspirante, on_delete=models.CASCADE, related_name="documentos_entregados")
    documento_requerido = models.ForeignKey(DocumentoRequerido, on_delete=models.PROTECT)
    archivo = models.FileField(upload_to=ruta_documento_aspirante)
    estado = models.CharField(max_length=20, choices=ESTADOS_DOCUMENTO, default='subido')
    fecha_subida = models.DateTimeField(auto_now_add=True)
    observaciones_revision = models.TextField(blank=True, help_text="Comentarios del personal de admisiones (ej: 'El documento no es legible').")
    
    # Campo denormalizado para mejorar rendimiento en las consultas
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', 
        on_delete=models.CASCADE, 
        editable=False,
        
    )

    class Meta:
        verbose_name = "Documento Entregado"
        verbose_name_plural = "Documentos Entregados"
        # Un aspirante solo puede subir un tipo de documento una vez
        unique_together = ('aspirante', 'documento_requerido')

    def __str__(self):
        return f"{self.documento_requerido.nombre} de {self.aspirante}"

    def save(self, *args, **kwargs):
        # Asigna automáticamente la institución del aspirante antes de guardar.
        if not self.institucion_id and self.aspirante:
            self.institucion = self.aspirante.institucion
        super().save(*args, **kwargs)       

class HorarioDisponible(models.Model):
    # --- CAMBIO 1: Añadir la institución ---
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', 
        on_delete=models.CASCADE,
        verbose_name="Institución"
    )

    TIPO_CITA_CHOICES = (
        ('entrevista', 'Entrevista con Admisiones'),
        ('psicologia', 'Entrevista con Psicología'),
        ('examen', 'Examen de Admisión'),
    )
    tipo_cita = models.CharField(max_length=20, choices=TIPO_CITA_CHOICES)
    
    # --- CAMBIO 2: Quitar unique=True ---
    fecha_hora_inicio = models.DateTimeField(verbose_name="Fecha y Hora de Inicio")
    
    duracion_minutos = models.PositiveIntegerField(default=30, help_text="Duración de la cita en minutos.")
    cupos_disponibles = models.PositiveIntegerField(default=1, help_text="Cuántos aspirantes pueden agendarse en este horario (usualmente 1).")
    entrevistador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        limit_choices_to=Q(rol='docente') | Q(rol='coordinador') | Q(rol='administrador'),
        verbose_name="Entrevistador/Responsable"
    )

    def __str__(self):
        return f"{self.get_tipo_cita_display()} - {self.fecha_hora_inicio.strftime('%d/%m/%Y %H:%M')}"

    # ... (Tus @property se mantienen igual)
    @property
    def fecha_hora_fin(self):
        return self.fecha_hora_inicio + timezone.timedelta(minutes=self.duracion_minutos)
    
    @property
    def cupos_ocupados(self):
        return self.citas_agendadas.count()

    @property
    def esta_disponible(self):
        return self.cupos_ocupados < self.cupos_disponibles

    class Meta:
        verbose_name = "Horario Disponible para Cita"
        verbose_name_plural = "Horarios Disponibles para Citas"
        ordering = ['fecha_hora_inicio']
        # --- CAMBIO 3: Añadir unicidad por institución y tipo/hora ---
        unique_together = ('institucion', 'fecha_hora_inicio', 'tipo_cita')


class CitaAgendada(models.Model):
    """
    Vincula a un Aspirante con un HorarioDisponible que ha reservado.
    """
    aspirante = models.OneToOneField(Aspirante, on_delete=models.CASCADE, related_name="cita_agendada")
    horario = models.ForeignKey(HorarioDisponible, on_delete=models.PROTECT, related_name="citas_agendadas")
    fecha_agendamiento = models.DateTimeField(auto_now_add=True)
    notas_adicionales = models.TextField(blank=True, help_text="Notas del padre de familia al momento de agendar.")
    estado = models.CharField(max_length=20, default='agendada', choices=[('agendada', 'Agendada'), ('completada', 'Completada'), ('cancelada', 'Cancelada')])

    # Campo denormalizado para mejorar rendimiento
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', 
        on_delete=models.CASCADE, 
        editable=False,
        
    )

    class Meta:
        verbose_name = "Cita Agendada"
        verbose_name_plural = "Citas Agendadas"

    def __str__(self):
        return f"Cita de {self.aspirante} para el {self.horario.fecha_hora_inicio.strftime('%d/%m/%Y %H:%M')}"

    def save(self, *args, **kwargs):
        # Asigna automáticamente la institución del aspirante antes de guardar.
        if not self.institucion_id and self.aspirante:
            self.institucion = self.aspirante.institucion
        super().save(*args, **kwargs)       

class AspiranteConDocumentos(Aspirante):
    """
    Este es un Modelo Proxy. Usa la misma tabla de base de datos que Aspirante,
    pero nos permite crear una vista de administrador separada y personalizada para él.
    """
    class Meta:
        proxy = True
        verbose_name = "Revisión de Documento por Aspirante"
        verbose_name_plural = "Revisión de Documentos por Aspirante"


def _ruta_archivo_lote_importacion(instance, filename):
    """Ruta de subida para los Excel de importación de aspirantes."""
    fecha = (instance.fecha_creacion or timezone.now()).strftime("%Y/%m")
    inst_id = instance.institucion_id or "sin_inst"
    return f"admisiones/importaciones/{inst_id}/{fecha}/{filename}"


class LoteImportacionAspirantes(models.Model):
    """Auditoría y orquestación de una carga masiva de aspirantes desde Excel.

    Cada subida del usuario crea un Lote; una tarea Celery la procesa fila a fila
    en background, actualiza el progreso aquí y emite eventos por WebSocket. El
    propio archivo queda persistido en MEDIA para poder reimprocesar o descargar.
    """

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente de procesar"
        EN_PROCESO = "EN_PROCESO", "En proceso"
        COMPLETADO = "COMPLETADO", "Completado"
        FALLIDO = "FALLIDO", "Fallido"
        CANCELADO = "CANCELADO", "Cancelado"

    institucion = models.ForeignKey(
        "finanzas.InstitucionEducativa",
        on_delete=models.CASCADE,
        related_name="lotes_importacion_aspirantes",
        verbose_name="Institución",
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="lotes_importacion_aspirantes_creados",
        verbose_name="Creado por",
    )
    archivo = models.FileField(
        upload_to=_ruta_archivo_lote_importacion,
        verbose_name="Archivo Excel",
        null=True, blank=True,
    )
    archivo_bytes = models.BinaryField(
        null=True, blank=True,
        verbose_name="Contenido del archivo (bytes)",
        help_text="Copia en BD para que Celery pueda leerlo sin acceso al disco.",
    )
    nombre_original = models.CharField(max_length=255, blank=True, verbose_name="Nombre original")
    dry_run = models.BooleanField(
        default=False,
        verbose_name="Modo simulación (no crea registros)",
        help_text="Cuando está marcado, valida y reporta errores sin persistir aspirantes.",
    )

    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
        verbose_name="Estado",
    )
    task_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="ID de tarea Celery",
        help_text="UUID de la tarea Celery que procesa este lote (necesario para revoke).",
    )
    cancelacion_solicitada = models.BooleanField(
        default=False,
        verbose_name="Cancelación solicitada",
        help_text=(
            "Marcado por el usuario al pedir cancelar. La tarea verifica este flag "
            "entre filas y termina limpiamente."
        ),
    )

    total_filas = models.PositiveIntegerField(default=0)
    filas_procesadas = models.PositiveIntegerField(default=0)
    filas_exitosas = models.PositiveIntegerField(default=0)
    filas_fallidas = models.PositiveIntegerField(default=0)
    filas_con_advertencia = models.PositiveIntegerField(
        default=0,
        verbose_name="Filas con advertencia",
        help_text=(
            "Filas creadas correctamente pero con problemas no críticos "
            "(p. ej. el aspirante se creó pero no se generó la cuenta de "
            "inscripción por configuración faltante)."
        ),
    )

    errores = models.JSONField(
        default=list, blank=True,
        verbose_name="Errores y advertencias por fila",
        help_text=(
            "Lista de diccionarios: {tipo, fila, documento, mensaje}. "
            "tipo='error' detiene la fila; tipo='warning' permite continuar."
        ),
    )
    mensaje_error_general = models.TextField(blank=True, verbose_name="Mensaje de error general")

    resumen_correos = models.JSONField(
        null=True, blank=True, default=None,
        verbose_name="Resumen del último envío de correos",
        help_text=(
            "Almacena el resultado del último envío/reenvío masivo de correos: "
            "{tipo, fecha, ok, errores_count, omitidos, total, detalle_errores[]}."
        ),
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_inicio = models.DateTimeField(null=True, blank=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_creacion"]
        verbose_name = "Lote de importación de aspirantes"
        verbose_name_plural = "Lotes de importación de aspirantes"
        indexes = [
            models.Index(fields=["institucion", "-fecha_creacion"]),
            models.Index(fields=["estado"]),
        ]

    def __str__(self):
        return f"Lote #{self.pk} ({self.estado}) — {self.nombre_original or 'sin nombre'}"

    @property
    def progreso_porcentaje(self):
        if not self.total_filas:
            return 0
        return min(100, int(round((self.filas_procesadas * 100) / self.total_filas)))

    @property
    def esta_finalizado(self):
        return self.estado in (
            self.Estado.COMPLETADO,
            self.Estado.FALLIDO,
            self.Estado.CANCELADO,
        )

    @property
    def puede_cancelarse(self):
        return self.estado in (self.Estado.PENDIENTE, self.Estado.EN_PROCESO)

    @property
    def puede_reintentarse(self):
        return self.estado in (self.Estado.FALLIDO, self.Estado.CANCELADO)