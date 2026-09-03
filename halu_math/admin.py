from django.contrib import admin

from proyecto_colegio.admin_mixins import InstitucionScopedAdminMixin

from .models import DominioDBA, EjercicioMath, IntentoEjercicioMath, IntentoManipulativo, OpcionEjercicioMath


class OpcionEjercicioMathInline(admin.TabularInline):
    model = OpcionEjercicioMath
    extra = 0


@admin.register(EjercicioMath)
class EjercicioMathAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    """El catálogo público (institucion vacío, es_publica=True) lo cura el
    propietario de la plataforma (superusuario). Un colegio puede tener,
    además, sus propios ejercicios privados generados por sus docentes."""
    list_display = ('dba', 'nivel_dificultad', 'es_publica', 'institucion', 'activo')
    search_fields = ('enunciado',)
    list_filter = ('nivel_dificultad', 'es_publica', 'activo')
    ordering = ('dba', 'nivel_dificultad')
    raw_id_fields = ('institucion', 'dba')
    inlines = [OpcionEjercicioMathInline]


@admin.register(DominioDBA)
class DominioDBAAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('estudiante', 'dba', 'nivel_actual', 'racha_actual', 'racha_fluida_actual', 'dominado', 'institucion')
    search_fields = ('estudiante__usuario__first_name', 'estudiante__usuario__last_name')
    list_filter = ('nivel_actual', 'dominado')
    ordering = ('-actualizado_en',)
    raw_id_fields = ('institucion', 'estudiante', 'dba')


@admin.register(IntentoEjercicioMath)
class IntentoEjercicioMathAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('estudiante', 'ejercicio', 'es_correcta', 'es_fluido', 'nivel_en_el_momento', 'creado_en', 'institucion')
    list_filter = ('es_correcta', 'es_fluido', 'nivel_en_el_momento')
    ordering = ('-creado_en',)
    raw_id_fields = ('institucion', 'estudiante', 'ejercicio', 'opcion_elegida')


@admin.register(IntentoManipulativo)
class IntentoManipulativoAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('estudiante', 'dba', 'tipo', 'es_correcta', 'es_fluido', 'nivel_en_el_momento', 'creado_en', 'institucion')
    list_filter = ('tipo', 'es_correcta', 'es_fluido', 'nivel_en_el_momento')
    ordering = ('-creado_en',)
    raw_id_fields = ('institucion', 'estudiante', 'dba')
