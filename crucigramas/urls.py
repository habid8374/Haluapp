from django.urls import path

from . import views

app_name = 'crucigramas'

urlpatterns = [
    # Docente / coordinador
    path('', views.lista, name='lista'),
    path('nuevo/', views.crear, name='crear'),
    path('<int:pk>/', views.detalle, name='detalle'),
    path('<int:pk>/publicar/', views.publicar, name='publicar'),
    path('<int:pk>/cerrar/', views.cerrar, name='cerrar'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
    path('<int:pk>/resultados/', views.resultados, name='resultados'),

    # Estudiante
    path('mis-crucigramas/', views.mis_crucigramas, name='mis_crucigramas'),
    path('resolver/<int:pk>/', views.resolver, name='resolver'),
    path('resultado/<int:pk>/', views.resultado, name='resultado'),
]
