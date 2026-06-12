from django.contrib import admin

from proyecto_colegio.admin_mixins import InstitucionScopedAdminMixin

from .models import Cuestionario, PreguntaCuestionario, OpcionPregunta

class OpcionPreguntaInline(admin.TabularInline):
    model = OpcionPregunta
    extra = 1

@admin.register(PreguntaCuestionario)
class PreguntaCuestionarioAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    institucion_lookup = 'cuestionario__institucion'
    list_display = ('enunciado', 'cuestionario', 'tipo', 'orden')  # Cambiado 'texto' a 'enunciado'
    list_filter = ('tipo', 'cuestionario__titulo')
    inlines = [OpcionPreguntaInline]

@admin.register(Cuestionario)
class CuestionarioAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('titulo', 'actividad_calificable', 'tiempo_limite', 'creado_por')
    search_fields = ('titulo', 'actividad_calificable__titulo')
