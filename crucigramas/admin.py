from django.contrib import admin
from proyecto_colegio.admin_mixins import InstitucionScopedAdminMixin

from .models import Crucigrama, IntentoCrucigrama, PalabraCrucigrama


class PalabraInline(admin.TabularInline):
    model = PalabraCrucigrama
    extra = 0


@admin.register(Crucigrama)
class CrucigramaAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('titulo', 'curso', 'estado', 'institucion', 'creado_en')
    list_filter = ('institucion', 'estado')
    search_fields = ('titulo',)
    inlines = [PalabraInline]


@admin.register(IntentoCrucigrama)
class IntentoCrucigramaAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('crucigrama', 'estudiante', 'porcentaje', 'puntaje', 'completado', 'fin')
    list_filter = ('institucion', 'completado')
