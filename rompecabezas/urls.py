from django.urls import path

from . import views

app_name = 'rompecabezas'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('nuevo/', views.crear, name='crear'),
    path('<int:pk>/', views.detalle, name='detalle'),
    path('<int:pk>/publicar/', views.publicar, name='publicar'),
    path('<int:pk>/cerrar/', views.cerrar, name='cerrar'),
    path('<int:pk>/fechas/', views.editar_fechas, name='editar_fechas'),
    path('<int:pk>/datos/', views.editar_datos, name='editar_datos'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
    path('<int:pk>/resultados/', views.resultados, name='resultados'),

    # Estudiante
    path('mis-rompecabezas/', views.mis_rompecabezas, name='mis_rompecabezas'),
    path('resolver/<int:pk>/', views.resolver, name='resolver'),
    path('resultado/<int:pk>/', views.resultado, name='resultado'),
]
