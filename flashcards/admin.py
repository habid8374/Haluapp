from django.contrib import admin

from .models import IntentoFlashcard, MazoFlashcard, TarjetaFlashcard


class TarjetaInline(admin.TabularInline):
    model = TarjetaFlashcard
    extra = 0


@admin.register(MazoFlashcard)
class MazoFlashcardAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'curso', 'estado', 'institucion', 'creado_en')
    list_filter = ('institucion', 'estado')
    search_fields = ('titulo',)
    inlines = [TarjetaInline]


@admin.register(IntentoFlashcard)
class IntentoFlashcardAdmin(admin.ModelAdmin):
    list_display = ('mazo', 'estudiante', 'aciertos', 'total', 'puntaje', 'completado', 'fin')
    list_filter = ('institucion', 'completado')
