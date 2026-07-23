from django.urls import path

from . import views

app_name = 'passkeys'

urlpatterns = [
    path('', views.gestionar, name='gestionar'),
    path('registro/opciones/', views.opciones_registro, name='opciones_registro'),
    path('registro/verificar/', views.verificar_registro, name='verificar_registro'),
    path('login/opciones/', views.opciones_login, name='opciones_login'),
    path('login/verificar/', views.verificar_login, name='verificar_login'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
]
