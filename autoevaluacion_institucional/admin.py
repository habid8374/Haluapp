from django.contrib import admin

from .models import (
    AutoevaluacionInstitucional, ComponenteGestion, ValoracionGestion,
)


@admin.register(ComponenteGestion)
class ComponenteGestionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'area', 'institucion', 'orden', 'activo')
    list_filter = ('institucion', 'area', 'activo')
    search_fields = ('nombre',)


@admin.register(AutoevaluacionInstitucional)
class AutoevaluacionInstitucionalAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'anio', 'institucion', 'estado', 'creada_en')
    list_filter = ('institucion', 'estado', 'anio')


@admin.register(ValoracionGestion)
class ValoracionGestionAdmin(admin.ModelAdmin):
    list_display = ('autoevaluacion', 'componente', 'valor')
    list_filter = ('autoevaluacion__institucion', 'componente__area')
