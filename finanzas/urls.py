# finanzas/urls.py
from django.urls import path
from . import views

app_name = 'finanzas'

urlpatterns = [
    # ---- 1. Dashboard y Vistas Principales ----
    path('', views.dashboard_financiero, name='dashboard_financiero'),
    path('reporte/general/', views.estado_pagos_estudiante, name='reporte_general_cuentas'),
    path('configuracion/pagos/', views.configurar_pagos, name='configurar_pagos'),

    # ---- 2. Gestión de Cuentas por Estudiante (Acciones) ----
    # Estas URLs se llaman desde la lista de estudiantes o desde el historial de uno
    path('historial-estudiante/<int:estudiante_id>/', views.historial_cuentas_estudiante, name='historial_cuentas_estudiante'),
    path('historial-estudiante/<int:estudiante_pk>/sincronizar/', views.sincronizar_cuentas_estudiante, name='sincronizar_cuentas'),
    
    # El CRUD para una cuenta individual se mantiene, usualmente se accede desde el historial
    path('cuenta/crear/para/<int:estudiante_id>/', views.CuentaPorCobrarEstudianteCreateView.as_view(), name='crear_cuenta_por_cobrar'),
    path('cuenta/<int:pk>/editar/', views.CuentaPorCobrarEstudianteUpdateView.as_view(), name='editar_cuenta_por_cobrar'),
    path('cuenta/<int:pk>/eliminar/', views.CuentaPorCobrarEstudianteDeleteView.as_view(), name='eliminar_cuenta_por_cobrar'),

    # ---- 3. Gestión de Pagos (Acciones) ----
    path('pago/registrar/<int:cuenta_id>/', views.registrar_pago, name='registrar_pago'),
    path('pago/<int:pago_id>/editar/', views.editar_pago, name='editar_pago'),
    path('pago/<int:pago_id>/eliminar/', views.eliminar_pago, name='eliminar_pago'),

    # ---- 4. Portal del Estudiante y Flujo de Pago Online ----
    path('mi-estado-de-cuenta/', views.mi_estado_de_cuenta, name='mi_estado_de_cuenta'),
    path('pago/iniciar/<int:cuenta_pk>/', views.iniciar_pago_mercadopago, name='iniciar_pago'),
    path('pago/respuesta/', views.pago_respuesta_mp, name='pago_respuesta_mp'),
    path('webhook/mercadopago/', views.finanzas_mercadopago_webhook, name='finanzas_mercadopago_webhook'),

    # ---- 5. Configuración del Módulo (Conceptos) ----
    path('configuracion/tipos-concepto/', views.TipoConceptoPagoListView.as_view(), name='lista_tipos_concepto_pago'),
    path('configuracion/tipos-concepto/crear/', views.TipoConceptoPagoCreateView.as_view(), name='crear_tipo_concepto_pago'),
    path('configuracion/tipos-concepto/<int:pk>/editar/', views.TipoConceptoPagoUpdateView.as_view(), name='editar_tipo_concepto_pago'),
    path('configuracion/tipos-concepto/<int:pk>/eliminar/', views.TipoConceptoPagoDeleteView.as_view(), name='eliminar_tipo_concepto_pago'),

    path('configuracion/conceptos-pago/', views.ConceptoPagoListView.as_view(), name='lista_conceptos_pago'),
    path('configuracion/conceptos-pago/crear/', views.ConceptoPagoCreateView.as_view(), name='crear_concepto_pago'),
    path('configuracion/conceptos-pago/<int:pk>/editar/', views.ConceptoPagoUpdateView.as_view(), name='editar_concepto_pago'),
    path('configuracion/conceptos-pago/<int:pk>/eliminar/', views.ConceptoPagoDeleteView.as_view(), name='eliminar_concepto_pago'),

    # ---- 6. Exportación y Documentos PDF ----
    path('exportar/excel/', views.exportar_excel_historial_cuentas, name='exportar_excel_historial_cuentas'),
    path('pdf/recibo-pago/<int:pago_id>/', views.generar_recibo_pago, name='generar_recibo_pago'),
    path('pdf/volante-matricula/<int:estudiante_id>/', views.generar_volante_matricula, name='volante_matricula'),
    path('pdf/volante-mensualidad/<int:cuenta_id>/', views.generar_volante_mensualidad, name='volante_mensualidad'), 

     # ---- 7. GESTIÓN DE GASTOS Y PROVEEDORES ----
    path('configuracion/categorias-gasto/', views.CategoriaGastoListView.as_view(), name='lista_categorias_gasto'),
    path('configuracion/categorias-gasto/crear/', views.CategoriaGastoCreateView.as_view(), name='crear_categoria_gasto'),
    path('configuracion/categorias-gasto/<int:pk>/editar/', views.CategoriaGastoUpdateView.as_view(), name='editar_categoria_gasto'),

    path('configuracion/proveedores/', views.ProveedorListView.as_view(), name='lista_proveedores'),
    path('configuracion/proveedores/crear/', views.ProveedorCreateView.as_view(), name='crear_proveedor'),
    path('configuracion/proveedores/<int:pk>/editar/', views.ProveedorUpdateView.as_view(), name='editar_proveedor'),

    path('gastos/', views.GastoListView.as_view(), name='lista_gastos'),
    path('gastos/registrar/', views.GastoCreateView.as_view(), name='registrar_gasto_nuevo'),
    path('gastos/<int:pk>/editar/', views.GastoUpdateView.as_view(), name='editar_gasto'),
    path('gastos/<int:pk>/eliminar/', views.GastoDeleteView.as_view(), name='eliminar_gasto'),
    path('reportes/estado-resultados/', views.reporte_estado_resultados, name='reporte_estado_resultados'),
    path('reportes/cartera-por-edades/', views.reporte_cartera_por_edades, name='reporte_cartera_por_edades'),
    path('reportes/flujo-caja/', views.reporte_flujo_caja, name='reporte_flujo_caja'),
    path('herramientas/facturacion-masiva/', views.facturacion_masiva, name='facturacion_masiva'),
    path('superadmin/', views.dashboard_superadmin, name='dashboard_superadmin'),
    path('superadmin/institucion/<int:pk>/toggle-active/', views.toggle_institucion_activa, name='toggle_institucion_activa'),
    path('herramientas/exportacion-contable/', views.exportacion_contable, name='exportacion_contable'),
    path('pdf/factura-venta/<int:cuenta_id>/', views.generar_factura_venta, name='generar_factura_venta'),
    path('pdf/comprobante-egreso/<int:gasto_id>/', views.generar_comprobante_egreso, name='generar_comprobante_egreso'),
    path('configuracion/categorias-gasto/<int:pk>/eliminar/', views.CategoriaGastoDeleteView.as_view(), name='eliminar_categoria_gasto'),
    path('configuracion/proveedores/<int:pk>/eliminar/', views.ProveedorDeleteView.as_view(), name='eliminar_proveedor'),
    path('configuracion/tipos-gasto/', views.TipoGastoListView.as_view(), name='lista_tipos_gasto'),
    path('configuracion/tipos-gasto/crear/', views.TipoGastoCreateView.as_view(), name='crear_tipo_gasto'),
    path('configuracion/tipos-gasto/<int:pk>/editar/', views.TipoGastoUpdateView.as_view(), name='editar_tipo_gasto'),
    path('configuracion/tipos-gasto/<int:pk>/eliminar/', views.TipoGastoDeleteView.as_view(), name='eliminar_tipo_gasto'),


    # ---- 8. GESTIÓN DE DESCUENTOS Y BECAS ----
    path('configuracion/descuentos/', views.DescuentoListView.as_view(), name='lista_descuentos'),
    path('configuracion/descuentos/crear/', views.DescuentoCreateView.as_view(), name='crear_descuento'),
    path('configuracion/descuentos/<int:pk>/editar/', views.DescuentoUpdateView.as_view(), name='editar_descuento'),
    path('configuracion/descuentos/<int:pk>/eliminar/', views.DescuentoDeleteView.as_view(), name='eliminar_descuento'),
    path('configuracion/cargar-puc/', views.ejecutar_seed_puc_view, name='ejecutar_seed_puc'),
    path('puc/', views.CuentaContableListView.as_view(), name='lista_cuentas_contables'),
    path('puc/crear/', views.CuentaContableCreateView.as_view(), name='crear_cuenta_contable'),
    path('puc/<int:pk>/editar/', views.CuentaContableUpdateView.as_view(), name='editar_cuenta_contable'),
    path('puc/<int:pk>/eliminar/', views.CuentaContableDeleteView.as_view(), name='eliminar_cuenta_contable'),
    path('pago/iniciar/<int:cuenta_pk>/', views.iniciar_pago, name='iniciar_pago'),
    path('sincronizar/masivo/', views.sincronizar_cuentas_masivo, name='sincronizar_cuentas_masivo'),
    path('superadmin/soporte/', views.superadmin_tickets_view, name='superadmin_tickets'),
    path('superadmin/soporte/ticket/<str:ticket_id>/', views.superadmin_ticket_detail_view, name='superadmin_ticket_detail'),
    path('superadmin/soporte/ticket/<str:ticket_id>/cerrar/', views.cerrar_ticket_view, name='cerrar_ticket'),
    path('seleccionar-estudiante/', views.seleccionar_estudiante_para_historial, name='seleccionar_estudiante_para_historial'),
    path('superadmin/login/', views.superadmin_login_view, name='superadmin_login'),
    path('superadmin/lock/', views.superadmin_lock_view, name='superadmin_lock'),

]