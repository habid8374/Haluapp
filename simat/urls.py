from django.urls import path

from . import views

app_name = 'simat'

urlpatterns = [
    path('', views.hub_simat, name='hub'),
    path('reporte/exportar/', views.exportar_reporte_simat, name='exportar_reporte'),
    # Sedes (institución-scoped)
    path('sedes/', views.lista_sedes, name='lista_sedes'),
    path('sedes/nueva/', views.crear_sede, name='crear_sede'),
    path('sedes/<int:pk>/editar/', views.editar_sede, name='editar_sede'),
    path('sedes/<int:pk>/eliminar/', views.eliminar_sede, name='eliminar_sede'),
    # Grupos / secciones (institución-scoped)
    path('grupos/', views.lista_grupos, name='lista_grupos'),
    path('grupos/nuevo/', views.crear_grupo, name='crear_grupo'),
    path('grupos/<int:pk>/editar/', views.editar_grupo, name='editar_grupo'),
    path('grupos/<int:pk>/eliminar/', views.eliminar_grupo, name='eliminar_grupo'),
]
