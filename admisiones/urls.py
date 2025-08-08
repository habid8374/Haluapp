from django.urls import path, reverse_lazy
from . import views
from django.views.generic.base import RedirectView

app_name = 'admisiones'

urlpatterns = [
    # ---- Vistas del Portal del Postulante y Flujo de Pago ----
    path('portal/<uuid:token>/', views.portal_postulante, name='portal_postulante'),
    path('portal-pagado/<uuid:token>/', views.portal_postulante_pagado, name='portal_postulante_pagado'),
    path('pago/respuesta/', views.pago_respuesta_mp, name='pago_respuesta_mp'),
    path('pago/iniciar/mp/<int:cuenta_por_cobrar_id>/', views.crear_preferencia_mercadopago, name='crear_preferencia_mercadopago'),
    path('pago/webhook_mp/', views.mercadopago_webhook, name='mercadopago_webhook'), # <-- CORREGIDO
    path('aspirantes/<int:aspirante_id>/matricular/', views.matricular_aspirante, name='matricular_aspirante'),
    path('pago/respuesta_mp/success/', views.pago_respuesta_mp, name='pago_respuesta_mp_success'),
    path('pago/procesando/', views.pago_procesando, name='pago_procesando'),

    # URL para el endpoint de verificación de estado
    path('pago/verificar/<int:cuenta_id>/', views.verificar_estado_pago, name='verificar_estado_pago'),
   
    # ---- Vistas de Gestión para Administradores (CRUD) ----
    
    path('lista/', views.lista_grados_aspirantes, name='lista_grados_aspirantes'),
    path('lista/por-grado/<int:grado_id>/', views.lista_aspirantes_por_grado, name='lista_aspirantes_por_grado'),
    path('aspirante/<int:pk>/', views.AspiranteDetailView.as_view(), name='detalle_aspirante'),
    path('aspirante/<int:pk>/editar/', views.AspiranteUpdateView.as_view(), name='editar_aspirante'),
    path('aspirante/<int:pk>/eliminar/', views.AspiranteDeleteView.as_view(), name='eliminar_aspirante'),
    path('aspirante/<int:aspirante_id>/admitir/', views.admitir_aspirante, name='admitir_aspirante'),
    path('aspirante/<int:aspirante_id>/revertir/', views.revertir_matriculacion, name='revertir_matriculacion'),

    # ---- Vistas de Documentos y Citas (Portal Postulante) ----
    path('portal/<uuid:token>/subir-documento/<int:doc_req_id>/', views.subir_documento, name='subir_documento'),
    path('portal/<uuid:token>/agendar/', views.vista_agendamiento, name='vista_agendamiento'),
    path('portal/<uuid:token>/agendar/confirmar/<int:horario_id>/', views.confirmar_agendamiento, name='confirmar_agendamiento'),
    path('portal/<uuid:token>/cancelar-cita/', views.cancelar_cita, name='cancelar_cita'),

    # ---- Vistas de Reportes e Importación/Exportación ----
    path('dashboard/', views.dashboard_admisiones, name='dashboard_admisiones'),
    path('importar/', views.importar_aspirantes_excel, name='importar_aspirantes'),
    path('importar/plantilla/', views.descargar_plantilla_importacion, name='descargar_plantilla_importacion'),
    path('exportar/matriculados/', views.exportar_matriculados_excel, name='exportar_matriculados'),
     path('aspirantes/crear/', views.crear_aspirante_manual, name='crear_aspirante_manual'),

    # ---- Vistas de API y Vistas Especiales ----
    path('api/dashboard-data/', views.dashboard_data, name='dashboard_data'),
    path('pipeline/', views.pipeline_admisiones, name='pipeline_admisiones'),
    path('api/actualizar-estado-aspirante/', views.actualizar_estado_aspirante_api, name='actualizar_estado_aspirante_api'),

    # ---- Redirecciones al Admin ----
    path('gestion-documentos-requeridos/', RedirectView.as_view(url=reverse_lazy('admin:admisiones_documentorequerido_changelist')), name='gestion_documentos_requeridos'),
    path('revision-documentos-entregados/', RedirectView.as_view(url=reverse_lazy('admin:admisiones_documentoentregado_changelist')), name='revision_documentos_entregados'),
    path('revision-documentos/', views.revision_documentos_lista, name='revision_documentos_lista'),
    path('revision-documentos/<int:aspirante_id>/', views.revision_documento_detalle, name='revision_documento_detalle'),

    

]