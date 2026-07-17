from django.urls import path

from . import views

app_name = 'autoevaluacion_institucional'

urlpatterns = [
    path('', views.panel, name='panel'),

    # Componentes (rúbrica editable)
    path('componentes/', views.gestionar_componentes, name='componentes'),
    path('componentes/<int:pk>/editar/', views.componente_editar, name='componente_editar'),
    path('componentes/<int:pk>/eliminar/', views.componente_eliminar, name='componente_eliminar'),

    # Autoevaluaciones
    path('nueva/', views.crear_autoevaluacion, name='crear'),
    path('<int:pk>/diligenciar/', views.diligenciar, name='diligenciar'),
    path('<int:pk>/cerrar/', views.cerrar_autoevaluacion, name='cerrar'),
    path('<int:pk>/reabrir/', views.reabrir_autoevaluacion, name='reabrir'),
    path('<int:pk>/resultados/', views.resultados, name='resultados'),
    path('<int:pk>/eliminar/', views.eliminar_autoevaluacion, name='eliminar'),
]
