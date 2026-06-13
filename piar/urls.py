from django.urls import path
from . import views

app_name = 'piar'

urlpatterns = [
    path('', views.lista_piars, name='lista_piars'),
    path('nuevo/', views.crear_piar, name='crear_piar'),
    path('<int:pk>/', views.detalle_piar, name='detalle_piar'),
    path('<int:pk>/editar/', views.editar_piar, name='editar_piar'),
    path('<int:pk>/eliminar/', views.eliminar_piar, name='eliminar_piar'),
    path('<int:piar_pk>/ajuste/nuevo/', views.crear_ajuste, name='crear_ajuste'),
    path('<int:piar_pk>/ajuste/<int:ajuste_pk>/editar/', views.editar_ajuste, name='editar_ajuste'),
    path('<int:piar_pk>/ajuste/<int:ajuste_pk>/eliminar/', views.eliminar_ajuste, name='eliminar_ajuste'),
    path('<int:piar_pk>/ajuste/<int:ajuste_pk>/seguimiento/', views.actualizar_seguimiento, name='actualizar_seguimiento'),
]
