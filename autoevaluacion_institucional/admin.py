from django.contrib import admin
from proyecto_colegio.admin_mixins import InstitucionScopedAdminMixin

from .models import (
    AutoevaluacionInstitucional, ComponenteGestion, ValoracionGestion,
)


@admin.register(ComponenteGestion)
class ComponenteGestionAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('nombre', 'area', 'institucion', 'orden', 'activo')
    list_filter = ('institucion', 'area', 'activo')
    search_fields = ('nombre',)


@admin.register(AutoevaluacionInstitucional)
class AutoevaluacionInstitucionalAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('titulo', 'anio', 'institucion', 'estado', 'creada_en')
    list_filter = ('institucion', 'estado', 'anio')


@admin.register(ValoracionGestion)
class ValoracionGestionAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    institucion_lookup = 'autoevaluacion__institucion'
    list_display = ('autoevaluacion', 'componente', 'valor')
    list_filter = ('autoevaluacion__institucion', 'componente__area')
