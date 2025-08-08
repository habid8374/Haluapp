# en admisiones/admin.py

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin

# Importamos TODOS los modelos, incluyendo el nuevo Proxy Model
from .models import (
    Aspirante, 
    DocumentoRequerido, 
    DocumentoEntregado,
    HorarioDisponible,
    CitaAgendada,
    AspiranteConDocumentos  # <-- IMPORTANTE: Importamos el nuevo modelo proxy
)

# ==============================================================================
# VISTA PRINCIPAL PARA REVISIÓN (LA QUE TÚ QUIERES)
# Esta será tu nueva entrada para revisar documentos.
# ==============================================================================
@admin.register(AspiranteConDocumentos)
class RevisionDocumentosAdmin(admin.ModelAdmin):
    # Usamos los campos del modelo Aspirante para mostrar la lista
    list_display = (
        'nombres', 
        'apellidos', 
        'grado_aspira', 
        'estado',
        'ver_documentos_link' # La columna con el enlace al detalle
    )
    list_filter = ('estado', 'grado_aspira', 'grado_aspira__institucion')
    search_fields = ('nombres', 'apellidos', 'numero_documento')
    ordering = ('-fecha_inscripcion',)

    def get_queryset(self, request):
        """
        La clave: solo mostramos aspirantes que tengan al menos un documento entregado.
        """
        return Aspirante.objects.filter(documentos_entregados__isnull=False).distinct()

    @admin.display(description='Revisar Documentos')
    def ver_documentos_link(self, obj):
        """Crea el enlace a la lista de documentos, filtrada por este aspirante."""
        count = obj.documentos_entregados.count()
        # La URL apunta al admin de DocumentoEntregado (el original)
        url = (
            reverse("admin:admisiones_documentoentregado_changelist")
            + f"?aspirante__id__exact={obj.id}"
        )
        return format_html('<a href="{}" class="button">Ver ({} Docs)</a>', url, count)

    def has_add_permission(self, request):
        # Deshabilitamos el botón "Añadir" en esta vista, ya que solo es para listar.
        return False

# ==============================================================================
# VISTA DE DETALLE: LISTA DE DOCUMENTOS ENTREGADOS
# Esta vista ahora solo se usará al hacer clic en el enlace de arriba.
# ==============================================================================
@admin.register(DocumentoEntregado)
class DocumentoEntregadoAdmin(admin.ModelAdmin):
    list_display = (
        'aspirante', 
        'documento_requerido', 
        'estado', 
        'fecha_subida',
        'view_file_link'
    )
    list_editable = ('estado',)
    search_fields = ('aspirante__nombres', 'aspirante__apellidos', 'documento_requerido__nombre')
    
    # Simplificamos los filtros, ya que usualmente llegaremos aquí con uno aplicado.
    list_filter = ('estado', 'documento_requerido__nombre')
    autocomplete_fields = ['aspirante'] # Mejora la selección si se crea manualmente

    @admin.display(description="Archivo")
    def view_file_link(self, obj):
        if obj.archivo:
            return format_html('<a href="{}" target="_blank">Ver Archivo</a>', obj.archivo.url)
        return "No hay archivo"

# ==============================================================================
# ADMIN DE ASPIRANTE ORIGINAL (PARA GESTIÓN GENERAL)
# Mantenemos tu admin original para gestionar TODOS los aspirantes.
# ==============================================================================
@admin.register(Aspirante)
class AspiranteAdmin(admin.ModelAdmin):
    """
    Configuración del panel de administración para el modelo Aspirante.
    CORREGIDO: Se añadió el enlace al portal del postulante.
    """
    list_display = (
        'nombres', 
        'apellidos', 
        'grado_aspira', 
        'estado', 
        'institucion', 
        'fecha_inscripcion',
        'link_al_portal' # <-- Columna añadida
    )
    list_filter = ('institucion', 'estado', 'grado_aspira')
    search_fields = ('nombres', 'apellidos', 'numero_documento', 'email_contacto')
    
    readonly_fields = ('access_token', 'usuario', 'estudiante_creado')

    fieldsets = (
        ('Información Personal', {
            'fields': ('nombres', 'apellidos', 'numero_documento', 'fecha_nacimiento', 'sexo')
        }),
        ('Información de Contacto', {
            'fields': ('email_contacto', 'telefono_contacto')
        }),
        ('Información Académica y de Admisión', {
            'fields': ('institucion', 'grado_aspira', 'colegio_procedencia', 'estado')
        }),
        ('Configuración del Proceso', {
            'fields': ('requiere_pago_inscripcion',)
        }),
        ('Datos Internos del Sistema', {
            'fields': ('usuario', 'estudiante_creado', 'access_token'),
            'classes': ('collapse',),
        }),
    )

    def link_al_portal(self, obj):
        """
        Crea un enlace HTML al portal del postulante.
        """
        if obj.estado != 'MATRICULADO' and obj.access_token:
            url = obj.get_portal_url()
            return format_html('<a href="{}" target="_blank">Abrir Portal</a>', url)
        return "N/A"
    link_al_portal.short_description = "Portal del Postulante"


# ==============================================================================
# REGISTRO DE TUS OTROS MODELOS (los mantenemos como estaban)
# ==============================================================================
@admin.register(DocumentoRequerido)
class DocumentoRequeridoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'es_obligatorio')
    list_editable = ('es_obligatorio',)
    search_fields = ('nombre', 'descripcion')

@admin.register(HorarioDisponible)
class HorarioDisponibleAdmin(admin.ModelAdmin):
    list_display = ('tipo_cita', 'fecha_hora_inicio', 'duracion_minutos', 'entrevistador', 'cupos_disponibles', 'cupos_ocupados', 'esta_disponible')
    list_filter = ('tipo_cita', 'entrevistador', 'fecha_hora_inicio')
    search_fields = ('tipo_cita', 'entrevistador__username')
    autocomplete_fields = ['entrevistador']

@admin.register(CitaAgendada)
class CitaAgendadaAdmin(admin.ModelAdmin):
    list_display = ('aspirante', 'horario', 'estado', 'fecha_agendamiento')
    list_filter = ('estado', 'horario__tipo_cita', 'horario__fecha_hora_inicio')
    search_fields = ('aspirante__nombres', 'aspirante__apellidos', 'horario__tipo_cita')
    list_editable = ('estado',)
    autocomplete_fields = ['aspirante', 'horario']
    readonly_fields = ('fecha_agendamiento',)

  

