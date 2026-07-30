from django.contrib import admin
from proyecto_colegio.admin_mixins import InstitucionScopedAdminMixin

from .models import IntentoMemoria, JuegoMemoria, ParejaMemoria


class ParejaInline(admin.TabularInline):
    model = ParejaMemoria
    extra = 0


@admin.register(JuegoMemoria)
class JuegoMemoriaAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('titulo', 'curso', 'estado', 'modo_nota', 'institucion', 'creado_en')
    list_filter = ('institucion', 'estado', 'modo_nota')
    search_fields = ('titulo',)
    inlines = [ParejaInline]


@admin.register(IntentoMemoria)
class IntentoMemoriaAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('juego', 'estudiante', 'movimientos', 'parejas_total', 'puntaje', 'completado', 'fin')
    list_filter = ('institucion', 'completado')
