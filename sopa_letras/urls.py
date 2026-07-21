from django.urls import path

from . import views

app_name = 'sopa_letras'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('nueva/', views.crear, name='crear'),
    path('<int:pk>/', views.detalle, name='detalle'),
    path('<int:pk>/publicar/', views.publicar, name='publicar'),
    path('<int:pk>/cerrar/', views.cerrar, name='cerrar'),
    path('<int:pk>/fechas/', views.editar_fechas, name='editar_fechas'),
    path('<int:pk>/datos/', views.editar_datos, name='editar_datos'),
    path('<int:pk>/palabra/agregar/', views.agregar_palabra, name='agregar_palabra'),
    path('<int:pk>/palabra/<int:palabra_pk>/editar/', views.editar_palabra, name='editar_palabra'),
    path('<int:pk>/palabra/<int:palabra_pk>/eliminar/', views.eliminar_palabra, name='eliminar_palabra'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
    path('<int:pk>/resultados/', views.resultados, name='resultados'),

    # Estudiante
    path('mis-sopas/', views.mis_sopas, name='mis_sopas'),
    path('resolver/<int:pk>/', views.resolver, name='resolver'),
    path('resultado/<int:pk>/', views.resultado, name='resultado'),
]
