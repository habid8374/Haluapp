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
    path('ingresos/<int:pk>/recaudo/', views.registrar_recaudo, name='registrar_recaudo'),

    path('apropiaciones/', views.lista_apropiaciones, name='lista_apropiaciones'),
    path('apropiaciones/nueva/', views.crear_apropiacion, name='crear_apropiacion'),

    path('modificaciones/', views.lista_modificaciones, name='lista_modificaciones'),
    path('modificaciones/nueva/', views.crear_modificacion, name='crear_modificacion'),

    path('cdp/', views.lista_cdp, name='lista_cdp'),
    path('cdp/nuevo/', views.crear_cdp, name='crear_cdp'),
    path('cdp/<int:pk>/anular/', views.anular_cdp, name='anular_cdp'),
    path('cdp/<int:pk>/imprimir/', views.imprimir_cdp, name='imprimir_cdp'),

    path('rp/', views.lista_rp, name='lista_rp'),
    path('rp/nuevo/', views.crear_rp, name='crear_rp'),
    path('rp/<int:pk>/anular/', views.anular_rp, name='anular_rp'),
    path('rp/<int:pk>/imprimir/', views.imprimir_rp, name='imprimir_rp'),

    path('obligaciones/', views.lista_obligaciones, name='lista_obligaciones'),
    path('obligaciones/nueva/', views.crear_obligacion, name='crear_obligacion'),
    path('obligaciones/<int:pk>/anular/', views.anular_obligacion, name='anular_obligacion'),
    path('obligaciones/<int:pk>/imprimir/', views.imprimir_obligacion, name='imprimir_obligacion'),

    path('ordenes-pago/', views.lista_ordenes_pago, name='lista_ordenes_pago'),
    path('ordenes-pago/nueva/', views.crear_orden_pago, name='crear_orden_pago'),
    path('ordenes-pago/<int:pk>/', views.detalle_orden_pago, name='detalle_orden_pago'),
    path('ordenes-pago/<int:pk>/anular/', views.anular_orden_pago, name='anular_orden_pago'),
    path('ordenes-pago/<int:pk>/retenciones/agregar/', views.agregar_retencion, name='agregar_retencion'),
    path('ordenes-pago/<int:pk>/retenciones/<int:retencion_pk>/quitar/', views.quitar_retencion, name='quitar_retencion'),
    path('ordenes-pago/<int:pk>/generar-comprobante/', views.generar_comprobante, name='generar_comprobante'),
    path('ordenes-pago/<int:pk>/imprimir/', views.imprimir_orden_pago, name='imprimir_orden_pago'),

    path('conceptos-retencion/', views.lista_conceptos_retencion, name='lista_conceptos_retencion'),
    path('conceptos-retencion/nuevo/', views.crear_concepto_retencion, name='crear_concepto_retencion'),

    path('comprobantes/', views.lista_comprobantes, name='lista_comprobantes'),
    path('comprobantes/<int:pk>/', views.detalle_comprobante, name='detalle_comprobante'),
    path('comprobantes/<int:pk>/contabilizar/', views.contabilizar_comprobante, name='contabilizar_comprobante'),
    path('comprobantes/<int:pk>/reversar/', views.reversar_comprobante, name='reversar_comprobante'),
    path('comprobantes/<int:pk>/imprimir/', views.imprimir_comprobante, name='imprimir_comprobante'),

    path('catalogo-cgc/', views.lista_catalogo_cgc, name='lista_catalogo_cgc'),

    path('categoria-cpc/buscar/', views.buscar_categoria_cpc, name='buscar_categoria_cpc'),

    path('cuentas-bancarias/', views.lista_cuentas_bancarias, name='lista_cuentas_bancarias'),
    path('cuentas-bancarias/nueva/', views.crear_cuenta_bancaria, name='crear_cuenta_bancaria'),

    path('tesoreria/movimientos/', views.lista_movimientos_tesoreria, name='lista_movimientos_tesoreria'),
    path('tesoreria/movimientos/<int:pk>/conciliar/', views.conciliar_movimiento_tesoreria, name='conciliar_movimiento_tesoreria'),

    path('almacen/elementos/', views.lista_elementos_almacen, name='lista_elementos_almacen'),
    path('almacen/elementos/nuevo/', views.crear_elemento_almacen, name='crear_elemento_almacen'),
    path('almacen/movimientos/', views.lista_movimientos_almacen, name='lista_movimientos_almacen'),
    path('almacen/movimientos/nuevo/', views.crear_movimiento_almacen, name='crear_movimiento_almacen'),

    path('reportes/', views.reporte_ejecucion, name='reporte_ejecucion'),
    path('reportes/exportar/', views.exportar_reporte_ejecucion_excel, name='exportar_reporte_ejecucion_excel'),
    path('reportes/exportar-pdf/', views.exportar_reporte_ejecucion_pdf, name='exportar_reporte_ejecucion_pdf'),
]
