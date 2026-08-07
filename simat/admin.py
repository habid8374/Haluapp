"""Admin de catálogos SIMAT y Sedes.

Los catálogos (Departamento, Municipio, Etnia, Resguardo, EPS, Caja de
Compensación) son tablas de referencia globales del MEN → admin normal de solo
consulta (como `DBAPredefinido`). `Sede` pertenece a una institución →
`InstitucionScopedAdminMixin`.
"""
from django.contrib import admin

from proyecto_colegio.admin_mixins import InstitucionScopedAdminMixin
from .models import (
    Departamento, Municipio, Etnia, Resguardo, EPS, CajaCompensacion, Sede,
)


class _CatalogoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'habilitado')
    search_fields = ('codigo', 'nombre')
    list_filter = ('habilitado',)
    ordering = ('nombre',)


@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre')
    search_fields = ('codigo', 'nombre')
    ordering = ('nombre',)


@admin.register(Municipio)
class MunicipioAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'departamento')
    search_fields = ('codigo', 'nombre')
    list_filter = ('departamento',)
    ordering = ('nombre',)
    autocomplete_fields = ()


@admin.register(Etnia)
class EtniaAdmin(_CatalogoAdmin):
    pass


@admin.register(Resguardo)
class ResguardoAdmin(_CatalogoAdmin):
    pass


@admin.register(EPS)
class EPSAdmin(_CatalogoAdmin):
    pass


@admin.register(CajaCompensacion)
class CajaCompensacionAdmin(_CatalogoAdmin):
    pass


@admin.register(Sede)
class SedeAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('nombre', 'codigo_dane_sede', 'zona', 'jornada_principal', 'es_principal', 'activa')
    search_fields = ('nombre', 'codigo_dane_sede', 'consecutivo')
    list_filter = ('zona', 'jornada_principal', 'es_principal', 'activa')
