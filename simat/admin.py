"""Admin de catálogos SIMAT y Sedes.

Los catálogos (Departamento, Municipio, Etnia, Resguardo, EPS, Caja de
Compensación) son tablas de referencia GLOBALES del MEN, compartidas por todas
las instituciones. Para respetar la separación multi-institución, SOLO el
superusuario de la plataforma puede administrarlas (`SuperuserOnlyAdminMixin`):
ninguna institución debe poder alterar datos que afectan a las demás. Las
instituciones solo las SELECCIONAN desde los formularios (no vía admin).

`Sede` sí pertenece a una institución → `InstitucionScopedAdminMixin`.
"""
from django.contrib import admin

from proyecto_colegio.admin_mixins import (
    InstitucionScopedAdminMixin, SuperuserOnlyAdminMixin,
)
from .models import (
    Departamento, Municipio, Etnia, Resguardo, EPS, CajaCompensacion, Sede,
)


class _CatalogoAdmin(SuperuserOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'habilitado')
    search_fields = ('codigo', 'nombre')
    list_filter = ('habilitado',)
    ordering = ('nombre',)


@admin.register(Departamento)
class DepartamentoAdmin(SuperuserOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('codigo', 'nombre')
    search_fields = ('codigo', 'nombre')
    ordering = ('nombre',)


@admin.register(Municipio)
class MunicipioAdmin(SuperuserOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'departamento')
    search_fields = ('codigo', 'nombre')
    list_filter = ('departamento',)
    ordering = ('nombre',)


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
