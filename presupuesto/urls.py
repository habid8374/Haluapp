from django.urls import path

from . import views

app_name = 'presupuesto'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    path('vigencias/', views.lista_vigencias, name='lista_vigencias'),
    path('vigencias/nueva/', views.crear_vigencia, name='crear_vigencia'),
    path('vigencias/<int:pk>/cerrar/', views.cerrar_vigencia, name='cerrar_vigencia'),

    path('rubros-ingreso/', views.lista_rubros_ingreso, name='lista_rubros_ingreso'),
    path('rubros-ingreso/nuevo/', views.crear_rubro_ingreso, name='crear_rubro_ingreso'),

    path('rubros-gasto/', views.lista_rubros_gasto, name='lista_rubros_gasto'),
    path('rubros-gasto/nuevo/', views.crear_rubro_gasto, name='crear_rubro_gasto'),

    path('ingresos/', views.lista_presupuesto_ingreso, name='lista_presupuesto_ingreso'),
    path('ingresos/nuevo/', views.crear_presupuesto_ingreso, name='crear_presupuesto_ingreso'),

    path('apropiaciones/', views.lista_apropiaciones, name='lista_apropiaciones'),
    path('apropiaciones/nueva/', views.crear_apropiacion, name='crear_apropiacion'),

    path('modificaciones/', views.lista_modificaciones, name='lista_modificaciones'),
    path('modificaciones/nueva/', views.crear_modificacion, name='crear_modificacion'),

    path('cdp/', views.lista_cdp, name='lista_cdp'),
    path('cdp/nuevo/', views.crear_cdp, name='crear_cdp'),
    path('cdp/<int:pk>/anular/', views.anular_cdp, name='anular_cdp'),

    path('rp/', views.lista_rp, name='lista_rp'),
    path('rp/nuevo/', views.crear_rp, name='crear_rp'),
    path('rp/<int:pk>/anular/', views.anular_rp, name='anular_rp'),

    path('obligaciones/', views.lista_obligaciones, name='lista_obligaciones'),
    path('obligaciones/nueva/', views.crear_obligacion, name='crear_obligacion'),
    path('obligaciones/<int:pk>/anular/', views.anular_obligacion, name='anular_obligacion'),

    path('ordenes-pago/', views.lista_ordenes_pago, name='lista_ordenes_pago'),
    path('ordenes-pago/nueva/', views.crear_orden_pago, name='crear_orden_pago'),
    path('ordenes-pago/<int:pk>/anular/', views.anular_orden_pago, name='anular_orden_pago'),
    path('ordenes-pago/<int:pk>/marcar-pagada/', views.marcar_orden_pagada, name='marcar_orden_pagada'),
]
