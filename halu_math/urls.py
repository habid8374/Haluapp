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

    # Laboratorio Matemático (manipulativos visuales de uso libre)
    path('laboratorio/', views.laboratorio_index, name='laboratorio_index'),
    path('laboratorio/recta-numerica/', views.laboratorio_recta_numerica, name='laboratorio_recta_numerica'),
    path('laboratorio/bloques-base10/', views.laboratorio_bloques_base10, name='laboratorio_bloques_base10'),
    path('laboratorio/balanza/', views.laboratorio_balanza, name='laboratorio_balanza'),

    # Modo Reto (calificado, alimenta el motor real)
    path('laboratorio/recta-numerica/reto/', views.reto_recta_numerica, name='reto_recta_numerica'),
    path('laboratorio/recta-numerica/reto/responder/', views.responder_reto_recta_numerica, name='responder_reto_recta_numerica'),
    path('laboratorio/bloques-base10/reto/', views.reto_bloques_base10, name='reto_bloques_base10'),
    path('laboratorio/bloques-base10/reto/responder/', views.responder_reto_bloques_base10, name='responder_reto_bloques_base10'),
]
