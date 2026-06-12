from django.contrib import admin

from proyecto_colegio.admin_mixins import InstitucionScopedAdminMixin

from .models import RecursoEducativo3D, EntregaRecurso3D


@admin.register(RecursoEducativo3D)
class RecursoEducativo3DAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('__str__', 'modo', 'valor_maximo', 'institucion')
    list_filter  = ('modo', 'institucion')
    search_fields = ('actividad__titulo', 'institucion__nombre')
    raw_id_fields = ('actividad',)


@admin.register(EntregaRecurso3D)
class EntregaRecurso3DAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display  = ('estudiante', 'recurso', 'piezas_colocadas', 'completado', 'fecha_inicio', 'institucion')
    list_filter   = ('completado', 'institucion')
    search_fields = ('estudiante__usuario__first_name', 'estudiante__usuario__last_name',
                     'recurso__actividad__titulo')
    readonly_fields = ('fecha_inicio', 'fecha_completado')
