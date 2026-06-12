from django.urls import path
from . import views

app_name = 'auditoria'

urlpatterns = [
    path('historial/', views.historial_auditoria, name='historial'),
]
