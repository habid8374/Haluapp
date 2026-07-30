from django.contrib import admin
from proyecto_colegio.admin_mixins import InstitucionScopedAdminMixin

from .models import (
    CampanaEvaluacion, CriterioEvaluacion, RespuestaEvaluacion, ValoracionCriterio,
)


@admin.register(CriterioEvaluacion)
class CriterioEvaluacionAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('texto', 'institucion', 'orden', 'activo')
    list_filter = ('institucion', 'activo')
    search_fields = ('texto',)


@admin.register(CampanaEvaluacion)
class CampanaEvaluacionAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('titulo', 'institucion', 'periodo_academico', 'estado', 'creada_en')
    list_filter = ('institucion', 'estado')


@admin.register(RespuestaEvaluacion)
class RespuestaEvaluacionAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('campana', 'docente', 'curso', 'anonimo', 'fecha')
    list_filter = ('institucion', 'campana', 'anonimo')


@admin.register(ValoracionCriterio)
class ValoracionCriterioAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    institucion_lookup = 'respuesta__institucion'
