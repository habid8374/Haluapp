# gestion_academica/admin.py
from django.contrib import admin
# Importamos el modelo InstitucionEducativa como cadena de texto en los modelos
# pero aquí en admin.py necesitamos importarlo directamente para registrarlo
from finanzas.models import InstitucionEducativa 
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from import_export.admin import ImportExportModelAdmin
from django.db.models import Q
from django.urls import path
from django.shortcuts import redirect

# Importa los modelos desde tu aplicación gestion_academica
from .models import (
    Usuario, Grado, Estudiante, Docente, Familiar,
    Materia, PeriodoAcademico, Curso, DirectorCurso,
    EsquemaCalificacion, TipoActividad, ActividadCalificable, Calificacion,
    PlanCurricular, Deber, EntregaDeber, MencionReconocimiento, ArchivoPlanAcademico,
    ConfiguracionInstitucion, Noticia, EnlaceVideollamada, AreaAcademica, 
    DescriptorLogro, RegistroAsistencia, Aula, BloqueHorario, Pregunta, Opcion, EscalaValorativa,
    LeccionDiaria, AnalisisRiesgo, PrediccionRiesgoEstudiante, Notificacion, AnotacionObservador,
    DisponibilidadDocente, CitaReunion, IntentoActividad, Egresado, ArchivoHistorico, SolicitudDocumento,
    EscalaCualitativa, NivelEscolaridad, DimensionDesarrollo, EvaluacionLogroPreescolar, LogroPreescolar,
    PlaneacionClase, DetalleClase
)
from import_export import resources

try:
    admin.site.unregister(Usuario)
except admin.sites.NotRegistered:
    pass

# --- Clases ModelAdmin (personalización para el panel de administración) ---

@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    """
    Configuración personalizada para el modelo Usuario en el panel de administración.
    VERSIÓN ACTUALIZADA: Incluye el campo para el ID del calendario de Google.
    """
    # --- INICIO DE LA CORRECCIÓN CLAVE ---
    # Añadimos la nueva sección "Conexiones Externas" a tus fieldsets existentes.
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Roles e Institución', {'fields': ('rol', 'institucion_asociada')}),
        ('Conexiones Externas', {'fields': ('google_calendar_id',)}),
    )
    # --- FIN DE LA CORRECCIÓN CLAVE ---

    # Tus configuraciones de list_display y list_filter se mantienen igual
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'rol')
    list_filter = BaseUserAdmin.list_filter + ('rol', 'institucion_asociada')

@admin.register(NivelEscolaridad)
class NivelEscolaridadAdmin(admin.ModelAdmin):
    # ✅ Se añade el nuevo campo a la lista
    list_display = ('nombre', 'institucion', 'orden', 'valor_inscripcion_estandar', 'valor_matricula_estandar', 'valor_pension_estandar')
    list_filter = ('institucion',)
    search_fields = ('nombre',)
    ordering = ('orden',)    

@admin.register(Grado)
class GradoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'nivel_escolaridad', 'institucion', 'orden', 'tipo_evaluacion')
    search_fields = ('nombre', 'nivel_escolaridad__nombre') 
    list_filter = ('institucion', 'tipo_evaluacion', 'nivel_escolaridad')
    ordering = ('institucion', 'orden',)
    raw_id_fields = ('institucion', 'nivel_escolaridad')

    # ✅ SE ELIMINÓ EL FIELDSET "Valores Financieros Estándar"
    fieldsets = (
        (None, {
            'fields': ('nombre', 'nivel_escolaridad', 'institucion')
        }),
        ('Configuración Académica', {
            'fields': ('orden', 'siguiente_grado', 'tipo_evaluacion')
        }),
    )

@admin.register(EscalaCualitativa)
class EscalaCualitativaAdmin(admin.ModelAdmin):
    list_display = ('nombre_escala', 'abreviatura', 'institucion', 'orden')
    list_filter = ('institucion',)
    search_fields = ('nombre_escala', 'abreviatura')
    
@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    list_display = ('usuario_nombre', 'codigo_estudiante', 'grado_actual', 'sexo', 'institucion',  'activo') # <-- 'sexo' añadido para vista rápida
    search_fields = ('usuario__username', 'usuario__first_name', 'usuario__last_name', 'codigo_estudiante', 'documento_identidad')
    list_filter = ('grado_actual', 'institucion', 'sexo', 'departamento') # <-- 'sexo' y 'departamento' añadidos como filtros
    ordering = ('institucion', 'grado_actual', 'usuario__last_name', 'usuario__first_name')
    raw_id_fields = ('usuario', 'grado_actual', 'institucion')
    filter_horizontal = ('descuentos',) 

    # --- fieldsets para organizar el formulario de edición ---
    fieldsets = (
        ('Información de Usuario y Académica', {
            'fields': ('usuario', 'codigo_estudiante', 'grado_actual', 'institucion')
        }),
        ('Información Personal', {
            'fields': ('documento_identidad', 'fecha_nacimiento', 'sexo', 'direccion') # <-- 'sexo' añadido aquí
        }),
        ('Datos de Procedencia (Heredados de Admisión)', {
            'fields': ('colegio_procedencia', 'municipio_ciudad', 'departamento'), # <-- Nuevos campos agrupados
            'classes': ('collapse',) # Opcional: para que aparezca colapsado
        }),
        ('Información Financiera', {
            'fields': ('valor_matricula', 'valor_mensualidad'),
            'classes': ('collapse',)
        })
    )

    def usuario_nombre(self, obj):
        # Esta función tuya es perfecta, se queda igual
        return obj.usuario.get_full_name() or obj.usuario.username
    usuario_nombre.admin_order_field = 'usuario__last_name'
    usuario_nombre.short_description = 'Nombre del Estudiante'


class RegistroAsistenciaResource(resources.ModelResource):
    def get_queryset(self):
        request = self.context.get('request')
        qs = super().get_queryset()
        if request and hasattr(request.user, 'institucioneducativa'):
            return qs.filter(institucion=request.user.institucioneducativa)
        return qs.none()

    class Meta:
        model = RegistroAsistencia
        fields = (
            'id',
            'fecha',
            'estudiante__usuario__first_name',
            'estudiante__usuario__last_name',
            'curso__materia__nombre_materia',
            'curso__grado__nombre',
            'aula__nombre',
            'estado',
            'registrado_por__username'
        )
        export_order = fields   

@admin.register(RegistroAsistencia)
class RegistroAsistenciaAdmin(ImportExportModelAdmin):
    resource_class = RegistroAsistenciaResource
    list_display = ('fecha', 'estudiante', 'curso', 'aula', 'estado', 'registrado_por')
    list_filter = ('fecha_solo', 'estado', 'curso__grado', 'curso', 'aula')
    search_fields = (
        'estudiante__usuario__username',
        'estudiante__usuario__first_name',
        'estudiante__usuario__last_name'
    )
    date_hierarchy = 'fecha_solo'
    autocomplete_fields = ['estudiante', 'curso', 'registrado_por']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'institucioneducativa'):
            return qs.filter(institucion=request.user.institucioneducativa)
        return qs.none()
    
@admin.register(Docente)
class DocenteAdmin(admin.ModelAdmin):
    list_display = ('usuario_nombre', 'codigo_docente', 'especialidad', 'institucion')
    search_fields = ('usuario__username', 'usuario__first_name', 'usuario__last_name', 'codigo_docente')
    list_filter = ('especialidad', 'institucion')
    ordering = ('institucion', 'usuario__last_name', 'usuario__first_name')
    raw_id_fields = ('usuario', 'institucion')

    def usuario_nombre(self, obj):
        return obj.usuario.get_full_name() if obj.usuario else obj.usuario.username
    usuario_nombre.admin_order_field = 'usuario__last_name'
    usuario_nombre.short_description = 'Nombre del Docente'

@admin.register(Familiar)
class FamiliarAdmin(admin.ModelAdmin):
    # Definimos las columnas que queremos mostrar
    list_display = ('usuario_nombre', 'email_contacto', 'parentesco', 'telefono')
    search_fields = ('usuario__first_name', 'usuario__last_name', 'usuario__email', 'telefono')
    filter_horizontal = ('estudiantes_asociados',)
    raw_id_fields = ('usuario',)
    
    def get_urls(self):
        urls = super().get_urls()
        # Esta lógica para el botón 'add' personalizado se mantiene igual
        custom_urls = [
            path('add/', self.admin_site.admin_view(self.add_view), name='gestion_academica_familiar_add'),
        ]
        return custom_urls + urls

    def add_view(self, request, form_url='', extra_context=None):
        return redirect('gestion_academica:crear_familiar')

    # ===============================================================
    # INICIO DE LA CORRECCIÓN: AÑADIMOS LAS FUNCIONES QUE FALTABAN
    # ===============================================================
    @admin.display(description='Nombre del Familiar', ordering='usuario__last_name')
    def usuario_nombre(self, obj):
        """Devuelve el nombre completo del usuario asociado al familiar."""
        if obj.usuario:
            return obj.usuario.get_full_name()
        return "N/A"

    @admin.display(description='Email de Contacto')
    def email_contacto(self, obj):
        """Devuelve el email del usuario asociado."""
        if obj.usuario:
            return obj.usuario.email
        return "N/A"

# --- PASO 1: Definimos el Inline para las Materias ---
# Esto le dice a Django: "Quiero mostrar una tabla para editar Materias".
class MateriaInline(admin.TabularInline):
    model = Materia
    
    # Mostramos solo los campos más relevantes en la tabla para no saturar
    fields = ('nombre_materia', 'codigo_materia', 'intensidad_horaria_semanal')
    
    extra = 1  # Muestra 1 fila en blanco para añadir una nueva materia fácilmente.
    
    # Usamos autocomplete_fields aquí también si la lista de instituciones es grande.
    raw_id_fields = ('institucion',) # Opcional aquí, usualmente no se necesita en el inline.


# --- PASO 2: Modificamos el Admin del Área para USAR el Inline ---
# Aquí le decimos a Django: "Cuando alguien edite un Área, muestra la tabla de Materias debajo".    


@admin.register(Materia)
class MateriaAdmin(admin.ModelAdmin):
    # La vista de Materia ahora es más simple porque no se preocupa por el área.
    list_display = ('nombre_materia', 'codigo_materia', 'institucion')
    search_fields = ('nombre_materia', 'codigo_materia')
    list_filter = ('institucion',)
    ordering = ('institucion', 'nombre_materia',)
    raw_id_fields = ('institucion',)

@admin.register(PeriodoAcademico)
class PeriodoAcademicoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'año_escolar', 'fecha_inicio', 'fecha_fin', 'activo', 'institucion')
    search_fields = ('nombre', 'año_escolar')
    list_filter = ('activo', 'año_escolar', 'institucion')
    ordering = ('institucion', '-año_escolar', '-fecha_inicio')
    raw_id_fields = ('institucion',)

@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ('materia', 'grado', 'periodo_academico', 'institucion')
    search_fields = ('materia__nombre_materia', 'grado__nombre', 'periodo_academico__nombre')
    list_filter = ('periodo_academico', 'grado', 'materia', 'institucion')
    ordering = ('institucion', 'periodo_academico', 'grado', 'materia')
    filter_horizontal = ('docentes_asignados',)
    raw_id_fields = ('materia', 'grado', 'periodo_academico', 'institucion')

@admin.register(DirectorCurso)
class DirectorCursoAdmin(admin.ModelAdmin):
    list_display = ('docente', 'grado', 'periodo_academico', 'institucion')
    search_fields = ('docente__usuario__first_name', 'docente__usuario__last_name', 'grado__nombre')
    list_filter = ('periodo_academico', 'grado', 'institucion')
    ordering = ('institucion', 'periodo_academico', 'grado')
    raw_id_fields = ('docente', 'grado', 'periodo_academico', 'institucion')

@admin.register(EsquemaCalificacion)
class EsquemaCalificacionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'institucion')
    search_fields = ('nombre',)
    list_filter = ('institucion',)
    ordering = ('institucion', 'nombre',)
    raw_id_fields = ('institucion',)

@admin.register(TipoActividad)
class TipoActividadAdmin(admin.ModelAdmin):
    # ✅ Se añade 'orden' a la lista de columnas a mostrar
    list_display = ('nombre', 'porcentaje', 'orden', 'institucion')
    
    search_fields = ('nombre',)
    list_filter = ('institucion',)
    
    # Ahora que 'orden' está en list_display, esta línea es válida
    list_editable = ('porcentaje', 'orden') 
    
    ordering = ('orden',) 
    raw_id_fields = ('institucion',)
    
@admin.register(ActividadCalificable)
class ActividadCalificableAdmin(admin.ModelAdmin):
    search_fields = ('titulo', 'curso__materia__nombre_materia', 'curso__grado__nombre')
    list_filter = ('curso__periodo_academico', 'curso__grado', 'tipo_actividad', 'institucion')
    ordering = ('institucion', 'curso__periodo_academico', 'curso__grado', 'curso__materia', '-fecha_publicacion')
    raw_id_fields = ('curso', 'tipo_actividad', 'institucion')

@admin.register(Calificacion)
class CalificacionAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'actividad_calificable', 'valor_numerico', 'valor_cualitativo', 'fecha_registro', 'registrada_por', 'institucion')
    search_fields = ('estudiante__usuario__username', 'actividad_calificable__titulo')
    list_filter = ('actividad_calificable__curso__periodo_academico', 'actividad_calificable__curso__grado', 'registrada_por', 'institucion')
    ordering = ('institucion', 'actividad_calificable__curso__periodo_academico', 'actividad_calificable__curso__grado', 'estudiante__usuario__last_name', '-fecha_registro')
    raw_id_fields = ('estudiante', 'actividad_calificable', 'registrada_por', 'institucion')

@admin.register(PlanCurricular)
class PlanCurricularAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'grado_asociado', 'materia_asociada', 'periodo_academico_asociado', 'fecha_publicacion', 'creado_por', 'institucion')
    search_fields = ('nombre', 'grado_asociado__nombre', 'materia_asociada__nombre_materia')
    list_filter = ('grado_asociado', 'materia_asociada', 'periodo_academico_asociado', 'institucion')
    ordering = ('institucion', '-fecha_publicacion', 'nombre')
    raw_id_fields = ('grado_asociado', 'materia_asociada', 'periodo_academico_asociado', 'creado_por', 'institucion')

@admin.register(Deber)
class DeberAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'curso', 'fecha_asignacion', 'fecha_entrega', 'institucion')
    search_fields = ('titulo', 'curso__materia__nombre_materia', 'curso__grado__nombre')
    list_filter = ('curso__periodo_academico', 'curso__grado', 'institucion')
    ordering = ('institucion', 'curso__periodo_academico', 'curso__grado', '-fecha_entrega')
    raw_id_fields = ('curso', 'institucion')

@admin.register(EntregaDeber)
class EntregaDeberAdmin(admin.ModelAdmin):
    list_display = ('deber', 'estudiante', 'fecha_entrega_real', 'calificacion_obtenida', 'institucion')
    search_fields = ('deber__titulo', 'estudiante__usuario__username')
    list_filter = ('deber__curso__periodo_academico', 'deber__curso__grado', 'institucion')
    ordering = ('institucion', 'deber__curso__periodo_academico', 'deber__curso__grado', '-fecha_entrega_real')
    raw_id_fields = ('deber', 'estudiante', 'institucion')

@admin.register(MencionReconocimiento)
class MencionReconocimientoAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'tipo', 'fecha_otorgamiento', 'otorgado_por', 'institucion')
    search_fields = ('estudiante__usuario__username', 'tipo', 'descripcion')
    list_filter = ('tipo', 'fecha_otorgamiento', 'institucion')
    ordering = ('institucion', '-fecha_otorgamiento', 'estudiante__usuario__last_name')
    raw_id_fields = ('estudiante', 'curso', 'periodo', 'otorgado_por', 'institucion')

@admin.register(ArchivoPlanAcademico)
class ArchivoPlanAcademicoAdmin(admin.ModelAdmin):
    list_display = ('nombre_archivo_descriptivo', 'tipo_documento', 'curso_asociado', 'materia_asociada', 'fecha_subida', 'subido_por', 'institucion')
    search_fields = ('nombre_archivo_descriptivo', 'tipo_documento', 'curso_asociado__materia__nombre_materia')
    list_filter = ('tipo_documento', 'curso_asociado__periodo_academico', 'institucion')
    ordering = ('institucion', '-fecha_subida', 'nombre_archivo_descriptivo')
    raw_id_fields = ('curso_asociado', 'materia_asociada', 'subido_por', 'institucion')

@admin.register(ConfiguracionInstitucion)
class ConfiguracionInstitucionAdmin(admin.ModelAdmin):
    list_display = ('institucion_principal', 'nombre_institucion', 'lema_institucion', 'telefono_contacto', 'email_contacto')
    search_fields = ('institucion_principal__nombre', 'nombre_institucion', 'lema_institucion')
    raw_id_fields = ('institucion_principal',) # Siempre usa raw_id_fields para OneToOneField que es primary_key

@admin.register(EnlaceVideollamada)
class EnlaceVideollamadaAdmin(admin.ModelAdmin):
    """
    Personalización del panel de admin para los enlaces de videollamada.
    """
    list_display = ('titulo', 'curso', 'url')
    list_filter = ('curso__grado', 'curso__materia')
    search_fields = ('titulo', 'curso__materia__nombre_materia')
    autocomplete_fields = ['curso'] # Facilita la selección del curso    

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True # Superusuarios pueden añadir si lo necesitan
        if hasattr(request.user, 'institucion_asociada') and request.user.institucion_asociada:
            # Solo permite añadir si NO existe ya una configuración para SU institución
            return not ConfiguracionInstitucion.objects.filter(institucion_principal=request.user.institucion_asociada).exists()
        return False # Otros usuarios no pueden añadir

@admin.register(Noticia)
class NoticiaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'fecha_publicacion', 'publicado_por', 'institucion')
    search_fields = ('titulo', 'contenido')
    list_filter = ('fecha_publicacion', 'institucion')
    ordering = ('institucion', '-fecha_publicacion',)
    raw_id_fields = ('publicado_por', 'institucion')

@admin.register(AreaAcademica)
class AreaAcademicaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'institucion')
    search_fields = ('nombre',)
    list_filter = ('institucion',)
    
    # Mantenemos el widget filter_horizontal, que es el ideal para esta tarea.
    filter_horizontal = ('materias',)

    def get_form(self, request, obj=None, **kwargs):
        """
        Este método se llama al construir el formulario.
        Guardamos una referencia al objeto que se está editando (si existe)
        para poder usarlo en otros métodos.
        """
        # Guardamos la instancia del área actual para usarla después.
        self.instance = obj 
        return super().get_form(request, obj, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """
        Este método personaliza el queryset para el campo 'materias',
        asegurando que solo se muestren las materias disponibles.
        """
        if db_field.name == "materias":
            # Obtenemos el área que estamos editando (si existe).
            area_actual = getattr(self, 'instance', None)
            
            # Por defecto, no mostramos ninguna materia.
            qs = Materia.objects.none()

            if area_actual:
                # CASO 1: Estamos EDITANDO un Área existente.
                # Mostramos las materias que ya pertenecen a ESTA área,
                # y las que no pertenecen a NINGUNA área (pero de la misma institución).
                qs = Materia.objects.filter(
                    Q(institucion=area_actual.institucion) & 
                    (Q(areaacademica__isnull=True) | Q(areaacademica=area_actual))
                )
            elif not request.user.is_superuser:
                # CASO 2: Estamos CREANDO un Área nueva y el usuario NO es superadmin.
                # Mostramos solo las materias de su institución que no tienen área.
                try:
                    institucion = request.user.docente.institucion
                    qs = Materia.objects.filter(institucion=institucion, areaacademica__isnull=True)
                except (AttributeError, Docente.DoesNotExist):
                    # Si el usuario no tiene institución, no mostramos nada.
                    pass
            # CASO 3: Superadmin CREANDO un área. No se muestra ninguna materia hasta que
            # el área se guarde y tenga una institución asignada. Esto es lo correcto.
            
            # Asignamos el queryset filtrado al widget.
            kwargs['queryset'] = qs.distinct()
            
        return super().formfield_for_manytomany(db_field, request, **kwargs)

@admin.register(DescriptorLogro)
class DescriptorLogroAdmin(admin.ModelAdmin):
    list_display = ('descripcion_corta', 'materia', 'periodo_academico', 'creado_por', 'institucion')
    
    search_fields = ('descripcion', 'materia__nombre_materia', 'creado_por__username', 'institucion__nombre')
    
    # --- FILTRO CORREGIDO: Eliminamos 'materia__area' ---
    list_filter = ('institucion', 'periodo_academico', 'creado_por')
    
    autocomplete_fields = ['materia', 'periodo_academico', 'creado_por', 'institucion']
    list_per_page = 20

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            try:
                return qs.filter(institucion=request.user.docente.institucion)
            except AttributeError:
                return qs.none()
        return qs

    @admin.display(description='Descripción')
    def descripcion_corta(self, obj):
        return str(obj.descripcion)[:70] + '...' if len(str(obj.descripcion)) > 70 else str(obj.descripcion)

    # Opcional: una función para mostrar una descripción corta en la lista
    @admin.display(description='Descripción')
    def descripcion_corta(self, obj):
        return str(obj.descripcion)[:70] + '...' if len(str(obj.descripcion)) > 70 else str(obj.descripcion)

@admin.register(Aula)
class AulaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'capacidad', 'institucion')
    list_filter = ('institucion',)
    search_fields = ('nombre',)
    ordering = ('nombre',)

@admin.register(BloqueHorario)
class BloqueHorarioAdmin(admin.ModelAdmin):
    list_display = ('curso', 'dia_semana', 'hora_inicio', 'hora_fin', 'aula')
    list_filter = ('dia_semana', 'curso__grado', 'curso__materia', 'aula')
    autocomplete_fields = ['curso', 'aula'] 


class OpcionInline(admin.TabularInline):
    """
    Permite editar las opciones directamente en la página de la pregunta.
    """
    model = Opcion
    extra = 1 # Muestra 1 campo de opción vacío por defecto.
    fields = ('texto', 'es_correcta')

@admin.register(Pregunta)
class PreguntaAdmin(admin.ModelAdmin):
    """
    Panel de administración para el modelo Pregunta.
    """
    list_display = ('enunciado', 'actividad', 'tipo', 'orden')
    list_filter = ('tipo', 'actividad__curso__materia', 'actividad__institucion')
    search_fields = ('enunciado', 'actividad__titulo')
    # Usamos inlines para que la creación de opciones sea intuitiva.
    inlines = [OpcionInline]
    # Hacemos que el campo 'actividad' sea un campo de búsqueda autocompletable.
    autocomplete_fields = ['actividad']  

@admin.register(IntentoActividad)
class IntentoActividadAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'actividad', 'estado', 'inicio', 'fin', 'puntaje_obtenido')
    list_filter = ('estado', 'actividad__curso__materia', 'institucion')
    search_fields = ('estudiante__usuario__username', 'actividad__titulo')
    readonly_fields = ('inicio', 'fin')    

class EscalaValorativaInline(admin.TabularInline):
    model = EscalaValorativa
    extra = 1
    ordering = ('orden',)   

@admin.register(LeccionDiaria)
class LeccionDiariaAdmin(admin.ModelAdmin):
    """
    Personaliza la vista del admin para las Lecciones Diarias.
    """
    list_display = ('fecha', 'curso', 'tema_tratado', 'creado_por')
    list_filter = ('fecha', 'curso__grado', 'curso__materia', 'creado_por')
    search_fields = ('tema_tratado', 'resumen_clase', 'curso__materia__nombre_materia')
    date_hierarchy = 'fecha' # Añade una navegación por fechas muy útil
    autocomplete_fields = ['curso', 'creado_por'] # Facilita la selección

    # Hacemos que el campo de resumen sea más grande
    fieldsets = (
        (None, {
            'fields': ('curso', 'fecha', 'tema_tratado', 'resumen_clase', 'archivo_adjunto')
        }),
        ('Metadatos (Autocompletado)', {
            'classes': ('collapse',), # Opcional: para que aparezca colapsado
            'fields': ('creado_por', 'institucion'),
        }),
    )  

@admin.register(AnalisisRiesgo)
class AnalisisRiesgoAdmin(admin.ModelAdmin):
    list_display = ('fecha_analisis', 'periodo_academico', 'resumen')
    list_filter = ('periodo_academico',)

@admin.register(PrediccionRiesgoEstudiante)
class PrediccionRiesgoEstudianteAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'materia', 'nivel_riesgo', 'analisis')
    list_filter = ('nivel_riesgo', 'materia', 'analisis__periodo_academico')
    search_fields = ('estudiante__usuario__first_name', 'estudiante__usuario__last_name')   

@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('destinatario', 'mensaje', 'leido', 'fecha_creacion')
    list_filter = ('leido', 'fecha_creacion')
    search_fields = ('destinatario__username', 'mensaje')  

@admin.register(AnotacionObservador)
class AnotacionObservadorAdmin(admin.ModelAdmin):
    list_display = ('fecha_hora', 'estudiante', 'tipo', 'descripcion_corta', 'registrado_por', 'sentimiento_detectado', 'requiere_revision')
    list_filter = ('requiere_revision', 'tipo', 'fecha_hora', 'estudiante__grado_actual')
    search_fields = ('estudiante__usuario__first_name', 'estudiante__usuario__last_name', 'descripcion')
    list_per_page = 20
    
    # Coloreamos la fila si requiere revisión para que sea muy visible
    def get_row_attributes(self, obj):
        if obj.requiere_revision:
            return {'class': 'bg-danger text-white'}
    
    @admin.display(description='Descripción')
    def descripcion_corta(self, obj):
        return str(obj.descripcion)[:50] + '...' if len(str(obj.descripcion)) > 50 else str(obj.descripcion) 

@admin.register(DisponibilidadDocente)
class DisponibilidadDocenteAdmin(admin.ModelAdmin):
    list_display = ('docente', 'get_dia_semana_display', 'hora_inicio', 'hora_fin')
    list_filter = ('docente', 'dia_semana')

@admin.register(CitaReunion)
class CitaReunionAdmin(admin.ModelAdmin):
    list_display = ('fecha_hora_inicio', 'docente', 'familiar', 'estudiante', 'estado')
    list_filter = ('estado', 'docente', 'familiar')
    search_fields = ('asunto', 'estudiante__usuario__last_name')   

@admin.register(Egresado)
class EgresadoAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'año_graduacion', 'fecha_egreso', 'estado')
    list_filter = ('año_graduacion', 'estado')
    search_fields = (
        'estudiante__usuario__first_name', 
        'estudiante__usuario__last_name',   
        'estudiante__documento_identidad'
    )
    autocomplete_fields = ('estudiante',)
    readonly_fields = ('estudiante',)


@admin.register(ArchivoHistorico)
class ArchivoHistoricoAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'año_academico', 'fecha_generacion')
    list_filter = ('año_academico', 'tipo_documento')
    search_fields = (
        'egresado__estudiante__usuario__first_name', 
        'egresado__estudiante__usuario__last_name'
    )
    autocomplete_fields = ('egresado',)  

@admin.register(SolicitudDocumento)
class SolicitudDocumentoAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'estado', 'fecha_solicitud', 'fecha_actualizacion')
    list_filter = ('estado',)
    list_editable = ('estado',)
    readonly_fields = ('egresado', 'tipo_documento_solicitado', 'cuenta_por_cobrar', 'fecha_solicitud', 'fecha_actualizacion')
    autocomplete_fields = ('egresado',)
    # El campo importante a editar por el admin es 'archivo_generado'
    fields = ('egresado', 'tipo_documento_solicitado', 'estado', 'archivo_generado', 'cuenta_por_cobrar', 'fecha_solicitud', 'fecha_actualizacion')                   


@admin.register(DimensionDesarrollo)
class DimensionDesarrolloAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'institucion', 'orden')
    list_filter = ('institucion',)
    search_fields = ('nombre',)
    ordering = ('institucion', 'orden',)
    list_editable = ('orden',)

    # --- INICIO DE LA MODIFICACIÓN ---
    # Esta línea mágica crea un widget de dos cajas para asignar
    # las materias a la dimensión de una forma muy cómoda.
    filter_horizontal = ('materias',)
    # --- FIN DE LA MODIFICACIÓN ---

@admin.register(LogroPreescolar)
class LogroPreescolarAdmin(admin.ModelAdmin):
    """
    Configuración del Admin para el nuevo modelo de Logros de Preescolar.
    """
    list_display = ('descripcion_corta', 'dimension', 'materia', 'periodo', 'institucion')
    list_filter = ('institucion', 'periodo', 'dimension', 'materia')
    search_fields = ('descripcion', 'materia__nombre_materia', 'dimension__nombre')
    ordering = ('dimension__orden', 'materia__nombre_materia', 'orden')
    
    # Campos que usarán un buscador para facilitar la selección
    autocomplete_fields = ['dimension', 'materia', 'periodo', 'institucion']
    
    list_per_page = 20

    def get_queryset(self, request):
        # Filtra automáticamente por la institución del usuario si no es superadmin
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(institucion=request.user.institucion_asociada)
        return

    @admin.display(description='Descripción del Logro')
    def descripcion_corta(self, obj):
        return str(obj.descripcion)[:80] + '...' if len(str(obj.descripcion)) > 80 else str(obj.descripcion)


@admin.register(EvaluacionLogroPreescolar)
class EvaluacionLogroPreescolarAdmin(admin.ModelAdmin):
    """
    Configuración del Admin para ver las evaluaciones de logros (principalmente para depuración).
    """
    list_display = ('estudiante', 'logro', 'estado', 'registrado_por')
    list_filter = ('institucion', 'estado', 'logro__dimension')
    search_fields = ('estudiante__usuario__username', 'logro__descripcion')
    autocomplete_fields = ['estudiante', 'logro', 'estado', 'registrado_por']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(institucion=request.user.institucion_asociada)
        return qs    

class DetalleClaseInline(admin.TabularInline):
    """
    Permite ver y editar los detalles de cada clase directamente
    dentro de la página de la planeación principal.
    """
    model = DetalleClase
    extra = 0 # No mostrar formularios extra por defecto
    readonly_fields = ('numero_clase', 'tema_clase', 'actividades_inicio', 'actividades_desarrollo', 'actividades_cierre')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class DetalleClaseInline(admin.TabularInline):
    model = DetalleClase
    extra = 0
    readonly_fields = ('numero_clase', 'tema_clase', 'actividades_inicio', 'actividades_desarrollo', 'actividades_cierre')
    can_delete = False
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(PlaneacionClase)
class PlaneacionClaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'titulo', 'curso', 'docente', 'estado_generacion', 'ultima_actualizacion')
    list_filter = ('estado_generacion', 'institucion', 'metodologia')
    search_fields = ('titulo', 'docente__usuario__first_name', 'docente__usuario__last_name', 'curso__materia__nombre_materia')
    
    # --- INICIO DE LA CORRECCIÓN CLAVE ---
    # Hacemos que el campo 'estado_generacion' sea editable.
    readonly_fields = ('fecha_creacion', 'ultima_actualizacion', 'error_generacion')
    
    fieldsets = (
        ('Información Principal', {
            'fields': ('titulo', 'curso', 'docente', 'metodologia', 'duracion_clases')
        }),
        ('Estado de la Generación', {
            # Ahora puedes cambiar el estado manualmente desde aquí
            'fields': ('estado_generacion', 'error_generacion', 'fecha_creacion', 'ultima_actualizacion')
        }),
        ('Contenido Generado por IA', {
            'classes': ('collapse',),
            'fields': ('objetivos_aprendizaje', 'recursos_necesarios', 'criterios_evaluacion'),
        }),
    )
    # --- FIN DE LA CORRECCIÓN CLAVE ---

    inlines = [DetalleClaseInline]     