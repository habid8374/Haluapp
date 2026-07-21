from django.contrib import admin

from .models import IntentoSecuencia, ItemSecuencia, SecuenciaActividad


class ItemInline(admin.TabularInline):
    model = ItemSecuencia
    extra = 0


@admin.register(SecuenciaActividad)
class SecuenciaActividadAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'curso', 'estado', 'institucion', 'creado_en')
    list_filter = ('institucion', 'estado')
    search_fields = ('titulo',)
    inlines = [ItemInline]


@admin.register(IntentoSecuencia)
class IntentoSecuenciaAdmin(admin.ModelAdmin):
    list_display = ('actividad', 'estudiante', 'aciertos', 'total', 'puntaje', 'completado', 'fin')
    list_filter = ('institucion', 'completado')
