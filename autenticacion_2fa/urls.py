from django.urls import path
from . import views

app_name = '2fa'

urlpatterns = [
    path('configurar/', views.configurar_2fa, name='configurar'),
    path('verificar/', views.verificar_2fa, name='verificar'),
    path('desactivar/', views.desactivar_2fa, name='desactivar'),
]
