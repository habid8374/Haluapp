from django.urls import path

from . import views

app_name = 'evaluacion_docente'

urlpatterns = [
    # Configuración (coordinador / administrador)
    path('', views.panel, name='panel'),
    path('criterios/', views.gestionar_criterios, name='criterios'),
    path('criterios/<int:pk>/editar/', views.criterio_editar, name='criterio_editar'),
    path('criterios/<int:pk>/eliminar/', views.criterio_eliminar, name='criterio_eliminar'),
    path('campanas/nueva/', views.crear_campana, name='crear_campana'),
    path('campanas/<int:pk>/estado/', views.campana_estado, name='campana_estado'),
    path('campanas/<int:pk>/resultados/', views.campana_resultados, name='campana_resultados'),
    path('campanas/<int:campana_pk>/docente/<int:docente_pk>/', views.resultados_docente, name='resultados_docente'),

    # Familias (acudientes)
    path('mis-evaluaciones/', views.mis_evaluaciones, name='mis_evaluaciones'),
    path('evaluar/<int:campana_pk>/<int:docente_pk>/<int:curso_pk>/<int:estudiante_pk>/', views.evaluar, name='evaluar'),

    # Docente
    path('mi-desempeno/', views.mi_desempeno, name='mi_desempeno'),
]
