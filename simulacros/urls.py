from django.urls import path
from . import views

app_name = 'simulacros'

urlpatterns = [
    # Banco de preguntas
    path('banco/',                        views.banco_preguntas,          name='banco_preguntas'),
    path('banco/nueva/',                  views.crear_pregunta,           name='crear_pregunta'),
    path('banco/<int:pk>/editar/',        views.editar_pregunta,          name='editar_pregunta'),
    path('banco/<int:pk>/eliminar/',      views.eliminar_pregunta,        name='eliminar_pregunta'),
    path('banco/importar/',               views.importar_preguntas,       name='importar_preguntas'),
    path('banco/plantilla/',              views.descargar_plantilla_excel, name='plantilla_excel'),
    path('banco/generar-ia/',             views.generar_preguntas_ia,     name='generar_ia'),
    path('banco/guardar-ia/',             views.guardar_preguntas_ia,     name='guardar_ia'),

    # Simulacros (docente)
    path('',                              views.lista_simulacros,         name='lista_simulacros'),
    path('nuevo/',                        views.crear_simulacro,          name='crear_simulacro'),
    path('<int:pk>/editar/',              views.editar_simulacro,         name='editar_simulacro'),
    path('<int:pk>/estado/',              views.cambiar_estado_simulacro, name='cambiar_estado'),
    path('<int:pk>/eliminar/',            views.eliminar_simulacro,       name='eliminar_simulacro'),
    path('<int:pk>/resultados/',          views.resultados_simulacro,     name='resultados_simulacro'),

    # Estudiante
    path('mis-simulacros/',              views.simulacros_estudiante,    name='simulacros_estudiante'),
    path('resolver/<int:pk>/',           views.resolver_simulacro,       name='resolver_simulacro'),
    path('resultado/<int:pk>/',          views.resultado_intento,        name='resultado_intento'),
]
