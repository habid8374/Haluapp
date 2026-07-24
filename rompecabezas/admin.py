from django.contrib import admin

from .models import IntentoRompecabezas, Rompecabezas


@admin.register(Rompecabezas)
class RompecabezasAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'curso', 'filas', 'columnas', 'estado', 'institucion', 'creado_en')
    list_filter = ('institucion', 'estado')
    search_fields = ('titulo',)


@admin.register(IntentoRompecabezas)
class IntentoRompecabezasAdmin(admin.ModelAdmin):
    list_display = ('rompecabezas', 'estudiante', 'movimientos', 'tiempo_segundos', 'puntaje', 'completado', 'fin')
    list_filter = ('institucion', 'completado')
