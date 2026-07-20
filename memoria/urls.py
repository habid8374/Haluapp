from django.urls import path

from . import views

app_name = 'memoria'

urlpatterns = [
    # Docente / coordinador
    path('', views.lista, name='lista'),
    path('nuevo/', views.crear, name='crear'),
    path('<int:pk>/', views.detalle, name='detalle'),
    path('<int:pk>/pareja/agregar/', views.agregar_pareja, name='agregar_pareja'),
    path('<int:pk>/pareja/<int:pareja_pk>/eliminar/', views.eliminar_pareja, name='eliminar_pareja'),
    path('<int:pk>/publicar/', views.publicar, name='publicar'),
    path('<int:pk>/cerrar/', views.cerrar, name='cerrar'),
    path('<int:pk>/fechas/', views.editar_fechas, name='editar_fechas'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
    path('<int:pk>/resultados/', views.resultados, name='resultados'),

    # Estudiante
    path('mis-juegos/', views.mis_juegos, name='mis_juegos'),
    path('jugar/<int:pk>/', views.jugar, name='jugar'),
    path('resultado/<int:pk>/', views.resultado, name='resultado'),
]
