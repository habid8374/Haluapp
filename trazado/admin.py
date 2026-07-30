from django.contrib import admin
from proyecto_colegio.admin_mixins import InstitucionScopedAdminMixin

from .models import (
    IntentoTrazado, PlantillaTrazado, TableroTrazado, TrazoEstudiante,
)


class PlantillaInline(admin.TabularInline):
    model = PlantillaTrazado
    extra = 0


@admin.register(TableroTrazado)
class TableroTrazadoAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('titulo', 'curso', 'estado', 'institucion', 'creado_en')
    list_filter = ('institucion', 'estado')
    search_fields = ('titulo',)
    inlines = [PlantillaInline]


@admin.register(IntentoTrazado)
class IntentoTrazadoAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('tablero', 'estudiante', 'hechas', 'total', 'puntaje', 'completado', 'fin')
    list_filter = ('institucion', 'completado')


@admin.register(TrazoEstudiante)
class TrazoEstudianteAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    institucion_lookup = 'intento__institucion'
