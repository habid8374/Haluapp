from django.urls import path

from . import views

app_name = 'secuencias'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('nueva/', views.crear, name='crear'),
    path('<int:pk>/', views.detalle, name='detalle'),
    path('<int:pk>/publicar/', views.publicar, name='publicar'),
    path('<int:pk>/cerrar/', views.cerrar, name='cerrar'),
    path('<int:pk>/datos/', views.editar_datos, name='editar_datos'),
    path('<int:pk>/item/agregar/', views.agregar_item, name='agregar_item'),
    path('<int:pk>/item/<int:item_pk>/editar/', views.editar_item, name='editar_item'),
    path('<int:pk>/item/<int:item_pk>/mover/', views.mover_item, name='mover_item'),
    path('<int:pk>/item/<int:item_pk>/eliminar/', views.eliminar_item, name='eliminar_item'),
    path('<int:pk>/fechas/', views.editar_fechas, name='editar_fechas'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
    path('<int:pk>/resultados/', views.resultados, name='resultados'),

    # Estudiante
    path('mis-secuencias/', views.mis_secuencias, name='mis_secuencias'),
    path('resolver/<int:pk>/', views.resolver, name='resolver'),
    path('resultado/<int:pk>/', views.resultado, name='resultado'),
]
