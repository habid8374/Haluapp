from django.contrib import admin

from .models import (
    CampanaEvaluacion, CriterioEvaluacion, RespuestaEvaluacion, ValoracionCriterio,
)


@admin.register(CriterioEvaluacion)
class CriterioEvaluacionAdmin(admin.ModelAdmin):
    list_display = ('texto', 'institucion', 'orden', 'activo')
    list_filter = ('institucion', 'activo')
    search_fields = ('texto',)


@admin.register(CampanaEvaluacion)
class CampanaEvaluacionAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'institucion', 'periodo_academico', 'estado', 'creada_en')
    list_filter = ('institucion', 'estado')


@admin.register(RespuestaEvaluacion)
class RespuestaEvaluacionAdmin(admin.ModelAdmin):
    list_display = ('campana', 'docente', 'curso', 'anonimo', 'fecha')
    list_filter = ('institucion', 'campana', 'anonimo')


admin.site.register(ValoracionCriterio)
