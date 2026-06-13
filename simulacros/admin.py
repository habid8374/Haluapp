from django.contrib import admin
from .models import BancoPregunta, IntentoSimulacro, OpcionPregunta, Simulacro


class OpcionInline(admin.TabularInline):
    model = OpcionPregunta
    extra = 4
    max_num = 4


@admin.register(BancoPregunta)
class BancoPreguntaAdmin(admin.ModelAdmin):
    list_display  = ['grado_nivel', 'area', 'nivel_dificultad', 'es_publica', 'enunciado_corto']
    list_filter   = ['grado_nivel', 'area', 'es_publica', 'nivel_dificultad']
    search_fields = ['enunciado']
    inlines       = [OpcionInline]

    def enunciado_corto(self, obj):
        return obj.enunciado[:80]
    enunciado_corto.short_description = 'Enunciado'


@admin.register(Simulacro)
class SimulacroAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'institucion', 'estado', 'grado_nivel', 'fecha_inicio', 'fecha_cierre']
    list_filter  = ['estado', 'grado_nivel', 'institucion']


@admin.register(IntentoSimulacro)
class IntentoAdmin(admin.ModelAdmin):
    list_display = ['simulacro', 'estudiante', 'puntaje', 'completado', 'inicio']
    list_filter  = ['completado', 'simulacro']
