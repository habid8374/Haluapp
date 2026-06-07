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

    # ------------------------------------------------------------------ #
    #  API JSON                                                            #
    # ------------------------------------------------------------------ #
    path('api/conversaciones/', views.api_conversaciones, name='api_conversaciones'),
    path('api/mensajes/<int:conversacion_id>/', views.api_mensajes, name='api_mensajes'),
    path('api/enviar/', views.api_enviar_mensaje, name='api_enviar'),
    path('api/no-leidos/', views.api_no_leidos, name='api_no_leidos'),
]
