from django.contrib import admin
from proyecto_colegio.admin_mixins import InstitucionScopedAdminMixin

from .models import IntentoFlashcard, MazoFlashcard, TarjetaFlashcard


class TarjetaInline(admin.TabularInline):
    model = TarjetaFlashcard
    extra = 0


@admin.register(MazoFlashcard)
class MazoFlashcardAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('titulo', 'curso', 'estado', 'institucion', 'creado_en')
    list_filter = ('institucion', 'estado')
    search_fields = ('titulo',)
    inlines = [TarjetaInline]


@admin.register(IntentoFlashcard)
class IntentoFlashcardAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('mazo', 'estudiante', 'aciertos', 'total', 'puntaje', 'completado', 'fin')
    list_filter = ('institucion', 'completado')
