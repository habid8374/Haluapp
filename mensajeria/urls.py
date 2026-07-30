"""
mensajeria/urls.py
==================
Rutas para el módulo de mensajería directa.

Namespace: 'mensajeria'
Prefijo configurado en proyecto_colegio/urls.py: /mensajeria/
"""
from django.urls import path

from . import views

app_name = 'mensajeria'

urlpatterns = [
    # ------------------------------------------------------------------ #
    #  Vistas HTML                                                         #
    # ------------------------------------------------------------------ #
    path('', views.inbox, name='inbox'),
    path('<int:conversacion_id>/', views.detalle_conversacion, name='detalle'),
    path('nuevo/', views.nuevo_mensaje, name='nuevo'),
    path('iniciar/<int:destinatario_pk>/', views.iniciar_conversacion, name='iniciar'),
    path('<int:conversacion_id>/archivar/', views.archivar_conversacion, name='archivar'),
    path('<int:conversacion_id>/marcar-leida/', views.marcar_leida_conversacion, name='marcar_leida'),
    path('<int:conversacion_id>/eliminar/', views.eliminar_conversacion, name='eliminar'),
    path('historial/eliminar/', views.eliminar_historial, name='eliminar_historial'),

    # ------------------------------------------------------------------ #
    #  API JSON                                                            #
    # ------------------------------------------------------------------ #
    path('api/conversaciones/', views.api_conversaciones, name='api_conversaciones'),
    path('api/mensajes/<int:conversacion_id>/', views.api_mensajes, name='api_mensajes'),
    path('api/enviar/', views.api_enviar_mensaje, name='api_enviar'),
    path('api/no-leidos/', views.api_no_leidos, name='api_no_leidos'),

    # ------------------------------------------------------------------ #
    #  Presencia (en línea / ausente)                                     #
    # ------------------------------------------------------------------ #
    path('api/presencia/estado/', views.set_presencia, name='set_presencia'),
    path('api/presencia/auto-away/', views.set_auto_away, name='set_auto_away'),
    path('api/presencia/mi-estado/', views.mi_estado_presencia, name='mi_estado_presencia'),
]
