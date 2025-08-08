# admisiones/models.py
from django.db import models, transaction
from django.utils import timezone
import uuid
from django.urls import reverse
from gestion_academica.models import Grado, Usuario, Estudiante # Importamos Grado para saber a cuál aspira
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

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"

    def get_portal_url(self):
        return reverse('admisiones:portal_postulante', kwargs={'token': self.access_token})
        
    @transaction.atomic
    def procesar_inscripcion_completa(self):
        """
        Lógica final. Crea el Usuario y el Estudiante preliminar,
        manejando de forma segura el caso de que un estudiante con el mismo
        documento ya exista. VERSIÓN RESTAURADA Y CORREGIDA.
        """
        from .utils import crear_cuenta_cobro_inscripcion

        # 1. Buscamos si ya existe un estudiante con este documento en la institución.
        estudiante_existente = Estudiante.objects.filter(
            institucion=self.institucion,
            documento_identidad=self.numero_documento
        ).first()

        if estudiante_existente:
            # Si el estudiante ya existe, lo vinculamos a este nuevo proceso de admisión.
            estudiante_obj = estudiante_existente
            usuario_obj = estudiante_existente.usuario
        else:
            # Si NO existe, procedemos a crear el Usuario y el Estudiante como lo hacías antes.
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
            
            # Usamos create() directamente ya que sabemos que no existe
            estudiante_obj = Estudiante.objects.create(
                usuario=usuario_obj,
                institucion=self.institucion,
                documento_identidad=self.numero_documento,
                fecha_nacimiento=self.fecha_nacimiento,
                grado_actual=self.grado_aspira,
                sexo=self.sexo,
                activo=False # El estudiante empieza inactivo
            )

        # 4. Vincula los perfiles al aspirante (esta parte no cambia)
        self.usuario = usuario_obj
        self.estudiante_creado = estudiante_obj
        self.save(update_fields=['usuario', 'estudiante_creado'])

        # 5. Lógica de cobro (esta parte no cambia y ahora sí se ejecutará sin errores)
        if self.requiere_pago_inscripcion:
            cuenta_creada = crear_cuenta_cobro_inscripcion(self)
            if cuenta_creada:
                self.cuenta_pago_inscripcion = cuenta_creada
                self.save(update_fields=['cuenta_pago_inscripcion'])

    @transaction.atomic
    def matricular(self):
        """
        Contiene toda la lógica para matricular a un aspirante.
        VERSIÓN DEFINITIVA: La creación de pensiones se maneja de forma segura
        para no revertir la transacción principal en caso de fallo.
        """
        from finanzas.models import CuentaPorCobrarEstudiante
        import logging # Importamos logging para registrar errores

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
        
        # --- INICIO DE LA CORRECCIÓN CLAVE ---
        # 4. Intentamos crear las pensiones, pero si falla, no revertimos toda la matrícula.
        try:
            cuentas_creadas = CuentaPorCobrarEstudiante.objects.sincronizar_cuentas_automaticas(estudiante_a_matricular)
            if cuentas_creadas > 0:
                logging.getLogger(__name__).info(f"Se generaron {cuentas_creadas} pensiones para el estudiante {estudiante_a_matricular.pk}.")
            else:
                logging.getLogger(__name__).warning(f"No se generaron pensiones automáticas para {estudiante_a_matricular.pk}. Revisar configuración de 'Concepto de Pago' para pensiones.")
        except Exception as e:
            # Si la creación de pensiones falla, solo registramos el error en los logs,
            # pero NO lanzamos una excepción, para que la transacción principal no se revierta.
            logging.getLogger(__name__).error(f"FALLO SECUNDARIO al sincronizar las pensiones para {estudiante_a_matricular.pk}: {e}", exc_info=True)
        # --- FIN DE LA CORRECCIÓN CLAVE ---
        
        return estudiante_a_matricular


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