from django.urls import path

from . import views

app_name = 'simat'

urlpatterns = [
    path('', views.hub_simat, name='hub'),
    path('reporte/exportar/', views.exportar_reporte_simat, name='exportar_reporte'),
]
