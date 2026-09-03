from django.urls import path

from . import views

app_name = 'halu_math'

urlpatterns = [
    # Banco de ejercicios (docente/coordinador)
    path('banco/', views.banco_ejercicios, name='banco_ejercicios'),
    path('banco/nuevo/', views.crear_ejercicio, name='crear_ejercicio'),
    path('banco/<int:pk>/editar/', views.editar_ejercicio, name='editar_ejercicio'),
    path('banco/<int:pk>/eliminar/', views.eliminar_ejercicio, name='eliminar_ejercicio'),
    path('banco/generar-ia/', views.generar_ia, name='generar_ia'),
    path('banco/guardar-ia/', views.guardar_ia, name='guardar_ia'),

    # Dashboard docente
    path('progreso/', views.progreso_grupo, name='progreso_grupo'),
    path('progreso/<int:estudiante_pk>/', views.progreso_estudiante, name='progreso_estudiante'),

    # Estudiante
    path('practicar/', views.elegir_dba, name='elegir_dba'),
    path('practicar/<int:dba_pk>/', views.practicar_dba, name='practicar_dba'),
    path('practicar/<int:dba_pk>/responder/', views.responder_ejercicio, name='responder_ejercicio'),
    path('mi-progreso/', views.mi_progreso_math, name='mi_progreso_math'),
]
