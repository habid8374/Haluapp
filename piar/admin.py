from django.contrib import admin
from .models import PIAR, AjustePIAR


class AjustePIARInline(admin.TabularInline):
    model = AjustePIAR
    extra = 0
    fields = ('materia', 'periodo', 'logro_ajustado', 'alcanzado')


@admin.register(PIAR)
class PIARAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'año_lectivo', 'condicion', 'estado', 'docente_lider', 'institucion')
    list_filter = ('estado', 'condicion', 'año_lectivo', 'institucion')
    search_fields = ('estudiante__usuario__first_name', 'estudiante__usuario__last_name')
    inlines = [AjustePIARInline]


@admin.register(AjustePIAR)
class AjustePIARAdmin(admin.ModelAdmin):
    list_display = ('piar', 'materia', 'periodo', 'alcanzado')
    list_filter = ('periodo', 'alcanzado')
