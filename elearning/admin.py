from django.contrib import admin

from proyecto_colegio.admin_mixins import InstitucionScopedAdminMixin

from .models import Curso, Modulo, Material, Evaluacion, Pregunta, Opcion, InscripcionCurso, ProgresoModulo

@admin.register(Curso)
class CursoAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('nombre', 'institucion', 'precio', 'duracion_horas', 'publicado', 'fecha_creacion')
    list_filter = ('institucion', 'publicado')
    search_fields = ('nombre', 'descripcion')

class MaterialInline(admin.TabularInline):
    model = Material
    extra = 1

@admin.register(Modulo)
class ModuloAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    institucion_lookup = 'curso__institucion'
    list_display = ('titulo', 'curso', 'orden')
    list_filter = ('curso__institucion', 'curso')
    search_fields = ('titulo',)
    inlines = [MaterialInline]

@admin.register(Evaluacion)
class EvaluacionAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    institucion_lookup = 'modulo__curso__institucion'
    list_display = ('titulo', 'modulo', 'porcentaje_aprobacion', 'intentos_permitidos')

class OpcionInline(admin.TabularInline):
    model = Opcion
    extra = 2

@admin.register(Pregunta)
class PreguntaAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    institucion_lookup = 'evaluacion__modulo__curso__institucion'
    list_display = ('texto', 'evaluacion', 'puntos')
    inlines = [OpcionInline]

@admin.register(InscripcionCurso)
class InscripcionCursoAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    institucion_lookup = 'curso__institucion'
    list_display = ('estudiante', 'curso', 'fecha_inscripcion', 'activo', 'progreso_porcentaje')
    list_filter = ('curso__institucion', 'curso', 'activo')
    search_fields = ('estudiante__usuario__first_name', 'estudiante__usuario__last_name', 'estudiante__documento_identidad')

@admin.register(ProgresoModulo)
class ProgresoModuloAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    institucion_lookup = 'inscripcion__curso__institucion'
    list_display = ('inscripcion', 'modulo', 'completado', 'aprobado', 'mejor_nota')
    list_filter = ('completado', 'aprobado')
