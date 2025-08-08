# gestion_academica/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Permission
from .models import (
    Usuario, Grado, Estudiante, Docente, Familiar,
    Materia, PeriodoAcademico, Curso, DirectorCurso,
    EsquemaCalificacion, TipoActividad, ActividadCalificable, Calificacion,
    PlanCurricular, Deber, EntregaDeber, MencionReconocimiento, Noticia, ArchivoPlanAcademico,
    ConfiguracionInstitucion,
    TipoConceptoPago, ConceptoPago, CuentaPorCobrarEstudiante, PagoRegistrado
)

admin.site.register(Permission)

admin.site.site_header = "Panel de Administración del Alu"
admin.site.site_title = "Administración Académica Alu"
admin.site.index_title = "Bienvenido al Sistema Alu de Gestión Escolar"
admin.site.site_url = '/academico/'  # Para ir al módulo académico desde "Ver el sitio"

# --- Usuarios Personalizados ---
class CustomUserAdmin(UserAdmin):
    model = Usuario
    list_display = UserAdmin.list_display + ('rol',)
    fieldsets = UserAdmin.fieldsets + (('Información Adicional', {'fields': ('rol',)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (('Información Adicional', {'fields': ('rol',)}),)

if admin.site.is_registered(Usuario):
    admin.site.unregister(Usuario)
admin.site.register(Usuario, CustomUserAdmin)

# --- Admins para modelos académicos ---
class EstudianteAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'documento_identidad', 'codigo_estudiante', 'grado_actual', 'valor_matricula', 'valor_mensualidad')
    search_fields = ('usuario__username', 'usuario__first_name', 'usuario__last_name', 'codigo_estudiante', 'documento_identidad')
    list_filter = ('grado_actual',)
    raw_id_fields = ('usuario', 'grado_actual')
    list_select_related = ('usuario', 'grado_actual')

class DocenteAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'codigo_docente', 'especialidad')
    search_fields = ('usuario__username', 'usuario__first_name', 'usuario__last_name', 'codigo_docente')
    list_filter = ('especialidad',)
    raw_id_fields = ('usuario',)
    list_select_related = ('usuario',)

class MateriaAdmin(admin.ModelAdmin):
    list_display = ('nombre_materia', 'codigo_materia')
    search_fields = ('nombre_materia', 'codigo_materia')

class PeriodoAcademicoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'año_escolar', 'fecha_inicio', 'fecha_fin', 'activo')
    list_filter = ('activo', 'año_escolar')
    search_fields = ('nombre', 'año_escolar')

    def marcar_como_activo(self, request, queryset):
        PeriodoAcademico.objects.filter(activo=True).update(activo=False)
        queryset.update(activo=True)
        self.message_user(request, "Periodo(s) marcado(s) como activo(s).")

    def marcar_como_inactivo(self, request, queryset):
        queryset.update(activo=False)
        self.message_user(request, "Periodo(s) marcado(s) como inactivo(s).")

class CursoAdmin(admin.ModelAdmin):
    list_display = ('materia', 'grado', 'periodo_academico', 'get_docentes_asignados_display')
    filter_horizontal = ('docentes_asignados',)
    raw_id_fields = ('materia', 'grado', 'periodo_academico')
    list_select_related = ('materia', 'grado', 'periodo_academico')

    def get_docentes_asignados_display(self, obj):
        return ", ".join([d.usuario.username for d in obj.docentes_asignados.all()])
    get_docentes_asignados_display.short_description = 'Docentes Asignados'

class DirectorCursoAdmin(admin.ModelAdmin):
    list_display = ('docente', 'grado', 'periodo_academico')
    raw_id_fields = ('docente', 'grado', 'periodo_academico')
    list_select_related = ('docente__usuario', 'grado', 'periodo_academico')

class ActividadCalificableAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'curso', 'tipo_actividad', 'fecha_publicacion', 'fecha_entrega_limite', 'porcentaje_en_periodo')
    raw_id_fields = ('curso', 'tipo_actividad')

class CalificacionAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'actividad_calificable', 'valor_numerico', 'valor_cualitativo', 'fecha_registro')
    raw_id_fields = ('estudiante', 'actividad_calificable', 'registrada_por')

class DeberAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'curso', 'fecha_asignacion', 'fecha_entrega')
    raw_id_fields = ('curso',)

class EntregaDeberAdmin(admin.ModelAdmin):
    list_display = ('deber', 'estudiante', 'fecha_entrega_real', 'calificacion_obtenida')
    raw_id_fields = ('deber', 'estudiante')

class MencionReconocimientoAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'tipo', 'fecha_otorgamiento')
    raw_id_fields = ('estudiante', 'curso', 'periodo', 'otorgado_por')

class PlanCurricularAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'grado_asociado', 'materia_asociada', 'periodo_academico_asociado', 'fecha_publicacion', 'creado_por')
    raw_id_fields = ('grado_asociado', 'materia_asociada', 'periodo_academico_asociado', 'creado_por')

class ArchivoPlanAcademicoAdmin(admin.ModelAdmin):
    list_display = ('nombre_archivo_descriptivo', 'tipo_documento', 'curso_asociado', 'materia_asociada', 'subido_por', 'fecha_subida')
    raw_id_fields = ('curso_asociado', 'materia_asociada', 'subido_por')

class ConfiguracionInstitucionAdmin(admin.ModelAdmin):
    list_display = ('nombre_institucion', 'email_contacto', 'sitio_web')
    def has_add_permission(self, request):
        return not ConfiguracionInstitucion.objects.exists()

class TipoConceptoPagoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)

class ConceptoPagoAdmin(admin.ModelAdmin):
    list_display = ('nombre_concepto', 'tipo_concepto', 'monto_estandar', 'automatico', 'periodo_academico_aplicable', 'fecha_vencimiento_general')
    list_filter = ('tipo_concepto', 'automatico')
    search_fields = ('nombre_concepto', 'descripcion_detallada')

class CuentaPorCobrarEstudianteAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'concepto_pago', 'monto_asignado', 'monto_pagado', 'saldo_pendiente', 'fecha_vencimiento_especifica', 'estado')
    search_fields = ('estudiante__usuario__username', 'concepto_pago__nombre_concepto')
    readonly_fields = ('fecha_creacion', 'ultima_modificacion', 'saldo_pendiente')

class PagoRegistradoAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'fecha_pago', 'valor_pagado', 'metodo_pago', 'registrado_por', 'fecha_registro_sistema')
    readonly_fields = ('fecha_registro_sistema',)

class NoticiaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'fecha_publicacion', 'publicado_por')
    raw_id_fields = ('publicado_por',)

# Registro en el admin site
admin.site.register(Grado)
admin.site.register(Estudiante, EstudianteAdmin)
admin.site.register(Docente, DocenteAdmin)
admin.site.register(Familiar)
admin.site.register(Materia, MateriaAdmin)
admin.site.register(PeriodoAcademico, PeriodoAcademicoAdmin)
admin.site.register(Curso, CursoAdmin)
admin.site.register(DirectorCurso, DirectorCursoAdmin)
admin.site.register(EsquemaCalificacion)
admin.site.register(TipoActividad)
admin.site.register(ActividadCalificable, ActividadCalificableAdmin)
admin.site.register(Calificacion, CalificacionAdmin)
admin.site.register(PlanCurricular, PlanCurricularAdmin)
admin.site.register(Deber, DeberAdmin)
admin.site.register(EntregaDeber, EntregaDeberAdmin)
admin.site.register(MencionReconocimiento, MencionReconocimientoAdmin)
admin.site.register(ArchivoPlanAcademico, ArchivoPlanAcademicoAdmin)
admin.site.register(ConfiguracionInstitucion, ConfiguracionInstitucionAdmin)
admin.site.register(TipoConceptoPago, TipoConceptoPagoAdmin)
admin.site.register(ConceptoPago, ConceptoPagoAdmin)
admin.site.register(CuentaPorCobrarEstudiante, CuentaPorCobrarEstudianteAdmin)
admin.site.register(PagoRegistrado, PagoRegistradoAdmin)
admin.site.register(Noticia, NoticiaAdmin)
