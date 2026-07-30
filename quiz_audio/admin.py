from django.contrib import admin
from proyecto_colegio.admin_mixins import InstitucionScopedAdminMixin

from .models import IntentoQuizAudio, OpcionAudio, PreguntaAudio, QuizAudio


class OpcionInline(admin.TabularInline):
    model = OpcionAudio
    extra = 0


@admin.register(PreguntaAudio)
class PreguntaAudioAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    institucion_lookup = 'quiz__institucion'
    list_display = ('quiz', 'orden', 'enunciado')
    inlines = [OpcionInline]


class PreguntaInline(admin.TabularInline):
    model = PreguntaAudio
    extra = 0


@admin.register(QuizAudio)
class QuizAudioAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('titulo', 'curso', 'estado', 'institucion', 'creado_en')
    list_filter = ('institucion', 'estado')
    search_fields = ('titulo',)
    inlines = [PreguntaInline]


@admin.register(IntentoQuizAudio)
class IntentoQuizAudioAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('quiz', 'estudiante', 'aciertos', 'total', 'puntaje', 'completado', 'fin')
    list_filter = ('institucion', 'completado')
