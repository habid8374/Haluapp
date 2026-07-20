from django.urls import path

from . import views

app_name = 'flashcards'

urlpatterns = [
    # Docente / coordinador
    path('', views.lista, name='lista'),
    path('nuevo/', views.crear, name='crear'),
    path('<int:pk>/', views.detalle, name='detalle'),
    path('<int:pk>/tarjeta/agregar/', views.agregar_tarjeta, name='agregar_tarjeta'),
    path('<int:pk>/tarjeta/<int:tarjeta_pk>/eliminar/', views.eliminar_tarjeta, name='eliminar_tarjeta'),
    path('<int:pk>/publicar/', views.publicar, name='publicar'),
    path('<int:pk>/cerrar/', views.cerrar, name='cerrar'),
    path('<int:pk>/fechas/', views.editar_fechas, name='editar_fechas'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
    path('<int:pk>/resultados/', views.resultados, name='resultados'),

    # Estudiante
    path('mis-flashcards/', views.mis_mazos, name='mis_mazos'),
    path('resolver/<int:pk>/', views.resolver, name='resolver'),
    path('resolver/<int:pk>/responder/', views.responder, name='responder'),
    path('resultado/<int:pk>/', views.resultado, name='resultado'),
]
