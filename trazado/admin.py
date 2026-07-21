from django.contrib import admin

from .models import (
    IntentoTrazado, PlantillaTrazado, TableroTrazado, TrazoEstudiante,
)


class PlantillaInline(admin.TabularInline):
    model = PlantillaTrazado
    extra = 0


@admin.register(TableroTrazado)
class TableroTrazadoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'curso', 'estado', 'institucion', 'creado_en')
    list_filter = ('institucion', 'estado')
    search_fields = ('titulo',)
    inlines = [PlantillaInline]


@admin.register(IntentoTrazado)
class IntentoTrazadoAdmin(admin.ModelAdmin):
    list_display = ('tablero', 'estudiante', 'hechas', 'total', 'puntaje', 'completado', 'fin')
    list_filter = ('institucion', 'completado')


admin.site.register(TrazoEstudiante)
