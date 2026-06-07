"""
recursos_educativos/urls.py
===========================
Todas las rutas bajo /academico/recursos/
"""
from django.urls import path
from . import views

app_name = 'recursos_educativos'

urlpatterns = [

    # ── Docente ────────────────────────────────────────────────────────────
    path('',
         views.lista_recursos_docente,
         name='lista'),

    path('crear/',
         views.crear_recurso_3d,
         name='crear'),

    path('<int:pk>/entregas/',
         views.ver_entregas_recurso,
         name='entregas'),

    # ── Galería 3D directa para docentes (sin actividad, para proyectar) ──
    path('galeria/',
         views.galeria_directa,
         name='galeria_directa'),

    # ── (legacy) galería ligada a actividad ────────────────────────────────
    path('<int:pk>/galeria/',
         views.abrir_visor_galeria,
         name='galeria'),

    path('<int:pk>/studio/',
         views.abrir_visor_studio,
         name='studio'),

    # ── API interna (llamada desde studio.js) ──────────────────────────────
    path('api/progreso/<int:pk>/',
         views.api_registrar_progreso,
         name='api_progreso'),
]
