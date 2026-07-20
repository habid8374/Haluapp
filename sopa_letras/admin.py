from django.contrib import admin

from .models import IntentoSopa, PalabraSopa, Sopa


class PalabraSopaInline(admin.TabularInline):
    model = PalabraSopa
    extra = 0


@admin.register(Sopa)
class SopaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'curso', 'estado', 'institucion', 'creado_en')
    list_filter = ('institucion', 'estado')
    search_fields = ('titulo',)
    inlines = [PalabraSopaInline]


@admin.register(IntentoSopa)
class IntentoSopaAdmin(admin.ModelAdmin):
    list_display = ('sopa', 'estudiante', 'encontradas', 'total', 'puntaje', 'completado', 'fin')
    list_filter = ('institucion', 'completado')
